import logging
from collections import defaultdict

import numpy as np
import pymateria.gta5 as pm
import pymateria.gta5.gen8 as pmg8

from ....types import DataSource, Matrix, Quaternion, Vector
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
    Light,
    LightFlashiness,
    LightType,
    LodLevel,
    Model,
    RenderBucket,
    ShaderGroup,
    ShaderInst,
    ShaderParameter,
    SkelBone,
    SkelBoneFlags,
    SkelBoneRotationLimit,
    SkelBoneTranslationLimit,
    Skeleton,
    VertexDataType,
)
from ._utils import (
    _h2s,
    apply_target,
    from_native_mat34,
    make_checkerboard_texture_data,
    to_native_mat34,
    to_native_quat,
    to_native_rgb,
    to_native_vec3,
    to_native_vec4,
)
from .bound import (
    NativeBound,
)

_DEFAULT_LOD_THRESHOLDS = {
    LodLevel.HIGH: 9998.0,
    LodLevel.MEDIUM: 9998.0,
    LodLevel.LOW: 9998.0,
    LodLevel.VERYLOW: 9998.0,
}

_VB_CHANNEL_NAMES_MAP = {
    "POSITION": "Position",
    "WEIGHT": "BlendWeights",
    "BINDING": "BlendIndices",
    "NORMAL": "Normal",
    "DIFFUSE": "Colour0",
    "SPECULAR": "Colour1",
    "TEXTURE0": "TexCoord0",
    "TEXTURE1": "TexCoord1",
    "TEXTURE2": "TexCoord2",
    "TEXTURE3": "TexCoord3",
    "TEXTURE4": "TexCoord4",
    "TEXTURE5": "TexCoord5",
    "TEXTURE6": "TexCoord6",
    "TEXTURE7": "TexCoord7",
    "TANGENT0": "Tangent",
}

_VB_CHANNEL_NAMES_INVERSE_MAP = {v: k for k, v in _VB_CHANNEL_NAMES_MAP.items()}


def _map_light_from_native(light: pm.Light) -> Light:
    culling_plane = light.culling_plane
    culling_plane_normal = culling_plane.normal if culling_plane else Vector((0.0, 0.0, 0.0))
    culling_plane_offset = culling_plane.distance if culling_plane else 0.0
    projected_texture_hash = jenkhash.hash_to_name(light.projected_texture_key)
    return Light(
        light_type=LightType(light.type.value),
        position=Vector(light.position),
        direction=Vector(light.direction),
        tangent=Vector(light.tangent),
        extent=Vector(light.extents),
        color=tuple(light.color),
        flashiness=LightFlashiness(light.flashiness.value),
        intensity=light.intensity,
        flags=light.flags.value,
        time_flags=light.time_flags.value,
        bone_id=light.bone_tag
        & 0xFFFF,  # bone tag in light is signed int, but everywhere else it is unsigned, keep the consistency
        group_id=light.group_id,
        light_hash=light.light_hash,
        falloff=light.falloff,
        falloff_exponent=light.falloff_exponent,
        culling_plane_normal=culling_plane_normal,
        culling_plane_offset=culling_plane_offset,
        volume_intensity=light.volume_intensity,
        volume_size_scale=light.volume_size_scale,
        volume_outer_color=tuple(light.volume_outer_color),
        volume_outer_intensity=light.volume_outer_intensity,
        volume_outer_exponent=light.volume_outer_exponent,
        corona_size=light.corona_size,
        corona_intensity=light.corona_intensity,
        corona_z_bias=light.corona_zbias,
        projected_texture_hash=projected_texture_hash,
        light_fade_distance=light.light_fade_distance,
        shadow_fade_distance=light.shadow_fade_distance,
        specular_fade_distance=light.specular_fade_distance,
        volumetric_fade_distance=light.volumetric_fade_distance,
        shadow_near_clip=light.shadow_near_clip,
        shadow_blur=light.shadow_blur,
        cone_inner_angle=light.cone_inner_angle,
        cone_outer_angle=light.cone_outer_angle,
    )


