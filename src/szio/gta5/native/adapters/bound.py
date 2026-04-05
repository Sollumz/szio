import pymateria as pma
import pymateria.gta5 as pm

from ....types import Vector
from ...bounds import (
    AssetBound,
    BoundPrimitive,
    BoundPrimitiveType,
    BoundType,
    BoundVertex,
    CollisionFlags,
    CollisionMaterial,
)
from ._utils import (
    from_native_mat34,
    from_native_rgba,
    to_native_mat34,
    to_native_rgba,
    to_native_vec3,
)


def load_bound_from_native(b: pm.Bound) -> AssetBound:
    bound_type = BoundType[b.type.name]
    result = AssetBound.create(bound_type)

    result.material = CollisionMaterial.from_packed(b.material_id_packed)
    result.centroid = Vector(b.position)
    result.radius_around_centroid = 0.0  # native format calculates on export
    result.cg = Vector(b.center_of_gravity_offset)
    result.margin = b.margin if b.margin is not None else 0.0
    result.volume = b.volume if b.volume is not None else 0.0
    result.inertia = Vector(b.angular_inertia) if b.angular_inertia is not None else Vector((0.0, 0.0, 0.0))

    if bound_type == BoundType.BOX:
        result.bb_min = Vector(b.min)
        result.bb_max = Vector(b.max)
    elif bound_type == BoundType.SPHERE:
        r = b.radius
        result.sphere_radius = r
        result.bb_min = Vector((-r, -r, -r))
        result.bb_max = Vector((r, r, r))
    elif bound_type == BoundType.CAPSULE:
        radius = b.radius
        length = b.length - (radius * 2.0)
        result.capsule_radius_length = (radius, length)
        result.bb_min = Vector((-radius, -b.length * 0.5, -radius))
        result.bb_max = Vector((radius, b.length * 0.5, radius))
    elif bound_type == BoundType.CYLINDER:
        radius = b.radius
        height = b.height
        result.cylinder_radius_length = (radius, height)
        result.bb_min = Vector((-radius, -height * 0.5, -radius))
        result.bb_max = Vector((radius, height * 0.5, radius))
    elif bound_type == BoundType.DISC:
        radius = b.radius + b.margin
        result.disc_radius = radius
        half_margin = b.margin
        result.bb_min = Vector((-half_margin, -radius, -radius))
        result.bb_max = Vector((half_margin, radius, radius))
    elif bound_type == BoundType.PLANE:
        result.plane_normal = Vector(b.normal)
    elif bound_type in (BoundType.GEOMETRY, BoundType.BVH):
        # Geometry primitives
        def _get_vertices(p: pm.BoundPrimitive):
            match p.type:
                case pm.BoundPrimitiveType.POLYGON:
                    return tuple(v.index for v in p.indices)
                case pm.BoundPrimitiveType.SPHERE:
                    return (p.center_index,)
                case pm.BoundPrimitiveType.CAPSULE | pm.BoundPrimitiveType.CYLINDER:
                    return (p.end_index0, p.end_index1)
                case pm.BoundPrimitiveType.BOX:
                    return tuple(p.vertex_indices)
                case _:
                    assert False, f"Unknown primitive type '{p.type}'"

        def _get_radius(p: pm.BoundPrimitive):
            match p.type:
                case pm.BoundPrimitiveType.SPHERE | pm.BoundPrimitiveType.CAPSULE | pm.BoundPrimitiveType.CYLINDER:
                    return p.radius
                case _:
                    return None

        result.geometry_primitives = [
            BoundPrimitive(
                primitive_type=BoundPrimitiveType(p.type.value),
                material=CollisionMaterial.from_packed(p.material_id),
                material_color=from_native_rgba(p.material_color),
                vertices=_get_vertices(p),
                radius=_get_radius(p),
            )
            for p in b.primitives
        ]

        # Geometry vertices
        has_colors = b.use_vertex_colors

        def _map_color(c: pma.ColorRGBA) -> tuple[int, int, int, int]:
            return (c.b, c.g, c.r, c.a)

        result.geometry_vertices = [
            BoundVertex(Vector(v.position), _map_color(v.color) if has_colors else None) for v in b.vertices
        ]

        # Geometry center & bounding box
        bbox = b.bounding_box
        if bbox is not None:
            result.geometry_center = Vector((bbox.max + bbox.min) * 0.5)
            result.bb_min = Vector(bbox.min)
            result.bb_max = Vector(bbox.max)
        else:
            result.geometry_center = Vector((0.0, 0.0, 0.0))
    elif bound_type == BoundType.COMPOSITE:
        composite: pm.BoundComposite = b
        result.children = []
        for e in composite.bounds:
            if e is None or e.bound is None:
                result.children.append(None)
            else:
                child = load_bound_from_native(e.bound)
                child.composite_transform = from_native_mat34(e.matrix)
                child.composite_collision_type_flags = CollisionFlags(e.type_flags.value)
                child.composite_collision_include_flags = CollisionFlags(e.include_flags.value)
                result.children.append(child)

    return result


