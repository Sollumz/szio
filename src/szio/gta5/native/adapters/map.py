from collections.abc import Sequence

import numpy as np
import pymateria as pma
import pymateria.gta5 as pm

from ....types import Vector
from ...entities import MapEntity
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
from ._utils import (
    _h2s,
    _s2h,
    to_native_aabb,
    to_native_vec3,
)
from .archetype import from_native_entity, to_native_entity


def _load_timecycle_modifiers(t: pm.MapData) -> list[MapTimeCycleModifier]:
    return [
        MapTimeCycleModifier(
            name=_h2s(tcm.name),
            extents=(Vector(tcm.min_extents), Vector(tcm.max_extents)),
            percentage=float(tcm.percentage),
            range=float(tcm.range),
            start_hour=int(tcm.start_hour),
            end_hour=int(tcm.end_hour),
        )
        for tcm in t.time_cycle_modifiers
    ]


def _load_car_generators(t: pm.MapData) -> list[MapCarGenerator]:
    return [
        MapCarGenerator(
            position=Vector(cargen.position),
            orient_x=float(cargen.orient.x),
            orient_y=float(cargen.orient.y),
            perpendicular_length=float(cargen.perpendicular_length),
            car_model=_h2s(cargen.car_model),
            flags=MapCarGeneratorFlags(int(cargen.flags) & 0x1FFFF),
            creation_rule=MapCarGeneratorCreationRule((int(cargen.flags) & 0xF0000000) >> 28),
            body_color_remap_1=int(cargen.body_color_remap_1),
            body_color_remap_2=int(cargen.body_color_remap_2),
            body_color_remap_3=int(cargen.body_color_remap_3),
            body_color_remap_4=int(cargen.body_color_remap_4),
            pop_group=_h2s(cargen.pop_group),
            livery=int(cargen.livery),
        )
        for cargen in t.car_generators
    ]


def _load_grass_instance_lists(t: pm.MapData) -> list[MapGrassInstanceList]:
    def _map_grass_instances(instances: list[pm.GrassInstance]) -> np.ndarray:
        arr = np.empty(len(instances), dtype=MAP_GRASS_INSTANCES_DTYPE)
        pos = arr["Position"]
        nml = arr["Normal"]
        col = arr["Color"]
        scl = arr["Scale"]
        ao = arr["Ao"]
        for i, inst in enumerate(instances):
            pos[i] = inst.position.x, inst.position.y, inst.position.z
            nml[i] = inst.normal.x, inst.normal.y
            col[i] = inst.color.r, inst.color.g, inst.color.b
            scl[i] = inst.scale
            ao[i] = inst.ambient_occlusion
        return arr

    return [
        MapGrassInstanceList(
            extents=(Vector(gil.batch_aabb.min), Vector(gil.batch_aabb.max)),
            scale_range=Vector(gil.scale_range),
            archetype_name=_h2s(gil.archetype_name),
            lod_dist=int(gil.lod_dist),
            lod_fade_start_dist=gil.lod_fade_start_dist,
            lod_inst_fade_range=gil.lod_inst_fade_range,
            orient_to_terrain=gil.orient_to_terrain,
            instances=_map_grass_instances(gil.instances),
        )
        for gil in t.instanced_data.grass_instance_lists
    ]


def _load_box_occluders(t: pm.MapData) -> list[MapBoxOccluder]:
    return [
        MapBoxOccluder(
            center_x=int(b.center.x),
            center_y=int(b.center.y),
            center_z=int(b.center.z),
            length=int(b.length),
            width=int(b.width),
            height=int(b.height),
            cos_z=int(b.cos_z),
            sin_z=int(b.sin_z),
        )
        for b in t.box_occluders
    ]


def _load_model_occluders(t: pm.MapData) -> list[MapModelOccluder]:
    result = []
    for m in t.occlude_models:
        assert m.float_vertex_format, "Only float vertex format of occlude models is supported"

        native_verts = m.vertices
        native_tris = m.tris

        vertices = np.empty((len(native_verts), 3), dtype=np.float32)
        for i, v in enumerate(native_verts):
            vertices[i] = (v.x, v.y, v.z)

        indices = np.empty((len(native_tris), 3), dtype=np.uint8)
        for i, tri in enumerate(native_tris):
            indices[i] = (tri.x, tri.y, tri.z)

        result.append(
            MapModelOccluder(
                flags=MapModelOccluderFlags(m.flags.value),
                vertices=vertices,
                indices=indices,
            )
        )
    return result


