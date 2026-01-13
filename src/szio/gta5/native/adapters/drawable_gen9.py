import ctypes
import itertools
import logging

import numpy as np
import pymateria.gta5 as pm
import pymateria.gta5.gen9 as pmg9

from ....types import DataSource, Matrix, Vector
from ... import jenkhash
from ...assets import (
    AssetFormat,
    AssetType,
    AssetVersion,
    canonical_asset,
)
from ...drawables import (
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
from .drawable import NativeDrawable

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


class NativeDrawableG9(NativeDrawable):
    ASSET_FORMAT = AssetFormat.NATIVE
    ASSET_VERSION = AssetVersion.GEN9
    ASSET_TYPE = AssetType.DRAWABLE

    def __init__(self, d: pmg9.Drawable, drawable_with_shader_group: pmg9.Drawable | None = None):
        super().__init__(d, drawable_with_shader_group)
        self._inner = d
        self._drawable_with_shader_group = drawable_with_shader_group

    @property
    def shader_group(self) -> ShaderGroup | None:
        if self._inner.shader_group is None:
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
                    # Convert parameter to Vector4s
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
                            # Handle array parameters
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
            tex_data_bytes = self._extract_embedded_texture_dds(tex)
            tex_data = DataSource.create(tex_data_bytes, f"{tex.name}.dds")
            return EmbeddedTexture(tex.name, tex.width, tex.height, tex_data)

        def _map_embedded_textures(txd: pmg9.TextureDictionary | None) -> dict[str, EmbeddedTexture]:
            if txd is None:
                return {}

            return {t.name: _map_embedded_texture(t) for t in txd.textures.values()}

        sg = self._inner.shader_group
        return ShaderGroup([_map_shader(s) for s in sg.shaders], _map_embedded_textures(sg.texture_dictionary))

    @shader_group.setter
    def shader_group(self, shader_group: ShaderGroup | None):
        if shader_group is None:
            self._inner.shader_group = None
            return

        sg = pmg9.ShaderGroup()
        if shader_group.embedded_textures:
            txd = pmg9.TextureDictionary()
            for embedded_tex in shader_group.embedded_textures.values():
                tex = pmg9.Texture()
                tex.name = embedded_tex.name
                tex.dimension = pmg9.ImageDimension.DIM_2D
                if data := embedded_tex.data:
                    with data.open() as data_stream:
                        tex.import_dds(data_stream)
                else:
                    # Texture data missing, create magenta/black checkerboard texture
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

            # Special case to initialize new parameters in gen9 shaders. These always have the same values and are
            # either hardcoded or unused, just ended up as parameters due to the new shader compilation pipeline for
            # gen9. For example, BloodZoneAdjust which got added to a buffer in gen9, when in gen8 it was inlined in
            # the shader itself. Required for ped blood decals, otherwise they break
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

            # Set user-defined parameters
            for param in shader.parameters:
                match param.value:
                    case None:
                        res_name = ShaderManager.lookup_texture_name_mapping_gen8_to_gen9(param.name, shader.name)
                        res_name = pm.HashString(res_name)
                        # Some texture parameters no longer exist in gen9 shaders (e.g. TextureSamplerDiffPal in
                        # ped_hair_spiked or DiffuseExtraSampler on weapon shaders)
                        # Make sure it exists
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
                                        param.value[: len(field_value)]
                                        if isinstance(field_value, ctypes.Array)
                                        else param.value[0]
                                    )
                                    setattr(data, field.name, param_value)
                                    break
                            else:
                                continue

                            break
                    case _:  # vector list
                        # MATRIX parameters don't really matter for our case, leave them default
                        pass

            sg.shaders.append(s)

        self._inner.shader_group = sg

    @property
    def models(self) -> dict[LodLevel, list[Model]]:
        sg = (
            self._drawable_with_shader_group.shader_group
            if self._drawable_with_shader_group
            else self._inner.shader_group
        )
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
                vertex_data_type=VertexDataType.DEFAULT,  # everything uses the same vertex formats
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

        return {
            LodLevel(lod_level.value): [_map_model(m) for m in lod.models]
            for lod_level, lod in self._inner.lods.items()
        }

    @models.setter
    def models(self, v: dict[LodLevel, list[Model]]):
        parent_sg = self._drawable_with_shader_group and self._drawable_with_shader_group.shader_group
        sg = self._inner.shader_group or parent_sg
        assert sg and sg.shaders, (
            "Need to assign the shader group or have a parent drawable with shaders before the models"
        )

        def _map_geometry(geom: Geometry) -> pmg9.Geometry:
            g = pmg9.Geometry()
            g.shader = sg.shaders[geom.shader_index]
            g.primitive_type = pm.PrimitiveType.TRIS
            g.matrix_palette = geom.bone_ids

            channels = [pmg9.FvfChannel[_VB_CHANNEL_NAMES_INVERSE_MAP[n]] for n in geom.vertex_buffer.dtype.names]
            channels.sort(key=lambda c: c.value)
            # Note, unlike gen8, we can ignore geom.vertex_data_type because gen9 always uses the same vertex formats,
            # even the envCloth meshes (they don't use packed normals anymore).
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

        lod_thresholds = self.lod_thresholds
        for lod_level, models in v.items():
            if not models:
                continue

            lod = pmg9.Lod()
            m = [_map_model(m) for m in models]
            lod.models.extend(m)
            lod.lod_threshold = lod_thresholds.get(lod_level, 9998.0)

            self._inner.lods[pm.LodType(lod_level.value)] = lod

        self._temp_lod_thresholds = None


