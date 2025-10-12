import math
from functools import cache

import numpy as np
import pymateria as pm

from ....types import Matrix, Quaternion, Vector
from ...jenkhash import try_resolve_maybe_hashed_name


def to_native_rgb(rgb: tuple[int, int, int]) -> pm.ColorRGB:
    return pm.ColorRGB(*rgb)


def to_native_rgba(rgba: tuple[int, int, int, int]) -> pm.ColorRGBA:
    return pm.ColorRGBA(*rgba)


def to_native_rgbaf(rgba: tuple[float, float, float, float]) -> pm.ColorRGBA:
    rgba = tuple(int(max(0, min(255, c * 255))) for c in rgba)
    return pm.ColorRGBA(*rgba)


def to_native_bgraf(rgba: tuple[float, float, float, float]) -> pm.ColorRGBA:
    rgba = tuple(int(max(0, min(255, c * 255))) for c in rgba)
    return pm.ColorRGBA(rgba[2], rgba[1], rgba[0], rgba[3])


def from_native_rgba(c: pm.ColorRGBA) -> tuple[int, int, int, int]:
    return (c.r, c.g, c.b, c.a)


def from_native_rgbaf(c: pm.ColorRGBA) -> tuple[float, float, float, float]:
    return (c.r / 255, c.g / 255, c.b / 255, c.a / 255)


# temporary workaround for some cases where the R and G components are swapped


def from_native_bgraf(c: pm.ColorRGBA) -> tuple[float, float, float, float]:
    return (c.b / 255, c.g / 255, c.r / 255, c.a / 255)


def to_native_uv(v: Vector) -> pm.UV:
    return pm.UV(*v.xy)


def to_native_vec3(v: Vector) -> pm.Vector3f:
    return pm.Vector3f(*v.xyz)


def to_native_vec4(v: Vector) -> pm.Vector4f:
    return pm.Vector4f(*v.xyzw)


def to_native_quat(v: Quaternion) -> pm.Quaternion:
    return pm.Quaternion(v.x, v.y, v.z, v.w)


def from_native_quat(v: pm.Quaternion) -> Quaternion:
    return Quaternion((v.w, v.x, v.y, v.z))


def to_native_mat34(m: Matrix) -> pm.Matrix34:
    shape = (len(m.col), len(m.row))
    match shape:
        case (4, 4):
            return pm.Matrix34(
                to_native_vec4(m.row[0]),
                to_native_vec4(m.row[1]),
                to_native_vec4(m.row[2]),
                to_native_vec4(m.row[3]),
            )
        case (3, 4):
            return pm.Matrix34(
                to_native_vec3(m.row[0]).to_vector4(math.nan),
                to_native_vec3(m.row[1]).to_vector4(math.nan),
                to_native_vec3(m.row[2]).to_vector4(math.nan),
                to_native_vec3(m.row[3]).to_vector4(math.nan),
            )
        case _:
            raise ValueError(f"Unsupported matrix shape {shape}")


def from_native_mat34(m: pm.Matrix34) -> Matrix:
    return Matrix(
        (
            m.col0.to_vector3().to_vector4(0.0),
            m.col1.to_vector3().to_vector4(0.0),
            m.col2.to_vector3().to_vector4(0.0),
            m.col3.to_vector3().to_vector4(1.0),
        )
    )


def to_native_aabb(bb_min: Vector, bb_max: Vector) -> pm.AABB3f:
    return pm.AABB3f(to_native_vec3(bb_min), to_native_vec3(bb_max))


def to_native_sphere(center: Vector, radius: float) -> pm.Sphere:
    return pm.Sphere(to_native_vec3(center), radius)


def _h2s(h: pm.gta5.CombinedHashString | pm.gta5.HashString) -> str:
    return try_resolve_maybe_hashed_name(h.string_or_placeholder.lower()) if h.hash != 0 else ""


def _s2h(s: str) -> pm.gta5.CombinedHashString:
    h = (int(s[5:], 16) & 0xFFFFFFFF) if s.startswith("hash_") else 0 if s == "" else s
    return pm.gta5.CombinedHashString(h)


def s2hs(s: str) -> pm.gta5.HashString:
    h = (int(s[5:], 16) & 0xFFFFFFFF) if s.startswith("hash_") else 0 if s == "" else s
    return pm.gta5.HashString(h)


@cache
def make_checkerboard_texture_data() -> np.ndarray:
    """Create magenta/black checkerboard texture for use when actual textures are missing."""
    magenta = [255, 0, 255, 255]
    black = [0, 0, 0, 255]
    tex_size = 16
    tile_size = 2

    tile_pattern = np.array([[0, 1], [1, 0]])
    checkerboard = np.tile(tile_pattern, (tex_size // 4, tex_size // 4))
    checkerboard = np.kron(checkerboard, np.ones((tile_size, tile_size), dtype=int))

    texture_data = np.empty((tex_size, tex_size, 4), dtype=np.uint8)
    texture_data[checkerboard == 0] = magenta
    texture_data[checkerboard != 0] = black
    return texture_data


def apply_target(parent_asset, asset):
    asset.ASSET_FORMAT = parent_asset.ASSET_FORMAT
    asset.ASSET_VERSION = parent_asset.ASSET_VERSION
    return asset
