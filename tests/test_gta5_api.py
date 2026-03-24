"""Tests for the szio.gta5 API using anonymized test data files."""

from pathlib import Path

import pytest

from szio.assets import AssetGame
from szio.gta5 import (
    AssetBound,
    AssetDrawable,
    AssetDrawableDictionary,
    AssetFormat,
    AssetTarget,
    AssetVersion,
    BoundPrimitiveType,
    BoundType,
    CollisionFlags,
    LodLevel,
    RenderBucket,
    try_load_asset,
    save_asset,
)
from szio.gta5.native import IS_BACKEND_AVAILABLE

DATA_DIR = Path(__file__).parent / "data" / "gta5"

requires_native = pytest.mark.skipif(
    not IS_BACKEND_AVAILABLE,
    reason="Native backend (pymateria) not available",
)


# ---------------------------------------------------------------------------
# Drawable tests
# ---------------------------------------------------------------------------

class DrawableTests:
    """Shared drawable test methods. Subclasses provide the `drawable` fixture."""

    def test_is_asset_drawable(self, drawable: AssetDrawable):
        assert isinstance(drawable, AssetDrawable)

    def test_asset_game(self, drawable: AssetDrawable):
        assert drawable.ASSET_GAME == AssetGame.GTA5

    def test_name(self, drawable: AssetDrawable):
        assert drawable.name == "test_drawable"

    def test_no_bounds(self, drawable: AssetDrawable):
        assert drawable.bounds is None

    def test_no_skeleton(self, drawable: AssetDrawable):
        assert drawable.skeleton is None

    def test_lights_empty(self, drawable: AssetDrawable):
        assert drawable.lights == []

    def test_shader_group(self, drawable: AssetDrawable):
        sg = drawable.shader_group
        assert sg is not None
        assert len(sg.shaders) == 1
        shader = sg.shaders[0]
        assert shader.render_bucket == RenderBucket.OPAQUE

    def test_models_high_lod(self, drawable: AssetDrawable):
        assert LodLevel.HIGH in drawable.models
        models = drawable.models[LodLevel.HIGH]
        assert len(models) == 1

    def test_geometry(self, drawable: AssetDrawable):
        geom = drawable.models[LodLevel.HIGH][0].geometries[0]
        assert geom.shader_index == 0
        assert len(geom.vertex_buffer) == 8
        assert len(geom.index_buffer) == 12


class TestDrawableCWXML(DrawableTests):
    @pytest.fixture()
    def drawable(self) -> AssetDrawable:
        asset = try_load_asset(DATA_DIR / "test_drawable.ydr.xml")
        assert asset is not None
        return asset

    def test_shader_name(self, drawable: AssetDrawable):
        assert drawable.shader_group.shaders[0].name == "emissive"

    def test_shader_preset_filename(self, drawable: AssetDrawable):
        assert drawable.shader_group.shaders[0].preset_filename == "emissive.sps"

    def test_shader_parameters(self, drawable: AssetDrawable):
        params = drawable.shader_group.shaders[0].parameters
        param_names = [p.name for p in params]
        assert "DiffuseSampler" in param_names
        assert "emissiveMultiplier" in param_names

        diffuse = next(p for p in params if p.name == "DiffuseSampler")
        assert diffuse.value == "test_texture"


@requires_native
class TestDrawableGen8(DrawableTests):
    @pytest.fixture()
    def drawable(self) -> AssetDrawable:
        asset = try_load_asset(DATA_DIR / "gen8" / "test_drawable.ydr")
        assert asset is not None
        return asset


    def test_shader_parameters(self, drawable: AssetDrawable):
        params = drawable.shader_group.shaders[0].parameters
        # gen8 uses lowercase parameter names
        param_names = [p.name.lower() for p in params]
        assert "diffusesampler" in param_names
        assert "emissivemultiplier" in param_names


@requires_native
class TestDrawableGen9(DrawableTests):
    @pytest.fixture()
    def drawable(self) -> AssetDrawable:
        asset = try_load_asset(DATA_DIR / "gen9" / "test_drawable.ydr")
        assert asset is not None
        return asset


    def test_shader_name(self, drawable: AssetDrawable):
        assert drawable.shader_group.shaders[0].name == "emissive"

    def test_shader_parameters(self, drawable: AssetDrawable):
        params = drawable.shader_group.shaders[0].parameters
        param_names = [p.name for p in params]
        assert "DiffuseSampler" in param_names
        assert "emissiveMultiplier" in param_names

        diffuse = next(p for p in params if p.name == "DiffuseSampler")
        assert diffuse.value == "test_texture"


