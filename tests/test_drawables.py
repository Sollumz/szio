import logging
from pathlib import Path

import pytest

import szio.gta5.native
from szio.dds import DdsFile
from szio.gta5 import (
    AssetTextureDictionary,
    AssetDrawable,
    AssetFormat,
    AssetTarget,
    AssetVersion,
    EmbeddedTexture,
    RenderBucket,
    ShaderGroup,
    ShaderInst,
    save_asset,
    try_load_asset,
)
from szio.types import DataSource

TESTS_DIR = Path(__file__).parent

skip_if_no_native_backend = pytest.mark.skipif(
    not szio.gta5.native.IS_BACKEND_AVAILABLE,
    reason="szio.gta5.native backend is not available",
)


@skip_if_no_native_backend
@pytest.mark.parametrize("target_version", (AssetVersion.GEN8, AssetVersion.GEN9))
@pytest.mark.parametrize(
    "tex_file",
    [
        *(TESTS_DIR / "data/textures/bad_mips").glob("*.dds"),
        *(TESTS_DIR / "data/textures/good_mips").glob("*.dds"),
    ],
    ids=lambda p: p.name,
)
def test_drawables_embed_texture_with_mipmaps(tex_file: Path, target_version: AssetVersion, tmp_path: Path, caplog):
    with caplog.at_level(logging.WARNING):
        tex_data = tex_file.read_bytes()

        drw = AssetDrawable()
        drw.shader_group = ShaderGroup(
            shaders=[
                ShaderInst(
                    name="default", preset_filename="default.sps", render_bucket=RenderBucket.OPAQUE, parameters=[]
                )
            ],
            embedded_textures={
                "test_tex": EmbeddedTexture(
                    name="test_tex",
                    width=-1,
                    height=-1,
                    data=DataSource.create(tex_data),
                ),
            },
        )

        target = AssetTarget(AssetFormat.NATIVE, target_version)
        save_asset(drw, [target], tmp_path, "test")

        # Basic sanity check that it correctly embedded the texture
        loaded_drw = try_load_asset(tmp_path / "test.ydr")
        loaded_tex_data = loaded_drw.shader_group.embedded_textures["test_tex"].data.read_bytes()
        loaded_dds = DdsFile.from_buffer(bytearray(loaded_tex_data))
        dds = DdsFile.from_buffer(bytearray(tex_data))
        assert loaded_dds.resolution == dds.resolution
        if "good_mips" in str(tex_file):
            # textures with good mips should have kept all mips
            assert loaded_dds.header.dwMipMapCount == dds.header.dwMipMapCount
        else:
            # but with bad mips, some should have been removed
            assert loaded_dds.header.dwMipMapCount < dds.header.dwMipMapCount

    errors_and_warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert not errors_and_warnings, "Unexpected warnings/errors logged:\n" + "\n".join(
        f"  [{r.levelname}] {r.name}: {r.message}" for r in errors_and_warnings
    )


@skip_if_no_native_backend
@pytest.mark.parametrize("target_version", (AssetVersion.GEN8, AssetVersion.GEN9))
@pytest.mark.parametrize(
    "tex_file",
    [
        *(TESTS_DIR / "data/textures/bad_mips").glob("*.dds"),
        *(TESTS_DIR / "data/textures/good_mips").glob("*.dds"),
    ],
    ids=lambda p: p.name,
)
def test_txd_embed_texture_with_mipmaps(tex_file: Path, target_version: AssetVersion, tmp_path: Path, caplog):
    with caplog.at_level(logging.WARNING):
        tex_data = tex_file.read_bytes()

        txd = AssetTextureDictionary()
        txd.textures = {
            "test_tex": EmbeddedTexture(
                name="test_tex",
                width=-1,
                height=-1,
                data=DataSource.create(tex_data),
            ),
        }

        target = AssetTarget(AssetFormat.NATIVE, target_version)
        save_asset(txd, [target], tmp_path, "test")

        # Basic sanity check that it correctly embedded the texture
        loaded_txd = try_load_asset(tmp_path / "test.ytd")
        print(f"{loaded_txd=}")
        loaded_tex_data = loaded_txd.textures["test_tex"].data.read_bytes()
        loaded_dds = DdsFile.from_buffer(bytearray(loaded_tex_data))
        dds = DdsFile.from_buffer(bytearray(tex_data))
        assert loaded_dds.resolution == dds.resolution
        if "good_mips" in str(tex_file):
            # textures with good mips should have kept all mips
            assert loaded_dds.header.dwMipMapCount == dds.header.dwMipMapCount
        else:
            # but with bad mips, some should have been removed
            assert loaded_dds.header.dwMipMapCount < dds.header.dwMipMapCount

    errors_and_warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert not errors_and_warnings, "Unexpected warnings/errors logged:\n" + "\n".join(
        f"  [{r.levelname}] {r.name}: {r.message}" for r in errors_and_warnings
    )


@skip_if_no_native_backend
@pytest.mark.parametrize("target_version", (AssetVersion.GEN8, AssetVersion.GEN9))
def test_txd_load_native_texture_with_undersized_mips(target_version: AssetVersion, tmp_path: Path):
    import numpy as np
    import pymateria as pma
    import pymateria.gta5 as pm
    import pymateria.gta5.gen8 as pmg8
    import pymateria.gta5.gen9 as pmg9

    if target_version == AssetVersion.GEN8:
        tex = pmg8.Texture()
        tex.format = pmg8.TextureFormat.DXT5
        tex.layer_count = 1
        txd = pmg8.TextureDictionary()
    else:
        tex = pmg9.Texture()
        tex.format = pmg9.BufferFormat.BC3_UNORM
        tex.dimension = pmg9.ImageDimension.DIM_2D
        txd = pmg9.TextureDictionary()
    tex.name = "test_tex"
    tex.width = 24
    tex.height = 24
    tex.depth = 1
    # 24x24 DXT5 sized at 1 byte/pixel: mips 6x6, 3x3 and 1x1 are smaller than their 4x4 blocks need
    for size in (576, 144, 36, 9, 1):
        mip = pm.TextureMip()
        mip.layers.append(np.zeros(size, np.uint8))
        tex.mips.append(mip)
    txd.textures[pm.HashString(tex.name)] = tex
    type(txd).export_rsc(txd, tmp_path / "test.ytd", pma.ExportSettings())

    loaded_txd = try_load_asset(tmp_path / "test.ytd")

    loaded_dds = DdsFile.from_buffer(bytearray(loaded_txd.textures["test_tex"].data.read_bytes()))
    assert loaded_dds.resolution == (24, 24)
    assert loaded_dds.header.dwMipMapCount == 2
