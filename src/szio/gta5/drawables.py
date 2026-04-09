import sys
from dataclasses import dataclass, field
from enum import Enum, IntEnum, IntFlag
from typing import NamedTuple

import numpy as np
from numpy.typing import NDArray

from ..assets import AssetGame
from ..types import DataSource, Matrix, Quaternion, Vector
from .assets import AssetType
from .bounds import AssetBound
from .textures import EmbeddedTexture


class SkelBoneFlags(IntFlag):
    ROTATE_X = 1 << 0
    ROTATE_Y = 1 << 1
    ROTATE_Z = 1 << 2
    HAS_ROTATE_LIMITS = 1 << 3
    TRANSLATE_X = 1 << 4
    TRANSLATE_Y = 1 << 5
    TRANSLATE_Z = 1 << 6
    HAS_TRANSLATE_LIMITS = 1 << 7
    SCALE_X = 1 << 8
    SCALE_Y = 1 << 9
    SCALE_Z = 1 << 10
    HAS_SCALE_LIMITS = 1 << 11
    HAS_CHILD = 1 << 12

    if sys.version_info < (3, 11):

        def __iter__(self):
            for flag in SkelBoneFlags:
                if flag in self:
                    yield flag


@dataclass(slots=True)
class SkelBoneTranslationLimit:
    min: Vector
    max: Vector


@dataclass(slots=True)
class SkelBoneRotationLimit:
    min: Vector
    max: Vector


@dataclass(slots=True)
class SkelBone:
    name: str
    tag: int
    flags: SkelBoneFlags
    position: Vector
    rotation: Quaternion
    scale: Vector
    parent_index: int
    translation_limit: SkelBoneTranslationLimit | None
    rotation_limit: SkelBoneRotationLimit | None


@dataclass(slots=True)
class Skeleton:
    bones: list[SkelBone]


class RenderBucket(IntEnum):
    OPAQUE = 0
    ALPHA = 1
    DECAL = 2
    CUTOUT = 3
    NO_SPLASH = 4
    NO_WATER = 5
    WATER = 6
    DISPLACEMENT_ALPHA = 7


@dataclass(slots=True)
class ShaderParameter:
    name: str
    value: Vector | list[Vector] | str | None  # str | None is texture reference

    def __hash__(self):
        v = self.value
        # Make sure value is hashable
        if isinstance(v, Vector):
            v = tuple(v)

        if isinstance(v, list):
            v = tuple(tuple(vv) for vv in v)
        return hash((self.name, v))


@dataclass(slots=True)
class ShaderInst:
    name: str
    preset_filename: str | None
    render_bucket: RenderBucket
    parameters: list[ShaderParameter]

    # Hash to be able to use an instance as key in dicts
    def __hash__(self):
        return hash((self.name, self.preset_filename, self.render_bucket, tuple(self.parameters)))


@dataclass(slots=True)
class ShaderGroup:
    shaders: list[ShaderInst]
    embedded_textures: dict[str, EmbeddedTexture]


class LodLevel(IntEnum):
    HIGH = 0
    MEDIUM = 1
    LOW = 2
    VERYLOW = 3


class VertexDataType(Enum):
    DEFAULT = 0x7755555555996996
    ENV_CLOTH = 0x030000000199A006
    ENV_CLOTH_NO_TANGENT = 0x0300000001996006
    BREAKABLE_GLASS = 0x7655555555996996