# ---------------------------------------------------------------------------
# Bounds tests
# ---------------------------------------------------------------------------

class BoundsTests:
    """Shared bounds test methods. Subclasses provide the `bound` fixture."""

    def test_is_asset_bound(self, bound: AssetBound):
        assert isinstance(bound, AssetBound)

    def test_asset_game(self, bound: AssetBound):
        assert bound.ASSET_GAME == AssetGame.GTA5

    def test_composite_type(self, bound: AssetBound):
        assert bound.bound_type == BoundType.COMPOSITE

    def test_children_count(self, bound: AssetBound):
        assert len(bound.children) == 1

    def test_child_is_bvh(self, bound: AssetBound):
        child = bound.children[0]
        assert child is not None
        assert child.bound_type == BoundType.BVH

    def test_child_geometry_vertices(self, bound: AssetBound):
        child = bound.children[0]
        assert len(child.geometry_vertices) == 2

    def test_child_geometry_primitives(self, bound: AssetBound):
        child = bound.children[0]
        prims = child.geometry_primitives
        assert len(prims) == 1
        assert prims[0].primitive_type == BoundPrimitiveType.CAPSULE
        assert prims[0].radius == pytest.approx(0.25)

    def test_child_composite_flags(self, bound: AssetBound):
        child = bound.children[0]
        type_flags = child.composite_collision_type_flags
        assert CollisionFlags.MAP_TYPE_COVER in type_flags
        assert CollisionFlags.MAP_TYPE_VEHICLE in type_flags

        include_flags = child.composite_collision_include_flags
        assert CollisionFlags.PED_TYPE in include_flags
        assert CollisionFlags.OBJECT_TYPE in include_flags

    def test_child_material(self, bound: AssetBound):
        child = bound.children[0]
        mat = child.geometry_primitives[0].material
        assert mat.material_index == 0


class TestBoundsCWXML(BoundsTests):
    @pytest.fixture()
    def bound(self) -> AssetBound:
        asset = try_load_asset(DATA_DIR / "test_bounds.ybn.xml")
        assert asset is not None
        return asset


@requires_native
class TestBoundsNative(BoundsTests):
    @pytest.fixture()
    def bound(self) -> AssetBound:
        asset = try_load_asset(DATA_DIR / "test_bounds.ybn")
        assert asset is not None
        return asset


# ---------------------------------------------------------------------------
# Drawable dictionary tests
# ---------------------------------------------------------------------------

class DrawableDictionaryTests:
    """Shared drawable dictionary test methods. Subclasses provide the `dd` fixture."""

    def test_is_asset_drawable_dictionary(self, dd: AssetDrawableDictionary):
        assert isinstance(dd, AssetDrawableDictionary)

    def test_asset_game(self, dd: AssetDrawableDictionary):
        assert dd.ASSET_GAME == AssetGame.GTA5

    def test_drawable_count(self, dd: AssetDrawableDictionary):
        assert len(dd.drawables) == 2

    def test_each_drawable_has_shader_group(self, dd: AssetDrawableDictionary):
        for name, drw in dd.drawables.items():
            assert drw.shader_group is not None, f"{name} missing shader_group"
            assert len(drw.shader_group.shaders) == 1

    def test_each_drawable_has_models(self, dd: AssetDrawableDictionary):
        for name, drw in dd.drawables.items():
            assert LodLevel.HIGH in drw.models, f"{name} missing HIGH lod"
            models = drw.models[LodLevel.HIGH]
            assert len(models) == 1
            assert len(models[0].geometries) == 1


class TestDrawableDictionaryCWXML(DrawableDictionaryTests):
    @pytest.fixture()
    def dd(self) -> AssetDrawableDictionary:
        asset = try_load_asset(DATA_DIR / "test_drawable_dictionary.ydd.xml")
        assert asset is not None
        return asset

    def test_drawable_names(self, dd: AssetDrawableDictionary):
        names = set(dd.drawables.keys())
        assert names == {"test_object_a_lod", "test_object_b_lod"}

    def test_shader_names(self, dd: AssetDrawableDictionary):
        for drw in dd.drawables.values():
            assert drw.shader_group.shaders[0].name == "trees_lod2"


