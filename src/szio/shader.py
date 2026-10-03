import xml.etree.ElementTree as ET
from abc import ABC
from dataclasses import dataclass, field
from enum import Enum, Flag, auto
from typing import Iterable

from . import jenkhash
from .flags import FlagIterCompat
from .types import Vector


class ShaderParameterType(str, Enum):
    TEXTURE = "Texture"
    FLOAT = "float"
    FLOAT2 = "float2"
    FLOAT3 = "float3"
    FLOAT4 = "float4"
    FLOAT4X4 = "float4x4"


class ShaderParameterUiHint(str, Enum):
    """Editor hint for a parameter."""
    HIDDEN = "hidden"
    RGB = "rgb"
    RGBA = "rgba"
    BOOL = "bool"


_COMPONENT_COUNTS = {
    ShaderParameterType.TEXTURE: 0,
    ShaderParameterType.FLOAT: 1,
    ShaderParameterType.FLOAT2: 2,
    ShaderParameterType.FLOAT3: 3,
    ShaderParameterType.FLOAT4: 4,
    ShaderParameterType.FLOAT4X4: 4,
}


@dataclass(slots=True)
class ShaderParameterDef:
    name: str
    type: ShaderParameterType
    ui_order: int = 0
    ui_hint: ShaderParameterUiHint | None = None
    uv: int | None = None
    """UV map index used by a texture."""
    count: int = 0
    """Array length; 0 for a single value."""
    default: Vector | None = None
    min: float | None = None
    max: float | None = None

    @property
    def name_hash(self) -> int:
        return jenkhash.name_to_hash(self.name)

    @property
    def is_texture(self) -> bool:
        return self.type == ShaderParameterType.TEXTURE

    @property
    def is_array(self) -> bool:
        return self.count > 0

    @property
    def is_vector(self) -> bool:
        return not self.is_texture and not self.is_array and self.type != ShaderParameterType.FLOAT4X4

    @property
    def component_count(self) -> int:
        return _COMPONENT_COUNTS[self.type]

    @property
    def row_count(self) -> int:
        return 4 if self.type == ShaderParameterType.FLOAT4X4 else max(1, self.count)

    @property
    def hidden(self) -> bool:
        return self.ui_hint == ShaderParameterUiHint.HIDDEN


class ShaderDefFlag(FlagIterCompat, Flag):
    IS_CLOTH = auto()
    IS_PED_CLOTH = auto()
    IS_TERRAIN = auto()
    IS_TERRAIN_MASK_ONLY = auto()


@dataclass(slots=True)
class ShaderDef(ABC):
    base_name: str = ""
    preset_name: str = ""
    render_bucket: int = 0
    flags: ShaderDefFlag = ShaderDefFlag(0)
    parameters: list[ShaderParameterDef] = field(default_factory=list)
    layouts: list[frozenset[str]] = field(default_factory=list)
    """Vertex channels per layout variant, named as in `STANDARD_VERTEX_ATTR_DTYPES`."""

    _parameters_by_hash: dict[int, ShaderParameterDef] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )

    def __post_init__(self):
        by_hash: dict[int, ShaderParameterDef] = {}
        for i, p in enumerate(self.parameters):
            p.ui_order = i
            by_hash.setdefault(p.name_hash, p)
        self._parameters_by_hash = by_hash

    def get_parameter(self, name: str | int) -> ShaderParameterDef | None:
        """By hash or name. Case-insensitive and allows hash strings like `hash_B98434A7`."""
        return self._parameters_by_hash.get(name if isinstance(name, int) else jenkhash.name_to_hash(name))

    def has_parameter(self, name: str | int) -> bool:
        return self.get_parameter(name) is not None

    @property
    def is_alpha(self) -> bool:
        return self.render_bucket == 1

    @property
    def is_decal(self) -> bool:
        return self.render_bucket == 2

    @property
    def is_cutout(self) -> bool:
        return self.render_bucket == 3

    @property
    def is_cloth(self) -> bool:
        return ShaderDefFlag.IS_CLOTH in self.flags

    @property
    def is_ped_cloth(self) -> bool:
        return ShaderDefFlag.IS_PED_CLOTH in self.flags

    @property
    def is_terrain(self) -> bool:
        return ShaderDefFlag.IS_TERRAIN in self.flags

    @property
    def is_terrain_mask_only(self) -> bool:
        return ShaderDefFlag.IS_TERRAIN_MASK_ONLY in self.flags

    @property
    def is_uv_animation_supported(self) -> bool:
        return self.has_parameter("globalAnimUV0") and self.has_parameter("globalAnimUV1")

    @property
    def required_normal(self) -> bool:
        return any("Normal" in layout for layout in self.layouts)

    @property
    def required_tangent(self) -> bool:
        return any("Tangent" in layout for layout in self.layouts)

    @property
    def used_texcoords(self) -> set[str]:
        return {name for layout in self.layouts for name in layout if "TexCoord" in name}

    @property
    def used_texcoords_indices(self) -> set[int]:
        return {int(name[len("TexCoord") :]) for name in self.used_texcoords}

    @property
    def used_colors(self) -> set[str]:
        return {name for layout in self.layouts for name in layout if "Colour" in name}

    @property
    def used_colors_indices(self) -> set[int]:
        return {int(name[len("Colour") :]) for name in self.used_colors}


