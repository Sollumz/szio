from typing import Sequence

import pymateria as pma
import pymateria.gta5 as pm

from ....types import Matrix, Vector
from ...assets import (
    AssetFormat,
    AssetType,
    AssetVersion,
    canonical_asset,
)
from ...bounds import (
    BoundPrimitive,
    BoundPrimitiveType,
    BoundType,
    BoundVertex,
    CollisionFlags,
    CollisionMaterial,
)
from ._utils import (
    apply_target,
    from_native_mat34,
    from_native_rgba,
    to_native_mat34,
    to_native_rgba,
    to_native_vec3,
)


class NativeBound:
    ASSET_FORMAT = AssetFormat.NATIVE
    ASSET_VERSION = AssetVersion.GEN8
    ASSET_TYPE = AssetType.BOUND

    def __init__(self, b: pm.Bound, parent: pm.BoundComposite | None = None):
        self._inner = b
        self._parent = parent

        # Used to fill the composite element properties while this bound does not have a parent
        self._temp_composite_element: pm.BoundCompositeElement | None = None

        self._temp_extent: tuple[Vector, Vector] | None = None

    @property
    def bound_type(self) -> BoundType:
        return BoundType[self._inner.type.name]

    @property
    def material(self) -> CollisionMaterial:
        return CollisionMaterial.from_packed(self._inner.material_id_packed)

    @material.setter
    def material(self, v: CollisionMaterial):
        self._inner.material_id_packed = v.to_packed()

    @property
    def centroid(self) -> Vector:
        return Vector(self._inner.position)

    @centroid.setter
    def centroid(self, v: Vector):
        self._inner.position = to_native_vec3(v)

    @property
    def radius_around_centroid(self) -> float:
        raise NotImplementedError("NativeBound.radius_around_centroid getter")

    @radius_around_centroid.setter
    def radius_around_centroid(self, v: float):
        pass  # let's assume materia calculates the correct value on export...

    @property
    def cg(self) -> Vector:
        return Vector(self._inner.center_of_gravity_offset)

    @cg.setter
    def cg(self, v: Vector):
        self._inner.center_of_gravity_offset = to_native_vec3(v)

    @property
    def children(self) -> list["NativeBound | None"]:
        assert self._inner.type == pm.BoundType.COMPOSITE
        composite: pm.BoundComposite = self._inner
        return [
            apply_target(self, NativeBound(b.bound, composite)) if b and b.bound else None for b in composite.bounds
        ]

    @children.setter
    def children(self, bounds: Sequence["NativeBound | None"]):
        assert self._inner.type == pm.BoundType.COMPOSITE
        composite: pm.BoundComposite = self._inner
        new_bounds = []
        for b in bounds:
            if b is None:
                e = pm.BoundCompositeElement()
                e.bound = None
            else:
                b = canonical_asset(b, NativeBound, self)
                if b._parent is not None:
                    old_e, _ = b._composite_element()
                    e = pm.BoundCompositeElement()
                    e.bound = b._inner
                    e.matrix = old_e.matrix
                elif b._temp_composite_element is None:
                    e = pm.BoundCompositeElement()
                    e.bound = b._inner
                else:
                    e = b._temp_composite_element

            new_bounds.append(e)

        composite.bounds = new_bounds

    @property
    def margin(self) -> float:
        return self._inner.margin if self._inner.margin is not None else 0.0

    @margin.setter
    def margin(self, v: float):
        self._inner.margin = v

    @property
    def volume(self) -> float:
        return self._inner.volume if self._inner.volume is not None else 0.0

    @volume.setter
    def volume(self, v: float):
        self._inner.volume = v

    @property
    def inertia(self) -> Vector:
        return (
            Vector(self._inner.angular_inertia) if self._inner.angular_inertia is not None else Vector((0.0, 0.0, 0.0))
        )

    @inertia.setter
    def inertia(self, v: Vector):
        self._inner.angular_inertia = to_native_vec3(v)

    @property
    def extent(self) -> tuple[Vector, Vector]:
        """Gets the bounding box (tuple of minimum and maximum corner vectors) that contains this bound."""
        inner = self._inner
        match inner.type:
            case pm.BoundType.BOX:
                return Vector(inner.min), Vector(inner.max)
            # case pm.BoundType.SPHERE:
            #     inner.radius = min(size) * 0.5
            # case pm.BoundType.CAPSULE:
            #     inner.radius = size.x * 0.5
            #     inner.length = size.y - (inner.radius * 2.0)
            # case pm.BoundType.CYLINDER:
            #     inner.radius = size.x * 0.5
            #     inner.height = size.y
            # case pm.BoundType.DISC:
            #     inner.radius = size.y * 0.5
            #     length = size.x
            #     inner.margin = length * 0.5  # in discs the margin equals half the length
            # case pm.BoundType.PLANE:
            #     pass
            # case pm.BoundType.GEOMETRY | pm.BoundType.BVH:
            #     inner.bounding_box = pma.AABB3f(vmin, vmax)
            # case pm.BoundType.COMPOSITE:
            #     pass
            case _:
                if self._temp_extent is None:
                    raise NotImplementedError(f"NativeBound.extent getter for type '{inner.type}'")
                else:
                    vmin, vmax = self._temp_extent
                    return Vector(vmin), Vector(vmax)

    @extent.setter
    def extent(self, v: tuple[Vector, Vector]):
        """Sets the dimensions of this bound from a bounding box (tuple of minimum and maximum corner vectors)."""
        inner = self._inner
        vmin, vmax = v
        size = vmax - vmin
        match inner.type:
            case pm.BoundType.BOX:
                inner.min = to_native_vec3(vmin)
                inner.max = to_native_vec3(vmax)
            case pm.BoundType.SPHERE:
                inner.radius = min(size) * 0.5
            case pm.BoundType.CAPSULE:
                inner.radius = size.x * 0.5
                inner.length = size.y
            case pm.BoundType.CYLINDER:
                inner.radius = size.x * 0.5
                inner.height = size.y
            case pm.BoundType.DISC:
                length = size.x
                inner.margin = length * 0.5  # in discs the margin equals half the length
                inner.radius = size.y * 0.5 - inner.margin
            case pm.BoundType.PLANE:
                pass  # empty
            case pm.BoundType.GEOMETRY | pm.BoundType.BVH:
                inner.bounding_box = pma.AABB3f(to_native_vec3(vmin), to_native_vec3(vmax))
            case pm.BoundType.COMPOSITE:
                pass  # empty

        self._temp_extent = Vector(vmin), Vector(vmax)

    @property
    def bb_min(self) -> Vector:
        assert self._inner.type == pm.BoundType.BOX
        return Vector(self._inner.min)

    @bb_min.setter
    def bb_min(self, v: Vector):
        assert self._inner.type == pm.BoundType.BOX
        self._inner.min = to_native_vec3(v)

    @property
    def bb_max(self) -> Vector:
        assert self._inner.type == pm.BoundType.BOX
        return Vector(self._inner.max)

    @bb_max.setter
    def bb_max(self, v: Vector):
        assert self._inner.type == pm.BoundType.BOX
        self._inner.max = to_native_vec3(v)

    @property
    def sphere_radius(self) -> float:
        assert self._inner.type == pm.BoundType.SPHERE
        return self._inner.radius

    @sphere_radius.setter
    def sphere_radius(self, v: float):
        assert self._inner.type == pm.BoundType.SPHERE
        self._inner.radius = v

    @property
    def capsule_radius_length(self) -> tuple[float, float]:
        assert self._inner.type == pm.BoundType.CAPSULE
        radius = self._inner.radius
        length = self._inner.length - (radius * 2.0)
        return radius, length

    @capsule_radius_length.setter
    def capsule_radius_length(self, v: tuple[float, float]):
        raise NotImplementedError("capsule_radius_length setter")

    @property
    def cylinder_radius_length(self) -> tuple[float, float]:
        assert self._inner.type == pm.BoundType.CYLINDER
        return self._inner.radius, self._inner.height

    @cylinder_radius_length.setter
    def cylinder_radius_length(self, v: tuple[float, float]):
        raise NotImplementedError("cylinder_radius_length setter")

    @property
    def disc_radius(self) -> float:
        assert self._inner.type == pm.BoundType.DISC
        return self._inner.radius + self._inner.margin

    @disc_radius.setter
    def disc_radius(self, v: float):
        assert self._inner.type == pm.BoundType.DISC
        self._inner.radius = v - self._inner.margin

    @property
    def geometry_primitives(self) -> list[BoundPrimitive]:
        assert self._inner.type == pm.BoundType.GEOMETRY or self._inner.type == pm.BoundType.BVH

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

        return [
            BoundPrimitive(
                primitive_type=BoundPrimitiveType(p.type.value),
                material=CollisionMaterial.from_packed(p.material_id),
                material_color=from_native_rgba(p.material_color),
                vertices=_get_vertices(p),
                radius=_get_radius(p),
            )
            for p in self._inner.primitives
        ]

    @geometry_primitives.setter
    def geometry_primitives(self, primitives: Sequence[BoundPrimitive]):
        assert self._inner.type == pm.BoundType.GEOMETRY or self._inner.type == pm.BoundType.BVH

        def _to_native_vertex_index(v: int) -> pm.BoundPrimitivePolygonVertexIndex:
            nv = pm.BoundPrimitivePolygonVertexIndex()
            nv.index = v
            nv.normal_code = 0
            return nv

        def _to_native_primitive(prim: BoundPrimitive) -> pm.BoundPrimitive:
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
            return nprim

        self._inner.primitives.clear()
        for prim in primitives:
            self._inner.primitives.append(_to_native_primitive(prim))

    @property
    def geometry_vertices(self) -> list[BoundVertex]:
        assert self._inner.type == pm.BoundType.GEOMETRY or self._inner.type == pm.BoundType.BVH
        has_colors = self._inner.use_vertex_colors

        def _map_color(c: pma.ColorRGBA) -> tuple[int, int, int, int]:
            return (c.b, c.g, c.r, c.a)

        return [
            BoundVertex(Vector(v.position), _map_color(v.color) if has_colors else None) for v in self._inner.vertices
        ]

    @geometry_vertices.setter
    def geometry_vertices(self, vertices: Sequence[BoundVertex]):
        assert self._inner.type == pm.BoundType.GEOMETRY or self._inner.type == pm.BoundType.BVH

        if vertices and vertices[0].color is not None:
            has_colors = True
        else:
            has_colors = False

        def _to_native_vertex(v: BoundVertex) -> pm.BoundVertex:
            nv = pm.BoundVertex()
            nv.position = to_native_vec3(v.co)
            if has_colors:
                nv.color = to_native_rgba((v.color[2], v.color[1], v.color[0], v.color[3]))
            return nv

        self._inner.use_vertex_colors = has_colors
        self._inner.vertices.clear()
        for v in vertices:
            self._inner.vertices.append(_to_native_vertex(v))

    def _composite_element(self) -> tuple[pm.BoundCompositeElement, int]:
        if self._parent is None:
            if self._temp_composite_element is None:
                self._temp_composite_element = pm.BoundCompositeElement()
                self._temp_composite_element.bound = self._inner
                m = pma.Matrix34()
                m.col0 = pma.Vector4f(1.0, 0.0, 0.0, 0.0)
                m.col1 = pma.Vector4f(0.0, 1.0, 0.0, 0.0)
                m.col2 = pma.Vector4f(0.0, 0.0, 1.0, 0.0)
                m.col3 = pma.Vector4f(0.0, 0.0, 0.0, 1.0)
                self._temp_composite_element.matrix = m
            return self._temp_composite_element, -1
        else:
            for i, b in enumerate(self._parent.bounds):
                if b.bound == self._inner:
                    return b, i

            assert False, "Bound not found in parent!"

    def _update_composite_element(self, e: pm.BoundCompositeElement, idx: int):
        """Call this after modifying the object returned by _composite_element.
        BoundCompositeElements are stored by value in the BoundComposite so when we access it we get a copy on Python
        side. If we modify it we need to update the actual item in the list.
        """
        if idx >= 0:
            assert self._parent is not None
            self._parent.bounds[idx] = e

    @property
    def geometry_center(self) -> Vector:
        assert self._inner.type == pm.BoundType.GEOMETRY or self._inner.type == pm.BoundType.BVH
        bbox = self._inner.bounding_box
        if bbox is None:
            return Vector((0.0, 0.0, 0.0))

        return Vector((bbox.max + bbox.min) * 0.5)

    @property
    def composite_transform(self) -> Matrix:
        b, _ = self._composite_element()
        return from_native_mat34(b.matrix)

    @composite_transform.setter
    def composite_transform(self, v: Matrix):
        b, i = self._composite_element()
        b.matrix = to_native_mat34(v)
        self._update_composite_element(b, i)

    @property
    def composite_collision_type_flags(self) -> CollisionFlags:
        b, _ = self._composite_element()
        return CollisionFlags(b.type_flags.value)

    @composite_collision_type_flags.setter
    def composite_collision_type_flags(self, v: CollisionFlags):
        b, i = self._composite_element()
        b.type_flags = pm.CollisionFlags(v.value)
        self._update_composite_element(b, i)

    @property
    def composite_collision_include_flags(self) -> int:
        b, _ = self._composite_element()
        return CollisionFlags(b.include_flags.value)

    @composite_collision_include_flags.setter
    def composite_collision_include_flags(self, v: int):
        b, i = self._composite_element()
        b.include_flags = pm.CollisionFlags(v.value)
        self._update_composite_element(b, i)
