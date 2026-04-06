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
from .. import bound as cw

CW_COLLISION_FLAGS_MAP = {
    "NONE": CollisionFlags(0),
    "UNKNOWN": CollisionFlags.DEFAULT_TYPE,
    "MAP_WEAPON": CollisionFlags.MAP_TYPE_WEAPON,
    "MAP_DYNAMIC": CollisionFlags.MAP_TYPE_MOVER,
    "MAP_ANIMAL": CollisionFlags.MAP_TYPE_HORSE,
    "MAP_COVER": CollisionFlags.MAP_TYPE_COVER,
    "MAP_VEHICLE": CollisionFlags.MAP_TYPE_VEHICLE,
    "VEHICLE_NOT_BVH": CollisionFlags.VEHICLE_NON_BVH_TYPE,
    "VEHICLE_BVH": CollisionFlags.VEHICLE_BVH_TYPE,
    "VEHICLE_BOX": CollisionFlags.BOX_VEHICLE_TYPE,
    "PED": CollisionFlags.PED_TYPE,
    "RAGDOLL": CollisionFlags.RAGDOLL_TYPE,
    "ANIMAL": CollisionFlags.HORSE_TYPE,
    "ANIMAL_RAGDOLL": CollisionFlags.HORSE_RAGDOLL_TYPE,
    "OBJECT": CollisionFlags.OBJECT_TYPE,
    "OBJECT_ENV_CLOTH": CollisionFlags.ENVCLOTH_OBJECT_TYPE,
    "PLANT": CollisionFlags.PLANT_TYPE,
    "PROJECTILE": CollisionFlags.PROJECTILE_TYPE,
    "EXPLOSION": CollisionFlags.EXPLOSION_TYPE,
    "PICKUP": CollisionFlags.PICKUP_TYPE,
    "FOLIAGE": CollisionFlags.FOLIAGE_TYPE,
    "FORKLIFT_FORKS": CollisionFlags.FORKLIFT_FORKS_TYPE,
    "TEST_WEAPON": CollisionFlags.WEAPON_TEST,
    "TEST_CAMERA": CollisionFlags.CAMERA_TEST,
    "TEST_AI": CollisionFlags.AI_TEST,
    "TEST_SCRIPT": CollisionFlags.SCRIPT_TEST,
    "TEST_VEHICLE_WHEEL": CollisionFlags.WHEEL_TEST,
    "GLASS": CollisionFlags.GLASS_TYPE,
    "MAP_RIVER": CollisionFlags.RIVER_TYPE,
    "SMOKE": CollisionFlags.SMOKE_TYPE,
    "UNSMASHED": CollisionFlags.UNSMASHED_TYPE,
    "MAP_STAIRS": CollisionFlags.STAIR_SLOPE_TYPE,
    "MAP_DEEP_SURFACE": CollisionFlags.DEEP_SURFACE_TYPE,
}
CW_COLLISION_FLAGS_INVERSE_MAP = {v: k for k, v in CW_COLLISION_FLAGS_MAP.items()}


def collision_flags_to_cw(flags: CollisionFlags) -> list[str]:
    converted_flags = []
    for flag in flags:
        converted_flags.append(CW_COLLISION_FLAGS_INVERSE_MAP[flag])
    return converted_flags


def collision_flags_from_cw(flags: Sequence[str]) -> CollisionFlags:
    converted_flags = CollisionFlags(0)
    for flag in flags:
        converted_flags |= CW_COLLISION_FLAGS_MAP.get(flag, 0)
    return converted_flags


def collision_material_flags_to_cw(flags: CollisionMaterialFlags) -> set[str]:
    converted_flags = []
    for flag in flags:
        converted_flags.append(f"FLAG_{flag.name}")
    return converted_flags if converted_flags else ["NONE"]


def collision_material_flags_from_cw(flags: set[str]) -> CollisionMaterialFlags:
    converted_flags = CollisionMaterialFlags(0)
    for flag in flags:
        if flag.startswith("FLAG_") and (flag_name := flag[5:]) in CollisionMaterialFlags.__members__:
            converted_flags |= CollisionMaterialFlags[flag_name]
    return converted_flags


def primitive_type_from_cw(p: cw.Polygon) -> BoundPrimitiveType:
    match type(p):
        case cw.PolyBox:
            return BoundPrimitiveType.BOX
        case cw.PolySphere:
            return BoundPrimitiveType.SPHERE
        case cw.PolyCapsule:
            return BoundPrimitiveType.CAPSULE
        case cw.PolyCylinder:
            return BoundPrimitiveType.CYLINDER
        case cw.PolyTriangle:
            return BoundPrimitiveType.TRIANGLE
        case _:
            assert False, f"Unknown primitive type '{type(p)}'"


