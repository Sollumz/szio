import ctypes
import itertools
import logging

import numpy as np
import pymateria as pma
import pymateria.gta5 as pm
import pymateria.gta5.gen9 as pmg9

from ....types import DataSource, Matrix, Vector
from ... import jenkhash
from ...assets import (
    AssetVersion,
)
from ...drawables import (
    AssetDrawable,
    AssetDrawableDictionary,
    AssetFragDrawable,
    EmbeddedTexture,
    Geometry,
    LodLevel,
    Model,
    RenderBucket,
    ShaderGroup,
    ShaderInst,
    ShaderParameter,
    VertexDataType,
)
from ...shader import ShaderManager
from ._utils import (
    _h2s,
    _s2h,
    from_native_mat34,
    make_checkerboard_texture_data,
    to_native_mat34,
)
from .bound import save_bound_to_native
from .drawable import (
    _DEFAULT_LOD_THRESHOLDS,
    _import_dds_g8,
    _load_lights_native,
    _load_lod_thresholds_native,
    _load_skeleton_native,
    _save_lights_native,
    _save_skeleton_native,
)

_VB_CHANNEL_NAMES_MAP = {
    "POSITION0": "Position",
    "BLEND_WEIGHT0": "BlendWeights",
    "BLEND_INDICES0": "BlendIndices",
    "NORMAL0": "Normal",
    "COLOR0": "Colour0",
    "COLOR1": "Colour1",
    "TEXCOORD0": "TexCoord0",
    "TEXCOORD1": "TexCoord1",
    "TEXCOORD2": "TexCoord2",
    "TEXCOORD3": "TexCoord3",
    "TEXCOORD4": "TexCoord4",
    "TEXCOORD5": "TexCoord5",
    "TEXCOORD6": "TexCoord6",
    "TEXCOORD7": "TexCoord7",
    "TANGENT0": "Tangent",
}

_VB_CHANNEL_NAMES_INVERSE_MAP = {v: k for k, v in _VB_CHANNEL_NAMES_MAP.items()}

_VERTEX_FORMATS = {
    pmg9.FvfChannel.POSITION0: pmg9.BufferFormat.R32G32B32_FLOAT,
    pmg9.FvfChannel.NORMAL0: pmg9.BufferFormat.R32G32B32_FLOAT,
    pmg9.FvfChannel.TANGENT0: pmg9.BufferFormat.R32G32B32A32_FLOAT,
    pmg9.FvfChannel.BLEND_WEIGHT0: pmg9.BufferFormat.R8G8B8A8_UNORM,
    pmg9.FvfChannel.BLEND_INDICES0: pmg9.BufferFormat.R8G8B8A8_UINT,
    pmg9.FvfChannel.COLOR0: pmg9.BufferFormat.R8G8B8A8_UNORM,
    pmg9.FvfChannel.COLOR1: pmg9.BufferFormat.R8G8B8A8_UNORM,
    pmg9.FvfChannel.TEXCOORD0: pmg9.BufferFormat.R32G32_FLOAT,
    pmg9.FvfChannel.TEXCOORD1: pmg9.BufferFormat.R32G32_FLOAT,
    pmg9.FvfChannel.TEXCOORD2: pmg9.BufferFormat.R32G32_FLOAT,
    pmg9.FvfChannel.TEXCOORD3: pmg9.BufferFormat.R32G32_FLOAT,
    pmg9.FvfChannel.TEXCOORD4: pmg9.BufferFormat.R32G32_FLOAT,
    pmg9.FvfChannel.TEXCOORD5: pmg9.BufferFormat.R32G32_FLOAT,
    pmg9.FvfChannel.TEXCOORD6: pmg9.BufferFormat.R32G32_FLOAT,
    pmg9.FvfChannel.TEXCOORD7: pmg9.BufferFormat.R32G32_FLOAT,
}


def _is_texture_compressed_g9(tex: pmg9.Texture) -> bool:
    f = tex.format.value
    return 70 <= f <= 84 or 94 <= f <= 99  # BC1 through BC7


