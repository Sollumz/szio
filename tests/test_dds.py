import pytest

from szio.dds import DDS_HEADER, DDS_HEADER_DXT10, DdsFile

DDSD_CAPS = 0x1
DDSD_HEIGHT = 0x2
DDSD_WIDTH = 0x4
DDSD_PITCH = 0x8
DDSD_PIXELFORMAT = 0x1000
DDSD_MIPMAPCOUNT = 0x20000
DDSD_LINEARSIZE = 0x80000

DDPF_ALPHAPIXELS = 0x1
DDPF_FOURCC = 0x4
DDPF_RGB = 0x40

DDSCAPS2_CUBEMAP = 0x200


def _make_dds(
    width,
    height,
    mip_sizes,
    *,
    fourcc=None,
    dxgi=None,
    bits=0,
    pitch=None,
    caps2=0,
    array_size=1,
    misc_flag=0,
    resource_dimension=3,
) -> bytes:
    header = DDS_HEADER()
    header.dwSize = 124
    flags = DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PIXELFORMAT
    if len(mip_sizes) > 1:
        flags |= DDSD_MIPMAPCOUNT
    if pitch is not None:
        flags |= DDSD_PITCH
        header.dwPitchOrLinearSize = pitch
    else:
        flags |= DDSD_LINEARSIZE
        header.dwPitchOrLinearSize = mip_sizes[0]
    header.dwFlags = flags
    header.dwWidth = width
    header.dwHeight = height
    header.dwMipMapCount = len(mip_sizes)
    header.dwCaps2 = caps2
    header.ddspf.dwSize = 32
    if dxgi is not None:
        header.ddspf.dwFlags = DDPF_FOURCC
        header.ddspf.dwFourCC = b"DX10"
    elif fourcc is not None:
        header.ddspf.dwFlags = DDPF_FOURCC
        header.ddspf.dwFourCC = fourcc
    else:
        header.ddspf.dwFlags = DDPF_RGB | DDPF_ALPHAPIXELS
        header.ddspf.dwRGBBitCount = bits

    blob = bytearray(b"DDS ")
    blob += bytes(header)
    if dxgi is not None:
        header10 = DDS_HEADER_DXT10()
        header10.dxgiFormat = dxgi
        header10.resourceDimension = resource_dimension
        header10.arraySize = array_size
        header10.miscFlag = misc_flag
        blob += bytes(header10)
    # Each mip level is filled with a distinct byte so slicing errors show up in the assertions.
    blob += b"".join(bytes([0x10 + i]) * size for i, size in enumerate(mip_sizes))
    return bytes(blob)


def _parse(data: bytes) -> DdsFile:
    return DdsFile.from_buffer(bytearray(data))


def _drop_mip(data: bytes) -> bytes:
    return _parse(data).drop_mip()


# 16x8 BC1 (8 bytes per 4x4 block): 4x2 blocks, 2x1, 1x1, 1x1, 1x1
BC1_16X8_MIPS = [64, 16, 8, 8, 8]


def test_drop_mip_bc1_legacy():
    data = _make_dds(16, 8, BC1_16X8_MIPS, fourcc=b"DXT1")

    result = _parse(_drop_mip(data))

    assert result.resolution == (8, 4)
    assert result.header.dwMipMapCount == 4
    assert result.header.dwPitchOrLinearSize == 16  # 2x1 blocks x 8 bytes
    assert bytes(result.pixel_data) == data[128 + 64 :]


def test_drop_mip_repeated_to_smallest():
    data = _make_dds(16, 8, BC1_16X8_MIPS, fourcc=b"DXT1")

    for _ in range(4):
        data = _drop_mip(data)
    result = _parse(data)

    assert result.resolution == (1, 1)
    assert result.header.dwMipMapCount == 1
    assert bytes(result.pixel_data) == b"\x14" * 8

    # Only one mip left now, so there is nothing more to drop
    with pytest.raises(ValueError, match="only has 1"):
        result.drop_mip()


def test_drop_mip_does_not_modify_instance():
    data = _make_dds(16, 8, BC1_16X8_MIPS, fourcc=b"DXT1")
    dds = _parse(data)

    first = dds.drop_mip()

    assert bytes(dds.buffer) == data
    assert dds.resolution == (16, 8)
    assert dds.header.dwMipMapCount == 5
    assert dds.drop_mip() == first


def test_drop_mip_dxt5_block_size():
    # DXT5 uses 16-byte blocks: same block counts as BC1 but double the bytes
    data = _make_dds(16, 8, [128, 32, 16, 16, 16], fourcc=b"DXT5")

    result = _parse(_drop_mip(data))

    assert result.resolution == (8, 4)
    assert result.header.dwPitchOrLinearSize == 32
    assert bytes(result.pixel_data) == data[128 + 128 :]


def test_drop_mip_bc7_dx10():
    # 16x16 BC7: 4x4 blocks x 16 bytes, then 2x2, 1x1, 1x1, 1x1
    data = _make_dds(16, 16, [256, 64, 16, 16, 16], dxgi=98)

    dropped = data
    for _ in range(2):
        dropped = _drop_mip(dropped)
    result = _parse(dropped)

    assert result.resolution == (4, 4)
    assert result.header.dwMipMapCount == 3
    assert result.header10 is not None
    assert result.header10.dxgiFormat == 98
    assert result.header.dwPitchOrLinearSize == 16
    assert bytes(result.pixel_data) == data[148 + 320 :]  # 20-byte DX10 header, mips 0-1 dropped


