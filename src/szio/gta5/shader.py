import json
import os
import xml.etree.ElementTree as ET

from ..shader import (  # noqa: F401
    ShaderDefFlag,
    ShaderParameterDef,
    ShaderParameterType,
    ShaderParameterUiHint,
)
from ..shader import ShaderDef as _ShaderDefBase
from ..shader import ShaderManager as _ShaderManagerBase
from ..types import Vector
from . import jenkhash


class ShaderDef(_ShaderDefBase):
    __slots__ = ()

    @property
    def filename(self) -> str:
        """Deprecated, use `preset_name` instead."""
        return self.preset_name


def _parse_parameter(element: ET.Element) -> ShaderParameterDef:
    attribs = element.attrib
    ui_hint = attribs.get("subtype", None)
    min_value = attribs.get("min", None)
    max_value = attribs.get("max", None)
    param = ShaderParameterDef(
        name=attribs["name"],
        type=ShaderParameterType(attribs["type"]),
        ui_hint=ShaderParameterUiHint(ui_hint) if ui_hint is not None else None,
        hidden=attribs.get("hidden", "").lower() == "true",
        count=int(attribs.get("count", 0)),
        min=float(min_value) if min_value is not None else None,
        max=float(max_value) if max_value is not None else None,
    )
    if param.is_texture:
        uv = attribs.get("uv", None)
        param.uv = int(uv) if uv is not None else None
    elif any(c in attribs for c in "xyzw"):
        # Shaders.xml gives arrays and matrices no default.
        param.default = Vector([float(attribs.get(c, 0.0)) for c in "xyzw"])
    return param


def _parse_flags(element: ET.Element | None) -> ShaderDefFlag:
    if element is None or not element.text:
        return ShaderDefFlag(0)

    flags = ShaderDefFlag(0)
    for name in element.text.split():
        if name not in ShaderDefFlag.__members__:
            raise ValueError(f"Unknown shader flag '{name}'")
        flags |= ShaderDefFlag[name]
    return flags


class ShaderManager(_ShaderManagerBase):
    shaderxml = os.path.join(os.path.dirname(__file__), "Shaders.xml")

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
            flags = _parse_flags(node.find("Flags"))
            parameters = [_parse_parameter(p) for p in node.findall("./Parameters/Item")]
            layouts = [frozenset(field.tag for field in item) for item in node.findall("./Layout/Item")]

            for filename_elem in node.findall("./FileName//*"):
                filename = filename_elem.text

                if filename is None:
                    continue

                shader = ShaderDef(
                    base_name=base_name,
                    preset_name=filename,
                    render_bucket=int(filename_elem.attrib["bucket"]),
                    flags=flags,
                    parameters=parameters,
                    layouts=layouts,
                )
                ShaderManager._register(shader)

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
    def generate_gen9_texture_name_mapping():
        from . import native

        assert native.IS_BACKEND_AVAILABLE
        from collections import defaultdict

        from pymateria.gta5 import gen8, gen9

        texture_map = defaultdict(set)
        texture_with_shader_map = defaultdict(lambda: defaultdict(set))
        for shader in ShaderManager.shaders():
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
        for shader in ShaderManager.shaders():
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