def _extract_embedded_texture_dds_g9(tex: pmg9.Texture) -> bytes:
    import io
    import math

    if _is_texture_compressed_g9(tex):
        mips = tex.mips
        w = tex.width
        h = tex.height
        max_mips_w = math.ceil(math.log2(w / 2))
        max_mips_h = math.ceil(math.log2(h / 2))
        max_mips = min(max_mips_w, max_mips_h)
        if len(mips) > max_mips:
            num_mips_to_remove = len(mips) - max_mips
            for _ in range(num_mips_to_remove):
                mips.pop()

    tex_dds = io.BytesIO()
    tex.export_dds(tex_dds)
    return tex_dds.getvalue()


def _load_shader_group_g9(d: pmg9.Drawable) -> ShaderGroup | None:
    if d.shader_group is None:
        return None

    def _map_parameters(shader: pmg9.Shader) -> list[ShaderParameter]:
        si = pmg9.ShaderRegistry.instance.get_shader(shader.basis_hash.hash)
        parameters = shader.parameters
        out_parameters = []
        for resource_info, resource in zip(si.resources, parameters.resources):
            if resource is None:
                param_value = None
            else:
                param_value = resource.name.lower()

            out_parameters.append(
                ShaderParameter(
                    ShaderManager.lookup_texture_name_mapping_gen9_to_gen8(resource_info.name, si.name), param_value
                )
            )

        for buffer_info, buffer in zip(si.buffers, parameters.buffers):
            data = buffer.data.contents
            for field in buffer_info.fields.values():
                param_value = getattr(data, field.name)
                if isinstance(param_value, ctypes.Array):

                    def _value_to_vec(a: np.ndarray) -> Vector | list[Vector]:
                        if len(a) <= 4:
                            return Vector(tuple(a) + (0,) * (4 - len(a)))
                        elif len(a) == 16:
                            return [
                                Vector(a[0:3]),
                                Vector(a[4:7]),
                                Vector(a[8:11]),
                                Vector(a[12:15]),
                            ]
                        else:
                            assert False, f"Unsupported parameter length {len(a)}"

                    param_value = np.ctypeslib.as_array(param_value)
                    if len(param_value.shape) == 1:
                        param_value = _value_to_vec(param_value)
                    else:
                        assert len(param_value.shape) == 2
                        param_value = []
                        for v in param_value:
                            v = _value_to_vec(v)
                            if isinstance(v, list):
                                param_value.extend(v)
                            else:
                                param_value.append(v)
                else:
                    param_value = Vector((param_value, 0.0, 0.0, 0.0))

                out_parameters.append(ShaderParameter(field.name, param_value))

        return out_parameters

    def _map_shader(shader: pmg9.Shader) -> ShaderInst:
        return ShaderInst(
            name=_h2s(shader.basis_hash),
            preset_filename=None,
            render_bucket=RenderBucket(shader.draw_bucket.value),
            parameters=_map_parameters(shader),
        )

    def _map_embedded_texture(tex: pmg9.Texture) -> EmbeddedTexture:
        tex_data_bytes = _extract_embedded_texture_dds_g9(tex)
        tex_data = DataSource.create(tex_data_bytes, f"{tex.name}.dds")
        return EmbeddedTexture(tex.name, tex.width, tex.height, tex_data)

    def _map_embedded_textures(txd: pmg9.TextureDictionary | None) -> dict[str, EmbeddedTexture]:
        if txd is None:
            return {}
        return {t.name: _map_embedded_texture(t) for t in txd.textures.values()}

    sg = d.shader_group
    return ShaderGroup([_map_shader(s) for s in sg.shaders], _map_embedded_textures(sg.texture_dictionary))


