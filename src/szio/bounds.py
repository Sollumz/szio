import sys
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum, IntFlag, auto
from typing import ClassVar

from .types import Matrix, Vector
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
    TAPERED_CAPSULE = auto()


class CollisionFlags(IntFlag):
    """Base class for game-specific collision flags. Game modules subclass this with their own members."""
    NONE = 0

    if sys.version_info < (3, 11):

        def __iter__(self):
            for flag in type(self):
                if flag in self:
                    yield flag


class CollisionMaterialFlags(IntFlag):
    """Base class for game-specific collision material flags. Game modules subclass this with their own members."""
    NONE = 0

    if sys.version_info < (3, 11):

        def __iter__(self):
            for flag in type(self):
                if flag in self:
                    yield flag


@dataclass(slots=True)
class CollisionMaterial(ABC):
    """Base collision material with fields common to all games."""
    procedural_id: int = 0
    room_id: int = 0
    ped_density: int = 0
    material_flags: CollisionMaterialFlags = CollisionMaterialFlags(0)


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
    ASSET_GAME: ClassVar[AssetGame] = AssetGame.GTA5
    ASSET_TYPE: ClassVar[AssetType] = AssetType.BOUND

    def __init_subclass__(cls, *, game: AssetGame | None = None, **kwargs):
        # NOTE: do not call super().__init_subclass__() here.
        # @dataclass(slots=True) recreates the class, leaving super()'s __class__
        # closure pointing at the original (dead) class object (CPython gh-91126).
        if game is not None:
            cls.ASSET_GAME = game

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
    composite_transform: Matrix = None
    composite_collision_type_flags: CollisionFlags = CollisionFlags(0)
    composite_collision_include_flags: CollisionFlags = CollisionFlags(0)

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
        self.capsule_radius_length = size.x * 0.5, size.y


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
        self.cylinder_radius_length = size.x * 0.5, size.y


@dataclass
class AssetBoundPlane(AssetBound):
    plane_normal: Vector = field(default_factory=Vector)

    @property
    def bound_type(self) -> BoundType:
        return BoundType.PLANE


@dataclass
class AssetBoundTaperedCapsule(AssetBound):
    # TODO: AssetBoundTaperedCapsule (used in RDR2)

    @property
    def bound_type(self) -> BoundType:
        return BoundType.TAPERED_CAPSULE
