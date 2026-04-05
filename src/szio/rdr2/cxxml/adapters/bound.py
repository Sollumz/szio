from typing import Sequence

from ....types import Matrix, Vector
from .. import bound as cx

# TODO: TEMPORARY
from ....gta5.bounds import (
    BoundType,
    AssetBound,
    CollisionMaterial,
    CollisionFlags,
    BoundVertex,
    BoundPrimitive,
    BoundPrimitiveType,
)


def _primitive_type_from_cx(p: cx.Polygon) -> BoundPrimitiveType:
    match p.kind:
        case cx.PolyBox.kind:
            return BoundPrimitiveType.BOX
        case cx.PolySphere.kind:
            return BoundPrimitiveType.SPHERE
        case cx.PolyCapsule.kind:
            return BoundPrimitiveType.CAPSULE
        case cx.PolyCylinder.kind:
            return BoundPrimitiveType.CYLINDER
        case cx.PolyTriangle.kind:
            return BoundPrimitiveType.TRIANGLE
        case _:
            raise ValueError(f"Unknown CXXML primitive type '{p.kind}'")


def _bound_type_from_cx(b: cx.Bound) -> BoundType:
    match b.type:
        case "Composite":
            return BoundType.COMPOSITE
        case "Box":
            return BoundType.BOX
        case "Sphere":
            return BoundType.SPHERE
        case "Capsule":
            return BoundType.CAPSULE
        case "Cylinder":
            return BoundType.CYLINDER
        case "Disc":
            return BoundType.DISC
        case "Geometry":
            return BoundType.GEOMETRY
        case "GeometryBVH":
            return BoundType.BVH
        case _:
            raise ValueError(f"Unknown CXXML bound type '{b.type}'")


_PRIMITIVE_TYPES = {"Box", "Sphere", "Cylinder", "Capsule", "Disc"}


def load_bound_from_cx(b: cx.Bound | None) -> None:
    if b is None:
        return None

    bound_type = _bound_type_from_cx(b)
    is_primitive = b.type in _PRIMITIVE_TYPES

    result = AssetBound.create(bound_type)

    # TODO: Material
    result.material = CollisionMaterial.from_packed(0)

    result.centroid = Vector(b.box_center)
    result.radius_around_centroid = b.sphere_radius
    result.cg = Vector(b.sphere_center)
    result.margin = b.margin
    result.volume = b.mass
    result.inertia = Vector(b.inertia)

    # Extent
    bb_min, bb_max = b.box_min, b.box_max
    if is_primitive:
        center = Vector(b.box_center)
        bb_min = bb_min - center
        bb_max = bb_max - center
    result.bb_min = Vector(bb_min)
    result.bb_max = Vector(bb_max)

    if bound_type == BoundType.COMPOSITE:
        result.children = []
        for child_b in b.children:
            if child_b is None:
                result.children.append(None)
            else:
                child = load_bound_from_cx(child_b)
                child.composite_transform = Matrix(child_b.composite_transform)
                child.composite_collision_type_flags = CollisionFlags(
                    0
                )  # collision_flags_from_cw(child_b.composite_flags1)
                child.composite_collision_include_flags = CollisionFlags(
                    0
                )  # collision_flags_from_cw(child_b.composite_flags2)
                result.children.append(child)
    elif bound_type == BoundType.SPHERE:
        result.sphere_radius = b.sphere_radius
    elif bound_type == BoundType.CAPSULE:
        extent = b.box_max - b.box_min
        radius = extent.x * 0.5
        length = extent.y - (radius * 2.0)
        result.capsule_radius_length = (radius, length)
    elif bound_type == BoundType.CYLINDER:
        extent = b.box_max - b.box_min
        radius = extent.x * 0.5
        length = extent.y
        result.cylinder_radius_length = (radius, length)
    elif bound_type == BoundType.DISC:
        result.disc_radius = b.sphere_radius
    elif bound_type == BoundType.PLANE:
        result.plane_normal = Vector(b.normal)
    elif bound_type in (BoundType.GEOMETRY, BoundType.BVH):
        # Inline geometry_primitives getter
        materials = [
            CollisionMaterial.from_packed(0)
            # CollisionMaterial(
            #     material_index=m.type,
            #     procedural_id=m.procedural_id,
            #     room_id=m.room_id,
            #     ped_density=m.ped_density,
            #     material_flags=collision_material_flags_from_cx(m.flags),
            #     material_color_index=m.material_color_index,
            # )
            for m in b.materials
        ]
        polys = b.polygons
        result.geometry_primitives = [
            BoundPrimitive(
                primitive_type=_primitive_type_from_cx(p),
                material=materials[p.material_index],
                material_color=(0, 0, 0, 0),
                vertices=p.vertices,
                radius=p.radius if isinstance(p, (cx.PolySphere, cx.PolyCapsule, cx.PolyCylinder)) else None,
            )
            for p in polys
        ]

        vertices = b.vertices
        # colors = b.vertex_colors
        # has_colors = bool(colors)
        center = (bb_min + bb_max) * 0.5
        result.geometry_vertices = [BoundVertex(vertices[i] + center, None) for i in range(len(vertices))]

        result.geometry_center = center

    return result


def save_bound_to_cx(asset: None) -> cx.Bound:
    return cx.BoundBox()