def _map_light_to_native(light: Light, definition: bool = False) -> pm.Light:
    li = pm.LightDefinition() if definition else pm.Light()
    li.type = pm.LightType(light.light_type.value)
    li.position = to_native_vec3(light.position)
    li.direction = to_native_vec3(light.direction)
    li.tangent = to_native_vec3(light.tangent)
    li.extents = to_native_vec3(light.extent)
    li.color = to_native_rgb(light.color)
    li.flashiness = pm.LightFlashiness(light.flashiness.value)
    li.intensity = light.intensity
    li.flags = pm.LightFlags(light.flags)
    li.time_flags = pm.TimeFlags(light.time_flags)
    li.bone_tag = t if (t := light.bone_id) < 0x8000 else t - 0x10000  # convert unsigned 16-bit integer to signed
    li.group_id = light.group_id
    li.light_hash = light.light_hash
    li.culling_plane = pm.LightCullingPlane()
    li.culling_plane.normal = to_native_vec3(light.culling_plane_normal)
    li.culling_plane.distance = light.culling_plane_offset
    li.falloff = light.falloff
    li.falloff_exponent = light.falloff_exponent
    li.volume_intensity = light.volume_intensity
    li.volume_size_scale = light.volume_size_scale
    li.volume_outer_color = to_native_rgb(light.volume_outer_color)
    li.volume_outer_intensity = light.volume_outer_intensity
    li.volume_outer_exponent = light.volume_outer_exponent
    li.projected_texture_key = jenkhash.name_to_hash(light.projected_texture_hash)
    li.corona_size = light.corona_size
    li.corona_intensity = light.corona_intensity
    li.corona_zbias = light.corona_z_bias
    li.light_fade_distance = light.light_fade_distance
    li.shadow_fade_distance = light.shadow_fade_distance
    li.specular_fade_distance = light.specular_fade_distance
    li.volumetric_fade_distance = light.volumetric_fade_distance
    li.shadow_near_clip = light.shadow_near_clip
    li.shadow_blur = light.shadow_blur
    li.cone_inner_angle = light.cone_inner_angle
    li.cone_outer_angle = light.cone_outer_angle
    return li


