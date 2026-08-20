"""Tests for the szio.gta5 API using anonymized test data files."""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from szio.assets import AssetGame
from szio.gta5 import (
    PHYS_ARTICULATED_BODY_MAX_JOINTS,
    AssetBound,
    AssetDrawable,
    AssetDrawableDictionary,
    AssetFormat,
    AssetFragment,
    AssetTarget,
    AssetVersion,
    BoundPrimitiveType,
    BoundType,
    CollisionFlags,
    FragmentTemplateAsset,
    LodLevel,
    PhysChild,
    PhysJoint,
    PhysJoint1Dof,
    PhysJoint3Dof,
    PhysJointType,
    PhysLod,
    RenderBucket,
    save_asset,
    try_load_asset,
)
from szio.gta5.native import IS_BACKEND_AVAILABLE
from szio.types import Matrix, Vector

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
# Fragment tests
# ---------------------------------------------------------------------------

class FragmentTests:
    """Shared fragment test methods. Subclasses provide the `fragment` fixture."""

    def test_is_asset_fragment(self, fragment: AssetFragment):
        assert isinstance(fragment, AssetFragment)

    def test_asset_game(self, fragment: AssetFragment):
        assert fragment.ASSET_GAME == AssetGame.GTA5

    def test_name(self, fragment: AssetFragment):
        assert fragment.name == "test_fragment"

    def test_gravity_factor(self, fragment: AssetFragment):
        assert fragment.gravity_factor == pytest.approx(1.0)

    def test_buoyancy_factor(self, fragment: AssetFragment):
        assert fragment.buoyancy_factor == pytest.approx(1.5)

    def test_template_asset(self, fragment: AssetFragment):
        assert fragment.template_asset == FragmentTemplateAsset.NONE

    def test_has_drawable(self, fragment: AssetFragment):
        assert fragment.drawable is not None

    def test_drawable_has_shader_group(self, fragment: AssetFragment):
        assert fragment.drawable.shader_group is not None
        assert len(fragment.drawable.shader_group.shaders) == 1

    def test_drawable_has_models(self, fragment: AssetFragment):
        assert LodLevel.HIGH in fragment.drawable.models
        models = fragment.drawable.models[LodLevel.HIGH]
        assert len(models) == 1
        assert len(models[0].geometries) == 1

    def test_drawable_geometry(self, fragment: AssetFragment):
        geom = fragment.drawable.models[LodLevel.HIGH][0].geometries[0]
        assert len(geom.vertex_buffer) == 8
        assert len(geom.index_buffer) == 12

    def test_has_physics(self, fragment: AssetFragment):
        assert fragment.physics is not None

    def test_physics_archetype(self, fragment: AssetFragment):
        arch = fragment.physics.lod1.archetype
        assert arch is not None
        assert arch.name == "test_fragment"
        assert arch.mass == pytest.approx(100.0)
        assert arch.bounds is not None
        assert arch.bounds.bound_type == BoundType.COMPOSITE

    def test_physics_groups(self, fragment: AssetFragment):
        groups = fragment.physics.lod1.groups
        assert len(groups) == 1
        assert groups[0].name == "test_group_root"
        assert groups[0].parent_group_index == -1
        assert groups[0].strength == pytest.approx(-1.0)

    def test_physics_children(self, fragment: AssetFragment):
        children = fragment.physics.lod1.children
        assert len(children) == 1
        assert children[0].group_index == 0
        assert children[0].pristine_mass == pytest.approx(100.0)


class TestFragmentSimpleCWXML(FragmentTests):
    @pytest.fixture()
    def fragment(self) -> AssetFragment:
        asset = try_load_asset(DATA_DIR / "test_fragment_simple.yft.xml")
        assert asset is not None
        return asset

    def test_no_extra_drawables(self, fragment: AssetFragment):
        assert fragment.extra_drawables == []

    def test_no_damaged_archetype(self, fragment: AssetFragment):
        assert fragment.physics.lod1.damaged_archetype is None

    def test_no_cloths(self, fragment: AssetFragment):
        assert fragment.cloths == []

    def test_no_glass_windows(self, fragment: AssetFragment):
        assert fragment.glass_windows == []

    def test_no_vehicle_windows(self, fragment: AssetFragment):
        assert fragment.vehicle_windows == []


