from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum, Flag
from typing import Protocol, runtime_checkable

from ..types import Quaternion, Vector
from .assets import Asset, AssetType
from .drawables import Light, LightFlashiness


class EntityLodLevel(Enum):
    HD = 0
    LOD = 1
    SLOD1 = 2
    SLOD2 = 3
    SLOD3 = 4
    ORPHANHD = 5
    SLOD4 = 6


class EntityPriorityLevel(Enum):
    REQUIRED = 0
    OPTIONAL_HIGH = 1
    OPTIONAL_MEDIUM = 2
    OPTIONAL_LOW = 3


class ScenarioPointFlags(Flag):
    IgnoreMaxInRange = 1 << 0
    NoSpawn = 1 << 1
    StationaryReactions = 1 << 2
    OnlySpawnInSameInterior = 1 << 3
    SpawnedPedIsArrestable = 1 << 4
    ActivateVehicleSiren = 1 << 5
    AggressiveVehicleDriving = 1 << 6
    LandVehicleOnArrival = 1 << 7
    IgnoreThreatsIfLosNotClear = 1 << 8
    EventsInRadiusTriggerDisputes = 1 << 9
    AerialVehiclePoint = 1 << 10
    TerritorialScenario = 1 << 11
    EndScenarioIfPlayerWithinRadius = 1 << 12
    EventsInRadiusTriggerThreatResponse = 1 << 13
    TaxiPlaneOnGround = 1 << 14
    FlyOffToOblivion = 1 << 15
    InWater = 1 << 16
    AllowInvestigation = 1 << 17
    OpenDoor = 1 << 18
    PreciseUseTime = 1 << 19
    NoRespawnUntilStreamedOut = 1 << 20
    NoVehicleSpawnMaxDistance = 1 << 21
    ExtendedRange = 1 << 22
    ShortRange = 1 << 23
    HighPriority = 1 << 24
    IgnoreLoitering = 1 << 25
    UseSearchlight = 1 << 26
    ResetNoCollisionOnCleanUp = 1 << 27
    CheckCrossedArrivalPlane = 1 << 28
    UseVehicleFrontForArrival = 1 << 29
    IgnoreWeatherRestrictions = 1 << 30


@dataclass(slots=True)
class Extension:
    name: str
    offset_position: Vector


@dataclass(slots=True)
class ExtensionDoor(Extension):
    enable_limit_angle: bool
    limit_angle: float
    starts_locked: bool
    can_break: bool
    door_target_ratio: float
    audio_hash: str


@dataclass(slots=True)
class ExtensionParticleEffect(Extension):
    offset_rotation: Quaternion
    fx_name: str
    fx_type: int
    bone_tag: int
    scale: float
    probability: float
    flags: int
    color: tuple[float, float, float, float]


@dataclass(slots=True)
class ExtensionAudioCollisionSettings(Extension):
    settings: str


@dataclass(slots=True)
class ExtensionAudioEmitter(Extension):
    offset_rotation: Quaternion
    effect_hash: str


@dataclass(slots=True)
class ExtensionExplosionEffect(Extension):
    offset_rotation: Quaternion
    explosion_name: str
    bone_tag: int
    explosion_tag: int
    explosion_type: int
    flags: int


@dataclass(slots=True)
class ExtensionLadder(Extension):
    bottom: Vector
    top: Vector
    normal: Vector
    material_type: str
    template: str
    can_get_off_at_top: bool
    can_get_off_at_bottom: bool


@dataclass(slots=True)
class ExtensionBuoyancy(Extension):
    pass


@dataclass(slots=True)
class ExtensionLightShaft(Extension):
    cornerA: Vector
    cornerB: Vector
    cornerC: Vector
    cornerD: Vector
    direction: Vector
    direction_amount: float
    length: float
    fade_in_time_start: float
    fade_in_time_end: float
    fade_out_time_start: float
    fade_out_time_end: float
    fade_distance_start: float
    fade_distance_end: float
    color: tuple[float, float, float, float]
    intensity: float
    flashiness: LightFlashiness
    flags: int
    density_type: str  # LightShaftDensityType
    volume_type: str  # LightShaftVolumeType
    softness: float
    scale_by_sun_intensity: bool


@dataclass(slots=True)
class ExtensionSpawnPoint(Extension):
    offset_rotation: Quaternion
    spawn_type: str
    ped_type: str
    group: str
    interior: str
    required_imap: str
    available_in_mp_sp: str  # TODO: use enum
    probability: float
    time_till_ped_leaves: float
    radius: float
    start: int
    end: int
    scenario_flags: str  # TODO: use enum ScenarioPointFlags, for now only there so native can convert it to a string, needs changes on Blender side for proper flags
    high_pri: bool
    extended_range: bool
    short_range: bool


@dataclass(slots=True)
class ExtensionSpawnPointOverride(Extension):
    scenario_type: str
    itime_start_override: int
    itime_end_override: int
    group: str
    model_set: str
    available_in_mp_sp: str
    scenario_flags: str
    radius: float
    time_till_ped_leaves: float


@dataclass(slots=True)
class ExtensionWindDisturbance(Extension):
    offset_rotation: Quaternion
    disturbance_type: int
    bone_tag: int
    size: Vector
    strength: float
    flags: int


@dataclass(slots=True)
class ExtensionProcObject(Extension):
    radius_inner: float
    radius_outer: float
    spacing: float
    min_scale: float
    max_scale: float
    min_scale_z: float
    max_scale_z: float
    min_z_offset: float
    max_z_offset: float
    object_hash: int
    flags: int


@dataclass(slots=True)
class ExtensionExpression(Extension):
    expression_dictionary_name: str
    expression_name: str
    creature_metadata_name: str
    initialize_on_collision: bool


@dataclass(slots=True)
class ExtensionLightEffect(Extension):
    instances: list[Light]


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
class MloEntity:
    archetype_name: str
    position: Vector
    rotation: Quaternion
    scale_xy: float
    scale_z: float
    flags: int
    guid: int
    parent_index: int
    lod_dist: float
    child_lod_dist: float
    lod_level: EntityLodLevel
    priority_level: EntityPriorityLevel
    num_children: int
    ambient_occlusion_multiplier: int
    artificial_ambient_occlusion: int
    tint_value: int
    extensions: list[Extension]


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


@runtime_checkable
class AssetMapTypes(Asset, Protocol):
    ASSET_TYPE = AssetType.MAP_TYPES

    @property
    def name(self) -> str: ...

    @name.setter
    def name(self, v: str): ...

    @property
    def archetypes(self) -> list[Archetype]: ...

    @archetypes.setter
    def archetypes(self, v: Sequence[Archetype]): ...
