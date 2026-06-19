import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum, Flag

import numpy as np

from ..assets import AssetGame
from ..types import Vector
from .assets import AssetType
from .entities import MapEntity


class MapFlags(Flag):
    SCRIPTED = 1 << 0
    IS_PARENT = 1 << 1

    if sys.version_info < (3, 11):

        def __iter__(self):
            for flag in MapFlags:
                if flag in self:
                    yield flag


class MapContentFlags(Flag):
    HAS_ENTITIES_HD = 1 << 0  # HD, ORPHANHD
    HAS_ENTITIES_LOD = 1 << 1  # LOD, SLOD1
    HAS_ENTITIES_CONTAINER_LOD = 1 << 2  # SLOD2, SLOD3, SLOD4
    HAS_MLO_INSTANCE = 1 << 3
    HAS_BLOCK_DESCRIPTION = 1 << 4
    HAS_OCCLUDERS = 1 << 5
    HAS_PHYSICS = 1 << 6
    HAS_LOD_LIGHTS = 1 << 7
    HAS_DISTANT_LOD_LIGHTS = 1 << 8
    HAS_ENTITIES_CRITICAL = 1 << 9
    HAS_INSTANCED_DATA = 1 << 10

    if sys.version_info < (3, 11):

        def __iter__(self):
            for flag in MapContentFlags:
                if flag in self:
                    yield flag


@dataclass(slots=True)
class MapTimeCycleModifier:
    name: str
    extents: tuple[Vector, Vector]
    percentage: float
    range: float
    start_hour: int
    end_hour: int


class MapCarGeneratorFlags(Flag):
    FORCE_SPAWN = 1 << 0
    IGNORE_DENSITY = 1 << 1
    POLICE = 1 << 2
    FIRETRUCK = 1 << 3
    AMBULANCE = 1 << 4
    DURING_DAY = 1 << 5
    AT_NIGHT = 1 << 6
    ALIGN_LEFT = 1 << 7
    ALIGN_RIGHT = 1 << 8
    SINGLE_PLAYER = 1 << 9
    NETWORK_PLAYER = 1 << 10
    LOW_PRIORITY = 1 << 11
    PREVENT_ENTRY = 1 << 12

    if sys.version_info < (3, 11):

        def __iter__(self):
            for flag in MapCarGeneratorFlags:
                if flag in self:
                    yield flag


class MapCarGeneratorCreationRule(Enum):
    ALL = 0
    ONLY_SPORTS = 1
    NO_SPORTS = 2
    ONLY_BIG = 3
    NO_BIG = 4
    ONLY_BIKES = 5
    NO_BIKES = 6
    ONLY_DELIVERY = 7
    NO_DELIVERY = 8
    BOATS = 9
    ONLY_POOR = 10
    NO_POOR = 11
    CAN_BE_BROKEN_DOWN = 12


@dataclass(slots=True)
class MapCarGenerator:
    position: Vector
    orient_x: float
    orient_y: float
    perpendicular_length: float
    car_model: str
    flags: MapCarGeneratorFlags
    creation_rule: MapCarGeneratorCreationRule
    body_color_remap_1: int
    body_color_remap_2: int
    body_color_remap_3: int
    body_color_remap_4: int
    pop_group: str
    livery: int

    @property
    def body_color_remap(self) -> tuple[int, int, int, int]:
        return self.body_color_remap_1, self.body_color_remap_2, self.body_color_remap_3, self.body_color_remap_4

    @body_color_remap.setter
    def body_color_remap(self, v: tuple[int, int, int, int]):
        self.body_color_remap_1, self.body_color_remap_2, self.body_color_remap_3, self.body_color_remap_4 = v


MAP_GRASS_INSTANCES_DTYPE = np.dtype(
    [
        ("Position", np.uint16, (3,)),
        ("Normal", np.uint8, (2,)),
        ("Color", np.uint8, (3,)),
        ("Scale", np.uint8),
        ("Ao", np.uint8),
    ]
)

MAP_GRASS_INSTANCES_UNPACKED_DTYPE = np.dtype(
    [
        ("Position", np.float32, (3,)),
        ("Normal", np.float32, (2,)),
        ("Color", np.float32, (3,)),
        ("Scale", np.float32),
        ("Ao", np.float32),
    ]
)