@requires_native
class TestDrawableDictionaryGen8(DrawableDictionaryTests):
    @pytest.fixture()
    def dd(self) -> AssetDrawableDictionary:
        asset = try_load_asset(DATA_DIR / "gen8" / "test_drawable_dictionary.ydd")
        assert asset is not None
        return asset



@requires_native
class TestDrawableDictionaryGen9(DrawableDictionaryTests):
    @pytest.fixture()
    def dd(self) -> AssetDrawableDictionary:
        asset = try_load_asset(DATA_DIR / "gen9" / "test_drawable_dictionary.ydd")
        assert asset is not None
        return asset



# ---------------------------------------------------------------------------
# Roundtrip tests
# ---------------------------------------------------------------------------

class TestRoundtripCWXML:
    TARGETS = [AssetTarget(AssetFormat.CWXML, AssetVersion.GEN8)]

    @pytest.mark.parametrize("filename", [
        "test_drawable.ydr.xml",
        "test_bounds.ybn.xml",
        "test_drawable_dictionary.ydd.xml",
    ])
    def test_save_and_reload(self, filename: str, tmp_path: Path):
        asset = try_load_asset(DATA_DIR / filename)
        assert asset is not None

        name = filename.split(".")[0]
        ext = "." + filename.split(".")[1]
        save_asset(asset, tmp_path, name, targets=self.TARGETS)

        reloaded = try_load_asset(tmp_path / f"{name}{ext}.xml")
        assert reloaded is not None
        assert reloaded.ASSET_GAME == AssetGame.GTA5

    def test_drawable_roundtrip_preserves_data(self, tmp_path: Path):
        original = try_load_asset(DATA_DIR / "test_drawable.ydr.xml")
        save_asset(original, tmp_path, "rt", targets=self.TARGETS)
        reloaded = try_load_asset(tmp_path / "rt.ydr.xml")

        assert reloaded.name == original.name
        assert len(reloaded.shader_group.shaders) == len(original.shader_group.shaders)
        assert reloaded.shader_group.shaders[0].name == original.shader_group.shaders[0].name

        orig_geom = original.models[LodLevel.HIGH][0].geometries[0]
        rt_geom = reloaded.models[LodLevel.HIGH][0].geometries[0]
        assert len(rt_geom.vertex_buffer) == len(orig_geom.vertex_buffer)
        assert len(rt_geom.index_buffer) == len(orig_geom.index_buffer)

    def test_bounds_roundtrip_preserves_data(self, tmp_path: Path):
        original = try_load_asset(DATA_DIR / "test_bounds.ybn.xml")
        save_asset(original, tmp_path, "rt", targets=self.TARGETS)
        reloaded = try_load_asset(tmp_path / "rt.ybn.xml")

        assert reloaded.bound_type == original.bound_type
        assert len(reloaded.children) == len(original.children)

        orig_child = original.children[0]
        rt_child = reloaded.children[0]
        assert rt_child.bound_type == orig_child.bound_type
        assert len(rt_child.geometry_vertices) == len(orig_child.geometry_vertices)
        assert len(rt_child.geometry_primitives) == len(orig_child.geometry_primitives)

    def test_drawable_dictionary_roundtrip_preserves_data(self, tmp_path: Path):
        original = try_load_asset(DATA_DIR / "test_drawable_dictionary.ydd.xml")
        save_asset(original, tmp_path, "rt", targets=self.TARGETS)
        reloaded = try_load_asset(tmp_path / "rt.ydd.xml")

        assert set(reloaded.drawables.keys()) == set(original.drawables.keys())
        for name in original.drawables:
            assert reloaded.drawables[name].shader_group.shaders[0].name == \
                original.drawables[name].shader_group.shaders[0].name

    def test_fragment_roundtrip_preserves_data(self, tmp_path: Path):
        original = try_load_asset(DATA_DIR / "test_fragment_simple.yft.xml")
        save_asset(original, tmp_path, "rt", targets=self.TARGETS)
        reloaded = try_load_asset(tmp_path / "rt.yft.xml")

        assert reloaded.name == original.name
        assert reloaded.gravity_factor == pytest.approx(original.gravity_factor)
        assert reloaded.buoyancy_factor == pytest.approx(original.buoyancy_factor)
        assert len(reloaded.physics.lod1.groups) == len(original.physics.lod1.groups)
        assert len(reloaded.physics.lod1.children) == len(original.physics.lod1.children)
        assert reloaded.physics.lod1.archetype.name == original.physics.lod1.archetype.name
        assert reloaded.physics.lod1.archetype.mass == pytest.approx(original.physics.lod1.archetype.mass)

    def test_fragment_damaged_roundtrip_preserves_data(self, tmp_path: Path):
        original = try_load_asset(DATA_DIR / "test_fragment_damaged.yft.xml")
        save_asset(original, tmp_path, "rt", targets=self.TARGETS)
        reloaded = try_load_asset(tmp_path / "rt.yft.xml")

        assert reloaded.name == original.name
        assert len(reloaded.extra_drawables) == len(original.extra_drawables)
        assert reloaded.physics.lod1.damaged_archetype is not None
        assert reloaded.physics.lod1.damaged_archetype.mass == pytest.approx(
            original.physics.lod1.damaged_archetype.mass
        )

    def test_fragment_cloth_roundtrip_no_physics(self, tmp_path: Path):
        original = try_load_asset(DATA_DIR / "test_fragment_cloth.yft.xml")
        assert original.physics is None
        save_asset(original, tmp_path, "rt", targets=self.TARGETS)
        reloaded = try_load_asset(tmp_path / "rt.yft.xml")
        assert reloaded.physics is None


