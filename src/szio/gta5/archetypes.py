from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum, Flag

from ..assets import AssetGame
from ..types import Quaternion, Vector
from .assets import AssetType
from .entities import EntityLodLevel, EntityPriorityLevel, MloEntity
from .extensions import (
    Extension,
    ExtensionAudioCollisionSettings,
    ExtensionAudioEmitter,
    ExtensionBuoyancy,
    ExtensionDoor,
    ExtensionExplosionEffect,
    ExtensionExpression,
    ExtensionLadder,
    ExtensionLightEffect,
    ExtensionLightShaft,
    ExtensionParticleEffect,
    ExtensionProcObject,
    ExtensionSpawnPoint,
    ExtensionSpawnPointOverride,
    ExtensionWindDisturbance,
    ScenarioPointFlags,
)


@dataclass(slots=True)
class MloRoom:
    name: str
    bb_min: Vector
    bb_max: Vector
    blend: float
    timecycle: str
    secondary_timecycle: str
    flags: int
    portal_count: int
    floor_id: int
    exterior_visibility_depth: int
    attached_objects: list[int]


@dataclass(slots=True)
class MloPortal:
    room_from: int
    room_to: int
    flags: int
    mirror_priority: int
    opacity: int
    audio_occlusion: int
    corners: tuple[Vector, Vector, Vector, Vector]
    attached_objects: list[int]


@dataclass(slots=True)
class MloEntitySet:
    name: str
    locations: list[int]
    entities: list[MloEntity]


@dataclass(slots=True)
class MloTimeCycleModifier:
    name: str
    sphere_center: Vector
    sphere_radius: float
    percentage: float
    range: float
    start_hour: int
    end_hour: int


class ArchetypeType(Enum):
    BASE = 0
    TIME = 1
    MLO = 2


class ArchetypeAssetType(Enum):
    UNINITIALIZED = 0
    FRAGMENT = 1
    DRAWABLE = 2
    DRAWABLE_DICTIONARY = 3
    ASSETLESS = 4


@dataclass(slots=True)
class Archetype:
    name: str
    type: ArchetypeType
    flags: int
    lod_dist: float
    special_attribute: int
    hd_texture_dist: float
    texture_dictionary: str
    clip_dictionary: str
    drawable_dictionary: str
    physics_dictionary: str
    bb_min: Vector
    bb_max: Vector
    bs_center: Vector
    bs_radius: float
    asset_name: str
    asset_type: ArchetypeAssetType
    extensions: list[Extension]

    # Time Archetype
    time_flags: int = 0

    # MLO Archetype
    mlo_flags: int = 0
    rooms: list[MloRoom] | None = None
    entities: list[MloEntity] | None = None
    portals: list[MloPortal] | None = None
    entity_sets: list[MloEntitySet] | None = None
    timecycle_modifiers: list[MloTimeCycleModifier] | None = None


@dataclass(slots=True)
class AssetMapTypes:
    ASSET_GAME: AssetGame = AssetGame.GTA5
    ASSET_TYPE: AssetType = AssetType.MAP_TYPES

    name: str = ""
    archetypes: list[Archetype] = field(default_factory=list)