def save_bound_to_native(asset: AssetBound) -> pm.Bound:
    match asset.bound_type:
        case BoundType.COMPOSITE:
            b = pm.BoundComposite()
        case BoundType.SPHERE:
            b = pm.BoundSphere()
        case BoundType.BOX:
            b = pm.BoundBox()
        case BoundType.CAPSULE:
            b = pm.BoundCapsule()
        case BoundType.CYLINDER:
            b = pm.BoundCylinder()
        case BoundType.DISC:
            b = pm.BoundDisc()
        case BoundType.GEOMETRY:
            b = pm.BoundGeometry()
        case BoundType.BVH:
            bvh = pm.BoundGeometry()
            bvh.generate_bvh = True
            b = bvh
        case BoundType.PLANE:
            b = pm.BoundPlane()
        case _:
            raise ValueError(f"Unsupported bound type '{asset.bound_type.name}'")

    b.material_id_packed = asset.material.to_packed() if asset.material else 0
    b.position = to_native_vec3(asset.centroid)
    b.center_of_gravity_offset = to_native_vec3(asset.cg)
    b.margin = asset.margin
    b.volume = asset.volume
    b.angular_inertia = to_native_vec3(asset.inertia)

    bt = asset.bound_type
    vmin, vmax = asset.bb_min, asset.bb_max

    if bt == BoundType.BOX:
        b.min = to_native_vec3(vmin)
        b.max = to_native_vec3(vmax)
    elif bt == BoundType.SPHERE:
        b.radius = asset.sphere_radius
    elif bt == BoundType.CAPSULE:
        b.radius, b.length = asset.capsule_radius_length
    elif bt == BoundType.CYLINDER:
        b.radius, b.length = asset.cylinder_radius_length
    elif bt == BoundType.DISC:
        b.radius = asset.disc_radius - b.margin
    elif bt == BoundType.PLANE:
        b.normal = to_native_vec3(asset.plane_normal)
    elif bt in (BoundType.GEOMETRY, BoundType.BVH):
        b.bounding_box = pma.AABB3f(to_native_vec3(vmin), to_native_vec3(vmax))

        # Save vertices
        has_colors = bool(asset.geometry_vertices and asset.geometry_vertices[0].color is not None)
        b.use_vertex_colors = has_colors
        b.vertices.clear()
        for v in asset.geometry_vertices or []:
            nv = pm.BoundVertex()
            nv.position = to_native_vec3(v.co)
            if has_colors:
                nv.color = to_native_rgba((v.color[2], v.color[1], v.color[0], v.color[3]))
            b.vertices.append(nv)

        # Save primitives
        b.primitives.clear()
        for prim in asset.geometry_primitives or []:
            match prim.primitive_type:
                case BoundPrimitiveType.BOX:
                    nprim = pm.BoundPrimitiveBox()
                    nprim.vertex_indices = prim.vertices
                case BoundPrimitiveType.SPHERE:
                    nprim = pm.BoundPrimitiveSphere()
                    nprim.center_index = prim.vertices[0]
                    nprim.radius = prim.radius
                case BoundPrimitiveType.CAPSULE:
                    nprim = pm.BoundPrimitiveCapsule()
                    nprim.end_index0 = prim.vertices[0]
                    nprim.end_index1 = prim.vertices[1]
                    nprim.radius = prim.radius
                case BoundPrimitiveType.CYLINDER:
                    nprim = pm.BoundPrimitiveCylinder()
                    nprim.end_index0 = prim.vertices[0]
                    nprim.end_index1 = prim.vertices[1]
                    nprim.radius = prim.radius
                case BoundPrimitiveType.TRIANGLE:
                    nprim = pm.BoundPrimitivePolygon()
                    nprim.indices = [_to_native_vertex_index(v) for v in prim.vertices]
                case _:
                    assert False, f"Unknown primitive type '{prim.primitive_type}'"

            nprim.material_id = prim.material.to_packed()
            nprim.material_color = to_native_rgba(prim.material_color)
            b.primitives.append(nprim)
    elif bt == BoundType.COMPOSITE:
        composite: pm.BoundComposite = b
        new_bounds = []
        for child in asset.children or []:
            if child is None:
                e = pm.BoundCompositeElement()
                e.bound = None
                new_bounds.append(e)
            else:
                child_b = save_bound_to_native(child)
                e = pm.BoundCompositeElement()
                e.bound = child_b
                e.matrix = to_native_mat34(child.composite_transform)
                e.type_flags = pm.CollisionFlags(child.composite_collision_type_flags.value)
                e.include_flags = pm.CollisionFlags(child.composite_collision_include_flags.value)
                new_bounds.append(e)
        composite.bounds = new_bounds

    return b


def _to_native_vertex_index(v: int) -> pm.BoundPrimitivePolygonVertexIndex:
    nv = pm.BoundPrimitivePolygonVertexIndex()
    nv.index = v
    nv.normal_code = 0
    return nv