class TestFragmentDamagedCWXML(FragmentTests):
    @pytest.fixture()
    def fragment(self) -> AssetFragment:
        asset = try_load_asset(DATA_DIR / "test_fragment_damaged.yft.xml")
        assert asset is not None
        return asset

    def test_has_extra_drawables(self, fragment: AssetFragment):
        assert len(fragment.extra_drawables) == 1

    def test_extra_drawable_has_models(self, fragment: AssetFragment):
        drw = fragment.extra_drawables[0]
        assert LodLevel.HIGH in drw.models
        assert len(drw.models[LodLevel.HIGH]) == 1

    def test_has_damaged_archetype(self, fragment: AssetFragment):
        damaged = fragment.physics.lod1.damaged_archetype
        assert damaged is not None
        assert damaged.bounds is not None
        assert damaged.bounds.bound_type == BoundType.COMPOSITE
        assert damaged.mass == pytest.approx(80.0)


class FragmentArticulatedTests:
    """Shared articulated fragment test methods. Subclasses provide the `fragment` fixture."""

    def test_has_articulated_body(self, fragment: AssetFragment):
        lod = fragment.physics.lod1
        assert lod.has_articulated_body
        assert len(lod.children) == 3

    def test_root_link_has_no_joint(self, fragment: AssetFragment):
        assert fragment.physics.lod1.children[0].joint is None

    def test_link_inertia_and_mass(self, fragment: AssetFragment):
        # a link is the physics child it describes, so the articulated body adds no mass/inertia
        children = fragment.physics.lod1.children
        masses = [60.0, 30.0, 10.0]
        inertias = [(0.5, 0.4, 0.3), (0.05, 0.04, 0.03), (0.005, 0.004, 0.003)]
        for child, mass, inertia in zip(children, masses, inertias, strict=True):
            assert child.pristine_mass == pytest.approx(mass)
            assert tuple(child.inertia)[:3] == pytest.approx(inertia)

    def test_joint_3dof(self, fragment: AssetFragment):
        joint = fragment.physics.lod1.children[1].joint
        assert isinstance(joint, PhysJoint3Dof)
        assert joint.joint_type == PhysJointType.DOF3
        assert joint.parent_link_index == 0
        assert joint.stiffness == pytest.approx(0.825)
        assert joint.hard_first_lean_angle_max == pytest.approx(0.319066)
        assert joint.hard_second_lean_angle_max == pytest.approx(0.319066)
        assert joint.hard_twist_angle_max == pytest.approx(0.144533)

    def test_joint_1dof(self, fragment: AssetFragment):
        joint = fragment.physics.lod1.children[2].joint
        assert isinstance(joint, PhysJoint1Dof)
        assert joint.joint_type == PhysJointType.DOF1
        assert joint.parent_link_index == 1
        assert joint.stiffness == pytest.approx(0.825)
        assert joint.hard_angle_min == pytest.approx(-1.017198)
        assert joint.hard_angle_max == pytest.approx(0.493599)
        assert joint.max_muscle_torque == pytest.approx(1e8)
        assert joint.min_muscle_torque == pytest.approx(-1e8)

    def test_joint_orients(self, fragment: AssetFragment):
        joint = fragment.physics.lod1.children[1].joint
        assert tuple(joint.orient_parent[3]) == pytest.approx((0.0, 0.0, 2.0, 1.0))
        assert tuple(joint.orient_child[3]) == pytest.approx((0.0, 0.0, -0.5, 1.0))
        for row in range(3):
            assert joint.orient_parent[row][3] == pytest.approx(0.0)

    def test_self_collisions(self, fragment: AssetFragment):
        assert fragment.physics.lod1.self_collisions == [(0, 2), (1, 2)]


class TestFragmentSelfCollisionsCWXML:
    def test_unpaired_self_collision_arrays_are_ignored(self, tmp_path: Path):
        """Some vanilla assets only have one of the two self-collision arrays (e.g. a_c_cormorant)."""
        source = (DATA_DIR / "test_fragment_articulated.yft.xml").read_text()
        unpaired = source.replace("<UnknownData1>0 1</UnknownData1>\n", "")
        assert "UnknownData1" not in unpaired
        path = tmp_path / "unpaired.yft.xml"
        path.write_text(unpaired)

        asset = try_load_asset(path)
        assert asset is not None
        assert asset.physics.lod1.self_collisions == []


