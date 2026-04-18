from typing import Sequence

from ....types import Matrix, Vector
from ...bounds import (
    AssetBound,
    BoundPrimitive,
    BoundPrimitiveType,
    BoundType,
    BoundVertex,
    CollisionFlags,
    CollisionMaterial,
    CollisionMaterialFlags,
    create_bound,
)
from .. import bound as cx


def _collision_flags_to_cx(flags: CollisionFlags) -> list[str]:
    converted_flags = []
    for flag in flags:
        converted_flags.append(f"CF_{flag.name}")
    return converted_flags if converted_flags else ["NONE"]


def _collision_flags_from_cx(flags: Sequence[str]) -> CollisionFlags:
    converted_flags = CollisionFlags(0)
    for flag in flags:
        if flag.startswith("CF_") and (flag_name := flag[3:]) in CollisionFlags.__members__:
            converted_flags |= CollisionFlags[flag_name]
    return converted_flags


def _collision_material_flags_to_cx(flags: CollisionMaterialFlags) -> list[str]:
    converted_flags = []
    for flag in flags:
        converted_flags.append(f"FLAG_{flag.name}")
    return converted_flags if converted_flags else ["NONE"]


def _collision_material_flags_from_cx(flags: set[str]) -> CollisionMaterialFlags:
    converted_flags = CollisionMaterialFlags(0)
    for flag in flags:
        if flag.startswith("FLAG_") and (flag_name := flag[5:]) in CollisionMaterialFlags.__members__:
            converted_flags |= CollisionMaterialFlags[flag_name]
    return converted_flags


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
        case "TaperedCapsule":
            return BoundType.TAPERED_CAPSULE
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


_BOUND_PRIMITIVE_TYPES = {"Box", "Sphere", "Cylinder", "Capsule", "Disc", "TaperedCapsule"}