@requires_native
class TestRoundtripNative:
    """Load native binary assets, save as binary, reload and verify."""

    GEN8_TARGETS = [AssetTarget(AssetFormat.NATIVE, AssetVersion.GEN8)]
    GEN9_TARGETS = [AssetTarget(AssetFormat.NATIVE, AssetVersion.GEN9)]

    def test_drawable_gen8_roundtrip(self, tmp_path: Path):
        original = try_load_asset(DATA_DIR / "gen8" / "test_drawable.ydr")
        assert original is not None
        save_asset(original, tmp_path, "rt", targets=self.GEN8_TARGETS)
        reloaded = try_load_asset(tmp_path / "rt.ydr")
        assert reloaded is not None

        assert reloaded.name == original.name
        orig_geom = original.models[LodLevel.HIGH][0].geometries[0]
        rt_geom = reloaded.models[LodLevel.HIGH][0].geometries[0]
        assert len(rt_geom.vertex_buffer) == len(orig_geom.vertex_buffer)
        assert len(rt_geom.index_buffer) == len(orig_geom.index_buffer)

    def test_drawable_gen9_roundtrip(self, tmp_path: Path):
        original = try_load_asset(DATA_DIR / "gen9" / "test_drawable.ydr")
        assert original is not None
        orig_geom = original.models[LodLevel.HIGH][0].geometries[0] # note: pymateria FVF dtype breaks after export so get geometry here
        save_asset(original, tmp_path, "rt", targets=self.GEN9_TARGETS)
        reloaded = try_load_asset(tmp_path / "rt.ydr")
        assert reloaded is not None

        assert reloaded.name == original.name
        rt_geom = reloaded.models[LodLevel.HIGH][0].geometries[0]
        assert len(rt_geom.vertex_buffer) == len(orig_geom.vertex_buffer)
        assert len(rt_geom.index_buffer) == len(orig_geom.index_buffer)

    def test_bounds_native_roundtrip(self, tmp_path: Path):
        original = try_load_asset(DATA_DIR / "test_bounds.ybn")
        assert original is not None
        save_asset(original, tmp_path, "rt", targets=self.GEN8_TARGETS)
        reloaded = try_load_asset(tmp_path / "rt.ybn")
        assert reloaded is not None

        assert reloaded.bound_type == original.bound_type
        assert len(reloaded.children) == len(original.children)
        assert reloaded.children[0].bound_type == original.children[0].bound_type

    def test_drawable_dictionary_gen8_roundtrip(self, tmp_path: Path):
        original = try_load_asset(DATA_DIR / "gen8" / "test_drawable_dictionary.ydd")
        assert original is not None
        save_asset(original, tmp_path, "rt", targets=self.GEN8_TARGETS)
        reloaded = try_load_asset(tmp_path / "rt.ydd")
        assert reloaded is not None

        assert len(reloaded.drawables) == len(original.drawables)

    def test_drawable_dictionary_gen9_roundtrip(self, tmp_path: Path):
        original = try_load_asset(DATA_DIR / "gen9" / "test_drawable_dictionary.ydd")
        assert original is not None
        save_asset(original, tmp_path, "rt", targets=self.GEN9_TARGETS)
        reloaded = try_load_asset(tmp_path / "rt.ydd")
        assert reloaded is not None

        assert len(reloaded.drawables) == len(original.drawables)
