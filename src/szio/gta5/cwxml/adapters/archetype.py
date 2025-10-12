import logging
from typing import Sequence

from ....types import Quaternion, Vector
from ... import jenkhash
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
)
from ...assets import (
    AssetFormat,
    AssetType,
    AssetVersion,
)
from ...drawables import (
    Light,
    LightFlashiness,
    LightType,
)
from .. import ymap as cwm
from .. import ytyp as cw

_CW_ENTITY_LOD_LEVEL_MAP = {
    "LODTYPES_DEPTH_HD": EntityLodLevel.HD,
    "LODTYPES_DEPTH_LOD": EntityLodLevel.LOD,
    "LODTYPES_DEPTH_SLOD1": EntityLodLevel.SLOD1,
    "LODTYPES_DEPTH_SLOD2": EntityLodLevel.SLOD2,
    "LODTYPES_DEPTH_SLOD3": EntityLodLevel.SLOD3,
    "LODTYPES_DEPTH_SLOD4": EntityLodLevel.SLOD4,
    "LODTYPES_DEPTH_ORPHANHD": EntityLodLevel.ORPHANHD,
}
_CW_ENTITY_LOD_LEVEL_INVERSE_MAP = {v: k for k, v in _CW_ENTITY_LOD_LEVEL_MAP.items()}

_CW_ENTITY_PRIORITY_LEVEL_MAP = {
    "PRI_REQUIRED": EntityPriorityLevel.REQUIRED,
    "PRI_OPTIONAL_HIGH": EntityPriorityLevel.OPTIONAL_HIGH,
    "PRI_OPTIONAL_MEDIUM": EntityPriorityLevel.OPTIONAL_MEDIUM,
    "PRI_OPTIONAL_LOW": EntityPriorityLevel.OPTIONAL_LOW,
}
_CW_ENTITY_PRIORITY_LEVEL_INVERSE_MAP = {v: k for k, v in _CW_ENTITY_PRIORITY_LEVEL_MAP.items()}

_CW_ASSET_TYPE_MAP = {
    "ASSET_TYPE_UNINITIALIZED": ArchetypeAssetType.UNINITIALIZED,
    "ASSET_TYPE_FRAGMENT": ArchetypeAssetType.FRAGMENT,
    "ASSET_TYPE_DRAWABLE": ArchetypeAssetType.DRAWABLE,
    "ASSET_TYPE_DRAWABLEDICTIONARY": ArchetypeAssetType.DRAWABLE_DICTIONARY,
    "ASSET_TYPE_ASSETLESS": ArchetypeAssetType.ASSETLESS,
}
_CW_ASSET_TYPE_INVERSE_MAP = {v: k for k, v in _CW_ASSET_TYPE_MAP.items()}