class NativeFragDrawableG9(NativeDrawableG9):
    def __init__(self, d: pmg9.FragmentDrawable, drawable_with_shader_group: pmg9.FragmentDrawable | None = None):
        super().__init__(d)
        self._inner = d
        self._drawable_with_shader_group = drawable_with_shader_group

    @property
    def name(self) -> str:
        return self._inner.name

    @name.setter
    def name(self, v: str):
        self._inner.name = v
        self._inner.skeleton_type = pm.SkeletonType.SKEL if v == "skel" else pm.SkeletonType.NONE

    @property
    def bounds(self) -> None:
        return None

    @bounds.setter
    def bounds(self, v):
        raise AssertionError("Cannot set bounds of FragDrawable")

    @property
    def lights(self) -> list:
        return []

    @lights.setter
    def lights(self, lights: list):
        raise AssertionError("Cannot set lights of FragDrawable")

    @property
    def frag_bound_matrix(self) -> Matrix:
        return from_native_mat34(self._inner.bound_matrix)

    @frag_bound_matrix.setter
    def frag_bound_matrix(self, v: Matrix):
        self._inner.bound_matrix = to_native_mat34(v)

    @property
    def frag_extra_bound_matrices(self) -> list[Matrix]:
        return [from_native_mat34(e.matrix) for e in self._inner.extra_bounds]

    @frag_extra_bound_matrices.setter
    def frag_extra_bound_matrices(self, v: list[Matrix]):
        self._inner.extra_bounds = [pm.ExtraBound(matrix=to_native_mat34(m)) for m in v]


class NativeDrawableDictionaryG9:
    ASSET_FORMAT = AssetFormat.NATIVE
    ASSET_VERSION = AssetVersion.GEN9
    ASSET_TYPE = AssetType.DRAWABLE_DICTIONARY

    def __init__(self, d: pmg9.DrawableDictionary):
        self._inner = d

    @property
    def drawables(self) -> dict[str, NativeDrawableG9]:
        dwd = self._inner
        return {jenkhash.hash_to_name(key.hash): NativeDrawableG9(drawable) for key, drawable in dwd.drawables.items()}

    @drawables.setter
    def drawables(self, d: dict[str, NativeDrawableG9]):
        dwd = self._inner
        dwd.drawables.clear()
        for name, drawable in d.items():
            dwd.drawables[pm.HashString(jenkhash.name_to_hash(name))] = canonical_asset(
                drawable, NativeDrawableG9, self
            )._inner
