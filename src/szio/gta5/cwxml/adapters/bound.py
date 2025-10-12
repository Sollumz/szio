from typing import Sequence

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
    CollisionMaterialFlags,
)
from .. import bound as cw
from ._utils import apply_target

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


class CWBound:
    ASSET_FORMAT = AssetFormat.CWXML
    ASSET_VERSION = AssetVersion.GEN8
    ASSET_TYPE = AssetType.BOUND

    def __init__(self, b: cw.Bound):
        self._inner = b

    @property
    def bound_type(self) -> BoundType:
        match self._inner.type:
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
                raise ValueError(f"Unknown CWXML bound type '{self._inner.type}'")

    @property
    def material(self) -> CollisionMaterial:
        lo = self._inner.unk_flags & 0xFF
        hi = self._inner.poly_flags & 0xFF
        flags = CollisionMaterialFlags((hi << 8) | lo)
        return CollisionMaterial(
            material_index=self._inner.material_index,
            procedural_id=self._inner.procedural_id,
            room_id=self._inner.room_id,
            ped_density=self._inner.ped_density,
            material_flags=flags,
            material_color_index=self._inner.material_color_index,
        )

    @material.setter
    def material(self, v: CollisionMaterial):
        lo = v.material_flags.value & 0xFF
        hi = (v.material_flags.value >> 8) & 0xFF
        self._inner.unk_flags = lo
        self._inner.poly_flags = hi
        self._inner.material_index = v.material_index
        self._inner.procedural_id = v.procedural_id
        self._inner.room_id = v.room_id
        self._inner.ped_density = v.ped_density
        self._inner.material_color_index = v.material_color_index

    @property
    def centroid(self) -> Vector:
        return Vector(self._inner.box_center)

    @centroid.setter
    def centroid(self, v: Vector):
        is_primitive = self._inner.type in {"Box", "Sphere", "Cylinder", "Capsule", "Disc"}
        if is_primitive:
            self._inner.box_min -= self._inner.box_center
            self._inner.box_max -= self._inner.box_center

        self._inner.box_center = Vector(v.xyz)

        if is_primitive:
            self._inner.box_min += self._inner.box_center
            self._inner.box_max += self._inner.box_center

    @property
    def radius_around_centroid(self) -> float:
        return self._inner.sphere_radius

    @radius_around_centroid.setter
    def radius_around_centroid(self, v: float):
        self._inner.sphere_radius = v

    @property
    def cg(self) -> Vector:
        return Vector(self._inner.sphere_center)

    @cg.setter
    def cg(self, v: Vector):
        self._inner.sphere_center = Vector(v.xyz)

    @property
    def children(self) -> list["CWBound | None"]:
        assert self._inner.type == "Composite"
        composite: cw.BoundComposite = self._inner
        return [apply_target(self, CWBound(b)) if b else None for b in composite.children]

    @children.setter
    def children(self, bounds: Sequence["CWBound | None"]):
        assert self._inner.type == "Composite"
        composite: cw.BoundComposite = self._inner
        composite.children = [canonical_asset(b, CWBound, self)._inner if b else None for b in bounds]

    @property
    def margin(self) -> float:
        return self._inner.margin

    @margin.setter
    def margin(self, v: float):
        self._inner.margin = v

    @property
    def volume(self) -> float:
        return self._inner.volume

    @volume.setter
    def volume(self, v: float):
        self._inner.volume = v

    @property
    def inertia(self) -> Vector:
        return Vector(self._inner.inertia)

    @inertia.setter
    def inertia(self, v: Vector):
        self._inner.inertia = Vector(v)

    @property
    def extent(self) -> tuple[Vector, Vector]:
        """Gets the bounding box (tuple of minimum and maximum corner vectors) that contains this bound."""
        return self._inner.box_min, self._inner.box_max

    @extent.setter
    def extent(self, v: tuple[Vector, Vector]):
        """Sets the dimensions of this bound from a bounding box (tuple of minimum and maximum corner vectors)."""
        vmin, vmax = v
        self._inner.box_min, self._inner.box_max = Vector(vmin), Vector(vmax)
        if self._inner.type == "Sphere":
            size = vmax - vmin
            self._inner.sphere_radius = min(size) * 0.5

        if self._inner.type in {"Box", "Sphere", "Cylinder", "Capsule", "Disc"}:
            self._inner.box_min += self._inner.box_center
            self._inner.box_max += self._inner.box_center

    @property
    def bb_min(self) -> Vector:
        assert self._inner.type == "Box"
        return Vector(self._inner.box_min)

    @bb_min.setter
    def bb_min(self, v: Vector):
        assert self._inner.type == "Box"
        self._inner.box_min = Vector(v.xyz)

    @property
    def bb_max(self) -> Vector:
        assert self._inner.type == "Box"
        return Vector(self._inner.box_max)

    @bb_max.setter
    def bb_max(self, v: Vector):
        assert self._inner.type == "Box"
        self._inner.box_max = Vector(v.xyz)

    @property
    def sphere_radius(self) -> float:
        assert self._inner.type == "Sphere"
        return self._inner.sphere_radius

    @sphere_radius.setter
    def sphere_radius(self, v: float):
        assert self._inner.type == "Sphere"
        self._inner.sphere_radius = v

    @property
    def capsule_radius_length(self) -> tuple[float, float]:
        assert self._inner.type == "Capsule"
        inner = self._inner
        bbmin, bbmax = inner.box_min, inner.box_max
        extent = bbmax - bbmin
        radius = extent.x * 0.5
        length = extent.y - (radius * 2.0)
        return radius, length

    @capsule_radius_length.setter
    def capsule_radius_length(self, v: tuple[float, float]):
        assert self._inner.type == "Capsule"
        raise NotImplementedError("capsule_radius_length setter")

    @property
    def cylinder_radius_length(self) -> tuple[float, float]:
        assert self._inner.type == "Cylinder"
        inner = self._inner
        bbmin, bbmax = inner.box_min, inner.box_max
        extent = bbmax - bbmin
        radius = extent.x * 0.5
        length = extent.y
        return radius, length

    @cylinder_radius_length.setter
    def cylinder_radius_length(self, v: tuple[float, float]):
        assert self._inner.type == "Cylinder"
        raise NotImplementedError("cylinder_radius setter")

    @property
    def disc_radius(self) -> float:
        assert self._inner.type == "Disc"
        return self._inner.sphere_radius

    @disc_radius.setter
    def disc_radius(self, v: float):
        assert self._inner.type == "Disc"
        self._inner.sphere_radius = v

    @property
    def geometry_primitives(self) -> list[BoundPrimitive]:
        assert self._inner.type == "Geometry" or self._inner.type == "GeometryBVH"
        materials = [
            CollisionMaterial(
                material_index=m.type,
                procedural_id=m.procedural_id,
                room_id=m.room_id,
                ped_density=m.ped_density,
                material_flags=collision_material_flags_from_cw(m.flags),
                material_color_index=m.material_color_index,
            )
            for m in self._inner.materials
        ]

        polys = self._inner.polygons
        return [
            BoundPrimitive(
                primitive_type=primitive_type_from_cw(p),
                material=materials[p.material_index],
                # NOTE: we don't really import/export material_colors, pretty sure they are unused
                material_color=(0, 0, 0, 0),
                vertices=p.vertices,
                radius=p.radius if isinstance(p, (cw.PolySphere, cw.PolyCapsule, cw.PolyCylinder)) else None,
            )
            for p in polys
        ]

    @geometry_primitives.setter
    def geometry_primitives(self, primitives: Sequence[BoundPrimitive]):
        assert self._inner.type == "Geometry" or self._inner.type == "GeometryBVH"

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

        self._inner.polygons = [_map_primitive(p) for p in primitives]
        self._inner.materials = materials

    @property
    def geometry_vertices(self) -> list[BoundVertex]:
        assert self._inner.type == "Geometry" or self._inner.type == "GeometryBVH"
        vertices = self._inner.vertices
        colors = self._inner.vertex_colors
        has_colors = bool(colors)
        center = self._inner.geometry_center
        return [BoundVertex(vertices[i] + center, colors[i] if has_colors else None) for i in range(len(vertices))]

    @geometry_vertices.setter
    def geometry_vertices(self, vertices: Sequence[BoundVertex]):
        assert self._inner.type == "Geometry" or self._inner.type == "GeometryBVH"

        if vertices and vertices[0].color is not None:
            has_colors = True
        else:
            has_colors = False

        geom_center = (self._inner.box_min + self._inner.box_max) * 0.5
        vertex_colors = [v.color for v in vertices] if has_colors else []
        vertices_pos = [v.co - geom_center for v in vertices]
        self._inner.geometry_center = geom_center
        self._inner.vertices = vertices_pos
        self._inner.vertex_colors = vertex_colors

    @property
    def geometry_center(self) -> Vector:
        assert self._inner.type == "Geometry" or self._inner.type == "GeometryBVH"
        return Vector(self._inner.geometry_center)

    @property
    def composite_transform(self) -> Matrix:
        return Matrix(self._inner.composite_transform)

    @composite_transform.setter
    def composite_transform(self, v: Matrix):
        self._inner.composite_transform = Matrix(v)

    @property
    def composite_collision_type_flags(self) -> CollisionFlags:
        return collision_flags_from_cw(self._inner.composite_flags1)

    @composite_collision_type_flags.setter
    def composite_collision_type_flags(self, v: CollisionFlags):
        self._inner.composite_flags1 = collision_flags_to_cw(v)

    @property
    def composite_collision_include_flags(self) -> CollisionFlags:
        return collision_flags_from_cw(self._inner.composite_flags2)

    @composite_collision_include_flags.setter
    def composite_collision_include_flags(self, v: CollisionFlags):
        self._inner.composite_flags2 = collision_flags_to_cw(v)