class CWMapTypes:
    ASSET_FORMAT = AssetFormat.CWXML
    ASSET_VERSION = AssetVersion.GEN8
    ASSET_TYPE = AssetType.MAP_TYPES

    def __init__(self, t: cw.CMapTypes):
        self._inner = t

    @property
    def name(self) -> str:
        return jenkhash.try_resolve_maybe_hashed_name(self._inner.name)

    @name.setter
    def name(self, v: str):
        self._inner.name = v

    @property
    def archetypes(self) -> list[Archetype]:
        def _text_list_to_vec(tl):
            return Vector([float(v) for v in tl])

        def _text_list_to_color(tl):
            return [int(v) for v in tl]

        def _map_light_type(light_type: str) -> LightType:
            match light_type:
                case "Point":
                    return LightType.POINT
                case "Spot":
                    return LightType.SPOT
                case "Capsule":
                    return LightType.CAPSULE

        def _map_light(light: cwm.LightInstance) -> Light:
            return Light(
                light_type=_map_light_type(light.light_type),
                position=_text_list_to_vec(light.position),
                direction=_text_list_to_vec(light.direction),
                tangent=_text_list_to_vec(light.tangent),
                extent=_text_list_to_vec(light.extents),
                color=_text_list_to_color(light.color),
                flashiness=LightFlashiness(light.flashiness),
                intensity=light.intensity,
                flags=light.flags,
                time_flags=light.time_flags,
                bone_id=light.bone_id,
                group_id=light.group_id,
                light_hash=light.light_hash,
                falloff=light.falloff,
                falloff_exponent=light.falloff_exponent,
                culling_plane_normal=_text_list_to_vec(light.culling_plane[:3]),
                culling_plane_offset=float(light.culling_plane[3]),
                volume_intensity=light.volume_intensity,
                volume_size_scale=light.volume_size_scale,
                volume_outer_color=_text_list_to_color(light.volume_outer_color),
                volume_outer_intensity=light.volume_outer_intensity,
                volume_outer_exponent=light.volume_outer_exponent,
                corona_size=light.corona_size,
                corona_intensity=light.corona_intensity,
                corona_z_bias=light.corona_z_bias,
                projected_texture_hash=jenkhash.hash_to_name(light.projected_texture_key),
                light_fade_distance=light.light_fade_distance,
                shadow_fade_distance=light.shadow_fade_distance,
                specular_fade_distance=light.specular_fade_distance,
                volumetric_fade_distance=light.volumetric_fade_distance,
                shadow_near_clip=light.shadow_near_clip,
                shadow_blur=light.shadow_blur,
                cone_inner_angle=light.cone_inner_angle,
                cone_outer_angle=light.cone_outer_angle,
            )

        def _map_extension(extension: cwm.Extension) -> Extension:
            base_kwargs = {
                "name": jenkhash.try_resolve_maybe_hashed_name(extension.name),
                "offset_position": Vector(extension.offset_position),
            }
            match extension:
                case cwm.ExtensionDoor():
                    return ExtensionDoor(
                        enable_limit_angle=extension.enable_limit_angle,
                        limit_angle=extension.limit_angle,
                        starts_locked=extension.starts_locked,
                        can_break=extension.can_break,
                        door_target_ratio=extension.door_target_ratio,
                        audio_hash=extension.audio_hash,
                        **base_kwargs,
                    )
                case cwm.ExtensionParticleEffect():
                    return ExtensionParticleEffect(
                        offset_rotation=extension.offset_rotation,
                        fx_name=extension.fx_name,
                        fx_type=extension.fx_type,
                        bone_tag=extension.bone_tag,
                        scale=extension.scale,
                        probability=extension.probability,
                        flags=extension.flags,
                        color=extension.color,
                        **base_kwargs,
                    )
                case cwm.ExtensionAudioCollision():
                    return ExtensionAudioCollisionSettings(
                        settings=extension.settings,
                        **base_kwargs,
                    )
                case cwm.ExtensionAudioEmitter():
                    # `effectHash` is stored as decimal value.
                    # Convert to `hash_` string or empty string for 0
                    try:
                        effect_hash_int = int(extension.effect_hash)
                    except ValueError:
                        effect_hash_int = 0
                    effect_hash = jenkhash.hash_to_name(effect_hash_int) if effect_hash_int != 0 else ""
                    return ExtensionAudioEmitter(
                        offset_rotation=extension.offset_rotation,
                        effect_hash=effect_hash,
                        **base_kwargs,
                    )
                case cwm.ExtensionExplosionEffect():
                    return ExtensionExplosionEffect(
                        offset_rotation=extension.offset_rotation,
                        explosion_name=extension.explosion_name,
                        bone_tag=extension.bone_tag,
                        explosion_tag=extension.explosion_tag,
                        explosion_type=extension.explosion_type,
                        flags=extension.flags,
                        **base_kwargs,
                    )
                case cwm.ExtensionLadder():
                    return ExtensionLadder(
                        bottom=extension.bottom,
                        top=extension.top,
                        normal=extension.normal,
                        material_type=extension.material_type,
                        template=extension.template,
                        can_get_off_at_top=extension.can_get_off_at_top,
                        can_get_off_at_bottom=extension.can_get_off_at_bottom,
                        **base_kwargs,
                    )
                case cwm.ExtensionBuoyancy():
                    return ExtensionBuoyancy(**base_kwargs)
                case cwm.ExtensionLightShaft():
                    extension: cwm.ExtensionLightShaft
                    return ExtensionLightShaft(
                        cornerA=extension.cornerA,
                        cornerB=extension.cornerB,
                        cornerC=extension.cornerC,
                        cornerD=extension.cornerD,
                        direction=extension.direction,
                        direction_amount=extension.direction_amount,
                        length=extension.length,
                        fade_in_time_start=extension.fade_in_time_start,
                        fade_in_time_end=extension.fade_in_time_end,
                        fade_out_time_start=extension.fade_out_time_start,
                        fade_out_time_end=extension.fade_out_time_end,
                        fade_distance_start=extension.fade_distance_start,
                        fade_distance_end=extension.fade_distance_end,
                        color=extension.color,
                        intensity=extension.intensity,
                        flashiness=LightFlashiness(extension.flashiness),
                        flags=extension.flags,
                        density_type=extension.density_type,
                        volume_type=extension.volume_type,
                        softness=extension.softness,
                        scale_by_sun_intensity=extension.scale_by_sun_intensity,
                        **base_kwargs,
                    )
                case cwm.ExtensionSpawnPoint():
                    return ExtensionSpawnPoint(
                        offset_rotation=extension.offset_rotation,
                        spawn_type=extension.spawn_type,
                        ped_type=extension.ped_type,
                        group=extension.group,
                        required_imap=extension.required_imap,
                        interior=extension.interior,
                        available_in_mp_sp=extension.available_in_mp_sp,
                        probability=extension.probability,
                        time_till_ped_leaves=extension.time_till_ped_leaves,
                        radius=extension.radius,
                        start=extension.start,
                        end=extension.end,
                        scenario_flags=extension.scenario_flags,
                        high_pri=extension.high_pri,
                        extended_range=extension.extended_range,
                        short_range=extension.short_range,
                        **base_kwargs,
                    )
                case cwm.ExtensionSpawnPointOverride():
                    return ExtensionSpawnPointOverride(
                        scenario_type=extension.scenario_type,
                        itime_start_override=extension.itime_start_override,
                        itime_end_override=extension.itime_end_override,
                        group=extension.group,
                        model_set=extension.model_set,
                        available_in_mp_sp=extension.available_in_mp_sp,
                        scenario_flags=extension.scenario_flags,
                        radius=extension.radius,
                        time_till_ped_leaves=extension.time_till_ped_leaves,
                        **base_kwargs,
                    )
                case cwm.ExtensionWindDisturbance():
                    return ExtensionWindDisturbance(
                        offset_rotation=extension.offset_rotation,
                        disturbance_type=extension.disturbance_type,
                        bone_tag=extension.bone_tag,
                        size=extension.size,
                        strength=extension.strength,
                        flags=extension.flags,
                        **base_kwargs,
                    )
                case cwm.ExtensionProcObject():
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
                        object_hash=extension.object_hash,
                        flags=extension.flags,
                        **base_kwargs,
                    )
                case cwm.ExtensionExpression():
                    return ExtensionExpression(
                        expression_dictionary_name=extension.expression_dictionary_name,
                        expression_name=extension.expression_name,
                        creature_metadata_name=extension.creature_metadata_name,
                        initialize_on_collision=extension.initialize_on_collision,
                        **base_kwargs,
                    )
                case cwm.ExtensionLightEffect():
                    return ExtensionLightEffect(
                        instances=[_map_light(li) for li in extension.instances],
                        **base_kwargs,
                    )

            logging.getLogger(__name__).warning(f"Unsupported extension type '{extension.type}'")
            return None

        def _map_entity(entity: cwm.Entity) -> MloEntity:
            return MloEntity(
                archetype_name=jenkhash.try_resolve_maybe_hashed_name(entity.archetype_name),
                position=entity.position,
                rotation=entity.rotation,
                scale_xy=entity.scale_xy,
                scale_z=entity.scale_z,
                flags=entity.flags,
                guid=entity.guid,
                parent_index=entity.parent_index,
                lod_dist=entity.lod_dist,
                child_lod_dist=entity.child_lod_dist,
                lod_level=_CW_ENTITY_LOD_LEVEL_MAP[entity.lod_level],
                priority_level=_CW_ENTITY_PRIORITY_LEVEL_MAP[entity.priority_level],
                num_children=entity.num_children,
                ambient_occlusion_multiplier=entity.ambient_occlusion_multiplier,
                artificial_ambient_occlusion=entity.artificial_ambient_occlusion,
                tint_value=entity.tint_value,
                extensions=[ext for e in entity.extensions if (ext := _map_extension(e)) is not None],
            )

        def _map_room(room: cw.Room) -> MloRoom:
            return MloRoom(
                name=room.name,
                bb_min=room.bb_min,
                bb_max=room.bb_max,
                blend=room.blend,
                timecycle=jenkhash.try_resolve_maybe_hashed_name(room.timecycle_name),
                secondary_timecycle=jenkhash.try_resolve_maybe_hashed_name(room.secondary_timecycle_name),
                flags=room.flags,
                portal_count=room.portal_count,
                floor_id=room.floor_id,
                exterior_visibility_depth=room.exterior_visibility_depth,
                attached_objects=room.attached_objects,
            )

        def _map_portal(portal: cw.Portal) -> MloPortal:
            return MloPortal(
                room_from=portal.room_from,
                room_to=portal.room_to,
                flags=portal.flags,
                mirror_priority=portal.mirror_priority,
                opacity=portal.opacity,
                audio_occlusion=portal.audio_occlusion,
                corners=tuple(Vector(c.value) for c in portal.corners),
                attached_objects=portal.attached_objects,
            )

        def _map_entity_set(entity_set: cw.EntitySet) -> MloEntitySet:
            return MloEntitySet(
                name=jenkhash.try_resolve_maybe_hashed_name(entity_set.name),
                locations=entity_set.locations,
                entities=[_map_entity(e) for e in entity_set.entities],
            )

        def _map_tcm(tcm: cw.TimeCycleModifier) -> MloTimeCycleModifier:
            return MloTimeCycleModifier(
                name=jenkhash.try_resolve_maybe_hashed_name(tcm.name),
                sphere_center=Vector((tcm.sphere.x, tcm.sphere.y, tcm.sphere.z)),
                sphere_radius=tcm.sphere.w,
                percentage=tcm.percentage,
                range=tcm.range,
                start_hour=tcm.start_hour,
                end_hour=tcm.end_hour,
            )

        def _map_archetype(archetype: cw.BaseArchetype) -> Archetype:
            arch_type = (
                ArchetypeType.MLO
                if isinstance(archetype, cw.MloArchetype)
                else ArchetypeType.TIME
                if isinstance(archetype, cw.TimeArchetype)
                else ArchetypeType.BASE
            )
            match arch_type:
                case ArchetypeType.TIME:
                    extra_kwargs = {
                        "time_flags": archetype.time_flags,
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
                name=jenkhash.try_resolve_maybe_hashed_name(archetype.name),
                type=arch_type,
                flags=archetype.flags,
                lod_dist=archetype.lod_dist,
                special_attribute=archetype.special_attribute,
                hd_texture_dist=archetype.hd_texture_dist,
                texture_dictionary=jenkhash.try_resolve_maybe_hashed_name(archetype.texture_dictionary),
                clip_dictionary=jenkhash.try_resolve_maybe_hashed_name(archetype.clip_dictionary),
                drawable_dictionary=jenkhash.try_resolve_maybe_hashed_name(archetype.drawable_dictionary),
                physics_dictionary=jenkhash.try_resolve_maybe_hashed_name(archetype.physics_dictionary),
                bb_min=archetype.bb_min,
                bb_max=archetype.bb_max,
                bs_center=archetype.bs_center,
                bs_radius=archetype.bs_radius,
                asset_name=jenkhash.try_resolve_maybe_hashed_name(archetype.asset_name),
                asset_type=_CW_ASSET_TYPE_MAP[archetype.asset_type],
                extensions=[ext for e in archetype.extensions if (ext := _map_extension(e)) is not None],
                **extra_kwargs,
            )

        typ = self._inner
        return [_map_archetype(a) for a in typ.archetypes]

    @archetypes.setter
    def archetypes(self, v: Sequence[Archetype]):
        def _vec_to_text_list(vec):
            return [str(v) for v in vec]

        def _color_to_text_list(color):
            return [str(int(v)) for v in color]

        def _map_light(light: Light) -> cwm.LightInstance:
            li = cwm.LightInstance()
            li.position = _vec_to_text_list(light.position)
            li.color = _color_to_text_list(light.color)
            li.flashiness = light.flashiness
            li.intensity = light.intensity
            li.flags = light.flags
            li.bone_id = light.bone_id
            li.light_type = light.light_type.value
            li.group_id = light.group_id
            li.time_flags = light.time_flags
            li.falloff = light.falloff
            li.falloff_exponent = light.falloff_exponent
            li.culling_plane = _vec_to_text_list(light.culling_plane_normal) + [str(light.culling_plane_offset)]
            li.volume_intensity = light.volume_intensity
            li.volume_size_scale = light.volume_size_scale
            li.volume_outer_color = _color_to_text_list(light.volume_outer_color)
            li.volume_outer_intensity = light.volume_outer_intensity
            li.volume_outer_exponent = light.volume_outer_exponent
            li.light_hash = light.light_hash
            li.corona_size = light.corona_size
            li.corona_intensity = light.corona_intensity
            li.corona_z_bias = light.corona_z_bias
            li.light_fade_distance = light.light_fade_distance
            li.shadow_fade_distance = light.shadow_fade_distance
            li.specular_fade_distance = light.specular_fade_distance
            li.volumetric_fade_distance = light.volumetric_fade_distance
            li.shadow_near_clip = light.shadow_near_clip
            li.direction = _vec_to_text_list(light.direction)
            li.tangent = _vec_to_text_list(light.tangent)
            li.cone_inner_angle = light.cone_inner_angle
            li.cone_outer_angle = light.cone_outer_angle
            li.extents = _vec_to_text_list(light.extent)
            li.shadow_blur = light.shadow_blur
            li.projected_texture_key = jenkhash.name_to_hash(light.projected_texture_hash)
            return li

        def _map_extension(extension: Extension) -> cwm.Extension:
            match extension:
                case ExtensionDoor():
                    e = cwm.ExtensionDoor()
                    e.enable_limit_angle = extension.enable_limit_angle
                    e.limit_angle = extension.limit_angle
                    e.starts_locked = extension.starts_locked
                    e.can_break = extension.can_break
                    e.door_target_ratio = extension.door_target_ratio
                    e.audio_hash = extension.audio_hash
                case ExtensionParticleEffect():
                    e = cwm.ExtensionParticleEffect()
                    e.offset_rotation = extension.offset_rotation
                    e.fx_name = extension.fx_name
                    e.fx_type = extension.fx_type
                    e.bone_tag = extension.bone_tag
                    e.scale = extension.scale
                    e.probability = extension.probability
                    e.flags = extension.flags
                    e.color = extension.color
                case ExtensionAudioCollisionSettings():
                    e = cwm.ExtensionAudioCollision()
                    e.settings = extension.settings
                case ExtensionAudioEmitter():
                    e = cwm.ExtensionAudioEmitter()
                    e.offset_rotation = extension.offset_rotation
                    e.effect_hash = extension.effect_hash
                case ExtensionExplosionEffect():
                    e = cwm.ExtensionExplosionEffect()
                    e.offset_rotation = extension.offset_rotation
                    e.explosion_name = extension.explosion_name
                    e.bone_tag = extension.bone_tag
                    e.explosion_tag = extension.explosion_tag
                    e.explosion_type = extension.explosion_type
                    e.flags = extension.flags
                case ExtensionLadder():
                    e = cwm.ExtensionLadder()
                    e.bottom = extension.bottom
                    e.top = extension.top
                    e.normal = extension.normal
                    e.material_type = extension.material_type
                    e.template = extension.template
                    e.can_get_off_at_top = extension.can_get_off_at_top
                    e.can_get_off_at_bottom = extension.can_get_off_at_bottom
                case ExtensionBuoyancy():
                    e = cwm.ExtensionBuoyancy()
                case ExtensionLightShaft():
                    e = cwm.ExtensionLightShaft()
                    e.cornerA = extension.cornerA
                    e.cornerB = extension.cornerB
                    e.cornerC = extension.cornerC
                    e.cornerD = extension.cornerD
                    e.direction = extension.direction
                    e.direction_amount = extension.direction_amount
                    e.length = extension.length
                    e.fade_in_time_start = extension.fade_in_time_start
                    e.fade_in_time_end = extension.fade_in_time_end
                    e.fade_out_time_start = extension.fade_out_time_start
                    e.fade_out_time_end = extension.fade_out_time_end
                    e.fade_distance_start = extension.fade_distance_start
                    e.fade_distance_end = extension.fade_distance_end
                    e.color = extension.color
                    e.intensity = extension.intensity
                    e.flashiness = extension.flashiness.value
                    e.flags = extension.flags
                    e.density_type = extension.density_type
                    e.volume_type = extension.volume_type
                    e.softness = extension.softness
                    e.scale_by_sun_intensity = extension.scale_by_sun_intensity
                case ExtensionSpawnPoint():
                    e = cwm.ExtensionSpawnPoint()
                    e.offset_rotation = extension.offset_rotation
                    e.spawn_type = extension.spawn_type
                    e.ped_type = extension.ped_type
                    e.group = extension.group
                    e.required_imap = extension.required_imap
                    e.interior = extension.interior
                    e.available_in_mp_sp = extension.available_in_mp_sp
                    e.probability = extension.probability
                    e.time_till_ped_leaves = extension.time_till_ped_leaves
                    e.radius = extension.radius
                    e.start = extension.start
                    e.end = extension.end
                    e.scenario_flags = extension.scenario_flags
                    e.high_pri = extension.high_pri
                    e.extended_range = extension.extended_range
                    e.short_range = extension.short_range
                case ExtensionSpawnPointOverride():
                    e = cwm.ExtensionSpawnPointOverride()
                    e.scenario_type = extension.scenario_type
                    e.time_start_override = extension.itime_start_override
                    e.time_end_override = extension.itime_end_override
                    e.group = extension.group
                    e.model_set = extension.model_set
                    e.available_in_mp_sp = extension.available_in_mp_sp
                    e.scenario_flags = extension.scenario_flags
                    e.radius = extension.radius
                    e.time_till_ped_leaves = extension.time_till_ped_leaves
                case ExtensionWindDisturbance():
                    e = cwm.ExtensionWindDisturbance()
                    e.offset_rotation = extension.offset_rotation
                    e.disturbance_type = extension.disturbance_type
                    e.bone_tag = extension.bone_tag
                    e.size = extension.size
                    e.strength = extension.strength
                    e.flags = extension.flags
                case ExtensionProcObject():
                    e = cwm.ExtensionProcObject()
                    e.radius_inner = extension.radius_inner
                    e.radius_outer = extension.radius_outer
                    e.spacing = extension.spacing
                    e.min_scale = extension.min_scale
                    e.max_scale = extension.max_scale
                    e.min_scale_z = extension.min_scale_z
                    e.max_scale_z = extension.max_scale_z
                    e.min_z_offset = extension.min_z_offset
                    e.max_z_offset = extension.max_z_offset
                    e.object_hash = extension.object_hash
                    e.flags = extension.flags
                case ExtensionExpression():
                    e = cwm.ExtensionExpression()
                    e.expression_dictionary_name = extension.expression_dictionary_name
                    e.expression_name = extension.expression_name
                    e.creature_metadata_name = extension.creature_metadata_name
                    e.initialize_on_collision = extension.initialize_on_collision
                case ExtensionLightEffect():
                    e = cwm.ExtensionLightEffect()
                    e.instances = [_map_light(li) for li in extension.instances]
                case _:
                    raise ValueError(f"Unsupported extension type '{type(extension).__name__}'")

            e.name = extension.name
            e.offset_position = extension.offset_position
            return e

        def _map_entity(entity: MloEntity) -> cwm.Entity:
            e = cwm.Entity()
            e.archetype_name = entity.archetype_name
            e.position = entity.position
            e.rotation = entity.rotation
            e.scale_xy = entity.scale_xy
            e.scale_z = entity.scale_z
            e.flags = entity.flags
            e.guid = entity.guid
            e.parent_index = entity.parent_index
            e.lod_dist = entity.lod_dist
            e.child_lod_dist = entity.child_lod_dist
            e.lod_level = _CW_ENTITY_LOD_LEVEL_INVERSE_MAP[entity.lod_level]
            e.priority_level = _CW_ENTITY_PRIORITY_LEVEL_INVERSE_MAP[entity.priority_level]
            e.num_children = entity.num_children
            e.ambient_occlusion_multiplier = entity.ambient_occlusion_multiplier
            e.artificial_ambient_occlusion = entity.artificial_ambient_occlusion
            e.tint_value = entity.tint_value
            e.extensions = [_map_extension(e) for e in entity.extensions]
            return e

        def _map_room(room: MloRoom) -> cw.Room:
            r = cw.Room()
            r.name = room.name
            r.bb_min = room.bb_min
            r.bb_max = room.bb_max
            r.blend = room.blend
            r.timecycle_name = room.timecycle
            r.secondary_timecycle_name = room.secondary_timecycle
            r.flags = room.flags
            r.portal_count = room.portal_count
            r.floor_id = room.floor_id
            r.exterior_visibility_depth = room.exterior_visibility_depth
            r.attached_objects = room.attached_objects
            return r

        def _map_portal(portal: MloPortal) -> cw.Portal:
            p = cw.Portal()
            p.room_from = portal.room_from
            p.room_to = portal.room_to
            p.flags = portal.flags
            p.mirror_priority = portal.mirror_priority
            p.opacity = portal.mirror_priority
            p.audio_occlusion = portal.audio_occlusion
            p.corners = [cw.Corner(value=tuple(c)) for c in portal.corners]
            p.attached_objects = portal.attached_objects
            return p

        def _map_entity_set(entity_set: MloEntitySet) -> cw.EntitySet:
            s = cw.EntitySet()
            s.name = entity_set.name
            s.locations = entity_set.locations
            s.entities = [_map_entity(e) for e in entity_set.entities]
            return s

        def _map_tcm(tcm: MloTimeCycleModifier) -> cw.TimeCycleModifier:
            m = cw.TimeCycleModifier()
            m.name = tcm.name
            m.sphere = Quaternion((tcm.sphere_radius, tcm.sphere_center.x, tcm.sphere_center.y, tcm.sphere_center.z))
            m.percentage = tcm.percentage
            m.range = tcm.range
            m.start_hour = tcm.start_hour
            m.end_hour = tcm.end_hour
            return m

        def _map_archetype(archetype: Archetype) -> cw.BaseArchetype:
            a = (
                cw.MloArchetype()
                if archetype.type == ArchetypeType.MLO
                else cw.TimeArchetype()
                if archetype.type == ArchetypeType.TIME
                else cw.BaseArchetype()
            )
            a.name = archetype.name
            a.flags = archetype.flags
            a.lod_dist = archetype.lod_dist
            a.special_attribute = archetype.special_attribute
            a.hd_texture_dist = archetype.hd_texture_dist
            a.texture_dictionary = archetype.texture_dictionary
            a.clip_dictionary = archetype.clip_dictionary
            a.drawable_dictionary = archetype.drawable_dictionary
            a.physics_dictionary = archetype.physics_dictionary
            a.bb_min = archetype.bb_min
            a.bb_max = archetype.bb_max
            a.bs_center = archetype.bs_center
            a.bs_radius = archetype.bs_radius
            a.asset_name = archetype.asset_name
            a.asset_type = _CW_ASSET_TYPE_INVERSE_MAP[archetype.asset_type]
            a.extensions = [_map_extension(e) for e in archetype.extensions]
            if archetype.type == ArchetypeType.TIME:
                a.time_flags = archetype.time_flags
            elif archetype.type == ArchetypeType.MLO:
                a.mlo_flags = archetype.mlo_flags
                a.entities = [_map_entity(e) for e in archetype.entities]
                a.rooms = [_map_room(r) for r in archetype.rooms]
                a.portals = [_map_portal(r) for r in archetype.portals]
                a.entity_sets = [_map_entity_set(s) for s in archetype.entity_sets]
                a.timecycle_modifiers = [_map_tcm(m) for m in archetype.timecycle_modifiers]
            return a

        self._inner.archetypes = [_map_archetype(a) for a in v]
