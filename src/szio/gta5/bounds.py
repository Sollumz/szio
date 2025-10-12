import sys
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum, IntFlag, auto
from typing import Protocol, runtime_checkable

from ..types import Matrix, Vector
from .assets import Asset, AssetType


class BoundType(Enum):
    SPHERE = auto()
    CAPSULE = auto()
    BOX = auto()
    GEOMETRY = auto()
    BVH = auto()
    COMPOSITE = auto()
    DISC = auto()
    CYLINDER = auto()
    PLANE = auto()


class CollisionFlags(IntFlag):
    DEFAULT_TYPE = 1 << 0
    MAP_TYPE_WEAPON = 1 << 1
    MAP_TYPE_MOVER = 1 << 2
    MAP_TYPE_HORSE = 1 << 3
    MAP_TYPE_COVER = 1 << 4
    MAP_TYPE_VEHICLE = 1 << 5
    VEHICLE_NON_BVH_TYPE = 1 << 6
    VEHICLE_BVH_TYPE = 1 << 7
    BOX_VEHICLE_TYPE = 1 << 8
    PED_TYPE = 1 << 9
    RAGDOLL_TYPE = 1 << 10
    HORSE_TYPE = 1 << 11
    HORSE_RAGDOLL_TYPE = 1 << 12
    OBJECT_TYPE = 1 << 13
    ENVCLOTH_OBJECT_TYPE = 1 << 14
    PLANT_TYPE = 1 << 15
    PROJECTILE_TYPE = 1 << 16
    EXPLOSION_TYPE = 1 << 17
    PICKUP_TYPE = 1 << 18
    FOLIAGE_TYPE = 1 << 19
    FORKLIFT_FORKS_TYPE = 1 << 20
    WEAPON_TEST = 1 << 21
    CAMERA_TEST = 1 << 22
    AI_TEST = 1 << 23
    SCRIPT_TEST = 1 << 24
    WHEEL_TEST = 1 << 25
    GLASS_TYPE = 1 << 26
    RIVER_TYPE = 1 << 27
    SMOKE_TYPE = 1 << 28
    UNSMASHED_TYPE = 1 << 29
    STAIR_SLOPE_TYPE = 1 << 30
    DEEP_SURFACE_TYPE = 1 << 31

    if sys.version_info < (3, 11):

        def __iter__(self):
            for flag in CollisionFlags:
                if flag in self:
                    yield flag


class CollisionMaterialFlags(IntFlag):
    STAIRS = 1 << 0
    NOT_CLIMBABLE = 1 << 1
    SEE_THROUGH = 1 << 2
    SHOOT_THROUGH = 1 << 3
    NOT_COVER = 1 << 4
    WALKABLE_PATH = 1 << 5
    NO_CAM_COLLISION = 1 << 6
    SHOOT_THROUGH_FX = 1 << 7
    NO_DECAL = 1 << 8
    NO_NAVMESH = 1 << 9
    NO_RAGDOLL = 1 << 10
    VEHICLE_WHEEL = 1 << 11
    NO_PTFX = 1 << 12
    TOO_STEEP_FOR_PLAYER = 1 << 13
    NO_NETWORK_SPAWN = 1 << 14
    NO_CAM_COLLISION_ALLOW_CLIPPING = 1 << 15

    if sys.version_info < (3, 11):

        def __iter__(self):
            for flag in CollisionMaterialFlags:
                if flag in self:
                    yield flag


@dataclass(slots=True)
class CollisionMaterial:
    material_index: int
    material_color_index: int
    procedural_id: int
    room_id: int
    ped_density: int
    material_flags: CollisionMaterialFlags

    @staticmethod
    def from_packed(material_packed: int) -> "CollisionMaterial":
        return CollisionMaterial(
            material_index=((material_packed >> 0) & 0xFF),
            procedural_id=((material_packed >> 8) & 0xFF),
            room_id=((material_packed >> 16) & 0x1F),
            ped_density=((material_packed >> 21) & 0x7),
            material_flags=CollisionMaterialFlags((material_packed >> 24) & 0xFFFF),
            material_color_index=((material_packed >> 40) & 0xFF),
        )

    def to_packed(self) -> int:
        return (
            (self.material_index & 0xFF)
            | ((self.procedural_id & 0xFF) << 8)
            | ((self.room_id & 0x1F) << 16)
            | ((self.ped_density & 0x7) << 21)
            | ((self.material_flags.value & 0xFFFF) << 24)
            | ((self.material_color_index & 0xFF) << 40)
        )

    def __hash__(self) -> int:
        return self.to_packed()

    def __eq__(self, o: object) -> int:
        return isinstance(o, CollisionMaterial) and self.to_packed() == o.to_packed()


class BoundPrimitiveType(Enum):
    TRIANGLE = 0  # 3 vertices
    SPHERE = 1  # 1 vertex
    CAPSULE = 2  # 2 vertices
    BOX = 3  # 4 vertices
    CYLINDER = 4  # 2 vertices


