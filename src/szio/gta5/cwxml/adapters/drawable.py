from typing import Optional, Sequence

import numpy as np

from ....types import Matrix, Quaternion, Vector
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
from .. import drawable as cw
from ._utils import apply_target
from .bound import CWBound

CW_BONE_FLAGS_MAP = {
    "None": SkelBoneFlags(0),
    "RotX": SkelBoneFlags.ROTATE_X,
    "RotY": SkelBoneFlags.ROTATE_Y,
    "RotZ": SkelBoneFlags.ROTATE_Z,
    "LimitRotation": SkelBoneFlags.HAS_ROTATE_LIMITS,
    "TransX": SkelBoneFlags.TRANSLATE_X,
    "TransY": SkelBoneFlags.TRANSLATE_Y,
    "TransZ": SkelBoneFlags.TRANSLATE_Z,
    "LimitTranslation": SkelBoneFlags.HAS_TRANSLATE_LIMITS,
    "ScaleX": SkelBoneFlags.SCALE_X,
    "ScaleY": SkelBoneFlags.SCALE_Y,
    "ScaleZ": SkelBoneFlags.SCALE_Z,
    "LimitScale": SkelBoneFlags.HAS_SCALE_LIMITS,
    "Unk0": SkelBoneFlags.HAS_CHILD,
}
CW_BONE_FLAGS_INVERSE_MAP = {v: k for k, v in CW_BONE_FLAGS_MAP.items()}


def _bone_flags_to_cw(flags: SkelBoneFlags) -> list[str]:
    return [CW_BONE_FLAGS_INVERSE_MAP[flag] for flag in flags]


def _bone_flags_from_cw(flags: Sequence[str]) -> SkelBoneFlags:
    converted_flags = SkelBoneFlags(0)
    for flag in flags:
        converted_flags |= CW_BONE_FLAGS_MAP.get(flag, 0)
    return converted_flags


def _find_bone_sibling_index(bone_index: int, skel: Skeleton) -> int:
    parent_index = skel.bones[bone_index].parent_index
    if parent_index == -1:
        return -1

    for i in range(bone_index + 1, len(skel.bones)):
        b = skel.bones[i]
        if b.parent_index == parent_index:
            sibling_index = i
            break
    else:
        sibling_index = -1

    return sibling_index


def _calculate_skeleton_unks(skeleton_xml: cw.Skeleton):
    # from what oiv calcs Unknown50 and Unknown54 are related to BoneTag and Flags, and obviously the hierarchy of bones
    # assuming those hashes/flags are all based on joaat
    # Unknown58 is related to BoneTag, Flags, Rotation, Location and Scale. Named as DataCRC so we stick to CRC-32 as a hack, since we and possibly oiv don't know how R* calc them
    # hopefully this doesn't break in game!
    # hacky solution with inaccurate results, the implementation here is only to ensure they are unique regardless the correctness, further investigation is required
    if not skeleton_xml.bones:
        return

    unk_50 = []
    unk_58 = []

    for bone in skeleton_xml.bones:
        unk_50_str = " ".join((str(bone.tag), " ".join(bone.flags)))

        translation = []
        for item in bone.translation:
            translation.append(str(item))

        rotation = []
        for item in bone.rotation:
            rotation.append(str(item))

        scale = []
        for item in bone.scale:
            scale.append(str(item))

        unk_58_str = " ".join(
            (str(bone.tag), " ".join(bone.flags), " ".join(translation), " ".join(rotation), " ".join(scale))
        )
        unk_50.append(unk_50_str)
        unk_58.append(unk_58_str)

    skeleton_xml.unknown_50 = jenkhash.hash_string(" ".join(unk_50))
    import zlib

    skeleton_xml.unknown_54 = zlib.crc32(" ".join(unk_50).encode())
    skeleton_xml.unknown_58 = zlib.crc32(" ".join(unk_58).encode())


