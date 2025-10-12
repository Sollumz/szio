import logging
from typing import Sequence

import pymateria.gta5 as pm

from ....types import Vector
from ...archetypes import (
    Archetype,
    ArchetypeAssetType,
    ArchetypeType,
    EntityLodLevel,
    EntityPriorityLevel,
    Extension,
    ExtensionAudioCollisionSettings,
    ExtensionAudioEmitter,
    ExtensionBuoyancy,
    ExtensionDoor,
    ExtensionExplosionEffect,
    ExtensionExpression,
    ExtensionLadder,
    ExtensionLightEffect,
    ExtensionLightShaft,
    ExtensionParticleEffect,
    ExtensionProcObject,
    ExtensionSpawnPoint,
    ExtensionSpawnPointOverride,
    ExtensionWindDisturbance,
    MloEntity,
    MloEntitySet,
    MloPortal,
    MloRoom,
    MloTimeCycleModifier,
    ScenarioPointFlags,
)
from ...assets import (
    AssetFormat,
    AssetType,
    AssetVersion,
)
from ...drawables import LightFlashiness
from ._utils import (
    _h2s,
    _s2h,
    from_native_bgraf,
    from_native_quat,
    to_native_aabb,
    to_native_bgraf,
    to_native_quat,
    to_native_sphere,
    to_native_vec3,
    to_native_vec4,
)
from .drawable import _map_light_from_native, _map_light_to_native

_NATIVE_SPAWN_POINT_AVAILABILITY_MAP = {
    pm.SpawnPointAvailability.BOTH: "kBoth",
    pm.SpawnPointAvailability.ONLY_SP: "kOnlySp",
    pm.SpawnPointAvailability.ONLY_MP: "kOnlyMp",
}

_NATIVE_SPAWN_POINT_AVAILABILITY_INVERSE_MAP = {v: k for k, v in _NATIVE_SPAWN_POINT_AVAILABILITY_MAP.items()}


def _native_scenario_flags_to_str(flags: int) -> str:
    flags = ScenarioPointFlags(flags)
    return ", ".join(f.name for f in flags)


def _native_scenario_flags_from_str(flags_str: str) -> int:
    flags = ScenarioPointFlags(0)
    for f in flags_str.split(","):
        f = f.strip()
        if f in ScenarioPointFlags._member_map_:
            flags |= ScenarioPointFlags[f]
    return flags.value


