"""Round-trip and backend parity tests for AssetMapData (YMAP)."""

from pathlib import Path

import numpy as np
import pytest

from szio.gta5 import (
    MAP_DISTANT_LOD_LIGHT_DTYPE,
    MAP_GRASS_INSTANCES_DTYPE,
    MAP_LOD_LIGHT_DTYPE,
    AssetFormat,
    AssetMapData,
    AssetTarget,
    AssetVersion,
    Entity,
    EntityFlags,
    EntityLodLevel,
    EntityMloInstance,
    EntityMloInstanceFlags,
    EntityPriorityLevel,
    ExtensionAudioEmitter,
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
    is_provider_available,
    save_asset,
    try_load_asset,
)
from szio.types import Quaternion, Vector

CWXML_TARGET = AssetTarget(AssetFormat.CWXML, AssetVersion.GEN8)
NATIVE_TARGET = AssetTarget(AssetFormat.NATIVE, AssetVersion.GEN8)

native_only = pytest.mark.skipif(
    not is_provider_available(NATIVE_TARGET),
    reason="native GTA5 provider not available",
)


def _make_entity(**overrides) -> Entity:
    kw = dict(
        archetype_name="hash_11111111",
        position=Vector((1.0, 2.0, 3.0)),
        rotation=Quaternion((0.0, 0.0, 0.0, 1.0)),
        scale_xy=1.25,
        scale_z=1.5,
        flags=EntityFlags.CAST_STATIC_SHADOWS | EntityFlags.IS_STATIC,
        guid=12345,
        parent_index=-1,
        lod_dist=100.0,
        child_lod_dist=50.0,
        lod_level=EntityLodLevel.HD,
        priority_level=EntityPriorityLevel.REQUIRED,
        num_children=0,
        ambient_occlusion_multiplier=255,
        artificial_ambient_occlusion=128,
        tint_value=0,
        extensions=[],
    )
    kw.update(overrides)
    return Entity(**kw)


def _make_mlo_instance(**overrides) -> EntityMloInstance:
    kw = dict(
        archetype_name="hash_22222222",
        position=Vector((10.0, 20.0, 30.0)),
        rotation=Quaternion((0.0, 0.0, 0.0, 1.0)),
        scale_xy=1.0,
        scale_z=1.0,
        flags=EntityFlags(0),
        guid=99999,
        parent_index=-1,
        lod_dist=0.0,
        child_lod_dist=0.0,
        lod_level=EntityLodLevel.HD,
        priority_level=EntityPriorityLevel.REQUIRED,
        num_children=0,
        ambient_occlusion_multiplier=0,
        artificial_ambient_occlusion=0,
        tint_value=0,
        extensions=[],
        group_id=1,
        floor_id=2,
        default_entity_sets=["hash_aaaaaaaa", "hash_bbbbbbbb"],
        num_exit_portals=4,
        mlo_inst_flags=EntityMloInstanceFlags.TURN_ON_GPS,
    )
    kw.update(overrides)
    return EntityMloInstance(**kw)


