import logging

import pymateria.gta5 as pm
import pymateria.gta5.gen8 as pmg8
import pymateria.gta5.gen9 as pmg9

from ....types import DataSource
from ...drawables import (
    EmbeddedTexture,
)
from ...textures import (
    AssetTextureDictionary,
)
from ._utils import (
    make_checkerboard_texture_data,
)


def _is_texture_compressed_g8(tex: pmg8.Texture) -> bool:
    match tex.format:
        case (
            pmg8.TextureFormat.DXT1
            | pmg8.TextureFormat.DXT2
            | pmg8.TextureFormat.DXT3
            | pmg8.TextureFormat.DXT4
            | pmg8.TextureFormat.DXT5
            | pmg8.TextureFormat.CTX1
            | pmg8.TextureFormat.DXT3A
            | pmg8.TextureFormat.DXT3A_1111
            | pmg8.TextureFormat.DXT5A
            | pmg8.TextureFormat.DXN
            | pmg8.TextureFormat.BC6
            | pmg8.TextureFormat.BC7
        ):
            return True
        case _:
            return False


def _drop_incomplete_mips_compressed(tex: pmg8.Texture | pmg9.Texture):
    """Removes mips from the first one whose data doesn't match its block-compressed size, so `export_dds` accepts
    textures from encoders that undersize mips smaller than a 4x4 block.
    """
    mips = tex.mips
    if not mips or not mips[0].layers:
        return

    def _num_blocks(w: int, h: int) -> int:
        return max(1, (w + 3) // 4) * max(1, (h + 3) // 4)

    w, h = tex.width, tex.height
    block_size = mips[0].layers[0].nbytes // _num_blocks(w, h)
    num_complete = 0
    for mip in mips:
        expected_size = _num_blocks(w, h) * block_size
        if any(layer.nbytes != expected_size for layer in mip.layers):
            break
        num_complete += 1
        w, h = max(1, w // 2), max(1, h // 2)

    for _ in range(len(mips) - max(1, num_complete)):
        mips.pop()


def _extract_embedded_texture_dds_g8(tex: pmg8.Texture) -> bytes:
    import io

    if _is_texture_compressed_g8(tex):
        _drop_incomplete_mips_compressed(tex)

    tex_dds = io.BytesIO()
    tex.export_dds(tex_dds)
    return tex_dds.getvalue()


def _import_dds(tex: pmg8.Texture | pmg9.Texture, data: DataSource | None) -> bool:
    if not data:
        return False

    try:
        with data.open() as data_stream:
            tex.import_dds(data_stream)
        return True
    except RuntimeError:
        import io

        from ....dds import DdsFile

        data_bytes = bytearray(data.read_bytes())
        try:
            dds = DdsFile.from_buffer(data_bytes)
            complete_mips = dds.complete_mip_count()
        except ValueError as e:
            err_msg = str(e)
            logging.getLogger(__name__).warning(f"Failed to embed texture '{tex.name}'. {err_msg}")
            return False

        if 0 < complete_mips < dds.header.dwMipMapCount:
            dds.header.dwMipMapCount = complete_mips
            try:
                with io.BytesIO(data_bytes) as data_stream:
                    tex.import_dds(data_stream)
                return True
            except RuntimeError:
                pass

        logging.getLogger(__name__).warning(f"Failed to embed texture '{tex.name}'. DDS image data may be corrupted.")
        return False


def load_textures_from_native_g8(txd: pmg8.TextureDictionary | None) -> dict[str, EmbeddedTexture]:
    if txd is None:
        return {}

    def _map_embedded_texture(tex: pmg8.Texture) -> EmbeddedTexture:
        tex_data_bytes = _extract_embedded_texture_dds_g8(tex)
        tex_data = DataSource.create(tex_data_bytes, f"{tex.name}.dds")
        return EmbeddedTexture(tex.name, tex.width, tex.height, tex_data)

    return {t.name: _map_embedded_texture(t) for t in txd.textures.values()}


def load_txd_from_native_g8(txd: pmg8.TextureDictionary | None) -> AssetTextureDictionary:
    return AssetTextureDictionary(textures=load_textures_from_native_g8(txd))


def save_textures_to_native_g8(
    textures: dict[str, EmbeddedTexture], out_native_textures: dict[str, pmg8.Texture] | None = None
) -> pmg8.TextureDictionary:
    txd = pmg8.TextureDictionary()
    for embedded_tex in textures.values():
        tex = pmg8.Texture()
        tex.name = embedded_tex.name
        if out_native_textures is not None:
            out_native_textures[tex.name] = tex
        if not _import_dds(tex, embedded_tex.data):
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

    return txd


def save_txd_to_native_g8(txd: AssetTextureDictionary) -> pmg8.TextureDictionary:
    return save_textures_to_native_g8(txd.textures)