def _map_light_from_cw(light: cw.Light) -> Light:
    light_type = light.type
    match light_type:
        case "Point":
            light_type = LightType.POINT
        case "Spot":
            light_type = LightType.SPOT
        case "Capsule":
            light_type = LightType.CAPSULE

    return Light(
        light_type=light_type,
        position=Vector(light.position),
        direction=Vector(light.direction),
        tangent=Vector(light.tangent),
        extent=Vector(light.extent),
        color=tuple(light.color),
        flashiness=LightFlashiness(light.flashiness),
        intensity=light.intensity,
        flags=light.flags,
        time_flags=light.time_flags,
        bone_id=light.bone_id,
        group_id=light.group_id,
        light_hash=light.light_hash,
        falloff=light.falloff,
        falloff_exponent=light.falloff_exponent,
        culling_plane_normal=Vector(light.culling_plane_normal),
        culling_plane_offset=light.culling_plane_offset,
        volume_intensity=light.volume_intensity,
        volume_size_scale=light.volume_size_scale,
        volume_outer_color=tuple(light.volume_outer_color),
        volume_outer_intensity=light.volume_outer_intensity,
        volume_outer_exponent=light.volume_outer_exponent,
        corona_size=light.corona_size,
        corona_intensity=light.corona_intensity,
        corona_z_bias=light.corona_z_bias,
        projected_texture_hash=light.projected_texture_hash,
        light_fade_distance=light.light_fade_distance,
        shadow_fade_distance=light.shadow_fade_distance,
        specular_fade_distance=light.specular_fade_distance,
        volumetric_fade_distance=light.volumetric_fade_distance,
        shadow_near_clip=light.shadow_near_clip,
        shadow_blur=light.shadow_blur,
        cone_inner_angle=light.cone_inner_angle,
        cone_outer_angle=light.cone_outer_angle,
    )


def _map_light_to_cw(light: Light) -> cw.Light:
    light_type = light.light_type
    match light_type:
        case LightType.POINT:
            light_type = "Point"
        case LightType.SPOT:
            light_type = "Spot"
        case LightType.CAPSULE:
            light_type = "Capsule"
    li = cw.Light()
    li.type = light_type
    li.position = Vector(light.position)
    li.direction = Vector(light.direction)
    li.tangent = Vector(light.tangent)
    li.extent = Vector(light.extent)
    li.color = list(light.color)
    li.flashiness = light.flashiness.value
    li.intensity = light.intensity
    li.flags = light.flags
    li.time_flags = light.time_flags
    li.bone_id = light.bone_id
    li.group_id = light.group_id
    li.light_hash = light.light_hash
    li.falloff = light.falloff
    li.falloff_exponent = light.falloff_exponent
    li.culling_plane_normal = Vector(light.culling_plane_normal)
    li.culling_plane_offset = light.culling_plane_offset
    li.volume_intensity = light.volume_intensity
    li.volume_size_scale = light.volume_size_scale
    li.volume_outer_color = list(light.volume_outer_color)
    li.volume_outer_intensity = light.volume_outer_intensity
    li.volume_outer_exponent = light.volume_outer_exponent
    li.corona_size = light.corona_size
    li.corona_intensity = light.corona_intensity
    li.corona_z_bias = light.corona_z_bias
    li.projected_texture_hash = light.projected_texture_hash
    li.light_fade_distance = light.light_fade_distance
    li.shadow_fade_distance = light.shadow_fade_distance
    li.specular_fade_distance = light.specular_fade_distance
    li.volumetric_fade_distance = light.volumetric_fade_distance
    li.shadow_near_clip = light.shadow_near_clip
    li.shadow_blur = light.shadow_blur
    li.cone_inner_angle = light.cone_inner_angle
    li.cone_outer_angle = light.cone_outer_angle
    return li


CW_VERTEX_DATA_TYPE_MAP = {
    "GTAV1": VertexDataType.DEFAULT,
    "GTAV2": VertexDataType.ENV_CLOTH,
    "GTAV3": VertexDataType.ENV_CLOTH_NO_TANGENT,
    "GTAV4": VertexDataType.BREAKABLE_GLASS,
}
CW_VERTEX_DATA_TYPE_INVERSE_MAP = {v: k for k, v in CW_VERTEX_DATA_TYPE_MAP.items()}


