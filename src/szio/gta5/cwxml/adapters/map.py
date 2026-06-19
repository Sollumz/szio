from collections.abc import Sequence

import numpy as np

from ....types import Vector
from ... import jenkhash
from ...entities import Entity, MapEntity
from ...maps import (
    MAP_DISTANT_LOD_LIGHT_DTYPE,
    MAP_GRASS_INSTANCES_DTYPE,
    MAP_LOD_LIGHT_DTYPE,
    AssetMapData,
    MapBlockDescription,
    MapBoxOccluder,
    MapCarGenerator,
    MapCarGeneratorCreationRule,
    MapCarGeneratorFlags,
    MapContentFlags,
    MapDistantLodLights,
    MapFlags,
    MapGrassInstanceList,
    MapLodLightCategory,
    MapLodLights,
    MapModelOccluder,
    MapModelOccluderFlags,
    MapTimeCycleModifier,
)
from .. import ymap as cw
from .archetype import from_cw_entity, to_cw_entity


def _load_timecycle_modifiers(t: cw.CMapData) -> list[MapTimeCycleModifier]:
    return [
        MapTimeCycleModifier(
            name=jenkhash.try_resolve_maybe_hashed_name(tcm.name),
            extents=(tcm.min_extents, tcm.max_extents),
            percentage=float(tcm.percentage),
            range=float(tcm.range),
            start_hour=int(tcm.start_hour),
            end_hour=int(tcm.end_hour),
        )
        for tcm in t.time_cycle_modifiers
    ]


def _load_car_generators(t: cw.CMapData) -> list[MapCarGenerator]:
    return [
        MapCarGenerator(
            position=cargen.position,
            orient_x=float(cargen.orient_x),
            orient_y=float(cargen.orient_y),
            perpendicular_length=float(cargen.perpendicular_length),
            car_model=jenkhash.try_resolve_maybe_hashed_name(cargen.car_model),
            flags=MapCarGeneratorFlags(cargen.flags & 0x1FFFF),
			creation_rule=MapCarGeneratorCreationRule((cargen.flags & 0xF0000000) >> 28),
            body_color_remap_1=int(cargen.body_color_remap_1),
            body_color_remap_2=int(cargen.body_color_remap_2),
            body_color_remap_3=int(cargen.body_color_remap_3),
            body_color_remap_4=int(cargen.body_color_remap_4),
            pop_group=jenkhash.try_resolve_maybe_hashed_name(cargen.pop_group),
            livery=int(cargen.livery),
        )
        for cargen in t.car_generators
    ]


def _load_grass_instance_lists(t: cw.CMapData) -> list[MapGrassInstanceList]:
    def _map_grass_instances(instances: list[cw.GrassInstance]) -> np.ndarray:
        arr = np.empty(len(instances), dtype=MAP_GRASS_INSTANCES_DTYPE)
        pos = arr["Position"]
        nml = arr["Normal"]
        col = arr["Color"]
        scl = arr["Scale"]
        ao = arr["Ao"]
        for i, inst in enumerate(instances):
            pos[i] = inst.position
            nml[i] = inst.normal_x, inst.normal_y
            col[i] = inst.color
            scl[i] = inst.scale
            ao[i] = inst.ao
        return arr

    return [
        MapGrassInstanceList(
            extents=(Vector(g.batch_aabb.min[:3]), Vector(g.batch_aabb.max[:3])),
            scale_range=g.scale_range,
            archetype_name=jenkhash.try_resolve_maybe_hashed_name(g.archetype_name),
            lod_dist=int(g.lod_dist),
            lod_fade_start_dist=g.lod_fade_start_dist,
            lod_inst_fade_range=g.lod_inst_fade_range,
            orient_to_terrain=g.orient_to_terrain,
            instances=_map_grass_instances(g.instance_list),
        )
        for g in t.instanced_data.grass_instance_list
    ]


