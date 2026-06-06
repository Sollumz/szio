import logging
from pathlib import Path

import pytest
from numpy.testing import assert_array_equal

import szio.gta5.native
from szio.gta5 import (
    AssetBound,
    AssetBoundBvh,
    AssetBoundComposite,
    AssetBoundGeometry,
    AssetBoundPlane,
    AssetFormat,
    AssetTarget,
    BoundPrimitive,
    BoundType,
    BoundVertex,
    CollisionMaterial,
    save_asset,
    try_load_asset,
)
from szio.types import Vector

asset_targets = [
    pytest.param(
        target,
        marks=pytest.mark.skipif(
            target.format == AssetFormat.NATIVE and not szio.gta5.native.IS_BACKEND_AVAILABLE,
            reason="native backend not available",
        ),
        id=str(target),
    )
    for target in AssetTarget.all()
]


@pytest.mark.parametrize("target", asset_targets)
def test_bounds_gta5(target: AssetTarget, tmp_path: Path, caplog):
    with caplog.at_level(logging.WARNING):
        default_material = CollisionMaterial.from_packed(0)

        comp = AssetBoundComposite()
        for bound_type in (BoundType.SPHERE, BoundType.CAPSULE, BoundType.BOX, BoundType.DISC, BoundType.CYLINDER):
            b = AssetBound.create(bound_type)
            b.extent = Vector((-1.0, -2.0, -1.0)), Vector((1.0, 2.0, 1.0))
            b.material = default_material
            comp.children.append(b)

        b = AssetBoundGeometry()
        b.geometry_vertices = [
            BoundVertex(co=Vector((-0.5, 0.0, -0.5)), color=None),
            BoundVertex(co=Vector((0.5, 0.0, -0.5)), color=None),
            BoundVertex(co=Vector((0.0, 0.0, 0.5)), color=None),
        ]
        b.geometry_primitives = [
            BoundPrimitive.new_triangle(0, 1, 2, default_material),
        ]
        b.extent = Vector((-0.5, 0.0, -0.5)), Vector((0.5, 0.0, 0.5))
        comp.children.append(b)

        b = AssetBoundBvh()
        b.geometry_vertices = [
            BoundVertex(co=Vector((-0.5, 0.0, -0.5)), color=None),
            BoundVertex(co=Vector((0.5, 0.0, -0.5)), color=None),
            BoundVertex(co=Vector((0.0, 0.0, 0.5)), color=None),
            BoundVertex(co=Vector((-0.5, 0.0, -0.75)), color=None),
            BoundVertex(co=Vector((0.5, 0.0, -0.75)), color=None),
            BoundVertex(co=Vector((-0.1, -0.1, -0.1)), color=None),
            BoundVertex(co=Vector((0.1, -0.1, 0.1)), color=None),
            BoundVertex(co=Vector((-0.1, 0.1, 0.1)), color=None),
            BoundVertex(co=Vector((0.1, 0.1, -0.1)), color=None),
        ]
        b.geometry_primitives = [
            BoundPrimitive.new_triangle(0, 1, 2, default_material),
            BoundPrimitive.new_sphere(2, 0.25, default_material),
            BoundPrimitive.new_capsule(0, 1, 0.25, default_material),
            BoundPrimitive.new_cylinder(3, 4, 0.25, default_material),
            BoundPrimitive.new_box(5, 6, 7, 8, default_material),
        ]
        b.extent = Vector((-0.75, -0.25, -1.0)), Vector((0.75, 0.25, 0.75))
        comp.children.append(b)

        b = AssetBoundPlane(plane_normal=Vector((0.0, 0.0, 1.0)))
        comp.children.append(b)

        save_asset(comp, [target], tmp_path, "test")

        ext = ".ybn.xml" if target.format == AssetFormat.CWXML else ".ybn"
        loaded_comp = try_load_asset(tmp_path / f"test{ext}")
        bounds = loaded_comp.children
        assert len(bounds) == 8

        assert tuple(b.bound_type for b in bounds) == (
            BoundType.SPHERE,
            BoundType.CAPSULE,
            BoundType.BOX,
            BoundType.DISC,
            BoundType.CYLINDER,
            BoundType.GEOMETRY,
            BoundType.BVH,
            BoundType.PLANE,
        )

        assert bounds[0].sphere_radius == 1.0
        assert bounds[1].capsule_radius_length == (1.0, 2.0)
        assert_array_equal(bounds[2].extent, ((-1.0, -2.0, -1.0), (1.0, 2.0, 1.0)))
        assert bounds[3].disc_radius == 2.0
        assert bounds[4].cylinder_radius_length == (1.0, 4.0)
        assert len(bounds[5].geometry_vertices) == 3
        assert len(bounds[5].geometry_primitives) == 1
        assert len(bounds[6].geometry_vertices) == 9
        assert len(bounds[6].geometry_primitives) == 5
        assert_array_equal(tuple(bounds[7].plane_normal), (0.0, 0.0, 1.0))

    errors_and_warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert not errors_and_warnings, "Unexpected warnings/errors logged:\n" + "\n".join(
        f"  [{r.levelname}] {r.name}: {r.message}" for r in errors_and_warnings
    )
