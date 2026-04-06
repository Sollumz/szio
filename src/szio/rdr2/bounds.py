from dataclasses import dataclass

from ..assets import AssetGame
from .. import bounds as _base

# Re-export shared types
from ..bounds import (  # noqa: F401
    AssetBound,
    BoundPrimitive,
    BoundPrimitiveType,
    BoundType,
    BoundVertex,
)


class CollisionFlags(_base.CollisionFlags):
    NONE = 0
    VOID_TYPE_BIT = 1 << 0
    MAP_TYPE_WEAPON = 1 << 1
    MAP_TYPE_MOVER = 1 << 2
    MAP_TYPE_HORSE = 1 << 3
    COVER_TYPE = 1 << 4
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
    NO_HORSE_WALKABLE_TYPE = 1 << 32
    MAP_TYPE_AI_MOVER = 1 << 33
    HORSE_AVOIDANCE = 1 << 34
    MAP_TYPE_CAMERA = 1 << 35


class CollisionMaterialFlags(_base.CollisionMaterialFlags):
    # TODO: verify RDR2 CollisionMaterialFlags, copied from GTA5
    NONE = 0
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


@dataclass(slots=True, unsafe_hash=True)
class CollisionMaterial(_base.CollisionMaterial):
    material_name: str = ""

    # TODO: verify this type is property hashable, added unsafe_hash for now
    # def __hash__(self) -> int:
    #     return self.to_packed()
    #
    # def __eq__(self, o: object) -> int:
    #     return isinstance(o, CollisionMaterial) and self.to_packed() == o.to_packed()


# Game-specific bound subclasses (thin wrappers that tag ASSET_GAME via __init_subclass__)
class AssetBoundSphere(_base.AssetBoundSphere, game=AssetGame.RDR2):
    __slots__ = ()


class AssetBoundCapsule(_base.AssetBoundCapsule, game=AssetGame.RDR2):
    __slots__ = ()


class AssetBoundBox(_base.AssetBoundBox, game=AssetGame.RDR2):
    __slots__ = ()


class AssetBoundGeometry(_base.AssetBoundGeometry, game=AssetGame.RDR2):
    __slots__ = ()


class AssetBoundBvh(_base.AssetBoundBvh, game=AssetGame.RDR2):
    __slots__ = ()


class AssetBoundComposite(_base.AssetBoundComposite, game=AssetGame.RDR2):
    __slots__ = ()


class AssetBoundDisc(_base.AssetBoundDisc, game=AssetGame.RDR2):
    __slots__ = ()


class AssetBoundCylinder(_base.AssetBoundCylinder, game=AssetGame.RDR2):
    __slots__ = ()


class AssetBoundPlane(_base.AssetBoundPlane, game=AssetGame.RDR2):
    __slots__ = ()


class AssetBoundTaperedCapsule(_base.AssetBoundTaperedCapsule, game=AssetGame.RDR2):
    __slots__ = ()


_BOUND_MAP: dict[BoundType, type[AssetBound]] = {
    BoundType.SPHERE: AssetBoundSphere,
    BoundType.CAPSULE: AssetBoundCapsule,
    BoundType.BOX: AssetBoundBox,
    BoundType.GEOMETRY: AssetBoundGeometry,
    BoundType.BVH: AssetBoundBvh,
    BoundType.COMPOSITE: AssetBoundComposite,
    BoundType.DISC: AssetBoundDisc,
    BoundType.CYLINDER: AssetBoundCylinder,
    BoundType.PLANE: AssetBoundPlane,
    BoundType.TAPERED_CAPSULE: AssetBoundTaperedCapsule,
}


def create_bound(bound_type: BoundType) -> AssetBound:
    cls = _BOUND_MAP.get(bound_type)
    if cls is None:
        raise ValueError(f"Unsupported bound type '{bound_type.name}'")
    return cls()
