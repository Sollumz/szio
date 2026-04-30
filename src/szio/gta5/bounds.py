import sys
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum, IntFlag, auto

from ..types import Matrix, Vector
from .assets import AssetGame, AssetType


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


@dataclass(slots=True)
class AssetBound(ABC):
    ASSET_GAME: AssetGame = AssetGame.GTA5
    ASSET_TYPE: AssetType = AssetType.BOUND

    material: CollisionMaterial | None = None
    centroid: Vector = field(default_factory=Vector)
    radius_around_centroid: float = 0.0
    cg: Vector = field(default_factory=Vector)
    margin: float = 0.0
    volume: float = 0.0
    inertia: Vector = field(default_factory=Vector)
    bb_min: Vector = field(default_factory=Vector)
    bb_max: Vector = field(default_factory=Vector)

    # Composite child properties (set by parent composite)
    composite_transform: Matrix = field(default_factory=lambda: Matrix())
    composite_collision_type_flags: CollisionFlags = field(default_factory=lambda: CollisionFlags(0))
    composite_collision_include_flags: CollisionFlags = field(default_factory=lambda: CollisionFlags(0))

    @property
    @abstractmethod
    def bound_type(self) -> BoundType: ...

    @property
    def extent(self) -> tuple[Vector, Vector]:
        """Gets the bounding box (tuple of minimum and maximum corner vectors) that contains this bound."""
        return self.bb_min, self.bb_max

    @extent.setter
    def extent(self, v: tuple[Vector, Vector]):
        """Sets the dimensions of this bound from a bounding box (tuple of minimum and maximum corner vectors)."""
        self.bb_min, self.bb_max = v
        self._apply_extent(v)

    def _apply_extent(self, v: tuple[Vector, Vector]):
        pass

    @staticmethod
    def create(bound_type: BoundType) -> "AssetBound":
        match bound_type:
            case BoundType.SPHERE:
                return AssetBoundSphere()
            case BoundType.CAPSULE:
                return AssetBoundCapsule()
            case BoundType.BOX:
                return AssetBoundBox()
            case BoundType.GEOMETRY:
                return AssetBoundGeometry()
            case BoundType.BVH:
                return AssetBoundBvh()
            case BoundType.COMPOSITE:
                return AssetBoundComposite()
            case BoundType.DISC:
                return AssetBoundDisc()
            case BoundType.CYLINDER:
                return AssetBoundCylinder()
            case BoundType.PLANE:
                return AssetBoundPlane()
            case _:
                raise AssertionError(f"Unknown bound type '{bound_type}'")


@dataclass(slots=True)
class AssetBoundSphere(AssetBound):
    sphere_radius: float = 0.0

    @property
    def bound_type(self) -> BoundType:
        return BoundType.SPHERE

    def _apply_extent(self, v: tuple[Vector, Vector]):
        size = v[1] - v[0]
        self.sphere_radius = min(size) * 0.5


@dataclass
class AssetBoundCapsule(AssetBound):
    capsule_radius_length: tuple[float, float] = (0.0, 0.0)

    @property
    def bound_type(self) -> BoundType:
        return BoundType.CAPSULE

    def _apply_extent(self, v: tuple[Vector, Vector]):
        size = v[1] - v[0]
        radius = size.x * 0.5
        length = size.y - (radius * 2.0)
        self.capsule_radius_length = radius, length


@dataclass
class AssetBoundBox(AssetBound):
    @property
    def bound_type(self) -> BoundType:
        return BoundType.BOX


@dataclass
class AssetBoundGeometry(AssetBound):
    geometry_primitives: list[BoundPrimitive] = field(default_factory=list)
    geometry_vertices: list[BoundVertex] = field(default_factory=list)
    geometry_center: Vector = field(default_factory=Vector)

    @property
    def bound_type(self) -> BoundType:
        return BoundType.GEOMETRY


@dataclass
class AssetBoundBvh(AssetBoundGeometry):
    @property
    def bound_type(self) -> BoundType:
        return BoundType.BVH


@dataclass
class AssetBoundComposite(AssetBound):
    children: list[AssetBound | None] = field(default_factory=list)

    @property
    def bound_type(self) -> BoundType:
        return BoundType.COMPOSITE


@dataclass
class AssetBoundDisc(AssetBound):
    disc_radius: float = 0.0

    @property
    def bound_type(self) -> BoundType:
        return BoundType.DISC

    def _apply_extent(self, v: tuple[Vector, Vector]):
        size = v[1] - v[0]
        self.margin = size.x * 0.5  # in discs the margin equals half the length
        self.disc_radius = size.y * 0.5


@dataclass
class AssetBoundCylinder(AssetBound):
    cylinder_radius_length: tuple[float, float] = (0.0, 0.0)

    @property
    def bound_type(self) -> BoundType:
        return BoundType.CYLINDER

    def _apply_extent(self, v: tuple[Vector, Vector]):
        size = v[1] - v[0]
        radius = size.x * 0.5
        length = size.y
        self.cylinder_radius_length = radius, length


@dataclass
class AssetBoundPlane(AssetBound):
    plane_normal: Vector = field(default_factory=Vector)

    @property
    def bound_type(self) -> BoundType:
        return BoundType.PLANE