def test_drop_mip_uncompressed_rgba_dx10():
    # 16x8 R8G8B8A8_UNORM (DXGI 28): width*height*4 bytes per mip
    data = _make_dds(16, 8, [512, 128, 32, 8, 4], dxgi=28)

    result = _parse(_drop_mip(data))

    assert result.resolution == (8, 4)
    assert result.header.dwMipMapCount == 4
    assert result.header10.dxgiFormat == 28
    assert result.header.dwPitchOrLinearSize == 128
    assert bytes(result.pixel_data) == data[148 + 512 :]


def test_drop_mip_uncompressed_pitch():
    # 8x4 RGBA8: width*height*4 bytes per mip, pitch = width*4
    data = _make_dds(8, 4, [128, 32, 8, 4], bits=32, pitch=32)

    result = _parse(_drop_mip(data))

    assert result.resolution == (4, 2)
    assert result.header.dwMipMapCount == 3
    assert result.header.dwPitchOrLinearSize == 16
    assert bytes(result.pixel_data) == data[128 + 128 :]


def test_drop_mip_uncompressed_odd_width_tight_rows():
    # 10x6 RGB8 (24 bpp): rows are tightly packed with no DWORD alignment, so mip sizes are
    # 30x6=180, then 5x3 -> 15x3=45, 2x1 -> 6, 1x1 -> 3
    data = _make_dds(10, 6, [180, 45, 6, 3], bits=24, pitch=30)

    result = _parse(_drop_mip(data))

    assert result.resolution == (5, 3)
    assert result.header.dwMipMapCount == 3
    assert result.header.dwPitchOrLinearSize == 15  # (5 * 24 + 7) // 8
    assert bytes(result.pixel_data) == data[128 + 180 :]


def test_drop_mip_block_compressed_with_pitch_flag():
    # Some legacy writers set DDSD_PITCH instead of DDSD_LINEARSIZE for block-compressed textures;
    # the pitch is then a row of blocks: 4 blocks x 8 bytes for the 16-wide base, 2 x 8 after the drop
    data = _make_dds(16, 8, BC1_16X8_MIPS, fourcc=b"DXT1", pitch=32)

    result = _parse(_drop_mip(data))

    assert result.resolution == (8, 4)
    assert result.header.dwPitchOrLinearSize == 16
    assert bytes(result.pixel_data) == data[128 + 64 :]


def test_drop_mip_nonsquare_clamps_dimensions():
    # 16x4 BC1: 4x1 blocks, 2x1, 1x1, 1x1, 1x1; height hits 1 before width
    data = _make_dds(16, 4, [32, 16, 8, 8, 8], fourcc=b"DXT1")

    dropped = data
    for _ in range(3):
        dropped = _drop_mip(dropped)
    result = _parse(dropped)

    assert result.resolution == (2, 1)
    assert result.header.dwMipMapCount == 2
    assert bytes(result.pixel_data) == data[128 + 56 :]


def test_drop_mip_odd_dimensions():
    # 10x6 BC1: 3x2 blocks (48), then 5x3 -> 2x1 blocks (16), then 2x1 -> 1x1 block (8)
    data = _make_dds(10, 6, [48, 16, 8], fourcc=b"DXT1")

    result = _parse(_drop_mip(data))

    assert result.resolution == (5, 3)
    assert result.header.dwMipMapCount == 2
    assert result.header.dwPitchOrLinearSize == 16
    assert bytes(result.pixel_data) == data[128 + 48 :]


def test_drop_mip_without_mip_chain():
    data = _make_dds(16, 8, [64], fourcc=b"DXT1")

    with pytest.raises(ValueError, match="only has 1"):
        _drop_mip(data)


@pytest.mark.parametrize(
    "kwargs, match",
    [
        ({"fourcc": b"DXT1", "caps2": DDSCAPS2_CUBEMAP}, "Cubemap"),
        ({"dxgi": 98, "misc_flag": 0x4}, "Cubemap"),
        ({"dxgi": 98, "resource_dimension": 4}, "Volume"),
        ({"dxgi": 98, "array_size": 2}, "arrays"),
        ({"fourcc": b"UYVY"}, "FourCC"),
        ({"dxgi": 68}, "DXGI"),  # R8G8_B8G8_UNORM: packed 4:2:2 formats are not supported
    ],
    ids=["cubemap-caps", "cubemap-dx10", "volume-dx10", "array-dx10", "unknown-fourcc", "packed-dx10"],
)
def test_drop_mip_unsupported_textures(kwargs, match):
    data = _make_dds(16, 8, BC1_16X8_MIPS, **kwargs)

    with pytest.raises(ValueError, match=match):
        _drop_mip(data)


def test_from_buffer_rejects_non_dds():
    with pytest.raises(ValueError):
        _parse(b"not a dds file")

    with pytest.raises(ValueError):
        _parse(b"XXXX" + bytes(200))