class CWDrawable:
    ASSET_FORMAT = AssetFormat.CWXML
    ASSET_VERSION = AssetVersion.GEN8
    ASSET_TYPE = AssetType.DRAWABLE

    def __init__(self, d: cw.Drawable):
        self._inner = d

    @property
    def name(self) -> str:
        return jenkhash.try_resolve_maybe_hashed_name(self._inner.name)

    @name.setter
    def name(self, v: str):
        self._inner.name = v

    @property
    def skeleton(self) -> Optional[Skeleton]:
        if not self._inner.joints:
            translation_limits = {}
            rotation_limits = {}
        else:
            translation_limits = {
                limit_xml.bone_id: SkelBoneTranslationLimit(Vector(limit_xml.min), Vector(limit_xml.max))
                for limit_xml in self._inner.joints.translation_limits
            }
            rotation_limits = {
                limit_xml.bone_id: SkelBoneRotationLimit(Vector(limit_xml.min), Vector(limit_xml.max))
                for limit_xml in self._inner.joints.rotation_limits
            }

        bones = []
        for bone_xml in self._inner.skeleton.bones:
            bones.append(
                SkelBone(
                    name=bone_xml.name,
                    tag=bone_xml.tag,
                    flags=_bone_flags_from_cw(bone_xml.flags),
                    position=Vector(bone_xml.translation),
                    rotation=Quaternion(bone_xml.rotation),
                    scale=Vector(bone_xml.scale),
                    parent_index=bone_xml.parent_index,
                    translation_limit=translation_limits.get(bone_xml.tag, None),
                    rotation_limit=rotation_limits.get(bone_xml.tag, None),
                )
            )

        return Skeleton(bones) if bones else None

    @skeleton.setter
    def skeleton(self, skel: Optional[Skeleton]):
        if skel is None:
            self._inner.skeleton = None
            self._inner.joints = None
            return

        s = cw.Skeleton()
        j = cw.Joints()
        for bone_index, bone in enumerate(skel.bones):
            b = cw.Bone()
            b.name = bone.name
            b.tag = bone.tag
            b.index = bone_index
            b.parent_index = bone.parent_index
            b.sibling_index = _find_bone_sibling_index(bone_index, skel)
            b.translation = bone.position
            b.rotation = bone.rotation
            b.scale = bone.scale
            b.flags = _bone_flags_to_cw(bone.flags)

            if bone.translation_limit is not None:
                tl = cw.BoneLimit()
                tl.bone_id = bone.tag
                tl.max = bone.translation_limit.max
                tl.min = bone.translation_limit.min
                j.translation_limits.append(tl)

            if bone.rotation_limit is not None:
                rl = cw.RotationLimit()
                rl.bone_id = bone.tag
                rl.max = bone.rotation_limit.max
                rl.min = bone.rotation_limit.min
                j.rotation_limits.append(rl)

            s.bones.append(b)

        _calculate_skeleton_unks(s)

        self._inner.skeleton = s
        if j.translation_limits or j.rotation_limits:
            self._inner.joints = j
        else:
            self._inner.joints = None

    @property
    def bounds(self) -> Optional[CWBound]:
        return apply_target(self, CWBound(self._inner.bounds)) if self._inner.bounds else None

    @bounds.setter
    def bounds(self, v: Optional[CWBound]):
        self._inner.bounds = canonical_asset(v, CWBound, self)._inner if v else None

    @property
    def shader_group(self) -> ShaderGroup | None:
        if self._inner.shader_group is None:
            return None

        def _map_parameter(param: cw.ShaderParameter) -> ShaderParameter:
            match param:
                case cw.VectorShaderParameter():
                    param_value = Vector((param.x, param.y, param.z, param.w))
                case cw.TextureShaderParameter():
                    param_value = param.texture_name or None
                case cw.ArrayShaderParameter():
                    param_value = [Vector(v) for v in param.values]

            return ShaderParameter(
                name=str(param.name),
                value=param_value,
            )

        def _map_shader(shader: cw.Shader) -> ShaderInst:
            return ShaderInst(
                name=str(shader.name),
                preset_filename=str(shader.filename),
                render_bucket=RenderBucket(shader.render_bucket),
                parameters=[_map_parameter(p) for p in shader.parameters],
            )

        def _map_embedded_textures(txd: cw.TextureDictionaryList | None) -> dict[str, EmbeddedTexture]:
            if txd is None:
                return {}

            return {t.name: EmbeddedTexture(t.name, t.width, t.height, None) for t in txd}

        sg = self._inner.shader_group
        return ShaderGroup([_map_shader(s) for s in sg.shaders], _map_embedded_textures(sg.texture_dictionary))

    @shader_group.setter
    def shader_group(self, v: ShaderGroup | None):
        if v is None:
            self._inner.shader_group = None
            return

        sg = cw.ShaderGroup()
        if v.embedded_textures:
            for tex in v.embedded_textures.values():
                t = cw.Texture()
                t.name = tex.name
                t.width = tex.width
                t.height = tex.height
                t.filename = tex.name + ".dds"
                # Other texture properties (format, mipmaps, etc.) are set by CW when importing the texture
                sg.texture_dictionary.append(t)

        for shader in v.shaders:
            assert shader.preset_filename is not None
            s = cw.Shader()
            s.name = shader.name
            s.filename = shader.preset_filename
            s.render_bucket = shader.render_bucket.value
            for param in shader.parameters:
                match param.value:
                    case None | str():
                        p = cw.TextureShaderParameter()
                        p.texture_name = param.value
                    case Vector():
                        p = cw.VectorShaderParameter()
                        p.x = param.value.x
                        p.y = param.value.y
                        p.z = param.value.z
                        p.w = param.value.w
                    case _:  # vector list
                        p = cw.ArrayShaderParameter()
                        p.values = param.value

                p.name = param.name
                s.parameters.append(p)

            if self.ASSET_VERSION == AssetVersion.GEN9:
                # Special case to initialize new parameters in gen9 shaders. These always have the same values and are
                # either hardcoded or unused, just ended up as parameters due to the new shader compilation pipeline for
                # gen9. For example, BloodZoneAdjust which got added to a buffer in gen9, when in gen8 it was inlined in
                # the shader itself. Required for ped blood decals, otherwise they break
                from ...shader import ShaderManager

                gen9_specific_defaults = ShaderManager.lookup_gen9_shader_params_defaults(shader.name)
                if gen9_specific_defaults:
                    for param_name, param_value in gen9_specific_defaults.items():
                        if any(p.name.lower() == param_name for p in s.parameters):
                            continue

                        if len(param_value) == 4:
                            p = cw.VectorShaderParameter()
                            p.x = param_value[0]
                            p.y = param_value[1]
                            p.z = param_value[2]
                            p.w = param_value[3]
                        else:
                            p = cw.ArrayShaderParameter()
                            p.values = [Vector(param_value[i : i + 4]) for i in range(0, len(param_value), 4)]

                        p.name = param_name
                        s.parameters.append(p)

            sg.shaders.append(s)

        self._inner.shader_group = sg

    @property
    def models(self) -> dict[LodLevel, list[Model]]:
        def _map_geometry(geom: cw.Geometry) -> Geometry:
            return Geometry(
                vertex_data_type=CW_VERTEX_DATA_TYPE_MAP.get(geom.vertex_buffer.get_element("layout").type),
                vertex_buffer=geom.vertex_buffer.data,
                index_buffer=geom.index_buffer.data,
                bone_ids=np.array(geom.bone_ids),
                shader_index=geom.shader_index,
            )

        def _map_model(model: cw.DrawableModel) -> Model:
            return Model(
                bone_index=model.bone_index,
                geometries=[_map_geometry(g) for g in model.geometries],
                render_bucket_mask=model.render_mask,
                has_skin=model.has_skin == 1,
                matrix_count=model.matrix_count,
                flags=model.flags,
            )

        def _map_models(models: list[cw.DrawableModel]) -> list[Model]:
            return [_map_model(m) for m in models]

        return {
            LodLevel.HIGH: _map_models(self._inner.drawable_models_high),
            LodLevel.MEDIUM: _map_models(self._inner.drawable_models_med),
            LodLevel.LOW: _map_models(self._inner.drawable_models_low),
            LodLevel.VERYLOW: _map_models(self._inner.drawable_models_vlow),
        }

    @models.setter
    def models(self, v: dict[LodLevel, list[Model]]):
        def _map_geometry(geom: Geometry) -> cw.Geometry:
            g = cw.Geometry()
            g.shader_index = geom.shader_index
            g.bone_ids = list(geom.bone_ids)
            g.vertex_buffer.data = geom.vertex_buffer
            g.vertex_buffer.get_element("layout").type = CW_VERTEX_DATA_TYPE_INVERSE_MAP[geom.vertex_data_type]
            g.index_buffer.data = geom.index_buffer

            positions = geom.vertex_buffer["Position"]
            g.bounding_box_max = Vector(np.max(positions, axis=0))
            g.bounding_box_min = Vector(np.min(positions, axis=0))
            return g

        def _map_model(model: Model) -> cw.DrawableModel:
            m = cw.DrawableModel()
            m.geometries = [_map_geometry(g) for g in model.geometries]
            m.render_mask = model.render_bucket_mask
            m.flags = model.flags
            m.has_skin = 1 if model.has_skin else 0
            m.bone_index = model.bone_index
            m.matrix_count = model.matrix_count
            return m

        inner = self._inner
        inner.drawable_models_high = [_map_model(m) for m in v.get(LodLevel.HIGH, [])]
        inner.drawable_models_med = [_map_model(m) for m in v.get(LodLevel.MEDIUM, [])]
        inner.drawable_models_low = [_map_model(m) for m in v.get(LodLevel.LOW, [])]
        inner.drawable_models_vlow = [_map_model(m) for m in v.get(LodLevel.VERYLOW, [])]
        inner.flags_high = len(inner.drawable_models_high)
        inner.flags_med = len(inner.drawable_models_med)
        inner.flags_low = len(inner.drawable_models_low)
        inner.flags_vlow = len(inner.drawable_models_vlow)

        # Calculate extents
        max_x = max_y = max_z = float("-inf")
        min_x = min_y = min_z = float("+inf")
        for geom_xml in inner.all_geoms:
            geom_max = geom_xml.bounding_box_max
            geom_min = geom_xml.bounding_box_min

            max_x = max(max_x, geom_max.x)
            max_y = max(max_y, geom_max.y)
            max_z = max(max_z, geom_max.z)
            min_x = min(min_x, geom_min.x)
            min_y = min(min_y, geom_min.y)
            min_z = min(min_z, geom_min.z)

        bbmax = Vector((max_x, max_y, max_z))
        bbmin = Vector((min_x, min_y, min_z))
        bs_center = (bbmin + bbmax) * 0.5
        bs_radius = (bbmax - bs_center).length
        inner.bounding_sphere_center = bs_center
        inner.bounding_sphere_radius = bs_radius
        inner.bounding_box_max = bbmax
        inner.bounding_box_min = bbmin

    @property
    def lod_thresholds(self) -> dict[LodLevel, float]:
        return {
            LodLevel.HIGH: self._inner.lod_dist_high,
            LodLevel.MEDIUM: self._inner.lod_dist_med,
            LodLevel.LOW: self._inner.lod_dist_low,
            LodLevel.VERYLOW: self._inner.lod_dist_vlow,
        }

    @lod_thresholds.setter
    def lod_thresholds(self, v: dict[LodLevel, float]):
        self._inner.lod_dist_high = v.get(LodLevel.HIGH, 9998.0)
        self._inner.lod_dist_med = v.get(LodLevel.MEDIUM, 9998.0)
        self._inner.lod_dist_low = v.get(LodLevel.LOW, 9998.0)
        self._inner.lod_dist_vlow = v.get(LodLevel.VERYLOW, 9998.0)

    @property
    def lights(self) -> list[Light]:
        return [_map_light_from_cw(light) for light in self._inner.lights]

    @lights.setter
    def lights(self, v: list[Light]):
        self._inner.lights = [_map_light_to_cw(light) for light in v]