def _load_box_occluders(t: cw.CMapData) -> list[MapBoxOccluder]:
    return [
        MapBoxOccluder(
            center_x=int(box.center_x),
            center_y=int(box.center_y),
            center_z=int(box.center_z),
            length=int(box.length),
            width=int(box.width),
            height=int(box.height),
            cos_z=int(box.cos_z),
            sin_z=int(box.sin_z),
        )
        for box in t.box_occluders
    ]


def _load_model_occluders(t: cw.CMapData) -> list[MapModelOccluder]:
    result = []
    for model in t.occlude_models:
        assert (model.num_tris & 0x8000) != 0, "Only float vertex format of occlude models is supported"

        num_verts_in_bytes = model.num_verts_in_bytes
        num_verts = num_verts_in_bytes // (4 * 3)  # sizeof(float)*3
        num_tris = model.num_tris & ~0x8000

        data = np.frombuffer(model.verts, dtype=np.uint8)
        vertices = data[:num_verts_in_bytes].view(dtype=np.float32).reshape((num_verts, 3))
        indices = data[num_verts_in_bytes:].reshape((num_tris, 3))

        result.append(
            MapModelOccluder(
                flags=MapModelOccluderFlags(model.flags),
                vertices=vertices,
                indices=indices,
            )
        )
    return result


def _load_lod_lights(t: cw.CMapData) -> MapLodLights | None:
    soa = t.lod_lights_soa
    if soa is None:
        return None

    direction = soa.direction
    n = len(direction)
    if n == 0:
        return None

    lights = np.empty(n, dtype=MAP_LOD_LIGHT_DTYPE)
    for i, d in enumerate(direction):
        lights["Direction"][i] = (d.x, d.y, d.z)
    lights["Falloff"] = soa.falloff
    lights["FalloffExponent"] = soa.falloff_exponent
    lights["TimeAndStateFlags"] = soa.time_and_state_flags
    lights["Hash"] = soa.hash
    lights["ConeInnerAngle"] = soa.cone_inner_angle
    lights["ConeOuterAngleOrCapExt"] = soa.cone_outer_angle_or_cap_ext
    lights["CoronaIntensity"] = soa.corona_intensity

    return MapLodLights(lights=lights)


def _load_distant_lod_lights(t: cw.CMapData) -> MapDistantLodLights | None:
    soa = t.distant_lod_lights_soa
    if soa is None:
        return None

    position = soa.position
    n = len(position)
    if n == 0:
        return None

    lights = np.empty(n, dtype=MAP_DISTANT_LOD_LIGHT_DTYPE)
    for i, p in enumerate(position):
        lights["Position"][i] = (p.x, p.y, p.z)

    rgbi_u32 = np.array(soa.rgbi, dtype=np.uint32)
    lights["RGBI"][:, 0] = (rgbi_u32 >> 16) & 0xFF  # R
    lights["RGBI"][:, 1] = (rgbi_u32 >> 8) & 0xFF  # G
    lights["RGBI"][:, 2] = rgbi_u32 & 0xFF  # B
    lights["RGBI"][:, 3] = (rgbi_u32 >> 24) & 0xFF  # I

    return MapDistantLodLights(
        lights=lights,
        num_street_lights=int(soa.num_street_lights),
        category=MapLodLightCategory(int(soa.category)),
    )


def _load_description(t: cw.CMapData) -> MapBlockDescription | None:
    b = t.block
    version = int(b.version) if b.version is not None else 0
    flags = int(b.flags) if b.flags is not None else 0
    name = b.name or ""
    exported_by = b.exported_by or ""
    owner = b.owner or ""
    time = b.time or ""
    if version == 0 and flags == 0 and not (name or exported_by or owner or time):
        return None
    return MapBlockDescription(
        version=version,
        flags=flags,
        name=name,
        exported_by=exported_by,
        owner=owner,
        time=time,
    )


