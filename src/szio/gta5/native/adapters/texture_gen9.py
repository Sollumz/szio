import ctypes
import itertools
import logging

import numpy as np
import pymateria.gta5 as pm
import pymateria.gta5.gen9 as pmg9

from ....types import DataSource
from ...drawables import (
    EmbeddedTexture,
)
from ...textures import AssetTextureDictionary
from ._utils import (
    make_checkerboard_texture_data,
)
from .texture import (
    _import_dds,
)


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


def load_textures_from_native_g9(txd: pmg9.TextureDictionary | None) -> dict[str, EmbeddedTexture]:
    if txd is None:
        return {}

    def _map_embedded_texture(tex: pmg9.Texture) -> EmbeddedTexture:
        tex_data_bytes = _extract_embedded_texture_dds_g9(tex)
        tex_data = DataSource.create(tex_data_bytes, f"{tex.name}.dds")
        return EmbeddedTexture(tex.name, tex.width, tex.height, tex_data)

    return {t.name: _map_embedded_texture(t) for t in txd.textures.values()}


def load_txd_from_native_g9(txd: pmg9.TextureDictionary | None) -> AssetTextureDictionary:
    return AssetTextureDictionary(textures=load_textures_from_native_g9(txd))


def save_textures_to_native_g9(textures: dict[str, EmbeddedTexture]) -> pmg9.TextureDictionary:
    txd = pmg9.TextureDictionary()
    for embedded_tex in textures.values():
        tex = pmg9.Texture()
        tex.name = embedded_tex.name
        tex.dimension = pmg9.ImageDimension.DIM_2D
        if not _import_dds(tex, embedded_tex.data):
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

    return txd


def save_txd_to_native_g9(txd: AssetTextureDictionary) -> pmg9.TextureDictionary:
    return save_textures_to_native_g9(txd.textures)