STANDARD_VERTEX_ATTR_DTYPES = {
    "Position": ("Position", np.float32, 3),
    "BlendWeights": ("BlendWeights", np.uint32, 4),
    "BlendIndices": ("BlendIndices", np.uint32, 4),
    "Normal": ("Normal", np.float32, 3),
    "Colour0": ("Colour0", np.uint32, 4),
    "Colour1": ("Colour1", np.uint32, 4),
    "TexCoord0": ("TexCoord0", np.float32, 2),
    "TexCoord1": ("TexCoord1", np.float32, 2),
    "TexCoord2": ("TexCoord2", np.float32, 2),
    "TexCoord3": ("TexCoord3", np.float32, 2),
    "TexCoord4": ("TexCoord4", np.float32, 2),
    "TexCoord5": ("TexCoord5", np.float32, 2),
    "TexCoord6": ("TexCoord6", np.float32, 2),
    "TexCoord7": ("TexCoord7", np.float32, 2),
    "Tangent": ("Tangent", np.float32, 4),
}
"""Expected vertex buffer types during import/export. Not actual formats found in the game files."""


@dataclass(slots=True)
class Geometry:
    vertex_data_type: VertexDataType
    vertex_buffer: NDArray
    index_buffer: NDArray[np.uint]
    bone_ids: NDArray[np.uint]
    shader_index: int


@dataclass(slots=True)
class Model:
    bone_index: int
    geometries: list[Geometry]
    render_bucket_mask: int
    has_skin: bool
    matrix_count: int
    flags: int


class LightFlashiness(Enum):
    CONSTANT = 0
    RANDOM = 1
    RANDOM_OVERRIDE_IF_WET = 2
    ONCE_PER_SECOND = 3
    TWICE_PER_SECOND = 4
    FIVE_PER_SECOND = 5
    RANDOM_FLASHINESS = 6
    OFF = 7
    UNUSED = 8
    ALARM = 9
    ON_WHEN_RAINING = 10
    CYCLE_1 = 11
    CYCLE_2 = 12
    CYCLE_3 = 13
    DISCO = 14
    CANDLE = 15
    PLANE = 16
    FIRE = 17
    THRESHOLD = 18
    ELECTRIC = 19
    STROBE = 20


class LightType(Enum):
    POINT = 1
    SPOT = 2
    CAPSULE = 4


@dataclass(slots=True)
class Light:
    light_type: LightType
    position: Vector
    direction: Vector
    tangent: Vector
    extent: Vector
    color: tuple[int, int, int]
    flashiness: LightFlashiness
    intensity: float
    flags: int
    time_flags: int
    bone_id: int
    group_id: int
    light_hash: int
    falloff: float
    falloff_exponent: float
    culling_plane_normal: Vector
    culling_plane_offset: float
    volume_intensity: float
    volume_size_scale: float
    volume_outer_color: tuple[int, int, int]
    volume_outer_intensity: float
    volume_outer_exponent: float
    corona_size: float
    corona_intensity: float
    corona_z_bias: float
    projected_texture_hash: str
    light_fade_distance: int
    shadow_fade_distance: int
    specular_fade_distance: int
    volumetric_fade_distance: int
    shadow_near_clip: float
    shadow_blur: int
    cone_inner_angle: float
    cone_outer_angle: float


@dataclass(slots=True)
class AssetDrawable:
    ASSET_GAME: AssetGame = AssetGame.GTA5
    ASSET_TYPE: AssetType = AssetType.DRAWABLE

    name: str = ""
    bounds: AssetBound | None = None
    skeleton: Skeleton | None = None
    shader_group: ShaderGroup | None = None
    models: dict[LodLevel, list[Model]] = field(default_factory=dict)
    lod_thresholds: dict[LodLevel, float] = field(default_factory=dict)
    lights: list[Light] = field(default_factory=list)


@dataclass(slots=True)
class AssetFragDrawable(AssetDrawable):
    frag_bound_matrix: Matrix = field(default_factory=Matrix)
    frag_extra_bound_matrices: list[Matrix] = field(default_factory=list)


@dataclass(slots=True)
class AssetDrawableDictionary:
    ASSET_GAME: AssetGame = AssetGame.GTA5
    ASSET_TYPE: AssetType = AssetType.DRAWABLE_DICTIONARY

    drawables: dict[str, AssetDrawable] = field(default_factory=dict)
