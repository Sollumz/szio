from pathlib import Path
from typing import Sequence

import numpy as np

from ....types import Matrix, Quaternion, Vector
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
from ...textures import AssetTextureDictionary
from .. import drawable as cw
from .bound import (
    load_bound_from_cw,
    save_bound_to_cw,
)

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


def _load_skeleton(d: cw.Drawable) -> Skeleton | None:
    if not d.skeleton or not d.skeleton.bones:
        return None

    if not d.joints:
        translation_limits = {}
        rotation_limits = {}
    else:
        translation_limits = {
            limit_xml.bone_id: SkelBoneTranslationLimit(Vector(limit_xml.min), Vector(limit_xml.max))
            for limit_xml in d.joints.translation_limits
        }
        rotation_limits = {
            limit_xml.bone_id: SkelBoneRotationLimit(Vector(limit_xml.min), Vector(limit_xml.max))
            for limit_xml in d.joints.rotation_limits
        }

    bones = []
    for bone_xml in d.skeleton.bones:
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

    return Skeleton(bones)


def _load_shader_group(d: cw.Drawable) -> ShaderGroup | None:
    if d.shader_group is None:
        return None

    def _map_parameter(param: cw.ShaderParameter) -> ShaderParameter:
        match param:
            case cw.VectorShaderParameter():
                param_value = Vector((param.x, param.y, param.z, param.w))
            case cw.TextureShaderParameter():
                param_value = param.texture_name or None
            case cw.ArrayShaderParameter():
                param_value = [Vector(v) for v in param.values]

        return ShaderParameter(name=str(param.name), value=param_value)

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

    sg = d.shader_group
    return ShaderGroup([_map_shader(s) for s in sg.shaders], _map_embedded_textures(sg.texture_dictionary))


def _load_models(d: cw.Drawable) -> dict[LodLevel, list[Model]]:
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
        LodLevel.HIGH: _map_models(d.drawable_models_high),
        LodLevel.MEDIUM: _map_models(d.drawable_models_med),
        LodLevel.LOW: _map_models(d.drawable_models_low),
        LodLevel.VERYLOW: _map_models(d.drawable_models_vlow),
    }


def _load_lod_thresholds(d: cw.Drawable) -> dict[LodLevel, float]:
    return {
        LodLevel.HIGH: d.lod_dist_high,
        LodLevel.MEDIUM: d.lod_dist_med,
        LodLevel.LOW: d.lod_dist_low,
        LodLevel.VERYLOW: d.lod_dist_vlow,
    }


def _load_lights(d: cw.Drawable) -> list[Light]:
    return [_map_light_from_cw(light) for light in d.lights]


def _load_bounds(d: cw.Drawable):
    return load_bound_from_cw(d.bounds) if d.bounds else None


def load_drawable_from_cw(d: cw.Drawable) -> AssetDrawable:
    """Load a CW XML Drawable into an AssetDrawable dataclass."""
    return AssetDrawable(
        name=jenkhash.try_resolve_maybe_hashed_name(d.name),
        bounds=_load_bounds(d),
        skeleton=_load_skeleton(d),
        shader_group=_load_shader_group(d),
        models=_load_models(d),
        lod_thresholds=_load_lod_thresholds(d),
        lights=_load_lights(d),
    )


def load_frag_drawable_from_cw(d: cw.Drawable) -> AssetFragDrawable:
    """Load a CW XML Drawable (from a fragment) into an AssetFragDrawable dataclass."""
    return AssetFragDrawable(
        name=jenkhash.try_resolve_maybe_hashed_name(d.name),
        bounds=None,
        skeleton=_load_skeleton(d),
        shader_group=_load_shader_group(d),
        models=_load_models(d),
        lod_thresholds=_load_lod_thresholds(d),
        lights=[],
        frag_bound_matrix=d.frag_bound_matrix,
        frag_extra_bound_matrices=d.frag_extra_bound_matrices or [],
    )


def load_drawable_dictionary_from_cw(d: cw.DrawableDictionary) -> AssetDrawableDictionary:
    """Load a CW XML DrawableDictionary into an AssetDrawableDictionary dataclass."""
    return AssetDrawableDictionary(
        drawables={
            jenkhash.try_resolve_maybe_hashed_name(drawable.name): load_drawable_from_cw(drawable) for drawable in d
        }
    )


def load_txd_from_cw(txd: cw.TextureDictionaryList) -> AssetTextureDictionary:
    return AssetTextureDictionary(
        textures={t.name: EmbeddedTexture(t.name, t.width, t.height, None) for t in txd.value}
    )


def _save_skeleton(skel: Skeleton | None, d: cw.Drawable):
    if skel is None:
        d.skeleton = None
        d.joints = None
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
    d.skeleton = s
    if j.translation_limits or j.rotation_limits:
        d.joints = j
    else:
        d.joints = None