def load_bound_from_cx(b: cx.Bound | None) -> AssetBound | None:
    if b is None:
        return None

    bound_type = _bound_type_from_cx(b)
    is_primitive = b.type in _BOUND_PRIMITIVE_TYPES

    result = create_bound(bound_type)

    result.material = CollisionMaterial(
        material_name=b.material_name,
        procedural_id=b.material_procedural_id,
        room_id=b.material_room_id,
        ped_density=b.material_ped_density,
        material_flags=_collision_material_flags_from_cx(b.material_flags),
    )

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
                child.composite_collision_type_flags = _collision_flags_from_cx(child_b.composite_type_flags)
                child.composite_collision_include_flags = _collision_flags_from_cx(child_b.composite_include_flags)
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
    elif bound_type == BoundType.TAPERED_CAPSULE:
        # TODO: load TaperedCapsule
        pass
    elif bound_type == BoundType.DISC:
        result.disc_radius = b.sphere_radius
    elif bound_type == BoundType.PLANE:
        result.plane_normal = Vector(b.normal)
    elif bound_type in (BoundType.GEOMETRY, BoundType.BVH):
        materials = [
            CollisionMaterial(
                material_name=m.name,
                procedural_id=m.procedural_id,
                room_id=m.room_id,
                ped_density=m.ped_density,
                material_flags=_collision_material_flags_from_cx(m.flags),
            )
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


def _create_cx_bound(bound_type: BoundType) -> cx.Bound:
    match bound_type:
        case BoundType.COMPOSITE:
            return cx.BoundComposite()
        case BoundType.BOX:
            return cx.BoundBox()
        case BoundType.SPHERE:
            return cx.BoundSphere()
        case BoundType.CAPSULE:
            return cx.BoundCapsule()
        case BoundType.CYLINDER:
            return cx.BoundCylinder()
        case BoundType.DISC:
            return cx.BoundDisc()
        case BoundType.GEOMETRY:
            return cx.BoundGeometry()
        case BoundType.BVH:
            return cx.BoundGeometryBVH()
        case _:
            raise ValueError(f"Unsupported CXXML bound type '{bound_type.name}'")


def _save_bound_to_cx_inner(asset: AssetBound) -> cx.Bound:
    b = _create_cx_bound(asset.bound_type)
    is_primitive = b.type in _BOUND_PRIMITIVE_TYPES

    b.box_center = Vector(asset.centroid[:3])
    b.sphere_center = Vector(asset.cg[:3])
    b.sphere_radius = asset.radius_around_centroid
    b.margin = asset.margin
    b.mass = asset.volume
    b.inertia = Vector(asset.inertia)

    if asset.material:
        b.material_name = asset.material.material_name
        b.material_procedural_id = asset.material.procedural_id
        b.material_room_id = asset.material.room_id
        b.material_ped_density = asset.material.ped_density
        b.material_flags = _collision_material_flags_to_cx(asset.material.material_flags)

    b.box_min = Vector(asset.bb_min)
    b.box_max = Vector(asset.bb_max)
    if is_primitive:
        b.box_min = b.box_min + b.box_center
        b.box_max = b.box_max + b.box_center

    bt = asset.bound_type
    if bt == BoundType.COMPOSITE:
        composite: cx.BoundComposite = b
        children_cx: list[cx.Bound | None] = []
        for child in asset.children or []:
            if child is None:
                children_cx.append(None)
            else:
                child_cx = _save_bound_to_cx_inner(child)
                child_cx.composite_transform = Matrix(child.composite_transform)
                child_cx.composite_type_flags = _collision_flags_to_cx(child.composite_collision_type_flags)
                child_cx.composite_include_flags = _collision_flags_to_cx(child.composite_collision_include_flags)
                children_cx.append(child_cx)
        composite.children = children_cx
    elif bt == BoundType.SPHERE:
        b.sphere_radius = asset.sphere_radius
    elif bt == BoundType.DISC:
        b.sphere_radius = asset.disc_radius
    elif bt in (BoundType.CAPSULE, BoundType.CYLINDER, BoundType.BOX):
        pass
    elif bt in (BoundType.GEOMETRY, BoundType.BVH):
        geom_center = (b.box_min + b.box_max) * 0.5
        b.vertices = [v.co - geom_center for v in (asset.geometry_vertices or [])]

        materials: list[cx.Material] = []
        materials_index_map: dict[int, int] = {}

        def _get_material_index(material: CollisionMaterial) -> int:
            key = hash(material)
            if (i := materials_index_map.get(key)) is None:
                i = len(materials)
                m = cx.Material()
                m.name = material.material_name
                m.procedural_id = material.procedural_id
                m.room_id = material.room_id
                m.ped_density = material.ped_density
                m.flags = _collision_material_flags_to_cx(material.material_flags)
                materials.append(m)
                materials_index_map[key] = i
            return i

        def _map_primitive(prim: BoundPrimitive) -> cx.Polygon:
            mi = _get_material_index(prim.material)
            match prim.primitive_type:
                case BoundPrimitiveType.BOX:
                    v1, v2, v3, v4 = prim.vertices
                    return cx.PolyBox(mi, v1, v2, v3, v4)
                case BoundPrimitiveType.SPHERE:
                    (v,) = prim.vertices
                    return cx.PolySphere(mi, v, prim.radius)
                case BoundPrimitiveType.CAPSULE:
                    v1, v2 = prim.vertices
                    return cx.PolyCapsule(mi, v1, v2, prim.radius)
                case BoundPrimitiveType.CYLINDER:
                    v1, v2 = prim.vertices
                    return cx.PolyCylinder(mi, v1, v2, prim.radius)
                case BoundPrimitiveType.TRIANGLE:
                    v1, v2, v3 = prim.vertices
                    return cx.PolyTriangle(mi, v1, v2, v3)
                case _:
                    raise ValueError(f"Unknown primitive type '{prim.primitive_type}'")

        b.polygons = [_map_primitive(p) for p in (asset.geometry_primitives or [])]
        b.materials = materials
    else:
        raise ValueError(f"Unsupported CXXML bound type '{bt.name}'")

    return b


def save_bound_to_cx(asset: AssetBound) -> cx.Bound:
    b = _save_bound_to_cx_inner(asset)
    b.tag_name = "RDR2Bounds"
    return b