class NativeDrawable:
    ASSET_FORMAT = AssetFormat.NATIVE
    ASSET_VERSION = AssetVersion.GEN8
    ASSET_TYPE = AssetType.DRAWABLE

    def __init__(self, d: pmg8.Drawable, drawable_with_shader_group: pmg8.Drawable | None = None):
        self._inner = d
        self._drawable_with_shader_group = drawable_with_shader_group

        self._temp_lod_thresholds: dict[LodLevel, float] | None = None

    @property
    def name(self) -> str:
        return self._inner.name

    @name.setter
    def name(self, v: str):
        self._inner.name = v

    @property
    def skeleton(self) -> Skeleton | None:
        bones = []

        def _map_translation_limit(limit: pm.BoneTranslationLimit | None) -> SkelBoneTranslationLimit | None:
            if limit is None:
                return None

            return SkelBoneTranslationLimit(Vector(limit.min), Vector(limit.max))

        def _map_rotation_limit(limit: pm.BoneRotationLimit | None) -> SkelBoneRotationLimit | None:
            if limit is None:
                return None

            # Checks for parity with CW backend.
            # All rotation limits are in "euler angles" mode where the control points actually contain the min and max
            # rotation angles, not swing&twist. This is the only mode we support.
            assert limit.num_control_points == 1
            assert limit.degrees_of_freedom == pm.BoneJointDofs.JOINT_3_DOF
            assert limit.use_euler_angles

            p0, p1 = limit.control_points[:2]
            min_rot = Vector((p0.max_swing, p0.min_twist, p0.max_twist))
            max_rot = Vector((p1.max_swing, p1.min_twist, p1.max_twist))
            return SkelBoneRotationLimit(min_rot, max_rot)

        def _add_bone(b: pm.Bone, parent_index: int):
            bone_index = len(bones)
            px, py, pz, _ = b.default_translation
            rx, ry, rz, rw = b.default_rotation
            sx, sy, sz, _ = b.default_scale
            bones.append(
                SkelBone(
                    name=b.name,
                    tag=b.id,
                    flags=SkelBoneFlags(b.degrees_of_freedom),
                    position=Vector((px, py, pz)),
                    rotation=Quaternion((rw, rx, ry, rz)),
                    scale=Vector((sx, sy, sz)),
                    parent_index=parent_index,
                    translation_limit=_map_translation_limit(b.translation_limit),
                    rotation_limit=_map_rotation_limit(b.rotation_limit),
                )
            )
            for c in b.children:
                _add_bone(c, bone_index)

        if self._inner.skeleton is not None:
            _add_bone(self._inner.skeleton.root_bone, -1)

        return Skeleton(bones) if bones else None

    @skeleton.setter
    def skeleton(self, skel: Skeleton | None):
        if skel is None:
            self._inner.skeleton = None
            self._inner.include_joint_data = False
            return

        has_any_limits = False

        def _convert_bone(bone: SkelBone) -> pm.Bone:
            nonlocal has_any_limits
            b = pm.Bone()
            b.name = bone.name
            b.id = bone.tag
            b.degrees_of_freedom = bone.flags.value
            b.default_translation = to_native_vec4(bone.position.to_4d())
            b.default_rotation = to_native_quat(bone.rotation)
            b.default_scale = to_native_vec4(bone.scale.to_4d())
            if bone.translation_limit:
                limit = pm.BoneTranslationLimit()
                limit.bone_id = bone.tag
                limit.min = to_native_vec3(bone.translation_limit.min)
                limit.max = to_native_vec3(bone.translation_limit.max)
                b.translation_limit = limit
                has_any_limits = True
            if bone.rotation_limit:
                limit = pm.BoneRotationLimit()
                limit.bone_id = bone.tag
                limit.degrees_of_freedom = pm.BoneJointDofs.JOINT_3_DOF
                limit.use_euler_angles = True
                # yes, it is one even though it uses 2, they are not actually control points just re-used for the euler angles
                limit.num_control_points = 1
                p0 = pm.BoneJointControlPoint(*bone.rotation_limit.min)
                p1 = pm.BoneJointControlPoint(*bone.rotation_limit.max)
                limit.control_points = (p0, p1) + limit.control_points[2:]
                b.rotation_limit = limit
                has_any_limits = True
            return b

        bones_by_parent = defaultdict(list)
        index_by_bone = {}

        for i, bone in enumerate(skel.bones):
            bones_by_parent[bone.parent_index].append(bone)
            index_by_bone[id(bone)] = i

        def _build_hierarchy(bone: SkelBone) -> pm.Bone:
            native_bone = _convert_bone(bone)
            for child_bone in bones_by_parent[index_by_bone[id(bone)]]:
                child_native_bone = _build_hierarchy(child_bone)
                native_bone.children.append(child_native_bone)
            return native_bone

        assert len(bones_by_parent[-1]) == 1

        s = pm.Skeleton()
        s.root_bone = _build_hierarchy(bones_by_parent[-1][0])
        self._inner.skeleton = s
        self._inner.include_joint_data = has_any_limits

    @property
    def bounds(self) -> NativeBound | None:
        return apply_target(self, NativeBound(self._inner.bound)) if self._inner.bound else None

    @bounds.setter
    def bounds(self, v: NativeBound | None):
        self._inner.bound = canonical_asset(v, NativeBound, self)._inner if v else None

    def _extract_embedded_texture_dds(self, tex: pmg8.Texture) -> bytes:
        import io
        import math

        # Try to fix mips if needed, some vanilla textures have too many
        # mips and export_dds will raise an exception
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

    @property
    def shader_group(self) -> ShaderGroup | None:
        if self._inner.shader_group is None:
            return None

        def _map_parameter(param: pmg8.ShaderParameter) -> ShaderParameter:
            data = param.data
            match data:
                case None:
                    param_value = None
                case pmg8.TextureBase():
                    param_value = data.name
                case [value]:
                    param_value = Vector(value)
                case [*values]:
                    param_value = [Vector(v) for v in values]
                case _:
                    assert False, f"Unsupported shader parameter data: {data}"

            return ShaderParameter(
                name=_h2s(param.name),
                value=param_value,
            )

        def _map_shader(shader: pmg8.Shader) -> ShaderInst:
            basis_shader = shader.basis_shader
            basis_material = shader.basis_material
            return ShaderInst(
                name=_h2s(basis_shader),
                preset_filename=_h2s(basis_material) if not basis_material.is_empty else None,
                render_bucket=RenderBucket(shader.draw_bucket.value),
                parameters=[_map_parameter(p) for p in shader.parameters],
            )

        def _map_embedded_texture(tex: pmg8.Texture) -> EmbeddedTexture:
            tex_data_bytes = self._extract_embedded_texture_dds(tex)
            tex_data = DataSource.create(tex_data_bytes, f"{tex.name}.dds")
            return EmbeddedTexture(tex.name, tex.width, tex.height, tex_data)

        def _map_embedded_textures(txd: pmg8.TextureDictionary | None) -> dict[str, EmbeddedTexture]:
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

        sg = pmg8.ShaderGroup()
        embedded_textures = {}
        if shader_group.embedded_textures:
            txd = pmg8.TextureDictionary()
            for embedded_tex in shader_group.embedded_textures.values():
                tex = pmg8.Texture()
                tex.name = embedded_tex.name
                embedded_textures[tex.name] = tex
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
                    tex.format = pmg8.TextureFormat.A8B8G8R8
                    tex.width = w
                    tex.height = h
                    tex.depth = 1
                    tex.layer_count = 1

                txd.textures[pm.HashString(tex.name)] = tex

            sg.texture_dictionary = txd

        for shader in shader_group.shaders:
            assert shader.preset_filename is not None
            s = pmg8.Shader()
            s.basis_shader = shader.name
            s.basis_material = shader.preset_filename
            s.draw_bucket = pm.ShaderDrawBucket(shader.render_bucket.value)
            s.draw_bucket_mask = 0xFF00 | (1 << shader.render_bucket.value)
            for param in shader.parameters:
                p = pmg8.ShaderParameter()
                p.name = param.name
                match param.value:
                    case None:
                        p.data = None
                    case str():
                        tex = embedded_textures.get(param.value, None)
                        if tex is None:
                            tex = pmg8.TextureReference()
                            tex.name = param.value
                        p.data = tex
                    case Vector():
                        p.data = [to_native_vec4(param.value)]
                    case _:  # vector list
                        p.data = [to_native_vec4(v) for v in param.value]
                s.parameters.append(p)

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

        def _find_shader_index(shader: pmg8.Shader) -> int:
            idx = shader_mapping.get(shader, None)
            if idx is None:
                raise ValueError(f"Shader {shader} not found in shader group!")

            return idx

        def _map_geometry(geom: pmg8.Geometry) -> Geometry:
            fvf = geom.vb.fvf
            vb = geom.vb.buffer
            vb.dtype.names = [_VB_CHANNEL_NAMES_MAP[n] for n in vb.dtype.names]

            # Cloth drawables have packed normals, unpack them
            if (
                fvf.is_channel_active(pmg8.FvfChannel.NORMAL)
                and fvf.get_channel_size_type(pmg8.FvfChannel.NORMAL) == pmg8.FvfDataType.PACKED_NORMAL
            ):
                packed_normals = vb["Normal"]
                x = (packed_normals & 0xFF).astype(dtype=np.int8) / 127
                y = ((packed_normals >> 8) & 0xFF).astype(dtype=np.int8) / 127
                z = ((packed_normals >> 16) & 0xFF).astype(dtype=np.int8) / 127

                new_dtype = [(n, (np.float32, 3) if n == "Normal" else vb.dtype.fields[n][0]) for n in vb.dtype.names]
                new_vb = np.empty_like(vb, dtype=new_dtype)
                for n in vb.dtype.names:
                    if n == "Normal":
                        normals = new_vb[n]
                        normals[:, 0] = x
                        normals[:, 1] = y
                        normals[:, 2] = z
                    else:
                        new_vb[n] = vb[n]

                vb = new_vb

            return Geometry(
                vertex_data_type=VertexDataType(fvf.size_signature),
                vertex_buffer=vb,
                index_buffer=geom.ib.indices,
                bone_ids=np.array(geom.matrix_palette),
                shader_index=_find_shader_index(geom.shader),
            )

        def _map_model(model: pmg8.Model) -> Model:
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

        def _map_geometry(geom: Geometry) -> pmg8.Geometry:
            g = pmg8.Geometry()
            g.shader = sg.shaders[geom.shader_index]
            g.primitive_type = pm.PrimitiveType.TRIS
            g.matrix_palette = geom.bone_ids

            channels = {pmg8.FvfChannel[_VB_CHANNEL_NAMES_INVERSE_MAP[n]] for n in geom.vertex_buffer.dtype.names}
            fvf = pmg8.Fvf(channels, size_signature=geom.vertex_data_type.value)
            g.vb.fvf = fvf
            g.vb.resize(len(geom.vertex_buffer))
            for channel in geom.vertex_buffer.dtype.names:
                if (
                    channel == "Normal"
                    and fvf.is_channel_active(pmg8.FvfChannel.NORMAL)
                    and fvf.get_channel_size_type(pmg8.FvfChannel.NORMAL) == pmg8.FvfDataType.PACKED_NORMAL
                ):
                    # Pack normals
                    normals = geom.vertex_buffer["Normal"]
                    x = normals[:, 0]
                    y = normals[:, 1]
                    z = normals[:, 2]
                    packed_normals = (
                        (x * 127.0).astype(dtype=np.uint8).astype(dtype=np.uint32)
                        | ((y * 127.0).astype(dtype=np.uint8).astype(dtype=np.uint32) << 8)
                        | ((z * 127.0).astype(dtype=np.uint8).astype(dtype=np.uint32) << 16)
                    )
                    channel_data = packed_normals
                else:
                    channel_data = geom.vertex_buffer[channel]

                g.vb.buffer[_VB_CHANNEL_NAMES_INVERSE_MAP[channel]] = channel_data

            g.ib.indices = geom.index_buffer
            return g

        def _map_model(model: Model) -> pmg8.Model:
            m = pmg8.Model()
            m.geometries = [_map_geometry(g) for g in model.geometries]
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

            lod = pmg8.Lod()
            lod.models = [_map_model(m) for m in models]
            lod.lod_threshold = lod_thresholds.get(lod_level, 9998.0)

            self._inner.lods[pm.LodType(lod_level.value)] = lod

        self._temp_lod_thresholds = None

    @property
    def lod_thresholds(self) -> dict[LodLevel, float]:
        if self._temp_lod_thresholds:
            return self._temp_lod_thresholds

        return (
            _DEFAULT_LOD_THRESHOLDS
            | {LodLevel(lod_level.value): lod.lod_threshold for lod_level, lod in self._inner.lods.items()}
            if self._inner.lods
            else {}
        )

    @lod_thresholds.setter
    def lod_thresholds(self, v: dict[LodLevel, float]):
        self._temp_lod_thresholds = _DEFAULT_LOD_THRESHOLDS | v

        if self._inner.lods:
            for lod_level, lod in self._inner.lods.items():
                lod.lod_threshold = self._temp_lod_thresholds.get(LodLevel(lod_level.value), 9998.0)

    @property
    def lights(self) -> list[Light]:
        return [_map_light_from_native(light) for light in self._inner.lights]

    @lights.setter
    def lights(self, lights: list[Light]):
        self._inner.lights = [_map_light_to_native(li) for li in lights]

    @property
    def frag_bound_matrix(self) -> Matrix:
        raise AssertionError("Cannot get frag_bound_matrix of regular drawable")

    @frag_bound_matrix.setter
    def frag_bound_matrix(self, v: Matrix):
        raise AssertionError("Cannot set frag_bound_matrix of regular drawable")