def _make_grass_instances(n: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    arr = np.empty(n, dtype=MAP_GRASS_INSTANCES_DTYPE)
    arr["Position"] = rng.integers(0, 65535, size=(n, 3), dtype=np.uint16)
    arr["Normal"] = rng.integers(0, 255, size=(n, 2), dtype=np.uint8)
    arr["Color"] = rng.integers(0, 255, size=(n, 3), dtype=np.uint8)
    arr["Scale"] = rng.integers(0, 255, size=n, dtype=np.uint8)
    arr["Ao"] = rng.integers(0, 255, size=n, dtype=np.uint8)
    return arr


def _make_lod_lights(n: int = 2) -> MapLodLights:
    arr = np.zeros(n, dtype=MAP_LOD_LIGHT_DTYPE)
    for i in range(n):
        arr[i]["Direction"] = (0.0, 0.0, -1.0)
        arr[i]["Falloff"] = 10.0 + i
        arr[i]["FalloffExponent"] = 64.0
        arr[i]["TimeAndStateFlags"] = 0xFFFFFFFF
        arr[i]["Hash"] = 0x12345678 + i
        arr[i]["ConeInnerAngle"] = 30
        arr[i]["ConeOuterAngleOrCapExt"] = 60
        arr[i]["CoronaIntensity"] = 100
    return MapLodLights(lights=arr)


def _make_distant_lod_lights(n: int = 3) -> MapDistantLodLights:
    arr = np.zeros(n, dtype=MAP_DISTANT_LOD_LIGHT_DTYPE)
    for i in range(n):
        arr[i]["Position"] = (float(i), float(i * 2), float(i * 3))
        arr[i]["RGBI"] = (255, 128, 64, 200)
    return MapDistantLodLights(
        lights=arr, num_street_lights=n, category=MapLodLightCategory.MEDIUM
    )


def _make_full_map() -> AssetMapData:
    """Build an AssetMapData with every supported feature populated."""
    audio_ext = ExtensionAudioEmitter(
        name="test_emitter",
        offset_position=Vector((0.0, 0.0, 0.0)),
        offset_rotation=Quaternion((0.0, 0.0, 0.0, 1.0)),
        effect_hash="hash_2CA1BFAB",
    )
    return AssetMapData(
        name="hash_cafebabe",
        parent_name="hash_deadbeef",
        flags=MapFlags.SCRIPTED,
        content_flags=MapContentFlags.HAS_ENTITIES_HD | MapContentFlags.HAS_OCCLUDERS,
        streaming_extents=(Vector((-100.0, -100.0, -50.0)), Vector((100.0, 100.0, 50.0))),
        entities_extents=(Vector((-80.0, -80.0, -40.0)), Vector((80.0, 80.0, 40.0))),
        entities=[
            _make_entity(extensions=[audio_ext]),
            _make_mlo_instance(),
        ],
        physics_dictionaries=["hash_33333333", "hash_44444444"],
        timecycle_modifiers=[
            MapTimeCycleModifier(
                name="test_tcm",
                extents=(Vector((-10.0, -10.0, -5.0)), Vector((10.0, 10.0, 5.0))),
                percentage=75.0,
                range=20.0,
                start_hour=6,
                end_hour=18,
            ),
        ],
        car_generators=[
            MapCarGenerator(
                position=Vector((1.0, 2.0, 3.0)),
                orient_x=0.5,
                orient_y=-0.5,
                perpendicular_length=2.5,
                car_model="hash_55555555",
                flags=MapCarGeneratorFlags.DURING_DAY | MapCarGeneratorFlags.POLICE,
                creation_rule=MapCarGeneratorCreationRule.ALL,
                body_color_remap_1=10,
                body_color_remap_2=20,
                body_color_remap_3=30,
                body_color_remap_4=40,
                pop_group="hash_66666666",
                livery=2,
            ),
        ],
        grass_instance_lists=[
            MapGrassInstanceList(
                extents=(Vector((0.0, 0.0, 0.0)), Vector((100.0, 100.0, 10.0))),
                scale_range=Vector((0.5, 1.0, 1.5)),
                archetype_name="hash_77777777",
                lod_dist=75,
                lod_fade_start_dist=40.0,
                lod_inst_fade_range=0.25,
                orient_to_terrain=1.0,
                instances=_make_grass_instances(5, seed=42),
            ),
        ],
        box_occluders=[
            MapBoxOccluder(
                center_x=100, center_y=200, center_z=300,
                length=40, width=50, height=60,
                cos_z=16384, sin_z=0,
            ),
            MapBoxOccluder(
                center_x=-100, center_y=-200, center_z=-300,
                length=80, width=70, height=90,
                cos_z=0, sin_z=16384,
            ),
        ],
        model_occluders=[
            MapModelOccluder(
                flags=MapModelOccluderFlags(0),
                vertices=np.array(
                    [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                    dtype=np.float32,
                ),
                indices=np.array(
                    [[0, 1, 2], [0, 2, 3]],
                    dtype=np.uint8,
                ),
            ),
            MapModelOccluder(
                flags=MapModelOccluderFlags.WATER_ONLY,
                vertices=np.array(
                    [[10.0, 0.0, 0.0], [11.0, 0.0, 0.0], [10.0, 1.0, 0.0]],
                    dtype=np.float32,
                ),
                indices=np.array([[0, 1, 2]], dtype=np.uint8),
            ),
        ],
        lod_lights=_make_lod_lights(2),
        distant_lod_lights=_make_distant_lod_lights(3),
        description=MapBlockDescription(
            version=2,
            flags=1,
            name="test_block",
            exported_by="test_user",
            owner="szio_tests",
            time="2026-04-27 12:00",
        ),
    )


def _assert_vec_equal(a, b, msg=""):
    assert np.allclose(tuple(a), tuple(b), atol=1e-4), f"{msg}: {tuple(a)} != {tuple(b)}"


def _assert_extents_equal(a, b, msg=""):
    _assert_vec_equal(a[0], b[0], f"{msg} min")
    _assert_vec_equal(a[1], b[1], f"{msg} max")


def _assert_entity_equal(a, b, idx):
    tag = f"entity[{idx}]"
    assert type(a) is type(b), f"{tag} type mismatch"
    assert a.archetype_name == b.archetype_name, f"{tag} archetype_name"
    _assert_vec_equal(a.position, b.position, f"{tag} position")
    assert a.flags == b.flags, f"{tag} flags"
    assert a.guid == b.guid, f"{tag} guid"
    assert a.parent_index == b.parent_index, f"{tag} parent_index"
    assert a.lod_level == b.lod_level, f"{tag} lod_level"
    assert a.priority_level == b.priority_level, f"{tag} priority_level"
    assert a.num_children == b.num_children, f"{tag} num_children"
    assert len(a.extensions) == len(b.extensions), f"{tag} extensions length"
    if isinstance(a, EntityMloInstance):
        assert a.group_id == b.group_id, f"{tag} group_id"
        assert a.floor_id == b.floor_id, f"{tag} floor_id"
        assert list(a.default_entity_sets) == list(b.default_entity_sets), f"{tag} default_entity_sets"
        assert a.num_exit_portals == b.num_exit_portals, f"{tag} num_exit_portals"
        assert a.mlo_inst_flags == b.mlo_inst_flags, f"{tag} mlo_inst_flags"


def _assert_grass_list_equal(a, b, idx):
    tag = f"grass_instance_list[{idx}]"
    _assert_extents_equal(a.extents, b.extents, f"{tag} extents")
    assert a.archetype_name == b.archetype_name, f"{tag} archetype_name"
    assert a.lod_dist == b.lod_dist, f"{tag} lod_dist"
    for field in ("Position", "Normal", "Color", "Scale", "Ao"):
        assert np.array_equal(a.instances[field], b.instances[field]), f"{tag} instances[{field}]"


def _assert_box_occluders_equal(a_list, b_list):
    assert len(a_list) == len(b_list), "box_occluders length"
    for i, (a, b) in enumerate(zip(a_list, b_list)):
        assert a == b, f"box_occluders[{i}]: {a} != {b}"


def _assert_model_occluders_equal(a_list, b_list):
    assert len(a_list) == len(b_list), "model_occluders length"
    for i, (a, b) in enumerate(zip(a_list, b_list)):
        assert a.flags == b.flags, f"model_occluders[{i}] flags"
        assert np.array_equal(a.vertices, b.vertices), f"model_occluders[{i}] vertices"
        assert np.array_equal(a.indices, b.indices), f"model_occluders[{i}] indices"


def _assert_map_data_equal(a: AssetMapData, b: AssetMapData):
    assert a.name == b.name
    assert a.parent_name == b.parent_name
    assert a.flags == b.flags
    assert a.content_flags == b.content_flags
    _assert_extents_equal(a.streaming_extents, b.streaming_extents, "streaming_extents")
    _assert_extents_equal(a.entities_extents, b.entities_extents, "entities_extents")

    assert len(a.entities) == len(b.entities)
    for i, (ea, eb) in enumerate(zip(a.entities, b.entities)):
        _assert_entity_equal(ea, eb, i)

    assert list(a.physics_dictionaries) == list(b.physics_dictionaries)

    assert len(a.timecycle_modifiers) == len(b.timecycle_modifiers)
    for ta, tb in zip(a.timecycle_modifiers, b.timecycle_modifiers):
        assert ta.name == tb.name
        assert ta.percentage == tb.percentage
        assert ta.start_hour == tb.start_hour
        assert ta.end_hour == tb.end_hour

    assert len(a.car_generators) == len(b.car_generators)
    for ca, cb in zip(a.car_generators, b.car_generators):
        assert ca.car_model == cb.car_model
        assert ca.pop_group == cb.pop_group
        assert ca.flags == cb.flags
        assert ca.body_color_remap == cb.body_color_remap
        assert ca.livery == cb.livery

    assert len(a.grass_instance_lists) == len(b.grass_instance_lists)
    for i, (ga, gb) in enumerate(zip(a.grass_instance_lists, b.grass_instance_lists)):
        _assert_grass_list_equal(ga, gb, i)

    _assert_box_occluders_equal(a.box_occluders, b.box_occluders)
    _assert_model_occluders_equal(a.model_occluders, b.model_occluders)

    if a.lod_lights is None:
        assert b.lod_lights is None
    else:
        assert b.lod_lights is not None
        for field in ("Direction", "Falloff", "Hash", "ConeInnerAngle"):
            assert np.array_equal(a.lod_lights.lights[field], b.lod_lights.lights[field]), f"lod_lights[{field}]"

    if a.distant_lod_lights is None:
        assert b.distant_lod_lights is None
    else:
        assert b.distant_lod_lights is not None
        assert a.distant_lod_lights.category == b.distant_lod_lights.category
        for field in ("Position", "RGBI"):
            assert np.array_equal(
                a.distant_lod_lights.lights[field], b.distant_lod_lights.lights[field]
            ), f"distant_lod_lights[{field}]"

    if a.description is None:
        assert b.description is None
    else:
        assert b.description is not None
        assert a.description == b.description


def _roundtrip(asset: AssetMapData, target: AssetTarget, tmp_path: Path) -> AssetMapData:
    tmp_path.mkdir(parents=True, exist_ok=True)
    save_asset(asset, [target], tmp_path, "rt_map")
    ext = ".ymap" if target.format == AssetFormat.NATIVE else ".ymap.xml"
    reloaded = try_load_asset(tmp_path / f"rt_map{ext}")
    assert reloaded is not None
    return reloaded


def test_maps_roundtrip_cwxml(tmp_path: Path):
    original = _make_full_map()
    reloaded = _roundtrip(original, CWXML_TARGET, tmp_path)
    _assert_map_data_equal(original, reloaded)


@native_only
def test_maps_roundtrip_native(tmp_path: Path):
    original = _make_full_map()
    reloaded = _roundtrip(original, NATIVE_TARGET, tmp_path)
    _assert_map_data_equal(original, reloaded)


@native_only
def test_maps_cross_backend_equivalence(tmp_path: Path):
    """Same AssetMapData saved through each backend and reloaded should be equivalent."""
    original = _make_full_map()
    via_cwxml = _roundtrip(original, CWXML_TARGET, tmp_path / "cw")
    via_native = _roundtrip(original, NATIVE_TARGET, tmp_path / "nat")
    _assert_map_data_equal(via_cwxml, via_native)


@native_only
def test_maps_native_preserves_box_occluders(tmp_path: Path):
    original = AssetMapData(
        box_occluders=[
            MapBoxOccluder(
                center_x=42, center_y=-7, center_z=9,
                length=80, width=60, height=120,
                cos_z=16384, sin_z=-100,
            ),
        ],
    )
    reloaded = _roundtrip(original, NATIVE_TARGET, tmp_path)
    _assert_box_occluders_equal(original.box_occluders, reloaded.box_occluders)


@native_only
def test_maps_native_preserves_model_occluders(tmp_path: Path):
    original = AssetMapData(
        model_occluders=[
            MapModelOccluder(
                flags=MapModelOccluderFlags.WATER_ONLY,
                vertices=np.array(
                    [[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, 2.0]],
                    dtype=np.float32,
                ),
                indices=np.array([[0, 1, 2], [0, 2, 3], [1, 3, 2]], dtype=np.uint8),
            ),
        ],
    )
    reloaded = _roundtrip(original, NATIVE_TARGET, tmp_path)
    _assert_model_occluders_equal(original.model_occluders, reloaded.model_occluders)


def test_maps_cwxml_preserves_default_entity_sets(tmp_path: Path):
    mlo = _make_mlo_instance(
        default_entity_sets=["hash_11111111", "hash_22222222", "hash_33333333"],
    )
    original = AssetMapData(entities=[mlo])
    reloaded = _roundtrip(original, CWXML_TARGET, tmp_path)
    assert list(reloaded.entities[0].default_entity_sets) == list(mlo.default_entity_sets)


def test_maps_cwxml_preserves_grass_instances(tmp_path: Path):
    original = AssetMapData(
        grass_instance_lists=[
            MapGrassInstanceList(
                extents=(Vector((0.0, 0.0, 0.0)), Vector((10.0, 10.0, 1.0))),
                scale_range=Vector((0.5, 1.0, 1.5)),
                archetype_name="hash_abcdef01",
                lod_dist=50,
                lod_fade_start_dist=30.0,
                lod_inst_fade_range=0.5,
                orient_to_terrain=1.0,
                instances=_make_grass_instances(10, seed=7),
            ),
        ],
    )
    reloaded = _roundtrip(original, CWXML_TARGET, tmp_path)
    _assert_grass_list_equal(original.grass_instance_lists[0], reloaded.grass_instance_lists[0], 0)