@dataclass(slots=True)
class MapGrassInstanceList:
    extents: tuple[Vector, Vector]
    scale_range: Vector
    archetype_name: str
    lod_dist: int
    lod_fade_start_dist: float
    lod_inst_fade_range: float
    orient_to_terrain: float
    instances: np.ndarray  # array of MAP_GRASS_INSTANCES_DTYPE

    def unpack_instances(self) -> np.ndarray:  # array of MAP_GRASS_INSTANCES_UNPACKED_DTYPE
        packed = self.instances
        emin, emax = np.array(self.extents)
        size = emax - emin

        unpacked = np.empty_like(packed, dtype=MAP_GRASS_INSTANCES_UNPACKED_DTYPE)
        unpacked["Position"] = emin + ((packed["Position"] / 65535) * size)
        unpacked["Normal"] = packed["Normal"] / 255 * 2.0 - 1.0
        unpacked["Color"] = packed["Color"] / 255
        unpacked["Scale"] = packed["Scale"] / 255
        unpacked["Ao"] = packed["Ao"] / 255
        return unpacked

    def pack_instances(self, unpacked_instances: np.ndarray):  # array of MAP_GRASS_INSTANCES_UNPACKED_DTYPE
        # TODO(ymap): test grass pack_instances
        unpacked = unpacked_instances
        emin = np.min(unpacked["Position"], axis=0)
        emax = np.max(unpacked["Position"], axis=0)
        size = emax - emin

        packed = np.empty_like(unpacked, dtype=MAP_GRASS_INSTANCES_DTYPE)
        packed["Position"] = (unpacked["Position"] - emin) / size * 65535
        packed["Normal"] = (unpacked["Normal"] + 1.0) / 2.0 * 255
        packed["Color"] = unpacked["Color"] * 255
        packed["Scale"] = unpacked["Scale"] * 255
        packed["Ao"] = unpacked["Ao"] * 255

        self.instances = packed
        self.extents = Vector(emin), Vector(emax)


@dataclass(slots=True)
class MapBoxOccluder:
    center_x: int
    center_y: int
    center_z: int
    length: int
    width: int
    height: int
    cos_z: int
    sin_z: int

    @property
    def center(self) -> Vector:
        return Vector((self.center_x * 0.25, self.center_y * 0.25, self.center_z * 0.25))

    @center.setter
    def center(self, v: Vector):
        self.center_x = int(v.x * 4.0)
        self.center_y = int(v.y * 4.0)
        self.center_z = int(v.z * 4.0)

    @property
    def size(self) -> Vector:
        return Vector((self.length * 0.25, self.width * 0.25, self.height * 0.25))

    @size.setter
    def size(self, v: Vector) -> Vector:
        self.length = int(v.x * 4.0)
        self.width = int(v.y * 4.0)
        self.height = int(v.z * 4.0)

    @property
    def cos_sin_z(self) -> tuple[float, float]:
        return self.cos_z / 16384.0, self.sin_z / 16384.0

    @cos_sin_z.setter
    def cos_sin_z(self, v: tuple[float, float]):
        self.cos_z = int(v[0] * 16384.0)
        self.sin_z = int(v[1] * 16384.0)


class MapModelOccluderFlags(Flag):
    WATER_ONLY = 1 << 0

    if sys.version_info < (3, 11):

        def __iter__(self):
            for flag in MapModelOccluderFlags:
                if flag in self:
                    yield flag


@dataclass(slots=True)
class MapModelOccluder:
    flags: MapModelOccluderFlags
    vertices: np.ndarray
    indices: np.ndarray


class MapLodLightCategory(Enum):
    SMALL = 0
    MEDIUM = 1
    LARGE = 2


MAP_LOD_LIGHT_DTYPE = np.dtype(
    [
        ("Direction", np.float32, (3,)),
        ("Falloff", np.float32),
        ("FalloffExponent", np.float32),
        ("TimeAndStateFlags", np.uint32),
        ("Hash", np.uint32),
        ("ConeInnerAngle", np.uint8),
        ("ConeOuterAngleOrCapExt", np.uint8),
        ("CoronaIntensity", np.uint8),
    ]
)

MAP_DISTANT_LOD_LIGHT_DTYPE = np.dtype(
    [
        ("Position", np.float32, (3,)),
        ("RGBI", np.uint8, (4,)),
    ]
)


@dataclass(slots=True)
class MapLodLights:
    lights: np.ndarray  # array of MAP_LOD_LIGHT_DTYPE


@dataclass(slots=True)
class MapDistantLodLights:
    lights: np.ndarray  # array of MAP_DISTANT_LOD_LIGHT_DTYPE
    num_street_lights: int
    category: MapLodLightCategory


@dataclass(slots=True)
class MapBlockDescription:
    version: int
    flags: int
    name: str
    exported_by: str
    owner: str
    time: str


@dataclass(slots=True)
class AssetMapData:
    ASSET_GAME: AssetGame = AssetGame.GTA5
    ASSET_TYPE: AssetType = AssetType.MAP_DATA

    name: str = ""
    parent_name: str = ""
    flags: MapFlags = MapFlags(0)
    content_flags: MapContentFlags = MapContentFlags(0)
    streaming_extents: tuple[Vector, Vector] = (Vector((0, 0, 0)), Vector((0, 0, 0)))
    entities_extents: tuple[Vector, Vector] = (Vector((0, 0, 0)), Vector((0, 0, 0)))
    entities: list[MapEntity] = field(default_factory=list)
    physics_dictionaries: list[str] = field(default_factory=list)
    timecycle_modifiers: list[MapTimeCycleModifier] = field(default_factory=list)
    car_generators: list[MapCarGenerator] = field(default_factory=list)
    grass_instance_lists: list[MapGrassInstanceList] = field(default_factory=list)
    box_occluders: list[MapBoxOccluder] = field(default_factory=list)
    model_occluders: list[MapModelOccluder] = field(default_factory=list)
    lod_lights: MapLodLights | None = None
    distant_lod_lights: MapDistantLodLights | None = None
    description: MapBlockDescription | None = None