class ShaderManager:
    """Subclasses parse their game's Shaders.xml and `_register` each definition."""

    _shaders: dict[str, ShaderDef]
    _shaders_by_hash: dict[int, ShaderDef]
    _shaders_by_base_name_hash_and_rb: dict[tuple[int, int], ShaderDef]
    _shaders_by_base_name_hash: dict[int, ShaderDef]

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._shaders = {}
        cls._shaders_by_hash = {}
        cls._shaders_by_base_name_hash_and_rb = {}
        cls._shaders_by_base_name_hash = {}

    @classmethod
    def _register(cls, shader: ShaderDef) -> None:
        preset_name = shader.preset_name
        assert preset_name not in cls._shaders, f"Shader definition '{preset_name}' already registered"
        cls._shaders[preset_name] = shader
        cls._shaders_by_hash[jenkhash.name_to_hash(preset_name)] = shader

        # When multiple presets share the same base shader and render bucket, the first one listed in
        # Shaders.xml is the canonical/most common one (e.g. vehicle_vehglass.sps before vehicle_lights.sps,
        # spec.sps before its gta_spec.sps alias), so use `setdefault` to keep the first registered entry
        # for base name+render bucket lookups.
        base_name_hash = jenkhash.name_to_hash(shader.base_name)
        cls._shaders_by_base_name_hash_and_rb.setdefault((base_name_hash, shader.render_bucket), shader)
        cls._shaders_by_base_name_hash.setdefault(base_name_hash, shader)

    @classmethod
    def _parse_layouts(cls, node: ET.Element) -> list[frozenset[str]]:
        """Reads a Shaders.xml `<Layouts>` block."""
        return [frozenset(item.text.split()) for item in node.findall("./Layouts/Item") if item.text]

    @classmethod
    def shaders(cls) -> Iterable[ShaderDef]:
        return cls._shaders.values()

    @classmethod
    def find_shader(cls, preset_name: str) -> ShaderDef | None:
        shader = cls._shaders.get(preset_name, None)
        if shader is None:
            shader = cls._shaders_by_hash.get(jenkhash.name_to_hash(preset_name), None)
        return shader

    @classmethod
    def find_shader_by_base_name(cls, base_name: str, render_bucket: int | None = None) -> ShaderDef | None:
        base_name_hash = jenkhash.name_to_hash(base_name)
        if render_bucket is not None:
            return cls._shaders_by_base_name_hash_and_rb.get((base_name_hash, int(render_bucket)), None)

        return cls._shaders_by_base_name_hash.get(base_name_hash, None)

    @classmethod
    def find_shader_preset_name(cls, base_name: str, render_bucket: int | None = None) -> str | None:
        shader = cls.find_shader_by_base_name(base_name, render_bucket)
        return shader.preset_name if shader is not None else None