def _bound_type_from_cw(b: cw.Bound) -> BoundType:
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
        case "Cloth":
            return BoundType.PLANE
        case "Geometry":
            return BoundType.GEOMETRY
        case "GeometryBVH":
            return BoundType.BVH
        case _:
            raise ValueError(f"Unknown CWXML bound type '{b.type}'")


_BOUND_PRIMITIVE_TYPES = {"Box", "Sphere", "Cylinder", "Capsule", "Disc"}


def load_bound_from_cw(b: cw.Bound | None) -> AssetBound | None:
    if b is None:
        return None

    bound_type = _bound_type_from_cw(b)
    is_primitive = b.type in _BOUND_PRIMITIVE_TYPES

    result = create_bound(bound_type)

    # Material
    lo = b.unk_flags & 0xFF
    hi = b.poly_flags & 0xFF
    flags = CollisionMaterialFlags((hi << 8) | lo)
    result.material = CollisionMaterial(
        material_index=b.material_index,
        procedural_id=b.procedural_id,
        room_id=b.room_id,
        ped_density=b.ped_density,
        material_flags=flags,
        material_color_index=b.material_color_index,
    )

    result.centroid = Vector(b.box_center)
    result.radius_around_centroid = b.sphere_radius
    result.cg = Vector(b.sphere_center)
    result.margin = b.margin
    result.volume = b.volume
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
        composite: cw.BoundComposite = b
        result.children = []
        for child_b in composite.children:
            if child_b is None:
                result.children.append(None)
            else:
                child = load_bound_from_cw(child_b)
                child.composite_transform = Matrix(child_b.composite_transform)
                child.composite_collision_type_flags = collision_flags_from_cw(child_b.composite_flags1)
                child.composite_collision_include_flags = collision_flags_from_cw(child_b.composite_flags2)
                result.children.append(child)
    elif bound_type == BoundType.SPHERE:
        result.sphere_radius = b.sphere_radius
    elif bound_type == BoundType.CAPSULE:
        # Inline capsule_radius_length getter
        extent = b.box_max - b.box_min
        radius = extent.x * 0.5
        length = extent.y - (radius * 2.0)
        result.capsule_radius_length = (radius, length)
    elif bound_type == BoundType.CYLINDER:
        # Inline cylinder_radius_length getter
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
            CollisionMaterial(
                material_index=m.type,
                procedural_id=m.procedural_id,
                room_id=m.room_id,
                ped_density=m.ped_density,
                material_flags=collision_material_flags_from_cw(m.flags),
                material_color_index=m.material_color_index,
            )
            for m in b.materials
        ]
        polys = b.polygons
        result.geometry_primitives = [
            BoundPrimitive(
                primitive_type=primitive_type_from_cw(p),
                material=materials[p.material_index],
                material_color=(0, 0, 0, 0),
                vertices=p.vertices,
                radius=p.radius if isinstance(p, (cw.PolySphere, cw.PolyCapsule, cw.PolyCylinder)) else None,
            )
            for p in polys
        ]

        # Inline geometry_vertices getter
        vertices = b.vertices
        colors = b.vertex_colors
        has_colors = bool(colors)
        center = b.geometry_center
        result.geometry_vertices = [
            BoundVertex(vertices[i] + center, colors[i] if has_colors else None) for i in range(len(vertices))
        ]

        result.geometry_center = Vector(b.geometry_center)

    return result


def _create_cw_bound(bound_type: BoundType) -> cw.Bound:
    match bound_type:
        case BoundType.COMPOSITE:
            return cw.BoundComposite()
        case BoundType.BOX:
            return cw.BoundBox()
        case BoundType.SPHERE:
            return cw.BoundSphere()
        case BoundType.CAPSULE:
            return cw.BoundCapsule()
        case BoundType.CYLINDER:
            return cw.BoundCylinder()
        case BoundType.DISC:
            return cw.BoundDisc()
        case BoundType.PLANE:
            return cw.BoundPlane()
        case BoundType.GEOMETRY:
            return cw.BoundGeometry()
        case BoundType.BVH:
            return cw.BoundGeometryBVH()
        case _:
            raise ValueError(f"Unsupported bound type '{bound_type.name}'")