def load_map_data_from_cw(t: cw.CMapData) -> AssetMapData:
    return AssetMapData(
        name=jenkhash.try_resolve_maybe_hashed_name(t.name),
        parent_name=jenkhash.try_resolve_maybe_hashed_name(t.parent),
        flags=MapFlags(t.flags),
        content_flags=MapContentFlags(t.content_flags),
        streaming_extents=(t.streaming_extents_min, t.streaming_extents_max),
        entities_extents=(t.entities_extents_min, t.entities_extents_max),
        entities=[from_cw_entity(e) for e in t.entities],
        physics_dictionaries=[d.value for d in t.physics_dictionaries],
        timecycle_modifiers=_load_timecycle_modifiers(t),
        car_generators=_load_car_generators(t),
        grass_instance_lists=_load_grass_instance_lists(t),
        box_occluders=_load_box_occluders(t),
        model_occluders=_load_model_occluders(t),
        lod_lights=_load_lod_lights(t),
        distant_lod_lights=_load_distant_lod_lights(t),
        description=_load_description(t),
    )


def _save_timecycle_modifiers(modifiers: Sequence[MapTimeCycleModifier]) -> list[cw.TimeCycleModifier]:
    result = []
    for tcm in modifiers:
        m = cw.TimeCycleModifier()
        m.name = tcm.name
        m.min_extents, m.max_extents = tcm.extents
        m.percentage = tcm.percentage
        m.range = tcm.range
        m.start_hour = tcm.start_hour
        m.end_hour = tcm.end_hour
        result.append(m)
    return result


def _save_car_generators(generators: Sequence[MapCarGenerator]) -> list[cw.CarGenerator]:
    result = []
    for cargen in generators:
        g = cw.CarGenerator()
        g.position = cargen.position
        g.orient_x = cargen.orient_x
        g.orient_y = cargen.orient_y
        g.perpendicular_length = cargen.perpendicular_length
        g.car_model = cargen.car_model
        g.flags = cargen.flags.value | (cargen.creation_rule.value << 28)
        g.body_color_remap_1 = cargen.body_color_remap_1
        g.body_color_remap_2 = cargen.body_color_remap_2
        g.body_color_remap_3 = cargen.body_color_remap_3
        g.body_color_remap_4 = cargen.body_color_remap_4
        g.pop_group = cargen.pop_group
        g.livery = cargen.livery
        result.append(g)
    return result


def _save_grass_instance_lists(lists: Sequence[MapGrassInstanceList]) -> list[cw.GrassInstanceListDef]:
    result = []
    for grass_instance_list in lists:
        g = cw.GrassInstanceListDef()
        emin, emax = grass_instance_list.extents
        g.batch_aabb.min = Vector((emin.x, emin.y, emin.z, 0))
        g.batch_aabb.max = Vector((emax.x, emax.y, emax.z, 0))
        g.scale_range = grass_instance_list.scale_range
        g.archetype_name = grass_instance_list.archetype_name
        g.lod_dist = grass_instance_list.lod_dist
        g.lod_fade_start_dist = grass_instance_list.lod_fade_start_dist
        g.lod_inst_fade_range = grass_instance_list.lod_inst_fade_range
        g.orient_to_terrain = grass_instance_list.orient_to_terrain
        instances = []
        for row in grass_instance_list.instances:
            inst = cw.GrassInstance()
            inst.position = [int(v) for v in row["Position"]]
            inst.normal_x = int(row["Normal"][0])
            inst.normal_y = int(row["Normal"][1])
            inst.color = [int(v) for v in row["Color"]]
            inst.scale = int(row["Scale"])
            inst.ao = int(row["Ao"])
            instances.append(inst)
        g.instance_list = instances
        result.append(g)
    return result


def _save_box_occluders(occluders: Sequence[MapBoxOccluder]) -> list[cw.BoxOccluder]:
    result = []
    for box in occluders:
        b = cw.BoxOccluder()
        b.center_x = box.center_x
        b.center_y = box.center_y
        b.center_z = box.center_z
        b.length = box.length
        b.width = box.width
        b.height = box.height
        b.cos_z = box.cos_z
        b.sin_z = box.sin_z
        result.append(b)
    return result


