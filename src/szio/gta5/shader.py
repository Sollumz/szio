import json
import os
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from enum import Enum, Flag, auto
from typing import Optional

from ..xml import (
    AttributeProperty,
    ElementProperty,
    ElementTree,
    ListProperty,
    TextProperty,
)
from . import jenkhash
from .cwxml import VertexLayoutList


class FileNameList(ListProperty):
    class FileName(TextProperty):
        tag_name = "Item"

    list_type = FileName
    tag_name = "FileName"


class LayoutList(ListProperty):
    class Layout(VertexLayoutList):
        tag_name = "Item"

    list_type = Layout
    tag_name = "Layout"


class ShaderParameterType(str, Enum):
    TEXTURE = "Texture"
    FLOAT = "float"
    FLOAT2 = "float2"
    FLOAT3 = "float3"
    FLOAT4 = "float4"
    FLOAT4X4 = "float4x4"


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
                    case _:
                        assert False, f"Unknown shader parameter type '{param_type}'"

                new.value.append(param)

        return new


class ShaderDefFlag(Flag):
    IS_CLOTH = auto()
    IS_PED_CLOTH = auto()
    IS_TERRAIN = auto()
    IS_TERRAIN_MASK_ONLY = auto()


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
        self.layouts = LayoutList()
        self.parameters = ShaderParameterDefsList("Parameters")
        self.render_bucket = 0
        self.uv_maps = {}
        self.parameter_map = {}
        self.parameter_ui_order = {}

    @property
    def filename(self) -> str:
        """Deprecated, use `preset_name` instead."""
        return self.preset_name

    @property
    def required_tangent(self):
        for layout in self.layouts:
            if "Tangent" in layout.value:
                return True
        return False

    @property
    def required_normal(self):
        for layout in self.layouts:
            if "Normal" in layout.value:
                return True
        return False

    @property
    def used_texcoords(self) -> set[str]:
        names = set()
        for layout in self.layouts:
            for field_name in layout.value:
                if "TexCoord" in field_name:
                    names.add(field_name)

        return names

    @property
    def used_texcoords_indices(self) -> set[int]:
        indices = set()
        for layout in self.layouts:
            for field_name in layout.value:
                if "TexCoord" in field_name:
                    indices.add(int(field_name[8:]))

        return indices

    @property
    def used_colors(self) -> set[str]:
        names = set()
        for layout in self.layouts:
            for field_name in layout.value:
                if "Colour" in field_name:
                    names.add(field_name)

        return names

    @property
    def used_colors_indices(self) -> set[int]:
        indices = set()
        for layout in self.layouts:
            for field_name in layout.value:
                if "Colour" in field_name:
                    indices.add(int(field_name[6:]))

        return indices

    @property
    def is_uv_animation_supported(self) -> bool:
        return "globalAnimUV0" in self.parameter_map and "globalAnimUV1" in self.parameter_map

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
    def is_alpha(self) -> bool:
        return self.render_bucket == 1

    @property
    def is_decal(self) -> bool:
        return self.render_bucket == 2

    @property
    def is_cutout(self) -> bool:
        return self.render_bucket == 3

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

    _gen9_texture_name_mapping_file = os.path.join(os.path.dirname(__file__), "ShadersG9TextureNameMapping.json")
    _gen9_texture_name_forward_mapping = {}  # gen8 -> gen9
    _gen9_texture_name_backward_mapping = {}  # gen9 -> gen8

    _gen9_params_defaults_file = os.path.join(os.path.dirname(__file__), "ShadersG9ParamsDefaults.json")
    _gen9_params_defaults = {}  # gen8 -> gen9

    # Tint shaders that use colour1 instead of colour0 to index the tint palette
    tint_colour1_shaders = ["trees_normal_diffspec_tnt.sps", "trees_tnt.sps", "trees_normal_spec_tnt.sps"]
    palette_shaders = [
        "ped_palette.sps",
        "ped_default_palette.sps",
        "weapon_normal_spec_cutout_palette.sps",
        "weapon_normal_spec_detail_palette.sps",
        "weapon_normal_spec_palette.sps",
    ]
    em_shaders = [
        "normal_spec_emissive.sps",
        "normal_spec_reflect_emissivenight.sps",
        "emissive.sps",
        "emissive_speclum.sps",
        "emissive_tnt.sps",
        "emissivenight.sps",
        "emissivenight_geomnightonly.sps",
        "emissivestrong_alpha.sps",
        "emissivestrong.sps",
        "glass_emissive.sps",
        "glass_emissivenight.sps",
        "glass_emissivenight_alpha.sps",
        "glass_emissive_alpha.sps",
        "decal_emissive_only.sps",
        "decal_emissivenight_only.sps",
        "vehicle_blurredrotor_emissive.sps",
        "vehicle_dash_emissive.sps",
        "vehicle_dash_emissive_opaque.sps",
        "vehicle_paint4_emissive.sps",
        "vehicle_emissive_alpha.sps",
        "vehicle_emissive_opaque.sps",
        "vehicle_tire_emissive.sps",
        "vehicle_track_emissive.sps",
        "vehicle_track2_emissive.sps",
        "vehicle_track_siren.sps",
        "vehicle_lightsemissive.sps",
        "vehicle_lightsemissive_siren.sps",
    ]
    water_shaders = [
        "water_fountain.sps",
        "water_poolenv.sps",
        "water_decal.sps",
        "water_terrainfoam.sps",
        "water_riverlod.sps",
        "water_shallow.sps",
        "water_riverfoam.sps",
        "water_riverocean.sps",
        "water_rivershallow.sps",
    ]

    veh_paints = [
        "vehicle_paint1.sps",
        "vehicle_paint1_enveff.sps",
        "vehicle_paint2.sps",
        "vehicle_paint2_enveff.sps",
        "vehicle_paint3.sps",
        "vehicle_paint3_enveff.sps",
        "vehicle_paint3_lvr.sps",
        "vehicle_paint4.sps",
        "vehicle_paint4_emissive.sps",
        "vehicle_paint4_enveff.sps",
        "vehicle_paint5_enveff.sps",
        "vehicle_paint6.sps",
        "vehicle_paint6_enveff.sps",
        "vehicle_paint7.sps",
        "vehicle_paint7_enveff.sps",
        "vehicle_paint8.sps",
        "vehicle_paint9.sps",
    ]

    @staticmethod
    def load_shaders():
        tree = ET.parse(ShaderManager.shaderxml)

        from . import native

        if native.IS_BACKEND_AVAILABLE:
            from pymateria.gta5 import HashResolver

            hash_resolver = HashResolver.instance

        for node in tree.getroot():
            base_name = node.find("Name").text
            base_name_hash = jenkhash.hash_string(base_name)
            for filename_elem in node.findall("./FileName//*"):
                filename = filename_elem.text

                if filename is None:
                    continue

                filename_hash = jenkhash.hash_string(filename)
                render_bucket = int(filename_elem.attrib["bucket"])

                shader = ShaderDef.from_xml(node)
                shader.base_name = base_name
                shader.preset_name = filename
                shader.render_bucket = render_bucket

                assert filename not in ShaderManager._shaders, f"Shader definition '{filename}' already registered"
                ShaderManager._shaders[filename] = shader
                ShaderManager._shaders_by_hash[filename_hash] = shader
                # Don't overwrite presets with their gta_ alias presets (e.g spec.sps with gta_spec.sps). They are the same
                # shader but their non-gta_ preset name is more commonly used, so when looking up a preset by base name+render
                # bucket we want the non-gta_ one.
                if (
                    not filename.startswith("gta_")
                    or (base_name, render_bucket) not in ShaderManager._shaders_by_base_name_and_rb
                ):
                    ShaderManager._shaders_by_base_name_and_rb[(base_name, render_bucket)] = shader
                    ShaderManager._shaders_by_base_name_hash_and_rb[(base_name_hash, render_bucket)] = shader

                if native.IS_BACKEND_AVAILABLE:
                    hash_resolver.add_string(filename)
                    for p in shader.parameters:
                        hash_resolver.add_string(p.name)

    @staticmethod
    def load_gen9_texture_name_mapping():
        with open(ShaderManager._gen9_texture_name_mapping_file, "r", encoding="utf-8") as fp:
            mapping = json.load(fp)
            ShaderManager._gen9_texture_name_forward_mapping = mapping["forward"]
            ShaderManager._gen9_texture_name_backward_mapping = mapping["backward"]

    def _lookup_texture_name_mapping(mappings: dict, name: str, shader_name: str) -> str:
        # Lookup shader-specific mapping
        if (shader_mapping := mappings.get(shader_name, None)) and (other_name := shader_mapping.get(name, None)):
            return other_name

        # Fallbakc to generic mapping
        return mappings["<common>"][name]

    def lookup_texture_name_mapping_gen8_to_gen9(name_g8: str, shader_name: str) -> str:
        mappings = ShaderManager._gen9_texture_name_forward_mapping
        return ShaderManager._lookup_texture_name_mapping(mappings, name_g8, shader_name)

    def lookup_texture_name_mapping_gen9_to_gen8(name_g9: str, shader_name: str) -> str:
        mappings = ShaderManager._gen9_texture_name_backward_mapping
        return ShaderManager._lookup_texture_name_mapping(mappings, name_g9, shader_name)

    @staticmethod
    def find_shader(filename: str) -> Optional[ShaderDef]:
        shader = ShaderManager._shaders.get(filename, None)
        if shader is None and filename.startswith("hash_"):
            filename_hash = int(filename[5:], 16)
            shader = ShaderManager._shaders_by_hash.get(filename_hash, None)
        return shader

    @staticmethod
    def find_shader_preset_name(base_name: str, render_bucket: int) -> Optional[str]:
        shader = ShaderManager._shaders_by_base_name_and_rb.get((base_name, render_bucket), None)
        if shader is None and base_name.startswith("hash_"):
            base_name_hash = int(base_name[5:], 16)
            shader = ShaderManager._shaders_by_base_name_hash_and_rb.get((base_name_hash, render_bucket), None)

        return shader.preset_name if shader is not None else None

    @staticmethod
    def generate_gen9_texture_name_mapping():
        from . import native

        assert native.IS_BACKEND_AVAILABLE
        from collections import defaultdict

        from pymateria.gta5 import gen8, gen9

        texture_map = defaultdict(set)
        texture_with_shader_map = defaultdict(lambda: defaultdict(set))
        for shader in ShaderManager._shaders.values():
            shader_g8 = gen8.ShaderRegistry.instance.get_shader(shader.base_name)
            shader_g9 = gen9.ShaderRegistry.instance.get_shader(shader.base_name)

            tex_g8 = [loc.name for loc in shader_g8.locals if loc.type == gen8.ShaderVariableType.TEXTURE]
            tex_g9 = [res.name for res in shader_g9.resources if res.type == gen9.ShaderResourceType.TEXTURE]

            if "heightSampler" in tex_g8 and "heightTexture" in tex_g8:
                # for some reason the sampler and texture appear even though in gen8 only the sampler name is used
                tex_g8.remove("heightTexture")

            if "DiffuseExtraSampler" in tex_g8:
                # DiffuseExtraSampler got removed from gen9 shaders
                tex_g8.remove("DiffuseExtraSampler")

            if len(tex_g8) != len(tex_g9):
                print(f"========= mismatch in {shader.base_name} =======")
                print(f"{tex_g8=}")
                print(f"{tex_g9=}")
                print()
                continue

            for name_g8, name_g9 in zip(tex_g8, tex_g9):
                texture_map[name_g8].add(name_g9)
                texture_with_shader_map[name_g8][name_g9].add(shader.base_name)

        for name_g8, names_g9 in texture_map.items():
            if len(names_g9) != 1:
                print(f"'{name_g8}' found multiple names in gen9: {dict(texture_with_shader_map[name_g8])}")
                print()
                continue

        out_forward_texture_map = defaultdict(dict)
        out_backward_texture_map = defaultdict(dict)
        for name_g8, names_g9 in texture_map.items():
            if len(names_g9) == 1:
                # This gen8 texture name has a unique mapping in gen9, add to the the generic mapping
                name_g9 = next(iter(names_g9))
                out_forward_texture_map["<common>"][name_g8] = name_g9
                out_backward_texture_map["<common>"][name_g9] = name_g8
            else:
                # Otherwise, add shader-specific mappings
                for name_g9, shaders in texture_with_shader_map[name_g8].items():
                    for shader in shaders:
                        out_forward_texture_map[shader][name_g8] = name_g9
                        out_backward_texture_map[shader][name_g9] = name_g8

        # Include 'DiffuseExtraSampler' even though it doesn't exist in gen9 to avoid too many special cases when
        # looking up texture names
        out_forward_texture_map["<common>"]["DiffuseExtraSampler"] = "DiffuseExtraSampler"
        out_backward_texture_map["<common>"]["DiffuseExtraSampler"] = "DiffuseExtraSampler"

        with open(ShaderManager._gen9_texture_name_mapping_file, "w", newline="\n") as fp:
            json.dump(
                {"forward": out_forward_texture_map, "backward": out_backward_texture_map}, fp, indent=2, sort_keys=True
            )

    @staticmethod
    def build_gen9_shader_params_map() -> dict:
        """Create a dictionary containing the parameters of each shader, classified as common (appear in both gen8 and
        gen9), gen8-specific and gen9-specific.
        """
        from . import native

        assert native.IS_BACKEND_AVAILABLE
        from collections import defaultdict

        from pymateria.gta5 import gen8, gen9

        shader_map = defaultdict(dict)
        for shader in ShaderManager._shaders.values():
            shader_g8 = gen8.ShaderRegistry.instance.get_shader(shader.base_name)
            shader_g9 = gen9.ShaderRegistry.instance.get_shader(shader.base_name)

            fields_g8 = [loc.name.lower() for loc in shader_g8.locals if loc.type != gen8.ShaderVariableType.TEXTURE]
            fields_g9 = [field.name.lower() for buff in shader_g9.buffers for field in buff.fields.values()]

            semantics_g8 = {
                loc.name.lower(): loc.semantic.lower()
                for loc in shader_g8.locals
                if loc.type != gen8.ShaderVariableType.TEXTURE
            }
            semantics_g9 = {
                field.name.lower(): field.semantic.lower()
                for buff in shader_g9.buffers
                for field in buff.fields.values()
            }

            common = list(set(fields_g8) & set(fields_g9))
            common.sort()
            g8_only = list(set(fields_g8).difference(set(fields_g9)))
            g8_only.sort()
            g9_only = list(set(fields_g9).difference(set(fields_g8)))
            g9_only.sort()
            shader_map[shader.base_name]["common"] = common
            shader_map[shader.base_name]["gen8_only"] = g8_only
            shader_map[shader.base_name]["gen9_only"] = g9_only
            shader_map[shader.base_name]["semantics"] = semantics_g8 | semantics_g9

        # with open(os.path.join(os.path.dirname(__file__), "ShadersG9Params.json"), "w", newline="\n") as fp:
        #     json.dump(
        #         shader_map,
        #         fp, indent=2, sort_keys=True
        #     )

        return shader_map

    @staticmethod
    def generate_gen9_shader_params_defaults():
        """Search for the default value of gen9-specific parameters and verify that they always use the same value
        (i.e. there are no new user-defined parameters in gen9, these parameters are just result of different shader
        compilation pipeline that ended up including either unused values or values that were previously hardcoded).
        """
        import sqlite3
        from collections import defaultdict
        from contextlib import closing

        shader_map = ShaderManager.build_gen9_shader_params_map()

        gen9_params = defaultdict(dict)
        gen9_params_common = defaultdict(set)

        # This DB contains all instances of shader parameters in gen9 assets. Originates from the CSV generated by this
        # code, and converted to a SQLite DB:
        # https://github.com/alexguirre/CodeWalker/blob/1055b0d392a0196786b5abe8d23063c18f591346/CodeWalker.Core/GameFiles/GameFileCache.cs#L5789
        with closing(sqlite3.connect("D:\\re\\gta5\\db\\db.db")) as db:
            cur = db.cursor()

            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_shader_param ON gen9_shader_parameters (ShaderName, ParameterName)"
            )

            for shader in shader_map.keys():
                gen9_only = shader_map[shader]["gen9_only"]
                if not gen9_only:
                    continue

                semantics = shader_map[shader]["semantics"]
                for param in gen9_only:
                    param_semantic = semantics[param]
                    param_hash = str(jenkhash.name_to_hash(param))
                    param_semantic_hash = str(jenkhash.name_to_hash(param_semantic))

                    res = cur.execute(
                        "SELECT DISTINCT Data FROM gen9_shader_parameters "
                        "WHERE ShaderName = ? AND ParameterName IN (?, ?, ?, ?)",
                        (shader, param, param_semantic, param_hash, param_semantic_hash),
                    ).fetchall()

                    if not res:
                        print(f"FOUND NONE     {shader=} {param=}")
                        # Output:
                        #   FOUND NONE     shader='radar' param='hdrcoloradjustments'
                        # Let's ignore this parameter
                    elif len(res) > 1:
                        print(f"FOUND DISTINCT {shader=} {param=}  {res=}")
                        # Output:
                        #   FOUND DISTINCT shader='terrain_cb_w_4lyr_2tex_blend_pxm_spm' param='specularfalloffmult'  res=[('32 0 0 0',), ('10 0 0 0',), ('48 0 0 0',), ('20 0 0 0',), ('18 0 0 0',), ('15 0 0 0',), ('100 0 0 0',), ('32.1 0 0 0',)]
                        #   FOUND DISTINCT shader='terrain_cb_w_4lyr_pxm_spm' param='specularfalloffmult'  res=[('48 0 0 0',), ('32 0 0 0',)]
                        #
                        # These are a bit weird, '_spm' refers to specular map and they should use the
                        # 'specularFalloffMultSpecMap' parameter, not 'specularFalloffMult'. Possibly the different
                        # values are because this parameter was still editable by artists even though not used? Or from presets shared with other terrain shaders.
                        # Hopefully still unused in gen9.
                    else:
                        # print(f"FOUND UNIQUE   {shader=} {param=}  {res=}")
                        data = res[0][0]
                        data = data.replace("[", " ").replace("]", " ")
                        data = list(map(float, data.split()))
                        gen9_params[shader][param] = data
                        gen9_params_common[param].add(tuple(data))

        with open(ShaderManager._gen9_params_defaults_file, "w", newline="\n") as fp:
            s = json.dumps(gen9_params, indent=2, sort_keys=True)
            # Hack to output arrays in single line instead of value per line
            import re

            s = re.sub(r'": \[\s+', r'": [', s)
            s = re.sub(r"([0-9]),\s+", r"\1, ", s)
            s = re.sub(r"([0-9])\s+\]", r"\1]", s)

            fp.write(s)

    @staticmethod
    def load_gen9_shader_params_defaults():
        with open(ShaderManager._gen9_params_defaults_file, "r", encoding="utf-8") as fp:
            ShaderManager._gen9_params_defaults = json.load(fp)

    def lookup_gen9_shader_params_defaults(shader_name: str) -> dict:
        return ShaderManager._gen9_params_defaults.get(shader_name, {})


ShaderManager.load_shaders()

# Uncomment to generate ShadersG9TextureNameMapping.json again
# ShaderManager.generate_gen9_texture_name_mapping()
# Uncomment to generate ShadersG9ParamsDefaults.json again
# ShaderManager.generate_gen9_shader_params_defaults()

ShaderManager.load_gen9_texture_name_mapping()
ShaderManager.load_gen9_shader_params_defaults()