def _load_lod_lights(t: pm.MapData) -> MapLodLights | None:
    native_lights = t.lod_lights.lights
    if not native_lights:
        return None

    n = len(native_lights)
    lights = np.empty(n, dtype=MAP_LOD_LIGHT_DTYPE)
    for i, light in enumerate(native_lights):
        d = light.direction
        lights["Direction"][i] = (d.x, d.y, d.z)
        lights["Falloff"][i] = light.falloff
        lights["FalloffExponent"][i] = light.falloff_exponent
        lights["TimeAndStateFlags"][i] = light.time_and_state_flags
        lights["Hash"][i] = light.hash
        lights["ConeInnerAngle"][i] = light.cone_inner_angle
        lights["ConeOuterAngleOrCapExt"][i] = light.cone_outer_angle_or_cap_ext
        lights["CoronaIntensity"][i] = light.corona_intensity

    return MapLodLights(lights=lights)


def _load_distant_lod_lights(t: pm.MapData) -> MapDistantLodLights | None:
    dl = t.distant_lod_lights
    native_lights = dl.lights
    if not native_lights:
        return None

    n = len(native_lights)
    lights = np.empty(n, dtype=MAP_DISTANT_LOD_LIGHT_DTYPE)
    num_street_lights = 0
    for i, light in enumerate(native_lights):
        p = light.position
        lights["Position"][i] = (p.x, p.y, p.z)
        c = light.color
        lights["RGBI"][i] = (c.r, c.g, c.b, c.a)
        if light.is_street_light:
            num_street_lights += 1

    return MapDistantLodLights(
        lights=lights,
        num_street_lights=num_street_lights,
        category=MapLodLightCategory(dl.category.value),
    )


def _load_description(t: pm.MapData) -> MapBlockDescription | None:
    d = t.description
    version = int(d.version)
    flags = int(d.flags)
    name = d.name or ""
    exported_by = d.exported_by or ""
    owner = d.owner or ""
    time = d.time or ""
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


def load_map_data_from_native(t: pm.MapData) -> AssetMapData:
    return AssetMapData(
        name=_h2s(t.name),
        parent_name=_h2s(t.parent),
        flags=MapFlags(t.flags),
        content_flags=MapContentFlags(t.content_flags),
        streaming_extents=(Vector(t.streaming_extents_min), Vector(t.streaming_extents_max)),
        entities_extents=(Vector(t.entities_extents_min), Vector(t.entities_extents_max)),
        entities=[from_native_entity(e) for e in t.entities],
        physics_dictionaries=[_h2s(d) for d in t.physics_dictionaries],
        timecycle_modifiers=_load_timecycle_modifiers(t),
        car_generators=_load_car_generators(t),
        grass_instance_lists=_load_grass_instance_lists(t),
        box_occluders=_load_box_occluders(t),
        model_occluders=_load_model_occluders(t),
        lod_lights=_load_lod_lights(t),
        distant_lod_lights=_load_distant_lod_lights(t),
        description=_load_description(t),
    )


def _save_timecycle_modifiers(modifiers: Sequence[MapTimeCycleModifier]) -> list[pm.TimeCycleModifier]:
    result = []
    for tcm in modifiers:
        m = pm.TimeCycleModifier()
        m.name = tcm.name
        emin, emax = tcm.extents
        m.min_extents = to_native_vec3(emin)
        m.max_extents = to_native_vec3(emax)
        m.percentage = tcm.percentage
        m.range = tcm.range
        m.start_hour = tcm.start_hour
        m.end_hour = tcm.end_hour
        result.append(m)
    return result


def _save_car_generators(generators: Sequence[MapCarGenerator]) -> list[pm.CarGenerator]:
    result = []
    for cargen in generators:
        g = pm.CarGenerator()
        g.position = to_native_vec3(cargen.position)
        g.orient = pma.Vector2f(cargen.orient_x, cargen.orient_y)
        g.perpendicular_length = cargen.perpendicular_length
        g.car_model = _s2h(cargen.car_model)
        g.flags = cargen.flags.value | (cargen.creation_rule.value << 28)
        g.body_color_remap_1 = cargen.body_color_remap_1
        g.body_color_remap_2 = cargen.body_color_remap_2
        g.body_color_remap_3 = cargen.body_color_remap_3
        g.body_color_remap_4 = cargen.body_color_remap_4
        g.pop_group = _s2h(cargen.pop_group)
        g.livery = cargen.livery
        result.append(g)
    return result


def _save_grass_instance_lists(lists: Sequence[MapGrassInstanceList]) -> list[pm.GrassInstanceList]:
    result = []
    for grass_instance_list in lists:
        g = pm.GrassInstanceList()
        emin, emax = grass_instance_list.extents
        g.batch_aabb = to_native_aabb(emin, emax)
        g.scale_range = to_native_vec3(grass_instance_list.scale_range)
        g.archetype_name = grass_instance_list.archetype_name
        g.lod_dist = grass_instance_list.lod_dist
        g.lod_fade_start_dist = grass_instance_list.lod_fade_start_dist
        g.lod_inst_fade_range = grass_instance_list.lod_inst_fade_range
        g.orient_to_terrain = grass_instance_list.orient_to_terrain

        instances = []
        for row in grass_instance_list.instances:
            inst = pm.GrassInstance()
            px, py, pz = row["Position"]
            inst.position = pma.Vector3u16(int(px), int(py), int(pz))
            nx, ny = row["Normal"]
            inst.normal = pma.Vector2u8(int(nx), int(ny))
            cr, cg, cb = row["Color"]
            inst.color = pma.ColorRGB(int(cr), int(cg), int(cb))
            inst.scale = int(row["Scale"])
            inst.ambient_occlusion = int(row["Ao"])
            instances.append(inst)
        g.instances = instances
        result.append(g)
    return result