class NativeFragDrawable(NativeDrawable):
    def __init__(self, d: pmg8.FragmentDrawable, drawable_with_shader_group: pmg8.FragmentDrawable | None = None):
        super().__init__(d, drawable_with_shader_group)
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
    def bounds(self) -> NativeBound | None:
        return None

    @bounds.setter
    def bounds(self, v: NativeBound | None):
        raise AssertionError("Cannot set bounds of FragDrawable")

    @property
    def lights(self) -> list[Light]:
        return []

    @lights.setter
    def lights(self, lights: list[Light]):
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


class NativeDrawableDictionary:
    ASSET_FORMAT = AssetFormat.NATIVE
    ASSET_VERSION = AssetVersion.GEN8
    ASSET_TYPE = AssetType.DRAWABLE_DICTIONARY

    def __init__(self, d: pmg8.DrawableDictionary):
        self._inner = d

    @property
    def drawables(self) -> dict[str, NativeDrawable]:
        dwd = self._inner
        return {jenkhash.hash_to_name(key.hash): NativeDrawable(drawable) for key, drawable in dwd.drawables.items()}

    @drawables.setter
    def drawables(self, d: dict[str, NativeDrawable]):
        dwd = self._inner
        dwd.drawables.clear()
        for name, drawable in d.items():
            dwd.drawables[pm.HashString(jenkhash.name_to_hash(name))] = canonical_asset(
                drawable, NativeDrawable, self
            )._inner