def _load_models_g9(
    d: pmg9.Drawable,
    shader_group: pmg9.ShaderGroup | None = None,
) -> dict[LodLevel, list[Model]]:
    sg = shader_group or d.shader_group
    shader_mapping = {s: i for i, s in enumerate(sg.shaders)}

    def _find_shader_index(shader: pmg9.Shader) -> int:
        idx = shader_mapping.get(shader, None)
        if idx is None:
            raise ValueError(f"Shader {shader} not found in shader group!")
        return idx

    def _map_geometry(geom: pmg9.Geometry) -> Geometry:
        vb = geom.vb.buffer
        vb.dtype.names = [_VB_CHANNEL_NAMES_MAP[n] for n in vb.dtype.names]
        return Geometry(
            vertex_data_type=VertexDataType.DEFAULT,
            vertex_buffer=vb,
            index_buffer=geom.ib.indices,
            bone_ids=np.array(geom.matrix_palette),
            shader_index=_find_shader_index(geom.shader),
        )

    def _map_model(model: pmg9.Model) -> Model:
        return Model(
            bone_index=model.matrix_index,
            geometries=[_map_geometry(g) for g in model.geometries],
            render_bucket_mask=model.render_bucket_mask,
            has_skin=model.has_skin,
            matrix_count=model.matrix_count,
            flags=model.flags,
        )

    return {LodLevel(lod_level.value): [_map_model(m) for m in lod.models] for lod_level, lod in d.lods.items()}


def load_drawable(d: pmg9.Drawable) -> AssetDrawable:
    """Convert a native gen9 Drawable to an AssetDrawable dataclass."""
    return AssetDrawable(
        name=d.name,
        bounds=None,  # gen9 bound loading handled separately
        skeleton=_load_skeleton_native(d),
        shader_group=_load_shader_group_g9(d),
        models=_load_models_g9(d),
        lod_thresholds=_load_lod_thresholds_native(d),
        lights=_load_lights_native(d),
    )


def load_frag_drawable(
    d: pmg9.FragmentDrawable,
    parent_shader_group: pmg9.ShaderGroup | None = None,
) -> AssetFragDrawable:
    """Convert a native gen9 FragmentDrawable to an AssetFragDrawable dataclass."""
    return AssetFragDrawable(
        name=d.name,
        bounds=None,
        skeleton=_load_skeleton_native(d),
        shader_group=_load_shader_group_g9(d),
        models=_load_models_g9(d, shader_group=parent_shader_group),
        lod_thresholds=_load_lod_thresholds_native(d),
        lights=[],
        frag_bound_matrix=from_native_mat34(d.bound_matrix),
        frag_extra_bound_matrices=[from_native_mat34(e.matrix) for e in d.extra_bounds],
    )


def load_drawable_dictionary(d: pmg9.DrawableDictionary) -> AssetDrawableDictionary:
    """Convert a native gen9 DrawableDictionary to an AssetDrawableDictionary dataclass."""
    return AssetDrawableDictionary(
        drawables={jenkhash.hash_to_name(key.hash): load_drawable(drawable) for key, drawable in d.drawables.items()}
    )


# --- Save functions ---


