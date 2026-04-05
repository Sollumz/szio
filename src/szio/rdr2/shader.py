import os
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from enum import Enum, Flag, auto

from ..xml import (
    AttributeProperty,
    ElementProperty,
    ElementTree,
    ListProperty,
)
from .. import jenkhash


class ShaderParameterType(str, Enum):
    TEXTURE = "Texture"
    FLOAT = "float"
    FLOAT2 = "float2"
    FLOAT3 = "float3"
    FLOAT4 = "float4"
    FLOAT4X4 = "float4x4"
    SAMPLER = "Sampler"
    CBUFFER = "CBuffer"
    UNKNOWN = "Unknown"


class ShaderParameterSubtype(str, Enum):
    RGB = "rgb"
    RGBA = "rgba"
    BOOL = "bool"


class ShaderParameterDef(ElementTree, ABC):
    tag_name = "Item"

    @property
    @abstractmethod
    def type() -> ShaderParameterType:
        raise NotImplementedError

    def __init__(self):
        super().__init__()
        self.name = AttributeProperty("name")
        self.type = AttributeProperty("type", self.type)
        self.subtype = AttributeProperty("subtype")
        self.hidden = AttributeProperty("hidden", False)


class ShaderParameterTextureDef(ShaderParameterDef):
    type = ShaderParameterType.TEXTURE

    def __init__(self):
        super().__init__()
        self.uv = AttributeProperty("uv")


class ShaderParameterFloatVectorDef(ShaderParameterDef, ABC):
    def __init__(self):
        super().__init__()
        self.count = AttributeProperty("count", 0)

    @property
    def is_array(self):
        return self.count > 0


class ShaderParameterFloatDef(ShaderParameterFloatVectorDef):
    type = ShaderParameterType.FLOAT

    def __init__(self):
        super().__init__()
        self.x = AttributeProperty("x", 0.0)


class ShaderParameterFloat2Def(ShaderParameterFloatVectorDef):
    type = ShaderParameterType.FLOAT2

    def __init__(self):
        super().__init__()
        self.x = AttributeProperty("x", 0.0)
        self.y = AttributeProperty("y", 0.0)


class ShaderParameterFloat3Def(ShaderParameterFloatVectorDef):
    type = ShaderParameterType.FLOAT3

    def __init__(self):
        super().__init__()
        self.x = AttributeProperty("x", 0.0)
        self.y = AttributeProperty("y", 0.0)
        self.z = AttributeProperty("z", 0.0)


class ShaderParameterFloat4Def(ShaderParameterFloatVectorDef):
    type = ShaderParameterType.FLOAT4

    def __init__(self):
        super().__init__()
        self.x = AttributeProperty("x", 0.0)
        self.y = AttributeProperty("y", 0.0)
        self.z = AttributeProperty("z", 0.0)
        self.w = AttributeProperty("w", 0.0)


class ShaderParameterFloat4x4Def(ShaderParameterDef):
    type = ShaderParameterType.FLOAT4X4

    def __init__(self):
        super().__init__()


class ShaderParameterSamplerDef(ShaderParameterDef):
    type = ShaderParameterType.SAMPLER

    def __init__(self):
        super().__init__()
        self.x = AttributeProperty("sampler", 0)
        self.index = AttributeProperty("index", 0)


class ShaderParameterCBufferDef(ShaderParameterDef):
    type = ShaderParameterType.CBUFFER

    def __init__(self):
        super().__init__()
        self.buffer = AttributeProperty("buffer", 0)
        self.length = AttributeProperty("length", 0)
        self.offset = AttributeProperty("offset", 0)
        self.value_type = AttributeProperty("value_type", "")
        self.count = AttributeProperty("count", 0)


class ShaderParameteUnknownDef(ShaderParameterDef):
    type = ShaderParameterType.UNKNOWN

    def __init__(self):
        super().__init__()


