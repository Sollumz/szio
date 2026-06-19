import sys
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum, Flag
from typing import Protocol, runtime_checkable

from ..types import Quaternion, Vector
from .extensions import Extension


class EntityFlags(Flag):
    ALLOW_FULL_ROTATION = 1 << 0
    STREAM_LOW_PRIORITY = 1 << 1
    DISABLE_EMBEDDED_COLLISIONS = 1 << 2
    LOD_IN_PARENT_MAP = 1 << 3
    LOD_ADOPT_ME = 1 << 4
    IS_STATIC = 1 << 5
    IS_INTERIOR_LOD = 1 << 6
    UNUSED_7 = 1 << 7
    UNUSED_8 = 1 << 8
    UNUSED_9 = 1 << 9
    UNUSED_10 = 1 << 10
    UNUSED_11 = 1 << 11
    UNUSED_12 = 1 << 12
    UNUSED_13 = 1 << 13
    UNUSED_14 = 1 << 14
    LOD_USE_ALT_FADE = 1 << 15
    UNUSED_16 = 1 << 16
    DOES_NOT_TOUCH_WATER = 1 << 17
    DOES_NOT_SPAWN_PEDS = 1 << 18
    CAST_STATIC_SHADOWS = 1 << 19
    CAST_DYNAMIC_SHADOWS = 1 << 20
    IGNORE_DAY_NIGHT_SETTINGS = 1 << 21
    DONT_RENDER_IN_SHADOWS = 1 << 22
    ONLY_RENDER_IN_SHADOWS = 1 << 23
    DONT_RENDER_IN_REFLECTIONS = 1 << 24
    ONLY_RENDER_IN_REFLECTIONS = 1 << 25
    DONT_RENDER_IN_WATER_REFLECTIONS = 1 << 26
    ONLY_RENDER_IN_WATER_REFLECTIONS = 1 << 27
    DONT_RENDER_IN_MIRROR_REFLECTIONS = 1 << 28
    ONLY_RENDER_IN_MIRROR_REFLECTIONS = 1 << 29
    UNUSED_30 = 1 << 30
    UNUSED_31 = 1 << 31

    if sys.version_info < (3, 11):

        def __iter__(self):
            for flag in EntityFlags:
                if flag in self:
                    yield flag


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


@dataclass(slots=True)
class Entity:
    archetype_name: str
    position: Vector
    rotation: Quaternion
    scale_xy: float
    scale_z: float
    flags: EntityFlags
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


class EntityMloInstanceFlags(Flag):
    TURN_ON_GPS = 1 << 0
    CAP_ENTITIES_ALPHA = 1 << 1
    SHORT_FADE_DISTANCE = 1 << 2


@dataclass(slots=True)
class EntityMloInstance(Entity):
    group_id: int
    floor_id: int
    default_entity_sets: list[str]
    num_exit_portals: int
    mlo_inst_flags: EntityMloInstanceFlags


MloEntity = Entity
MapEntity = Entity | EntityMloInstance