def _save_shader_group_g9(shader_group: ShaderGroup | None, d: pmg9.Drawable):
    if shader_group is None:
        d.shader_group = None
        return

    sg = pmg9.ShaderGroup()
    if shader_group.embedded_textures:
        txd = pmg9.TextureDictionary()
        for embedded_tex in shader_group.embedded_textures.values():
            tex = pmg9.Texture()
            tex.name = embedded_tex.name
            tex.dimension = pmg9.ImageDimension.DIM_2D
            if not _import_dds_g8(tex, embedded_tex.data):
                texture_data = make_checkerboard_texture_data()
                h, w, _ = texture_data.shape
                mip = pm.TextureMip()
                mip.layers.append(texture_data)
                tex.mips.append(mip)
                tex.format = pmg9.BufferFormat.R8G8B8A8_UNORM
                tex.width = w
                tex.height = h
                tex.depth = 1

            txd.textures[pm.HashString(tex.name)] = tex

        sg.texture_dictionary = txd

    for shader in shader_group.shaders:
        s = pmg9.Shader()
        s.basis_hash = _s2h(shader.name)
        s.draw_bucket = pm.ShaderDrawBucket(shader.render_bucket.value)
        s.draw_bucket_mask = 0xFF00 | (1 << shader.render_bucket.value)

        gen9_specific_defaults = ShaderManager.lookup_gen9_shader_params_defaults(shader.name)
        if gen9_specific_defaults:
            for buffer in s.parameters.buffers:
                buffer_info = buffer.info
                data = buffer.data.contents
                for field in buffer_info.fields.values():
                    param_default_value = gen9_specific_defaults.get(field.name.lower(), None)
                    if param_default_value is None:
                        continue
                    field_value = getattr(data, field.name)
                    field_value_np = np.ctypeslib.as_array(field_value).ravel()
                    field_value_np[:] = param_default_value[: len(field_value_np)]

        for param in shader.parameters:
            match param.value:
                case None:
                    res_name = ShaderManager.lookup_texture_name_mapping_gen8_to_gen9(param.name, shader.name)
                    res_name = pm.HashString(res_name)
                    if s.parameters.get_resource_index_by_name(res_name) != -1:
                        s.parameters.set_resource_by_name(res_name, None)
                case str():
                    tex = pmg9.TextureReference(param.value)
                    res_name = ShaderManager.lookup_texture_name_mapping_gen8_to_gen9(param.name, shader.name)
                    res_name = pm.HashString(res_name)
                    if s.parameters.get_resource_index_by_name(res_name) != -1:
                        s.parameters.set_resource_by_name(res_name, tex)
                case Vector():
                    for buffer in s.parameters.buffers:
                        buffer_info = buffer.info
                        data = buffer.data.contents
                        for field in buffer_info.fields.values():
                            if field.name.lower() == param.name.lower():
                                field_value = getattr(data, field.name)
                                param_value = (
                                    type(field_value)(*param.value[: len(field_value)])
                                    if isinstance(field_value, ctypes.Array)
                                    else float(param.value[0])
                                )
                                setattr(data, field.name, param_value)
                                break
                        else:
                            continue
                        break
                case _:  # vector list
                    pass

        sg.shaders.append(s)

    d.shader_group = sg