class ShaderParameterDefsList(ListProperty):
    list_type = ShaderParameterDef
    tag_name = "Parameters"

    @staticmethod
    def from_xml(element: ET.Element):
        new = ShaderParameterDefsList()

        for child in element.iter():
            if "type" in child.attrib:
                param_type = child.get("type")
                match param_type:
                    case ShaderParameterType.TEXTURE:
                        param = ShaderParameterTextureDef.from_xml(child)
                    case ShaderParameterType.FLOAT:
                        param = ShaderParameterFloatDef.from_xml(child)
                    case ShaderParameterType.FLOAT2:
                        param = ShaderParameterFloat2Def.from_xml(child)
                    case ShaderParameterType.FLOAT3:
                        param = ShaderParameterFloat3Def.from_xml(child)
                    case ShaderParameterType.FLOAT4:
                        param = ShaderParameterFloat4Def.from_xml(child)
                    case ShaderParameterType.FLOAT4X4:
                        param = ShaderParameterFloat4x4Def.from_xml(child)
                    case ShaderParameterType.SAMPLER:
                        param = ShaderParameterSamplerDef.from_xml(child)
                    case ShaderParameterType.CBUFFER:
                        param = ShaderParameterCBufferDef.from_xml(child)
                        attribs = child.attrib
                        match param.value_type:
                            case ShaderParameterType.FLOAT:
                                param.x = float(attribs["x"])
                            case ShaderParameterType.FLOAT2:
                                param.x = float(attribs["x"])
                                param.y = float(attribs["y"])
                            case ShaderParameterType.FLOAT3:
                                param.x = float(attribs["x"])
                                param.y = float(attribs["y"])
                                param.z = float(attribs["z"])
                            case ShaderParameterType.FLOAT4:
                                if "count" in attribs:
                                    param.count = int(attribs["count"])
                                else:
                                    param.count = 0
                                    param.x = float(attribs["x"])
                                    param.y = float(attribs["y"])
                                    param.z = float(attribs["z"])
                                    param.w = float(attribs["w"])
                    case ShaderParameterType.UNKNOWN:
                        param = ShaderParameteUnknownDef.from_xml(child)
                    case _:
                        assert False, f"Unknown shader parameter type '{param_type}'"

                new.value.append(param)

        return new


class SemanticsList(ElementTree):
    tag_name = "Semantics"

    def __init__(self) -> None:
        super().__init__()
        self.values = []

    @staticmethod
    def from_xml(element: ET.Element):
        new = SemanticsList()
        for child in element.findall("Item"):
            new.values.append(child.text)
        return new


class ShaderDefFlag(Flag):
    IS_TERRAIN = auto()


class ShaderDefFlagProperty(ElementProperty):
    value_types = ShaderDefFlag

    def __init__(self, tag_name: str = "Flags", value: ShaderDefFlag = ShaderDefFlag(0)):
        super().__init__(tag_name, value)

    @staticmethod
    def from_xml(element: ET.Element):
        new = ShaderDefFlagProperty(element.tag)
        if element.text:
            text = element.text.split()
            for flag in text:
                if flag in ShaderDefFlag.__members__:
                    new.value = new.value | ShaderDefFlag[flag]
                else:
                    ShaderDefFlagProperty.read_value_error(element)

        return new

    def to_xml(self):
        element = ET.Element(self.tag_name)
        if len(self.value) > 0:
            element.text = " ".join(f.name for f in self.value)
        return element


class ShaderDef(ElementTree):
    tag_name = "Item"

    render_bucket: int
    uv_maps: dict[str, int]
    parameter_map: dict[str, ShaderParameterDef]
    parameter_ui_order: dict[str, int]

    def __init__(self):
        super().__init__()
        self.preset_name = ""
        self.base_name = ""
        self.flags = ShaderDefFlagProperty()
        self.render_bucket = 0
        self.render_bucket_flag = False
        self.buffer_size = []
        self.parameters = ShaderParameterDefsList("Params")
        self.semantics = SemanticsList()
        self.uv_maps = {}
        self.parameter_map = {}
        self.parameter_ui_order = {}

    @classmethod
    def from_xml(cls, element: ET.Element) -> "ShaderDef":
        new: ShaderDef = super().from_xml(element)
        new.uv_maps = {
            p.name: p.uv for p in new.parameters if p.type == ShaderParameterType.TEXTURE and p.uv is not None
        }
        new.parameter_map = {p.name: p for p in new.parameters}
        new.parameter_ui_order = {p.name: i for i, p in enumerate(new.parameters)}
        return new