class TestFragmentArticulatedCWXML(FragmentArticulatedTests):
    @pytest.fixture()
    def fragment(self) -> AssetFragment:
        asset = try_load_asset(DATA_DIR / "test_fragment_articulated.yft.xml")
        assert asset is not None
        return asset


class FragmentClothTests:
    """Shared cloth fragment test methods. Subclasses provide the `fragment` fixture."""

    def test_is_asset_fragment(self, fragment: AssetFragment):
        assert isinstance(fragment, AssetFragment)

    def test_no_main_drawable(self, fragment: AssetFragment):
        assert fragment.drawable is None

    def test_base_drawable_from_cloth(self, fragment: AssetFragment):
        assert fragment.base_drawable is not None

    def test_has_cloths(self, fragment: AssetFragment):
        assert len(fragment.cloths) == 1

    def test_cloth_has_drawable(self, fragment: AssetFragment):
        cloth = fragment.cloths[0]
        assert cloth.drawable is not None
        assert cloth.drawable.shader_group is not None
        assert len(cloth.drawable.shader_group.shaders) == 1

    def test_cloth_controller(self, fragment: AssetFragment):
        ctrl = fragment.cloths[0].controller
        assert ctrl.name == "test_cloth"
        assert ctrl.bridge.vertex_count_high == 4

    def test_cloth_verlet(self, fragment: AssetFragment):
        vc = fragment.cloths[0].controller.cloth_high
        assert len(vc.vertex_positions) == 4
        assert len(vc.edges) == 2

    def test_cloth_tuning(self, fragment: AssetFragment):
        tuning = fragment.cloths[0].tuning
        assert tuning is not None
        assert tuning.weight == pytest.approx(1.0)


class TestFragmentClothCWXML(FragmentClothTests):
    @pytest.fixture()
    def fragment(self) -> AssetFragment:
        asset = try_load_asset(DATA_DIR / "test_fragment_cloth.yft.xml")
        assert asset is not None
        return asset


@requires_native
class TestFragmentSimpleGen8(FragmentTests):
    @pytest.fixture()
    def fragment(self) -> AssetFragment:
        asset = try_load_asset(DATA_DIR / "gen8" / "test_fragment_simple.yft")
        assert asset is not None
        return asset


@requires_native
class TestFragmentSimpleGen9(FragmentTests):
    @pytest.fixture()
    def fragment(self) -> AssetFragment:
        asset = try_load_asset(DATA_DIR / "gen9" / "test_fragment_simple.yft")
        assert asset is not None
        return asset


@requires_native
class TestFragmentDamagedGen8(FragmentTests):
    @pytest.fixture()
    def fragment(self) -> AssetFragment:
        asset = try_load_asset(DATA_DIR / "gen8" / "test_fragment_damaged.yft")
        assert asset is not None
        return asset

    def test_has_extra_drawables(self, fragment: AssetFragment):
        assert len(fragment.extra_drawables) == 1

    def test_extra_drawable_has_models(self, fragment: AssetFragment):
        drw = fragment.extra_drawables[0]
        assert LodLevel.HIGH in drw.models
        assert len(drw.models[LodLevel.HIGH]) == 1

    def test_has_damaged_archetype(self, fragment: AssetFragment):
        damaged = fragment.physics.lod1.damaged_archetype
        assert damaged is not None
        assert damaged.bounds is not None
        assert damaged.bounds.bound_type == BoundType.COMPOSITE
        assert damaged.mass == pytest.approx(80.0)


@requires_native
class TestFragmentDamagedGen9(FragmentTests):
    @pytest.fixture()
    def fragment(self) -> AssetFragment:
        asset = try_load_asset(DATA_DIR / "gen9" / "test_fragment_damaged.yft")
        assert asset is not None
        return asset

    def test_has_extra_drawables(self, fragment: AssetFragment):
        assert len(fragment.extra_drawables) == 1

    def test_extra_drawable_has_models(self, fragment: AssetFragment):
        drw = fragment.extra_drawables[0]
        assert LodLevel.HIGH in drw.models
        assert len(drw.models[LodLevel.HIGH]) == 1

    def test_has_damaged_archetype(self, fragment: AssetFragment):
        damaged = fragment.physics.lod1.damaged_archetype
        assert damaged is not None
        assert damaged.bounds is not None
        assert damaged.bounds.bound_type == BoundType.COMPOSITE
        assert damaged.mass == pytest.approx(80.0)