def _save_models_g9(
    asset_models: dict[LodLevel, list[Model]],
    lod_thresholds: dict[LodLevel, float],
    d: pmg9.Drawable,
    parent_shader_group: pmg9.ShaderGroup | None = None,
):
    sg = d.shader_group or parent_shader_group
    has_models = any(models for models in asset_models.values())
    if has_models:
        assert sg and sg.shaders, "Need to assign the shader group or have a parent drawable with shaders before the models"

    def _map_geometry(geom: Geometry) -> pmg9.Geometry:
        g = pmg9.Geometry()
        g.shader = sg.shaders[geom.shader_index]
        g.primitive_type = pm.PrimitiveType.TRIS
        g.matrix_palette = geom.bone_ids

        channels = [pmg9.FvfChannel[_VB_CHANNEL_NAMES_INVERSE_MAP[n]] for n in geom.vertex_buffer.dtype.names]
        channels.sort(key=lambda c: c.value)
        formats = [_VERTEX_FORMATS[c] for c in channels]
        offsets = list(itertools.accumulate(f.bits_per_pixel // 8 for f in formats))
        vertex_byte_size = offsets[-1]
        fvf = pmg9.Fvf()
        for channel, fmt, offset in zip(channels, formats, [0] + offsets[:-1]):
            fvf.enable_channel(channel, offset, vertex_byte_size, fmt)
        fvf.vertex_data_size = vertex_byte_size

        g.vb = pmg9.VertexBuffer()
        g.vb.fvf = fvf
        g.vb.resize(len(geom.vertex_buffer))
        for channel in geom.vertex_buffer.dtype.names:
            g.vb.buffer[_VB_CHANNEL_NAMES_INVERSE_MAP[channel]] = geom.vertex_buffer[channel]
        g.ib = pmg9.IndexBuffer()
        g.ib.indices = geom.index_buffer
        return g

    def _map_model(model: Model) -> pmg9.Model:
        m = pmg9.Model()
        gs = [_map_geometry(g) for g in model.geometries]
        m.geometries.extend(gs)
        m.render_bucket_mask = model.render_bucket_mask
        m.flags = pm.ModelFlags(model.flags)
        m.has_skin = model.has_skin
        m.matrix_index = model.bone_index
        m.matrix_count = model.matrix_count
        return m

    thresholds = _DEFAULT_LOD_THRESHOLDS | lod_thresholds
    for lod_level, models in asset_models.items():
        if not models:
            continue

        lod = pmg9.Lod()
        m = [_map_model(m) for m in models]
        lod.models.extend(m)
        lod.lod_threshold = thresholds.get(lod_level, 9998.0)

        d.lods[pm.LodType(lod_level.value)] = lod


def save_drawable_to_native(asset: AssetDrawable) -> pmg9.Drawable:
    """Convert an AssetDrawable dataclass to a native gen9 Drawable."""
    d = pmg9.Drawable()
    d.name = asset.name
    _save_skeleton_native(asset.skeleton, d)
    _save_shader_group_g9(asset.shader_group, d)
    _save_models_g9(asset.models, asset.lod_thresholds, d)
    _save_lights_native(asset.lights, d)
    if asset.bounds:
        d.bound = save_bound_to_native(asset.bounds)
    return d


def save_frag_drawable_to_native(
    asset: AssetFragDrawable, parent_shader_group: pmg9.ShaderGroup | None = None,
) -> pmg9.FragmentDrawable:
    """Convert an AssetFragDrawable dataclass to a native gen9 FragmentDrawable."""
    d = pmg9.FragmentDrawable()
    d.name = asset.name
    d.skeleton_type = pm.SkeletonType.SKEL if asset.name == "skel" else pm.SkeletonType.NONE
    _save_skeleton_native(asset.skeleton, d)
    _save_shader_group_g9(asset.shader_group, d)
    _save_models_g9(asset.models, asset.lod_thresholds, d, parent_shader_group=parent_shader_group)
    if asset.frag_bound_matrix is not None:
        m = asset.frag_bound_matrix
        d.bound_matrix = pma.Matrix34(
            pma.Vector4f(float(m[0][0]), float(m[0][1]), float(m[0][2]), float(m[0][3])),
            pma.Vector4f(float(m[1][0]), float(m[1][1]), float(m[1][2]), float(m[1][3])),
            pma.Vector4f(float(m[2][0]), float(m[2][1]), float(m[2][2]), float(m[2][3])),
            pma.Vector4f(float(m[3][0]), float(m[3][1]), float(m[3][2]), float(m[3][3])),
        )
    d.extra_bounds = [
        pm.ExtraBound(
            matrix=pma.Matrix34(
                pma.Vector4f(float(m[0][0]), float(m[0][1]), float(m[0][2]), float(m[0][3])),
                pma.Vector4f(float(m[1][0]), float(m[1][1]), float(m[1][2]), float(m[1][3])),
                pma.Vector4f(float(m[2][0]), float(m[2][1]), float(m[2][2]), float(m[2][3])),
                pma.Vector4f(float(m[3][0]), float(m[3][1]), float(m[3][2]), float(m[3][3])),
            )
        )
        for m in (asset.frag_extra_bound_matrices or [])
    ]
    return d


def save_drawable_dictionary_to_native(asset: AssetDrawableDictionary) -> pmg9.DrawableDictionary:
    """Convert an AssetDrawableDictionary dataclass to a native gen9 DrawableDictionary."""
    dwd = pmg9.DrawableDictionary()
    for name, drawable in asset.drawables.items():
        dwd.drawables[pm.HashString(jenkhash.name_to_hash(name))] = save_drawable_to_native(drawable)
    return dwd