class ShaderManager:
    shaderxml = os.path.join(os.path.dirname(__file__), "Shaders.xml")

    # Map shader filenames to base shader names
    _shaders: dict[str, ShaderDef] = {}
    _shaders_by_hash: dict[int, ShaderDef] = {}
    _shaders_by_base_name_and_rb: dict[(str, int), ShaderDef] = {}
    _shaders_by_base_name_hash_and_rb: dict[(int, int), ShaderDef] = {}

    rdr_standard_2lyr = [
        "standard_2lyr",
        "standard_2lyr_ground",
        "standard_2lyr_pxm",
        "standard_2lyr_pxm_ground",
        "standard_2lyr_tnt",
        "campfire_standard_2lyr",
    ]

    @staticmethod
    def load_shaders():
        tree = ET.parse(ShaderManager.shaderxml)

        # Just to register strings from shaders to hash resolver
        from ..gta5 import native

        if native.IS_BACKEND_AVAILABLE:
            from pymateria.gta5 import HashResolver

            hash_resolver = HashResolver.instance

        for node in tree.getroot():
            base_name = node.find("Name").text
            base_name_hash = jenkhash.hash_string(base_name)

            buffer_size = node.find("BufferSizes").text
            if buffer_size is not None:
                buffer_size = tuple(int(x) for x in node.find("BufferSizes").text.split(" "))

            render_bucket = node.find("DrawBucket").text.split(" ")
            render_bucket = sorted([int(x, 16) for x in render_bucket])

            # Register a ShaderDef per render bucket, similar to how .sps files worked in GTA5
            for rb in render_bucket:
                preset_name = base_name
                rb_flag = (rb & 0x80) != 0
                rb &= 0x7F
                if len(render_bucket) > 1:
                    # If we have more than one render bucket, add a suffix to differentiate them
                    # TODO: might want to match these names to the .sps found in the game files.
                    #       Currently by just adding a suffix, they are close but not always the same.
                    if rb == 0:
                        suffix = ""
                    elif rb == 1:
                        suffix = "_alpha"
                    elif rb == 2:
                        suffix = "_decal"
                    elif rb == 3:
                        suffix = "_cutout"
                    elif rb == 4:
                        suffix = "_nosplash"
                    elif rb == 5:
                        suffix = "_nowater"
                    else:
                        assert "Unsupported render bucket for suffix"

                    preset_name += suffix

                preset_name_hash = jenkhash.hash_string(preset_name)

                shader = ShaderDef.from_xml(node)
                shader.base_name = base_name
                shader.preset_name = preset_name
                shader.render_bucket = rb
                shader.render_bucket_flag = rb_flag

                assert preset_name not in ShaderManager._shaders, (
                    f"Shader definition '{preset_name}' already registered"
                )
                ShaderManager._shaders[preset_name] = shader
                ShaderManager._shaders_by_hash[preset_name_hash] = shader
                ShaderManager._shaders_by_base_name_and_rb[(base_name, rb)] = shader
                ShaderManager._shaders_by_base_name_hash_and_rb[(base_name_hash, rb)] = shader

                if native.IS_BACKEND_AVAILABLE:
                    hash_resolver.add_string(preset_name)
                    for p in shader.parameters:
                        hash_resolver.add_string(p.name)

    @staticmethod
    def find_shader(filename: str) -> ShaderDef | None:
        shader = ShaderManager._shaders.get(filename, None)
        if shader is None and filename.startswith("hash_"):
            filename_hash = int(filename[5:], 16)
            shader = ShaderManager._shaders_by_hash.get(filename_hash, None)
        return shader

    @staticmethod
    def find_shader_preset_name(base_name: str, render_bucket: int) -> str | None:
        shader = ShaderManager._shaders_by_base_name_and_rb.get((base_name, render_bucket), None)
        if shader is None and base_name.startswith("hash_"):
            base_name_hash = int(base_name[5:], 16)
            shader = ShaderManager._shaders_by_base_name_hash_and_rb.get((base_name_hash, render_bucket), None)

        return shader.preset_name if shader is not None else None


ShaderManager.load_shaders()