def save_bound_to_cw(asset: AssetBound) -> cw.Bound:
    b = _create_cw_bound(asset.bound_type)
    is_primitive = b.type in _PRIMITIVE_TYPES

    # Set common properties directly on the CW object
    b.box_center = Vector(asset.centroid[:3])
    b.sphere_center = Vector(asset.cg[:3])
    b.sphere_radius = asset.radius_around_centroid
    b.margin = asset.margin
    b.volume = asset.volume
    b.inertia = Vector(asset.inertia)

    if asset.material:
        lo = asset.material.material_flags.value & 0xFF
        hi = (asset.material.material_flags.value >> 8) & 0xFF
        b.unk_flags = lo
        b.poly_flags = hi
        b.material_index = asset.material.material_index
        b.procedural_id = asset.material.procedural_id
        b.room_id = asset.material.room_id
        b.ped_density = asset.material.ped_density
        b.material_color_index = asset.material.material_color_index

    # Set extent (un-centered bb_min/bb_max, add center for primitives)
    b.box_min = Vector(asset.bb_min)
    b.box_max = Vector(asset.bb_max)
    if is_primitive:
        b.box_min = b.box_min + b.box_center
        b.box_max = b.box_max + b.box_center

    bt = asset.bound_type
    if bt == BoundType.COMPOSITE:
        composite: cw.BoundComposite = b
        children_cw = []
        for child in asset.children or []:
            if child is None:
                children_cw.append(None)
            else:
                child_cw = save_bound_to_cw(child)
                child_cw.composite_transform = Matrix(child.composite_transform)
                child_cw.composite_flags1 = collision_flags_to_cw(child.composite_collision_type_flags)
                child_cw.composite_flags2 = collision_flags_to_cw(child.composite_collision_include_flags)
                children_cw.append(child_cw)
        composite.children = children_cw
    elif bt == BoundType.SPHERE:
        b.sphere_radius = asset.sphere_radius
    elif bt == BoundType.DISC:
        b.sphere_radius = asset.disc_radius
    elif bt == BoundType.PLANE:
        b.normal = Vector(asset.plane_normal)
    elif bt in (BoundType.GEOMETRY, BoundType.BVH):
        # Save geometry vertices (inlined from CWBound.geometry_vertices setter)
        has_colors = bool(asset.geometry_vertices and asset.geometry_vertices[0].color is not None)
        geom_center = (b.box_min + b.box_max) * 0.5
        b.geometry_center = geom_center
        b.vertices = [v.co - geom_center for v in (asset.geometry_vertices or [])]
        b.vertex_colors = [v.color for v in asset.geometry_vertices] if has_colors else []

        # Save geometry primitives (inlined from CWBound.geometry_primitives setter)
        materials = []
        materials_index_map = {}

        def _get_material_index(material: CollisionMaterial) -> int:
            material_id = material.to_packed()
            if (i := materials_index_map.get(material_id, None)) is None:
                i = len(materials)
                m = cw.Material()
                m.type = material.material_index
                m.procedural_id = material.procedural_id
                m.room_id = material.room_id
                m.ped_density = material.ped_density
                m.flags = collision_material_flags_to_cw(material.material_flags)
                m.material_color_index = material.material_color_index
                materials.append(m)
                materials_index_map[material_id] = i
            return i

        def _map_primitive(prim: BoundPrimitive) -> cw.Polygon:
            match prim.primitive_type:
                case BoundPrimitiveType.BOX:
                    p = cw.PolyBox()
                    p.v1, p.v2, p.v3, p.v4 = prim.vertices
                case BoundPrimitiveType.SPHERE:
                    p = cw.PolySphere()
                    p.v = prim.vertices[0]
                    p.radius = prim.radius
                case BoundPrimitiveType.CAPSULE:
                    p = cw.PolyCapsule()
                    p.v1, p.v2 = prim.vertices
                    p.radius = prim.radius
                case BoundPrimitiveType.CYLINDER:
                    p = cw.PolyCylinder()
                    p.v1, p.v2 = prim.vertices
                    p.radius = prim.radius
                case BoundPrimitiveType.TRIANGLE:
                    p = cw.PolyTriangle()
                    p.v1, p.v2, p.v3 = prim.vertices
                case _:
                    assert False, f"Unknown primitive type '{prim.primitive_type}'"
            p.material_index = _get_material_index(prim.material)
            return p

        b.polygons = [_map_primitive(p) for p in (asset.geometry_primitives or [])]
        b.materials = materials

    return b