def _save_box_occluders(occluders: Sequence[MapBoxOccluder]) -> list[pm.BoxOccluder]:
    result = []
    for box in occluders:
        b = pm.BoxOccluder()
        b.center = pma.Vector3s16(box.center_x, box.center_y, box.center_z)
        b.length = box.length
        b.width = box.width
        b.height = box.height
        b.cos_z = box.cos_z
        b.sin_z = box.sin_z
        result.append(b)
    return result


def _save_model_occluders(occluders: Sequence[MapModelOccluder]) -> list[pm.OccludeModel]:
    result = []
    for model in occluders:
        m = pm.OccludeModel()
        m.flags = pm.OccludeModelFlags(model.flags.value)
        m.float_vertex_format = True
        m.vertices = [pma.Vector3f(float(v[0]), float(v[1]), float(v[2])) for v in model.vertices]
        m.tris = [pma.Vector3u8(int(t[0]), int(t[1]), int(t[2])) for t in model.indices]
        result.append(m)
    return result


def _save_lod_lights(lod_lights: MapLodLights) -> list[pm.LODLights.Light]:
    result = []
    for row in lod_lights.lights:
        light = pm.LODLights.Light()
        dx, dy, dz = row["Direction"]
        light.direction = pma.Vector3f(float(dx), float(dy), float(dz))
        light.falloff = float(row["Falloff"])
        light.falloff_exponent = float(row["FalloffExponent"])
        light.time_and_state_flags = int(row["TimeAndStateFlags"])
        light.hash = int(row["Hash"])
        light.cone_inner_angle = int(row["ConeInnerAngle"])
        light.cone_outer_angle_or_cap_ext = int(row["ConeOuterAngleOrCapExt"])
        light.corona_intensity = int(row["CoronaIntensity"])
        result.append(light)
    return result


def _save_distant_lod_lights(distant_lod_lights: MapDistantLodLights | None) -> pm.DistantLODLights:
    result = []
    num_street_lights = distant_lod_lights.num_street_lights
    for i, row in enumerate(distant_lod_lights.lights):
        light = pm.DistantLODLights.Light()
        px, py, pz = row["Position"]
        light.position = pma.Vector3f(float(px), float(py), float(pz))
        r, g, b, intensity = row["RGBI"]
        light.color = pma.ColorRGBA(int(r), int(g), int(b), int(intensity))
        light.is_street_light = i < num_street_lights
        result.append(light)
    return result, pm.LodLightCategory(distant_lod_lights.category.value)


def _save_description(description: MapBlockDescription, d: pm.MapDataDescription) -> None:
    d.version = description.version
    d.flags = description.flags
    d.name = description.name
    d.exported_by = description.exported_by
    d.owner = description.owner
    d.time = description.time


def save_map_data_to_native(asset: AssetMapData) -> pm.MapData:
    t = pm.MapData()
    t.name = asset.name
    t.parent = asset.parent_name
    t.flags = asset.flags.value
    t.content_flags = asset.content_flags.value
    t.streaming_extents_min = to_native_vec3(asset.streaming_extents[0])
    t.streaming_extents_max = to_native_vec3(asset.streaming_extents[1])
    t.entities_extents_min = to_native_vec3(asset.entities_extents[0])
    t.entities_extents_max = to_native_vec3(asset.entities_extents[1])
    t.entities = [to_native_entity(e) for e in asset.entities]
    t.physics_dictionaries = [_s2h(d) for d in asset.physics_dictionaries]
    t.time_cycle_modifiers = _save_timecycle_modifiers(asset.timecycle_modifiers)
    t.car_generators = _save_car_generators(asset.car_generators)
    t.instanced_data.grass_instance_lists = _save_grass_instance_lists(asset.grass_instance_lists)
    t.box_occluders = _save_box_occluders(asset.box_occluders)
    t.occlude_models = _save_model_occluders(asset.model_occluders)
    if asset.lod_lights is not None:
        t.lod_lights.lights = _save_lod_lights(asset.lod_lights)
    if asset.distant_lod_lights is not None:
        lights, category = _save_distant_lod_lights(asset.distant_lod_lights)
        t.distant_lod_lights.lights = lights
        t.distant_lod_lights.category = category
    if asset.description is not None:
        _save_description(asset.description, t.description)
    return t