class CWFragDrawable(CWDrawable):
    def __init__(self, d: cw.Drawable):
        super().__init__(d)

    @property
    def bounds(self) -> Optional[CWBound]:
        return None

    @bounds.setter
    def bounds(self, v: Optional[CWBound]):
        raise AssertionError("Cannot set bounds of FragDrawable")

    @property
    def lights(self) -> list[Light]:
        return []

    @lights.setter
    def lights(self, lights: list[Light]):
        raise AssertionError("Cannot set lights of FragDrawable")

    @property
    def frag_bound_matrix(self) -> Matrix:
        return self._inner.frag_bound_matrix

    @frag_bound_matrix.setter
    def frag_bound_matrix(self, v: Matrix):
        self._inner.frag_bound_matrix = Matrix(
            (
                v[0][:3],
                v[1][:3],
                v[2][:3],
                v[3][:3],
            )
        )

    @property
    def frag_extra_bound_matrices(self) -> list[Matrix]:
        return self._inner.frag_extra_bound_matrices

    @frag_extra_bound_matrices.setter
    def frag_extra_bound_matrices(self, v: list[Matrix]):
        self._inner.frag_extra_bound_matrices = [
            Matrix(
                (
                    m[0][:3],
                    m[1][:3],
                    m[2][:3],
                    m[3][:3],
                )
            )
            for m in v
        ]


class CWDrawableDictionary:
    ASSET_FORMAT = AssetFormat.CWXML
    ASSET_VERSION = AssetVersion.GEN8
    ASSET_TYPE = AssetType.DRAWABLE_DICTIONARY

    def __init__(self, d: cw.DrawableDictionary):
        self._inner = d

    @property
    def drawables(self) -> dict[str, CWDrawable]:
        dwd = self._inner
        return {
            jenkhash.try_resolve_maybe_hashed_name(drawable.name): apply_target(self, CWDrawable(drawable))
            for drawable in dwd
        }

    @drawables.setter
    def drawables(self, d: dict[str, CWDrawable]):
        dwd = self._inner
        dwd.clear()
        dwd.extend(canonical_asset(drawable, CWDrawable, self)._inner for drawable in d.values())

        dwd.sort(key=lambda d: jenkhash.name_to_hash(d.name))