def _save_model_occluders(occluders: Sequence[MapModelOccluder]) -> list[cw.OccludeModel]:
    result = []
    for model in occluders:
        vertices_in_bytes = model.vertices.tobytes()
        indices_in_bytes = model.indices.tobytes()
        data = vertices_in_bytes + indices_in_bytes
        num_tris = model.indices.shape[0]

        bmin = np.min(model.vertices, axis=0)
        bmax = np.max(model.vertices, axis=0)

        m = cw.OccludeModel()
        m.bmin = Vector(bmin)
        m.bmax = Vector(bmax)
        m.verts = data
        m.num_verts_in_bytes = len(vertices_in_bytes)
        m.num_tris = num_tris | 0x8000  # add float vertex format marker
        m.data_size = len(data)
        m.flags = model.flags.value
        result.append(m)
    return result


def _save_lod_lights(lod_lights: MapLodLights, soa: cw.LODLightsSOA):
    lights = lod_lights.lights

    directions = []
    for d in lights["Direction"]:
        item = cw.FloatXYZ()
        item.x = float(d[0])
        item.y = float(d[1])
        item.z = float(d[2])
        directions.append(item)

    soa.direction = directions
    soa.falloff = lights["Falloff"].tolist()
    soa.falloff_exponent = lights["FalloffExponent"].tolist()
    soa.time_and_state_flags = lights["TimeAndStateFlags"].tolist()
    soa.hash = lights["Hash"].tolist()
    soa.cone_inner_angle = lights["ConeInnerAngle"].tolist()
    soa.cone_outer_angle_or_cap_ext = lights["ConeOuterAngleOrCapExt"].tolist()
    soa.corona_intensity = lights["CoronaIntensity"].tolist()


def _save_distant_lod_lights(distant_lod_lights: MapDistantLodLights, soa: cw.DistantLODLightsSOA):
    lights = distant_lod_lights.lights

    positions = []
    for p in lights["Position"]:
        item = cw.FloatXYZ()
        item.x = float(p[0])
        item.y = float(p[1])
        item.z = float(p[2])
        positions.append(item)

    soa.position = positions
    rgbi = lights["RGBI"]
    rgbi_u32 = (
        (rgbi[:, 3].astype(np.uint32) << 24)
        | (rgbi[:, 0].astype(np.uint32) << 16)
        | (rgbi[:, 1].astype(np.uint32) << 8)
        | rgbi[:, 2].astype(np.uint32)
    )
    soa.rgbi = rgbi_u32.tolist()
    soa.num_street_lights = distant_lod_lights.num_street_lights
    soa.category = distant_lod_lights.category.value


def _save_description(description: MapBlockDescription, block: cw.Block) -> None:
    block.version = description.version
    block.flags = description.flags
    block.name = description.name
    block.exported_by = description.exported_by
    block.owner = description.owner
    block.time = description.time


def save_map_data_to_cw(asset: AssetMapData) -> cw.CMapData:
    t = cw.CMapData()
    t.name = asset.name
    t.parent = asset.parent_name
    t.flags = asset.flags.value
    t.content_flags = asset.content_flags.value
    t.streaming_extents_min, t.streaming_extents_max = asset.streaming_extents
    t.entities_extents_min, t.entities_extents_max = asset.entities_extents
    t.entities = [to_cw_entity(e) for e in asset.entities]
    t.physics_dictionaries = [
        cw.PhysicsDictionariesList.PhysicsDictionarie(tag_name="Item", value=d) for d in asset.physics_dictionaries
    ]
    t.time_cycle_modifiers = _save_timecycle_modifiers(asset.timecycle_modifiers)
    t.car_generators = _save_car_generators(asset.car_generators)
    t.instanced_data.grass_instance_list = _save_grass_instance_lists(asset.grass_instance_lists)
    t.box_occluders = _save_box_occluders(asset.box_occluders)
    t.occlude_models = _save_model_occluders(asset.model_occluders)
    if asset.lod_lights is not None:
        _save_lod_lights(asset.lod_lights, t.lod_lights_soa)
    if asset.distant_lod_lights is not None:
        _save_distant_lod_lights(asset.distant_lod_lights, t.distant_lod_lights_soa)
    if asset.description is not None:
        _save_description(asset.description, t.block)
    return t