def _save_shader_group(v: ShaderGroup | None, d: cw.Drawable, asset_version: AssetVersion = AssetVersion.GEN8):
    if v is None:
        d.shader_group = None
        return

    sg = cw.ShaderGroup()
    if v.embedded_textures:
        for tex in v.embedded_textures.values():
            t = cw.Texture()
            t.name = tex.name
            t.width = tex.width
            t.height = tex.height
            t.filename = tex.name + ".dds"
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

        if asset_version == AssetVersion.GEN9:
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

    d.shader_group = sg


def _save_models(v: dict[LodLevel, list[Model]], d: cw.Drawable):
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

    d.drawable_models_high = [_map_model(m) for m in v.get(LodLevel.HIGH, [])]
    d.drawable_models_med = [_map_model(m) for m in v.get(LodLevel.MEDIUM, [])]
    d.drawable_models_low = [_map_model(m) for m in v.get(LodLevel.LOW, [])]
    d.drawable_models_vlow = [_map_model(m) for m in v.get(LodLevel.VERYLOW, [])]
    d.flags_high = len(d.drawable_models_high)
    d.flags_med = len(d.drawable_models_med)
    d.flags_low = len(d.drawable_models_low)
    d.flags_vlow = len(d.drawable_models_vlow)

    # Calculate extents
    all_geoms = d.all_geoms
    if all_geoms:
        max_x = max_y = max_z = float("-inf")
        min_x = min_y = min_z = float("+inf")
        for geom_xml in all_geoms:
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
        bs_radius = float(np.linalg.norm(bbmax - bs_center))
    else:
        bbmax = Vector((0.0, 0.0, 0.0))
        bbmin = Vector((0.0, 0.0, 0.0))
        bs_center = Vector((0.0, 0.0, 0.0))
        bs_radius = 0.0

    d.bounding_sphere_center = bs_center
    d.bounding_sphere_radius = bs_radius
    d.bounding_box_max = bbmax
    d.bounding_box_min = bbmin


def _save_lod_thresholds(v: dict[LodLevel, float], d: cw.Drawable):
    default_lod_dist = 0.0 if d.is_empty else 9998.0
    d.lod_dist_high = v.get(LodLevel.HIGH, default_lod_dist)
    d.lod_dist_med = v.get(LodLevel.MEDIUM, default_lod_dist)
    d.lod_dist_low = v.get(LodLevel.LOW, default_lod_dist)
    d.lod_dist_vlow = v.get(LodLevel.VERYLOW, default_lod_dist)


def _save_lights(v: list[Light], d: cw.Drawable):
    d.lights = [_map_light_to_cw(light) for light in v]


def _save_bounds(v, d: cw.Drawable):
    if v is None:
        d.bounds = None
    else:
        d.bounds = save_bound_to_cw(v)


def save_drawable_to_cw(asset: AssetDrawable, asset_version: AssetVersion = AssetVersion.GEN8) -> cw.Drawable:
    """Convert an AssetDrawable dataclass to a CW XML Drawable object."""
    d = cw.Drawable()
    d.name = asset.name
    d.frag_bound_matrix = None
    _save_skeleton(asset.skeleton, d)
    _save_shader_group(asset.shader_group, d, asset_version)
    _save_models(asset.models, d)
    _save_lod_thresholds(asset.lod_thresholds, d)
    _save_lights(asset.lights, d)
    _save_bounds(asset.bounds, d)
    return d


def save_frag_drawable_to_cw(asset: AssetFragDrawable, asset_version: AssetVersion = AssetVersion.GEN8) -> cw.Drawable:
    """Convert an AssetFragDrawable dataclass to a CW XML Drawable object."""
    d = save_drawable_to_cw(asset, asset_version)
    if asset.frag_bound_matrix is not None:
        d.frag_bound_matrix = Matrix(
            (
                asset.frag_bound_matrix[0][:3],
                asset.frag_bound_matrix[1][:3],
                asset.frag_bound_matrix[2][:3],
                asset.frag_bound_matrix[3][:3],
            )
        )
    d.frag_extra_bound_matrices = [
        Matrix(
            (
                m[0][:3],
                m[1][:3],
                m[2][:3],
                m[3][:3],
            )
        )
        for m in asset.frag_extra_bound_matrices
    ]
    return d


def save_drawable_dictionary_to_cw(
    asset: AssetDrawableDictionary, asset_version: AssetVersion = AssetVersion.GEN8
) -> cw.DrawableDictionary:
    """Convert an AssetDrawableDictionary dataclass to a CW XML DrawableDictionary object."""
    dwd = cw.DrawableDictionary()
    for name, drawable in asset.drawables.items():
        d = save_drawable_to_cw(drawable, asset_version)
        d.name = name
        dwd.append(d)
    dwd.sort(key=lambda d: jenkhash.name_to_hash(d.name))
    return dwd


def save_txd_to_cw(asset: AssetTextureDictionary) -> cw.TextureDictionaryList:
    txd = cw.TextureDictionaryList()
    for tex in asset.textures.values():
        t = cw.Texture()
        t.name = tex.name
        t.width = tex.width
        t.height = tex.height
        t.filename = tex.name + ".dds"
        txd.value.append(t)

    return txd