@dataclass(slots=True)
class BoundPrimitive:
    primitive_type: BoundPrimitiveType
    material: CollisionMaterial
    material_color: tuple[int, int, int, int]
    vertices: Sequence[int]
    radius: float | None

    @staticmethod
    def new_triangle(
        v0: int,
        v1: int,
        v2: int,
        material: CollisionMaterial,
        material_color: tuple[int, int, int, int] = (0, 0, 0, 0),
    ) -> "BoundPrimitive":
        return BoundPrimitive(BoundPrimitiveType.TRIANGLE, material, material_color, (v0, v1, v2), None)

    @staticmethod
    def new_box(
        v0: int,
        v1: int,
        v2: int,
        v3: int,
        material: CollisionMaterial,
        material_color: tuple[int, int, int, int] = (0, 0, 0, 0),
    ) -> "BoundPrimitive":
        return BoundPrimitive(BoundPrimitiveType.BOX, material, material_color, (v0, v1, v2, v3), None)

    @staticmethod
    def new_sphere(
        v: int,
        radius: float,
        material: CollisionMaterial,
        material_color: tuple[int, int, int, int] = (0, 0, 0, 0),
    ) -> "BoundPrimitive":
        return BoundPrimitive(BoundPrimitiveType.SPHERE, material, material_color, (v,), radius)

    @staticmethod
    def new_capsule(
        v0: int,
        v1: int,
        radius: float,
        material: CollisionMaterial,
        material_color: tuple[int, int, int, int] = (0, 0, 0, 0),
    ) -> "BoundPrimitive":
        return BoundPrimitive(BoundPrimitiveType.CAPSULE, material, material_color, (v0, v1), radius)

    @staticmethod
    def new_cylinder(
        v0: int,
        v1: int,
        radius: float,
        material: CollisionMaterial,
        material_color: tuple[int, int, int, int] = (0, 0, 0, 0),
    ) -> "BoundPrimitive":
        return BoundPrimitive(BoundPrimitiveType.CYLINDER, material, material_color, (v0, v1), radius)


@dataclass(slots=True)
class BoundVertex:
    co: Vector
    color: tuple[int, int, int, int] | None


@runtime_checkable
class AssetBound(Asset, Protocol):
    ASSET_TYPE = AssetType.BOUND

    @property
    def bound_type(self) -> BoundType: ...

    @property
    def material(self) -> CollisionMaterial: ...

    @material.setter
    def material(self, v: CollisionMaterial): ...

    @property
    def centroid(self) -> Vector: ...

    @centroid.setter
    def centroid(self, v: Vector): ...

    @property
    def radius_around_centroid(self) -> float: ...

    @radius_around_centroid.setter
    def radius_around_centroid(self, v: float): ...

    @property
    def cg(self) -> Vector: ...

    @cg.setter
    def cg(self, v: Vector): ...

    @property
    def children(self) -> list["AssetBound | None"]: ...

    @children.setter
    def children(self, bounds: Sequence["AssetBound | None"]): ...

    @property
    def margin(self) -> float: ...

    @margin.setter
    def margin(self, v: float): ...

    @property
    def volume(self) -> float: ...

    @volume.setter
    def volume(self, v: float): ...

    @property
    def inertia(self) -> Vector: ...

    @inertia.setter
    def inertia(self, v: Vector): ...

    @property
    def extent(self) -> tuple[Vector, Vector]:
        """Gets the bounding box (tuple of minimum and maximum corner vectors) that contains this bound."""
        ...

    @extent.setter
    def extent(self, v: tuple[Vector, Vector]):
        """Sets the dimensions of this bound from a bounding box (tuple of minimum and maximum corner vectors)."""
        ...

    @property
    def bb_min(self) -> Vector: ...

    @bb_min.setter
    def bb_min(self, v: Vector): ...

    @property
    def bb_max(self) -> Vector: ...

    @bb_max.setter
    def bb_max(self, v: Vector): ...

    @property
    def sphere_radius(self) -> float: ...

    @sphere_radius.setter
    def sphere_radius(self, v: float): ...

    @property
    def capsule_radius_length(self) -> tuple[float, float]: ...

    @capsule_radius_length.setter
    def capsule_radius_length(self, v: tuple[float, float]): ...

    @property
    def cylinder_radius_length(self) -> tuple[float, float]: ...

    @cylinder_radius_length.setter
    def cylinder_radius_length(self, v: tuple[float, float]): ...

    @property
    def disc_radius(self) -> float: ...

    @disc_radius.setter
    def disc_radius(self, v: float): ...

    @property
    def geometry_primitives(self) -> list[BoundPrimitive]: ...

    @geometry_primitives.setter
    def geometry_primitives(self, v: Sequence[BoundPrimitive]): ...

    @property
    def geometry_vertices(self) -> list[BoundVertex]: ...

    @geometry_vertices.setter
    def geometry_vertices(self, v: Sequence[BoundVertex]): ...

    @property
    def geometry_center(self) -> Vector: ...

    @property
    def composite_transform(self) -> Matrix: ...

    @composite_transform.setter
    def composite_transform(self, v: Matrix): ...

    @property
    def composite_collision_type_flags(self) -> CollisionFlags: ...

    @composite_collision_type_flags.setter
    def composite_collision_type_flags(self, v: CollisionFlags): ...

    @property
    def composite_collision_include_flags(self) -> CollisionFlags: ...

    @composite_collision_include_flags.setter
    def composite_collision_include_flags(self, v: CollisionFlags): ...