class NativeMapTypes:
    ASSET_FORMAT = AssetFormat.NATIVE
    ASSET_VERSION = AssetVersion.GEN8
    ASSET_TYPE = AssetType.MAP_TYPES

    def __init__(self, t: pm.gen8.MapTypes):
        self._inner = t

    @property
    def name(self) -> str:
        return _h2s(self._inner.name)

    @name.setter
    def name(self, v: str):
        self._inner.name = v

    @property
    def archetypes(self) -> list[Archetype]:
        def _map_extension(extension: pm.Extension) -> Extension | None:
            base_kwargs = {
                "name": _h2s(extension.name),
                "offset_position": Vector(extension.offset_position),
            }
            match extension:
                case pm.ExtensionDoor():
                    print(f"{extension.name}   {extension.door_target_ratio=}")
                    enable_limit_angle = extension.limit_angle is not None
                    return ExtensionDoor(
                        enable_limit_angle=enable_limit_angle,
                        limit_angle=extension.limit_angle if enable_limit_angle else 0.0,
                        starts_locked=extension.starts_locked,
                        can_break=extension.can_break,
                        door_target_ratio=extension.door_target_ratio,
                        audio_hash=_h2s(extension.audio_hash),
                        **base_kwargs,
                    )
                case pm.ExtensionParticleEffect():
                    return ExtensionParticleEffect(
                        offset_rotation=from_native_quat(extension.offset_rotation),
                        fx_name=extension.fx_name,
                        fx_type=extension.fx_type,
                        bone_tag=extension.bone_tag,
                        scale=extension.scale,
                        probability=extension.probability,
                        flags=extension.flags,
                        color=(
                            from_native_bgraf(extension.tint_color)
                            if extension.tint_color is not None
                            else (1.0, 1.0, 1.0, 1.0)
                        ),
                        **base_kwargs,
                    )
                case pm.ExtensionAudioCollisionSettings():
                    return ExtensionAudioCollisionSettings(
                        settings=_h2s(extension.settings),
                        **base_kwargs,
                    )
                case pm.ExtensionAudioEmitter():
                    return ExtensionAudioEmitter(
                        offset_rotation=from_native_quat(extension.offset_rotation),
                        effect_hash=_h2s(extension.effect_hash),
                        **base_kwargs,
                    )
                case pm.ExtensionExplosionEffect():
                    return ExtensionExplosionEffect(
                        offset_rotation=from_native_quat(extension.offset_rotation),
                        explosion_name=extension.explosion_name,
                        bone_tag=extension.bone_tag,
                        explosion_tag=extension.explosion_tag,
                        explosion_type=extension.explosion_type,
                        flags=extension.flags,
                        **base_kwargs,
                    )
                case pm.ExtensionLadder():
                    return ExtensionLadder(
                        bottom=Vector(extension.bottom),
                        top=Vector(extension.top),
                        normal=Vector(extension.normal),
                        material_type=extension.material_type.name,
                        template=_h2s(extension.template_string),
                        can_get_off_at_top=extension.can_get_off_at_top,
                        can_get_off_at_bottom=extension.can_get_off_at_bottom,
                        **base_kwargs,
                    )
                case pm.ExtensionBuoyancy():
                    return ExtensionBuoyancy(**base_kwargs)
                case pm.ExtensionLightShaft():
                    cornerA, cornerB, cornerC, cornerD = extension.corners
                    return ExtensionLightShaft(
                        cornerA=Vector(cornerA),
                        cornerB=Vector(cornerB),
                        cornerC=Vector(cornerC),
                        cornerD=Vector(cornerD),
                        direction=Vector(extension.direction),
                        direction_amount=extension.direction_amount,
                        length=extension.length,
                        fade_in_time_start=extension.fade_in_time_start,
                        fade_in_time_end=extension.fade_in_time_end,
                        fade_out_time_start=extension.fade_out_time_start,
                        fade_out_time_end=extension.fade_out_time_end,
                        fade_distance_start=extension.fade_distance_start,
                        fade_distance_end=extension.fade_distance_end,
                        color=from_native_bgraf(extension.color),
                        intensity=extension.intensity,
                        flashiness=LightFlashiness(extension.flashiness.value),
                        flags=extension.flags,
                        density_type=f"LIGHTSHAFT_DENSITYTYPE_{extension.density_type.name}",
                        volume_type=f"LIGHTSHAFT_VOLUMETYPE_{extension.volume_type.name}",
                        softness=extension.softness,
                        scale_by_sun_intensity=extension.scale_by_sun_intensity,
                        **base_kwargs,
                    )
                case pm.ExtensionSpawnPoint():
                    return ExtensionSpawnPoint(
                        offset_rotation=from_native_quat(extension.offset_rotation),
                        spawn_type=_h2s(extension.spawn_type),
                        ped_type=_h2s(extension.ped_type),
                        group=_h2s(extension.group),
                        required_imap=_h2s(extension.required_imap),
                        interior=_h2s(extension.interior),
                        available_in_mp_sp=_NATIVE_SPAWN_POINT_AVAILABILITY_MAP[extension.availability],
                        probability=extension.probability,
                        time_till_ped_leaves=extension.time_till_ped_leaves,
                        radius=extension.radius,
                        start=extension.start,
                        end=extension.end,
                        scenario_flags=_native_scenario_flags_to_str(extension.flags),
                        high_pri=extension.high_priority,
                        extended_range=extension.extended_range,
                        short_range=extension.short_range,
                        **base_kwargs,
                    )
                case pm.ExtensionSpawnPointOverride():
                    return ExtensionSpawnPointOverride(
                        scenario_type=_h2s(extension.scenario_type),
                        itime_start_override=extension.time_start_override,
                        itime_end_override=extension.time_end_override,
                        group=_h2s(extension.group),
                        model_set=_h2s(extension.model_set),
                        available_in_mp_sp=_NATIVE_SPAWN_POINT_AVAILABILITY_MAP[extension.availability],
                        scenario_flags=_native_scenario_flags_to_str(extension.flags),
                        radius=extension.radius,
                        time_till_ped_leaves=extension.time_till_ped_leaves,
                        **base_kwargs,
                    )
                case pm.ExtensionWindDisturbance():
                    return ExtensionWindDisturbance(
                        offset_rotation=from_native_quat(extension.offset_rotation),
                        disturbance_type=extension.disturbance_type.value,
                        bone_tag=extension.bone_tag,
                        size=Vector(extension.size),
                        strength=extension.strength,
                        flags=extension.flags,
                        **base_kwargs,
                    )
                case pm.ExtensionProcObject():
                    return ExtensionProcObject(
                        radius_inner=extension.radius_inner,
                        radius_outer=extension.radius_outer,
                        spacing=extension.spacing,
                        min_scale=extension.min_scale,
                        max_scale=extension.max_scale,
                        min_scale_z=extension.min_scale_z,
                        max_scale_z=extension.max_scale_z,
                        min_z_offset=extension.min_z_offset,
                        max_z_offset=extension.max_z_offset,
                        object_hash=extension.object_hash.hash,
                        flags=extension.flags,
                        **base_kwargs,
                    )
                case pm.ExtensionExpression():
                    return ExtensionExpression(
                        expression_dictionary_name=_h2s(extension.expression_dictionary_name),
                        expression_name=_h2s(extension.expression_name),
                        creature_metadata_name=_h2s(extension.creature_metadata_name),
                        initialize_on_collision=extension.initialize_on_collision,
                        **base_kwargs,
                    )
                case pm.ExtensionLightEffect():
                    return ExtensionLightEffect(
                        instances=[_map_light_from_native(li) for li in extension.instances],
                        **base_kwargs,
                    )

            logging.getLogger(__name__).warning(f"Unsupported extension type '{extension.type}'")
            return None

        def _map_entity(entity: pm.ArchetypeEntity) -> MloEntity:
            return MloEntity(
                archetype_name=_h2s(entity.archetype_name),
                position=Vector(entity.position),
                rotation=from_native_quat(entity.rotation),
                scale_xy=entity.scale_xy,
                scale_z=entity.scale_z,
                flags=entity.flags,
                guid=entity.guid,
                parent_index=entity.parent_index,
                lod_dist=entity.lod_distance,
                child_lod_dist=entity.child_lod_distance,
                lod_level=EntityLodLevel(entity.lod_level.value),
                priority_level=EntityPriorityLevel(entity.priority_level.value),
                num_children=entity.num_children,
                ambient_occlusion_multiplier=entity.ambient_occlusion_multiplier,
                artificial_ambient_occlusion=entity.artificial_ambient_occlusion,
                tint_value=entity.tint_value,
                extensions=[ext for e in entity.extensions if (ext := _map_extension(e)) is not None],
            )

        def _map_room(room: pm.MloRoomDefinition) -> MloRoom:
            return MloRoom(
                name=room.name,
                bb_min=Vector(room.bounding_box.min),
                bb_max=Vector(room.bounding_box.max),
                blend=room.blend,
                timecycle=_h2s(room.timecycle_name),
                secondary_timecycle=_h2s(room.secondary_timecycle_name),
                flags=room.flags,
                portal_count=room.portal_count,
                floor_id=room.floor_id,
                exterior_visibility_depth=room.exterior_visibility_depth,
                attached_objects=room.attached_objects,
            )

        def _map_portal(portal: pm.MloPortalDefinition) -> MloPortal:
            return MloPortal(
                room_from=portal.room_from,
                room_to=portal.room_to,
                flags=portal.flags,
                mirror_priority=portal.mirror_priority,
                opacity=portal.opacity,
                audio_occlusion=portal.audio_occlusion,
                corners=tuple(Vector(c) for c in portal.corners),
                attached_objects=portal.attached_objects,
            )

        def _map_entity_set(entity_set: pm.MloEntitySet) -> MloEntitySet:
            return MloEntitySet(
                name=_h2s(entity_set.name),
                locations=entity_set.locations,
                entities=[_map_entity(e) for e in entity_set.entities],
            )

        def _map_tcm(tcm: pm.MloTimeCycleModifier) -> MloTimeCycleModifier:
            return MloTimeCycleModifier(
                name=_h2s(tcm.name),
                sphere_center=Vector(tcm.sphere.center),
                sphere_radius=tcm.sphere.radius,
                percentage=tcm.percentage,
                range=tcm.range,
                start_hour=tcm.start_hour,
                end_hour=tcm.end_hour,
            )

        def _map_archetype(archetype: pm.ArchetypeDefinition) -> Archetype:
            arch_type = (
                ArchetypeType.MLO
                if isinstance(archetype, pm.ArchetypeDefinitionMlo)
                else ArchetypeType.TIME
                if isinstance(archetype, pm.ArchetypeDefinitionTime)
                else ArchetypeType.BASE
            )
            match arch_type:
                case ArchetypeType.TIME:
                    extra_kwargs = {
                        "time_flags": archetype.time_flags.value,
                    }
                case ArchetypeType.MLO:
                    extra_kwargs = {
                        "mlo_flags": archetype.mlo_flags,
                        "entities": [_map_entity(e) for e in archetype.entities],
                        "rooms": [_map_room(r) for r in archetype.rooms],
                        "portals": [_map_portal(p) for p in archetype.portals],
                        "entity_sets": [_map_entity_set(s) for s in archetype.entity_sets],
                        "timecycle_modifiers": [_map_tcm(m) for m in archetype.timecycle_modifiers],
                    }
                case _:
                    extra_kwargs = {}

            return Archetype(
                name=_h2s(archetype.name),
                type=arch_type,
                flags=archetype.flags,
                lod_dist=archetype.lod_distance,
                special_attribute=archetype.special_attribute,
                hd_texture_dist=archetype.hd_texture_distance,
                texture_dictionary=_h2s(archetype.texture_dictionary),
                clip_dictionary=_h2s(archetype.clip_dictionary),
                drawable_dictionary=_h2s(archetype.drawable_dictionary),
                physics_dictionary=_h2s(archetype.physics_dictionary),
                bb_min=Vector(archetype.bounding_box.min),
                bb_max=Vector(archetype.bounding_box.max),
                bs_center=Vector(archetype.bounding_sphere.center),
                bs_radius=archetype.bounding_sphere.radius,
                asset_name=_h2s(archetype.asset_name),
                asset_type=ArchetypeAssetType(archetype.asset_type.value),
                extensions=[ext for e in archetype.extensions if (ext := _map_extension(e)) is not None],
                **extra_kwargs,
            )

        typ = self._inner
        return [_map_archetype(a) for a in typ.archetypes]

    @archetypes.setter
    def archetypes(self, v: Sequence[Archetype]):
        def _map_extension(extension: Extension) -> pm.Extension:
            match extension:
                case ExtensionDoor():
                    e = pm.ExtensionDoor()
                    e.limit_angle = extension.limit_angle if extension.enable_limit_angle else None
                    e.starts_locked = extension.starts_locked
                    e.can_break = extension.can_break
                    e.door_target_ratio = extension.door_target_ratio
                    e.audio_hash = _s2h(extension.audio_hash)
                case ExtensionParticleEffect():
                    e = pm.ExtensionParticleEffect()
                    e.offset_rotation = to_native_quat(extension.offset_rotation)
                    e.fx_name = extension.fx_name
                    e.fx_type = extension.fx_type
                    e.bone_tag = extension.bone_tag
                    e.scale = extension.scale
                    e.probability = extension.probability
                    e.flags = extension.flags
                    e.tint_color = to_native_bgraf(extension.color) if (extension.flags & 1) != 0 else None
                case ExtensionAudioCollisionSettings():
                    e = pm.ExtensionAudioCollisionSettings()
                    e.settings = _s2h(extension.settings)
                case ExtensionAudioEmitter():
                    e = pm.ExtensionAudioEmitter()
                    e.offset_rotation = to_native_quat(extension.offset_rotation)
                    e.effect_hash = _s2h(extension.effect_hash)
                case ExtensionExplosionEffect():
                    e = pm.ExtensionExplosionEffect()
                    e.offset_rotation = to_native_quat(extension.offset_rotation)
                    e.explosion_name = extension.explosion_name
                    e.bone_tag = extension.bone_tag
                    e.explosion_tag = extension.explosion_tag
                    e.explosion_type = extension.explosion_type
                    e.flags = extension.flags
                case ExtensionLadder():
                    e = pm.ExtensionLadder()
                    e.bottom = to_native_vec3(extension.bottom)
                    e.top = to_native_vec3(extension.top)
                    e.normal = to_native_vec3(extension.normal)
                    e.material_type = pm.LadderMaterialType[extension.material_type]
                    e.template_string = _s2h(extension.template)
                    e.can_get_off_at_top = extension.can_get_off_at_top
                    e.can_get_off_at_bottom = extension.can_get_off_at_bottom
                case ExtensionBuoyancy():
                    e = pm.ExtensionBuoyancy()
                case ExtensionLightShaft():
                    e = pm.ExtensionLightShaft()
                    e.corners = (
                        to_native_vec3(extension.cornerA),
                        to_native_vec3(extension.cornerB),
                        to_native_vec3(extension.cornerC),
                        to_native_vec3(extension.cornerD),
                    )
                    e.direction = to_native_vec3(extension.direction)
                    e.direction_amount = extension.direction_amount
                    e.length = extension.length
                    e.fade_in_time_start = extension.fade_in_time_start
                    e.fade_in_time_end = extension.fade_in_time_end
                    e.fade_out_time_start = extension.fade_out_time_start
                    e.fade_out_time_end = extension.fade_out_time_end
                    e.fade_distance_start = extension.fade_distance_start
                    e.fade_distance_end = extension.fade_distance_end
                    e.color = to_native_bgraf(extension.color)
                    e.intensity = extension.intensity
                    e.flashiness = pm.LightFlashiness(extension.flashiness.value)
                    e.flags = extension.flags
                    # [23:] removes 'LIGHTSHAFT_DENSITYTYPE_' prefix
                    e.density_type = pm.LightShaftDensityType[extension.density_type[23:]]
                    # [22:] removes 'LIGHTSHAFT_VOLUMETYPE_' prefix
                    e.volume_type = pm.LightShaftVolumeType[extension.volume_type[22:]]
                    e.softness = extension.softness
                    e.scale_by_sun_intensity = extension.scale_by_sun_intensity
                case ExtensionSpawnPoint():
                    e = pm.ExtensionSpawnPoint()
                    e.offset_rotation = to_native_quat(extension.offset_rotation)
                    e.spawn_type = _s2h(extension.spawn_type)
                    e.ped_type = _s2h(extension.ped_type)
                    e.group = _s2h(extension.group)
                    e.required_imap = _s2h(extension.required_imap)
                    e.interior = _s2h(extension.interior)
                    e.availability = _NATIVE_SPAWN_POINT_AVAILABILITY_INVERSE_MAP[extension.available_in_mp_sp]
                    e.probability = extension.probability
                    e.time_till_ped_leaves = extension.time_till_ped_leaves
                    e.radius = extension.radius
                    e.start = extension.start
                    e.end = extension.end
                    e.flags = _native_scenario_flags_from_str(extension.scenario_flags)
                    e.high_priority = extension.high_pri
                    e.extended_range = extension.extended_range
                    e.short_range = extension.short_range
                case ExtensionSpawnPointOverride():
                    e = pm.ExtensionSpawnPointOverride()
                    e.scenario_type = _s2h(extension.scenario_type)
                    e.time_start_override = extension.itime_start_override
                    e.time_end_override = extension.itime_end_override
                    e.group = _s2h(extension.group)
                    e.model_set = _s2h(extension.model_set)
                    e.availability = _NATIVE_SPAWN_POINT_AVAILABILITY_INVERSE_MAP[extension.available_in_mp_sp]
                    e.flags = _native_scenario_flags_from_str(extension.scenario_flags)
                    e.radius = extension.radius
                    e.time_till_ped_leaves = extension.time_till_ped_leaves
                case ExtensionWindDisturbance():
                    e = pm.ExtensionWindDisturbance()
                    e.offset_rotation = to_native_quat(extension.offset_rotation)
                    e.disturbance_type = pm.WindDisturbanceType(extension.disturbance_type)
                    e.bone_tag = extension.bone_tag
                    e.size = to_native_vec4(extension.size)
                    e.strength = extension.strength
                    e.flags = extension.flags
                case ExtensionProcObject():
                    e = pm.ExtensionProcObject()
                    e.radius_inner = extension.radius_inner
                    e.radius_outer = extension.radius_outer
                    e.spacing = extension.spacing
                    e.min_scale = extension.min_scale
                    e.max_scale = extension.max_scale
                    e.min_scale_z = extension.min_scale_z
                    e.max_scale_z = extension.max_scale_z
                    e.min_z_offset = extension.min_z_offset
                    e.max_z_offset = extension.max_z_offset
                    e.object_hash = pm.CombinedHashString(extension.object_hash)
                    e.flags = extension.flags
                case ExtensionExpression():
                    e = pm.ExtensionExpression()
                    e.expression_dictionary_name = _s2h(extension.expression_dictionary_name)
                    e.expression_name = _s2h(extension.expression_name)
                    e.creature_metadata_name = _s2h(extension.creature_metadata_name)
                    e.initialize_on_collision = extension.initialize_on_collision
                case ExtensionLightEffect():
                    e = pm.ExtensionLightEffect()
                    e.instances = [_map_light_to_native(li, True) for li in extension.instances]
                case _:
                    raise ValueError(f"Unsupported extension type '{type(extension).__name__}'")

            e.name = _s2h(extension.name)
            e.offset_position = to_native_vec3(extension.offset_position)
            return e

        def _map_entity(entity: MloEntity) -> pm.ArchetypeEntity:
            e = pm.ArchetypeEntity()
            e.archetype_name = _s2h(entity.archetype_name)
            e.position = to_native_vec3(entity.position)
            e.rotation = to_native_quat(entity.rotation)
            e.scale_xy = entity.scale_xy
            e.scale_z = entity.scale_z
            e.flags = entity.flags
            e.guid = entity.guid
            e.parent_index = entity.parent_index
            e.lod_distance = entity.lod_dist
            e.child_lod_distance = entity.child_lod_dist
            e.lod_level = pm.ArchetypeLodType(entity.lod_level.value)
            e.priority_level = pm.PriorityLevel(entity.priority_level.value)
            e.num_children = entity.num_children
            e.ambient_occlusion_multiplier = entity.ambient_occlusion_multiplier
            e.artificial_ambient_occlusion = entity.artificial_ambient_occlusion
            e.tint_value = entity.tint_value
            e.extensions = [_map_extension(e) for e in entity.extensions]
            return e

        def _map_room(room: MloRoom) -> pm.MloRoomDefinition:
            r = pm.MloRoomDefinition()
            r.name = room.name
            r.bounding_box = to_native_aabb(room.bb_min, room.bb_max)
            r.blend = room.blend
            r.timecycle_name = _s2h(room.timecycle)
            r.secondary_timecycle_name = _s2h(room.secondary_timecycle)
            r.flags = room.flags
            r.portal_count = room.portal_count
            r.floor_id = room.floor_id
            r.exterior_visibility_depth = room.exterior_visibility_depth
            r.attached_objects = room.attached_objects
            return r

        def _map_portal(portal: MloPortal) -> pm.MloPortalDefinition:
            p = pm.MloPortalDefinition()
            p.room_from = portal.room_from
            p.room_to = portal.room_to
            p.flags = portal.flags
            p.mirror_priority = portal.mirror_priority
            p.opacity = portal.mirror_priority
            p.audio_occlusion = portal.audio_occlusion
            p.corners = [to_native_vec3(c) for c in portal.corners]
            p.attached_objects = portal.attached_objects
            return p

        def _map_entity_set(entity_set: MloEntitySet) -> pm.MloEntitySet:
            s = pm.MloEntitySet()
            s.name = _s2h(entity_set.name)
            s.locations = entity_set.locations
            s.entities = [_map_entity(e) for e in entity_set.entities]
            return s

        def _map_tcm(tcm: MloTimeCycleModifier) -> pm.MloTimeCycleModifier:
            m = pm.MloTimeCycleModifier()
            m.name = _s2h(tcm.name)
            m.sphere = to_native_sphere(tcm.sphere_center, tcm.sphere_radius)
            m.percentage = tcm.percentage
            m.range = tcm.range
            m.start_hour = tcm.start_hour
            m.end_hour = tcm.end_hour
            return m

        def _map_archetype(archetype: Archetype) -> pm.ArchetypeDefinition:
            a = (
                pm.ArchetypeDefinitionMlo()
                if archetype.type == ArchetypeType.MLO
                else pm.ArchetypeDefinitionTime()
                if archetype.type == ArchetypeType.TIME
                else pm.ArchetypeDefinition()
            )
            a.name = _s2h(archetype.name)
            a.flags = archetype.flags
            a.lod_distance = archetype.lod_dist
            a.special_attribute = archetype.special_attribute
            a.hd_texture_distance = archetype.hd_texture_dist
            a.texture_dictionary = _s2h(archetype.texture_dictionary)
            a.clip_dictionary = _s2h(archetype.clip_dictionary)
            a.drawable_dictionary = _s2h(archetype.drawable_dictionary)
            a.physics_dictionary = _s2h(archetype.physics_dictionary)
            a.bounding_box = to_native_aabb(archetype.bb_min, archetype.bb_max)
            a.bounding_sphere = to_native_sphere(archetype.bs_center, archetype.bs_radius)
            a.asset_name = _s2h(archetype.asset_name)
            a.asset_type = pm.ArchetypeAssetType(archetype.asset_type.value)
            a.extensions = [_map_extension(e) for e in archetype.extensions]
            if archetype.type == ArchetypeType.TIME:
                a.time_flags = pm.TimeFlags(archetype.time_flags)
            elif archetype.type == ArchetypeType.MLO:
                a.mlo_flags = archetype.mlo_flags
                a.entities = [_map_entity(e) for e in archetype.entities]
                a.rooms = [_map_room(r) for r in archetype.rooms]
                a.portals = [_map_portal(r) for r in archetype.portals]
                a.entity_sets = [_map_entity_set(s) for s in archetype.entity_sets]
                a.timecycle_modifiers = [_map_tcm(m) for m in archetype.timecycle_modifiers]
            return a

        self._inner.archetypes = [_map_archetype(a) for a in v]


class NativeMapTypesG9(NativeMapTypes):
    ASSET_FORMAT = AssetFormat.NATIVE
    ASSET_VERSION = AssetVersion.GEN9
    ASSET_TYPE = AssetType.MAP_TYPES

    def __init__(self, t: pm.gen9.MapTypes):
        self._inner = t