@requires_native
class TestFragmentArticulatedGen8(FragmentArticulatedTests):
    @pytest.fixture()
    def fragment(self) -> AssetFragment:
        asset = try_load_asset(DATA_DIR / "gen8" / "test_fragment_articulated.yft")
        assert asset is not None
        return asset


@requires_native
class TestFragmentArticulatedGen9(FragmentArticulatedTests):
    @pytest.fixture()
    def fragment(self) -> AssetFragment:
        asset = try_load_asset(DATA_DIR / "gen9" / "test_fragment_articulated.yft")
        assert asset is not None
        return asset


@requires_native
class TestFragmentClothGen8(FragmentClothTests):
    @pytest.fixture()
    def fragment(self) -> AssetFragment:
        asset = try_load_asset(DATA_DIR / "gen8" / "test_fragment_cloth.yft")
        assert asset is not None
        return asset


@requires_native
class TestFragmentClothGen9(FragmentClothTests):
    @pytest.fixture()
    def fragment(self) -> AssetFragment:
        asset = try_load_asset(DATA_DIR / "gen9" / "test_fragment_cloth.yft")
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
        "test_fragment_simple.yft.xml",
        "test_fragment_damaged.yft.xml",
        "test_fragment_cloth.yft.xml",
        "test_fragment_articulated.yft.xml",
    ])
    def test_save_and_reload(self, filename: str, tmp_path: Path):
        asset = try_load_asset(DATA_DIR / filename)
        assert asset is not None

        name = filename.split(".")[0]
        ext = "." + filename.split(".")[1]
        save_asset(asset, self.TARGETS, tmp_path, name)

        reloaded = try_load_asset(tmp_path / f"{name}{ext}.xml")
        assert reloaded is not None
        assert reloaded.ASSET_GAME == AssetGame.GTA5

    def test_drawable_roundtrip_preserves_data(self, tmp_path: Path):
        original = try_load_asset(DATA_DIR / "test_drawable.ydr.xml")
        save_asset(original, self.TARGETS, tmp_path, "rt")
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
        save_asset(original, self.TARGETS, tmp_path, "rt")
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
        save_asset(original, self.TARGETS, tmp_path, "rt")
        reloaded = try_load_asset(tmp_path / "rt.ydd.xml")

        assert set(reloaded.drawables.keys()) == set(original.drawables.keys())
        for name in original.drawables:
            assert reloaded.drawables[name].shader_group.shaders[0].name == \
                original.drawables[name].shader_group.shaders[0].name

    def test_fragment_roundtrip_preserves_data(self, tmp_path: Path):
        original = try_load_asset(DATA_DIR / "test_fragment_simple.yft.xml")
        save_asset(original, self.TARGETS, tmp_path, "rt")
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
        save_asset(original, self.TARGETS, tmp_path, "rt")
        reloaded = try_load_asset(tmp_path / "rt.yft.xml")

        assert reloaded.name == original.name
        assert len(reloaded.extra_drawables) == len(original.extra_drawables)
        assert reloaded.physics.lod1.damaged_archetype is not None
        assert reloaded.physics.lod1.damaged_archetype.mass == pytest.approx(
            original.physics.lod1.damaged_archetype.mass
        )

    def test_fragment_articulated_roundtrip_preserves_data(self, tmp_path: Path):
        original = try_load_asset(DATA_DIR / "test_fragment_articulated.yft.xml")
        save_asset(original, self.TARGETS, tmp_path, "rt")
        reloaded = try_load_asset(tmp_path / "rt.yft.xml")

        orig_lod = original.physics.lod1
        rt_lod = reloaded.physics.lod1
        assert rt_lod.has_articulated_body
        assert len(rt_lod.children) == len(orig_lod.children)
        for rt_child, orig_child in zip(rt_lod.children, orig_lod.children, strict=True):
            assert rt_child.pristine_mass == pytest.approx(orig_child.pristine_mass)
            assert tuple(rt_child.inertia)[:3] == pytest.approx(tuple(orig_child.inertia)[:3])
            assert (rt_child.joint is None) == (orig_child.joint is None)

        orig_joint = orig_lod.children[1].joint
        rt_joint = rt_lod.children[1].joint
        assert isinstance(rt_joint, PhysJoint3Dof)
        assert rt_joint.stiffness == pytest.approx(orig_joint.stiffness)
        assert rt_joint.parent_link_index == orig_joint.parent_link_index
        assert rt_joint.hard_twist_angle_max == pytest.approx(orig_joint.hard_twist_angle_max)
        for row in range(4):
            assert tuple(rt_joint.orient_parent[row]) == pytest.approx(tuple(orig_joint.orient_parent[row]))
            assert tuple(rt_joint.orient_child[row]) == pytest.approx(tuple(orig_joint.orient_child[row]))
        assert isinstance(rt_lod.children[2].joint, PhysJoint1Dof)
        assert reloaded.physics.lod1.self_collisions == original.physics.lod1.self_collisions

    def test_fragment_articulated_xml_output_format(self, tmp_path: Path):
        """The emitted XML must follow CodeWalker's articulated body conventions."""
        original = try_load_asset(DATA_DIR / "test_fragment_articulated.yft.xml")
        save_asset(original, self.TARGETS, tmp_path, "rt")
        text = (tmp_path / "rt.yft.xml").read_text()

        # ItemIndices/ItemFlags are derived from the joints and zero-padded to 22 entries
        indices = re.search(r"<ItemIndices>([^<]*)</ItemIndices>", text)
        assert indices is not None
        assert indices.group(1).split() == ["0", "1"] + ["0"] * 20
        flags = re.search(r"<ItemFlags>([^<]*)</ItemFlags>", text)
        assert flags is not None
        assert flags.group(1).split() == ["1", "0"] + ["0"] * 20

    def test_fragment_articulated_link_mass_follows_child(self, tmp_path: Path):
        """UnknownVectors is derived from the children, not stored alongside them."""
        original = try_load_asset(DATA_DIR / "test_fragment_articulated.yft.xml")
        child = original.physics.lod1.children[1]
        child.pristine_mass = 12.5
        child.inertia = Vector((1.25, 2.5, 3.75, 0.0))
        save_asset(original, self.TARGETS, tmp_path, "rt")

        text = (tmp_path / "rt.yft.xml").read_text()
        vectors = re.search(r"<UnknownVectors>([^<]*)</UnknownVectors>", text)
        assert vectors is not None
        rows = [row.strip() for row in vectors.group(1).strip().splitlines()]
        assert [float(v) for v in rows[1].split(",")] == pytest.approx([1.25, 2.5, 3.75, 12.5])

        reloaded = try_load_asset(tmp_path / "rt.yft.xml")
        rt_child = reloaded.physics.lod1.children[1]
        assert rt_child.pristine_mass == pytest.approx(12.5)
        assert tuple(rt_child.inertia)[:3] == pytest.approx((1.25, 2.5, 3.75))

    def test_fragment_cloth_roundtrip_no_physics(self, tmp_path: Path):
        original = try_load_asset(DATA_DIR / "test_fragment_cloth.yft.xml")
        assert original.physics is None
        save_asset(original, self.TARGETS, tmp_path, "rt")
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
        save_asset(original, self.GEN8_TARGETS, tmp_path, "rt")
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
        save_asset(original, self.GEN9_TARGETS, tmp_path, "rt")
        reloaded = try_load_asset(tmp_path / "rt.ydr")
        assert reloaded is not None

        assert reloaded.name == original.name
        rt_geom = reloaded.models[LodLevel.HIGH][0].geometries[0]
        assert len(rt_geom.vertex_buffer) == len(orig_geom.vertex_buffer)
        assert len(rt_geom.index_buffer) == len(orig_geom.index_buffer)

    def test_bounds_native_roundtrip(self, tmp_path: Path):
        original = try_load_asset(DATA_DIR / "test_bounds.ybn")
        assert original is not None
        save_asset(original, self.GEN8_TARGETS, tmp_path, "rt")
        reloaded = try_load_asset(tmp_path / "rt.ybn")
        assert reloaded is not None

        assert reloaded.bound_type == original.bound_type
        assert len(reloaded.children) == len(original.children)
        assert reloaded.children[0].bound_type == original.children[0].bound_type

    def test_drawable_dictionary_gen8_roundtrip(self, tmp_path: Path):
        original = try_load_asset(DATA_DIR / "gen8" / "test_drawable_dictionary.ydd")
        assert original is not None
        save_asset(original, self.GEN8_TARGETS, tmp_path, "rt")
        reloaded = try_load_asset(tmp_path / "rt.ydd")
        assert reloaded is not None

        assert len(reloaded.drawables) == len(original.drawables)

    def test_drawable_dictionary_gen9_roundtrip(self, tmp_path: Path):
        original = try_load_asset(DATA_DIR / "gen9" / "test_drawable_dictionary.ydd")
        assert original is not None
        save_asset(original, self.GEN9_TARGETS, tmp_path, "rt")
        reloaded = try_load_asset(tmp_path / "rt.ydd")
        assert reloaded is not None

        assert len(reloaded.drawables) == len(original.drawables)

    def test_fragment_cwxml_to_gen8_roundtrip(self, tmp_path: Path):
        """Load fragment from CWXML, save as native gen8, reload and verify."""
        original = try_load_asset(DATA_DIR / "test_fragment_simple.yft.xml")
        assert original is not None
        save_asset(original, self.GEN8_TARGETS, tmp_path, "rt")
        reloaded = try_load_asset(tmp_path / "rt.yft")
        assert reloaded is not None

        assert reloaded.name == original.name
        assert reloaded.physics is not None
        assert reloaded.physics.lod1.archetype is not None
        assert len(reloaded.physics.lod1.children) == len(original.physics.lod1.children)

    def test_fragment_cwxml_to_gen9_roundtrip(self, tmp_path: Path):
        """Load fragment from CWXML, save as native gen9, reload and verify."""
        original = try_load_asset(DATA_DIR / "test_fragment_simple.yft.xml")
        assert original is not None
        save_asset(original, self.GEN9_TARGETS, tmp_path, "rt")
        reloaded = try_load_asset(tmp_path / "rt.yft")
        assert reloaded is not None

        assert reloaded.name == original.name
        assert reloaded.physics is not None
        assert reloaded.physics.lod1.archetype is not None
        assert len(reloaded.physics.lod1.children) == len(original.physics.lod1.children)

    def test_fragment_simple_gen8_roundtrip(self, tmp_path: Path):
        original = try_load_asset(DATA_DIR / "gen8" / "test_fragment_simple.yft")
        assert original is not None
        save_asset(original, self.GEN8_TARGETS, tmp_path, "rt")
        reloaded = try_load_asset(tmp_path / "rt.yft")
        assert reloaded is not None

        assert reloaded.name == original.name
        assert reloaded.physics is not None
        assert len(reloaded.physics.lod1.children) == len(original.physics.lod1.children)

    def test_fragment_simple_gen9_roundtrip(self, tmp_path: Path):
        original = try_load_asset(DATA_DIR / "gen9" / "test_fragment_simple.yft")
        assert original is not None
        save_asset(original, self.GEN9_TARGETS, tmp_path, "rt")
        reloaded = try_load_asset(tmp_path / "rt.yft")
        assert reloaded is not None

        assert reloaded.name == original.name
        assert reloaded.physics is not None
        assert len(reloaded.physics.lod1.children) == len(original.physics.lod1.children)

    def test_fragment_articulated_gen8_roundtrip(self, tmp_path: Path):
        original = try_load_asset(DATA_DIR / "gen8" / "test_fragment_articulated.yft")
        assert original is not None
        save_asset(original, self.GEN8_TARGETS, tmp_path, "rt")
        reloaded = try_load_asset(tmp_path / "rt.yft")
        assert reloaded is not None

        orig_lod = original.physics.lod1
        lod = reloaded.physics.lod1
        assert lod.has_articulated_body
        assert len(lod.children) == len(orig_lod.children)
        assert lod.children[0].joint is None
        assert isinstance(lod.children[1].joint, PhysJoint3Dof)
        assert isinstance(lod.children[2].joint, PhysJoint1Dof)
        assert reloaded.physics.lod1.self_collisions == original.physics.lod1.self_collisions

    def test_fragment_articulated_gen9_roundtrip(self, tmp_path: Path):
        original = try_load_asset(DATA_DIR / "gen9" / "test_fragment_articulated.yft")
        assert original is not None
        save_asset(original, self.GEN9_TARGETS, tmp_path, "rt")
        reloaded = try_load_asset(tmp_path / "rt.yft")
        assert reloaded is not None

        orig_lod = original.physics.lod1
        lod = reloaded.physics.lod1
        assert lod.has_articulated_body
        assert len(lod.children) == len(orig_lod.children)
        assert lod.children[0].joint is None
        assert isinstance(lod.children[1].joint, PhysJoint3Dof)
        assert isinstance(lod.children[2].joint, PhysJoint1Dof)
        assert reloaded.physics.lod1.self_collisions == original.physics.lod1.self_collisions

    def test_fragment_articulated_cwxml_to_gen8_roundtrip(self, tmp_path: Path):
        """Load articulated fragment from CWXML, save as native gen8, reload and verify."""
        original = try_load_asset(DATA_DIR / "test_fragment_articulated.yft.xml")
        assert original is not None
        save_asset(original, self.GEN8_TARGETS, tmp_path, "rt")
        reloaded = try_load_asset(tmp_path / "rt.yft")
        assert reloaded is not None

        lod = reloaded.physics.lod1
        assert lod.has_articulated_body
        assert len(lod.children) == 3
        assert lod.children[0].joint is None
        joint = lod.children[1].joint
        assert isinstance(joint, PhysJoint3Dof)
        assert joint.hard_twist_angle_max == pytest.approx(0.144533)
        assert reloaded.physics.lod1.self_collisions == [(0, 2), (1, 2)]

    def test_fragment_articulated_cwxml_to_gen9_roundtrip(self, tmp_path: Path):
        """Load articulated fragment from CWXML, save as native gen9, reload and verify."""
        original = try_load_asset(DATA_DIR / "test_fragment_articulated.yft.xml")
        assert original is not None
        save_asset(original, self.GEN9_TARGETS, tmp_path, "rt")
        reloaded = try_load_asset(tmp_path / "rt.yft")
        assert reloaded is not None

        lod = reloaded.physics.lod1
        assert lod.has_articulated_body
        assert len(lod.children) == 3
        assert lod.children[0].joint is None
        assert isinstance(lod.children[1].joint, PhysJoint3Dof)
        assert isinstance(lod.children[2].joint, PhysJoint1Dof)
        assert reloaded.physics.lod1.self_collisions == [(0, 2), (1, 2)]

    def test_fragment_damaged_gen8_roundtrip(self, tmp_path: Path):
        original = try_load_asset(DATA_DIR / "gen8" / "test_fragment_damaged.yft")
        assert original is not None
        save_asset(original, self.GEN8_TARGETS, tmp_path, "rt")
        reloaded = try_load_asset(tmp_path / "rt.yft")
        assert reloaded is not None

        assert reloaded.name == original.name
        assert len(reloaded.extra_drawables) == len(original.extra_drawables)
        assert reloaded.physics.lod1.damaged_archetype is not None

    def test_fragment_damaged_gen9_roundtrip(self, tmp_path: Path):
        original = try_load_asset(DATA_DIR / "gen9" / "test_fragment_damaged.yft")
        assert original is not None
        save_asset(original, self.GEN9_TARGETS, tmp_path, "rt")
        reloaded = try_load_asset(tmp_path / "rt.yft")
        assert reloaded is not None

        assert reloaded.name == original.name
        assert len(reloaded.extra_drawables) == len(original.extra_drawables)
        assert reloaded.physics.lod1.damaged_archetype is not None


@requires_native
class TestFragmentArticulatedNativeToCwxml:
    def test_native_fragment_saves_to_cwxml(self, tmp_path: Path):
        original = try_load_asset(DATA_DIR / "gen8" / "test_fragment_articulated.yft")
        assert original is not None
        save_asset(original, [AssetTarget(AssetFormat.CWXML, AssetVersion.GEN8)], tmp_path, "rt")

        root = ET.parse(tmp_path / "rt.yft.xml").getroot()
        body = root.find(".//ArticulatedBody")
        assert body is not None
        joints = body.find("Joints").findall("Item")
        assert [j.get("type") for j in joints] == ["DOF3", "DOF1"]
        children = root.findall("./Physics/LOD1/Children/Item")
        assert len(children) == len(original.physics.lod1.children)
        for child, orig in zip(children, original.physics.lod1.children, strict=True):
            for tag in ("InertiaTensor", "UnkVec"):
                assert set(child.find(tag).attrib) == {"x", "y", "z", "w"}
                assert float(child.find(tag).get("w")) == 0.0
            assert float(child.find("InertiaTensor").get("x")) == pytest.approx(orig.inertia[0])
