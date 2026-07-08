"""
DDS file parsing and manipulation utilities.
"""

import ctypes
from dataclasses import dataclass

__all__ = [
    "DDS_PIXELFORMAT",
    "DDS_HEADER",
    "DDS_HEADER_DXT10",
    "DdsFile",
]


class DDS_PIXELFORMAT(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.c_uint32),
        ("dwFlags", ctypes.c_uint32),
        ("dwFourCC", ctypes.c_char * 4),
        ("dwRGBBitCount", ctypes.c_uint32),
        ("dwRBitMask", ctypes.c_uint32),
        ("dwGBitMask", ctypes.c_uint32),
        ("dwBBitMask", ctypes.c_uint32),
        ("dwABitMask", ctypes.c_uint32),
    ]


class DDS_HEADER(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.c_uint32),
        ("dwFlags", ctypes.c_uint32),
        ("dwHeight", ctypes.c_uint32),
        ("dwWidth", ctypes.c_uint32),
        ("dwPitchOrLinearSize", ctypes.c_uint32),
        ("dwDepth", ctypes.c_uint32),
        ("dwMipMapCount", ctypes.c_uint32),
        ("dwReserved1", ctypes.c_uint32 * 11),
        ("ddspf", DDS_PIXELFORMAT),
        ("dwCaps", ctypes.c_uint32),
        ("dwCaps2", ctypes.c_uint32),
        ("dwCaps3", ctypes.c_uint32),
        ("dwCaps4", ctypes.c_uint32),
        ("dwReserved2", ctypes.c_uint32),
    ]


class DDS_HEADER_DXT10(ctypes.Structure):
    _fields_ = [
        ("dxgiFormat", ctypes.c_uint32),
        ("resourceDimension", ctypes.c_uint32),
        ("miscFlag", ctypes.c_uint32),
        ("arraySize", ctypes.c_uint32),
        ("miscFlag2", ctypes.c_uint32),
    ]


@dataclass(slots=True, frozen=True)
class DdsFile:
    buffer: memoryview
    header: DDS_HEADER
    header10: DDS_HEADER_DXT10 | None
    pixel_data: memoryview

    @property
    def width(self) -> int:
        return int(self.header.dwWidth)

    @property
    def height(self) -> int:
        return int(self.header.dwHeight)

    @property
    def resolution(self) -> tuple[int, int]:
        return self.width, self.height

    @property
    def is_compressed(self):
        if self.header10 is not None:
            # https://learn.microsoft.com/en-us/windows/win32/api/dxgiformat/ne-dxgiformat-dxgi_format
            f = self.header10.dxgiFormat
            return 70 <= f <= 84 or 94 <= f <= 99  # BC1 through BC7
        else:
            _COMPRESSED_FOURCC = (
                b"DXT1",
                b"DXT2",
                b"DXT3",
                b"DXT4",
                b"DXT5",
                b"BC4U",
                b"BC4S",
                b"BC5U",
                b"BC5S",
                b"ATI1",
                b"ATI2",
            )
            return self.header.ddspf.dwFourCC in _COMPRESSED_FOURCC

    def drop_mip(self) -> bytes:
        """Rebuilds the file's bytes with the top mip level removed. The instance is not modified.

        The result's base level is bit-identical to mip 1 of the input (width/height halved,
        clamped to 1), which makes it suitable for deriving lower-resolution texture variants
        that stay consistent with the original's mip chain.
        """
        header = self.header
        if header.dwCaps2 & _DDSCAPS2_CUBEMAP:
            raise ValueError("Cubemap textures are not supported")
        if header.dwCaps2 & _DDSCAPS2_VOLUME:
            raise ValueError("Volume textures are not supported")
        header10 = self.header10
        if header10 is not None:
            if header10.resourceDimension == _DDS_DIMENSION_TEXTURE3D:
                raise ValueError("Volume textures are not supported")
            if header10.miscFlag & _DDS_RESOURCE_MISC_TEXTURECUBE:
                raise ValueError("Cubemap textures are not supported")
            if header10.arraySize > 1:
                raise ValueError("Texture arrays are not supported")

        mip_count = max(1, int(header.dwMipMapCount)) if header.dwFlags & _DDSD_MIPMAPCOUNT else 1
        if mip_count < 2:
            raise ValueError(f"Cannot drop a mip level: the texture only has {mip_count}")

        block_size, bits_per_pixel = _format_layout(self)
        base_mip_size = _mip_size(self.width, self.height, block_size, bits_per_pixel)
        new_width = max(1, self.width // 2)
        new_height = max(1, self.height // 2)

        if len(self.pixel_data) < base_mip_size:
            raise ValueError(
                f"Unexpected pixel data size: expected at least {base_mip_size} bytes for a {self.width}x{self.height} "
                f"texture, got {len(self.pixel_data)}"
            )

        # Update a copy of the header bytes so this instance stays untouched.
        header_size = len(self.buffer) - len(self.pixel_data)
        out = bytearray(self.buffer[:header_size])
        out_header = DDS_HEADER.from_buffer(out, 4)
        out_header.dwWidth = new_width
        out_header.dwHeight = new_height
        out_header.dwMipMapCount = mip_count - 1
        if header.dwFlags & _DDSD_LINEARSIZE:
            out_header.dwPitchOrLinearSize = _mip_size(new_width, new_height, block_size, bits_per_pixel)
        elif header.dwFlags & _DDSD_PITCH:
            # One row: a row of blocks for block-compressed formats, a row of pixels otherwise.
            out_header.dwPitchOrLinearSize = _mip_size(new_width, 1, block_size, bits_per_pixel)

        return bytes(out) + bytes(self.pixel_data[base_mip_size:])

    @staticmethod
    def from_buffer(buffer) -> "DdsFile":
        buffer = memoryview(buffer)
        if buffer.readonly:
            raise ValueError("Buffer must be writable")
        if buffer.ndim != 1 or buffer.itemsize != 1:
            raise ValueError(f"Buffer must be a 1D byte buffer, got ndim={buffer.ndim}, itemsize={buffer.itemsize}")

        HEADER_SIZE = 4 + ctypes.sizeof(DDS_HEADER)

        if len(buffer) < HEADER_SIZE:
            raise ValueError(
                f"Buffer too small to contain a DDS header: expected at least {HEADER_SIZE} bytes, got {len(buffer)}"
            )

        magic = buffer[:4]
        if magic != b"DDS ":
            raise ValueError(f"Invalid DDS magic bytes: expected 'DDS ', got {bytes(magic)!r}")
        header = DDS_HEADER.from_buffer(buffer, 4)

        header10 = None
        pixel_data_offset = HEADER_SIZE
        pf = header.ddspf
        if (pf.dwFlags & _DDPF_FOURCC) != 0 and pf.dwFourCC == b"DX10":
            HEADER10_SIZE = ctypes.sizeof(DDS_HEADER_DXT10)

            if len(buffer) < HEADER_SIZE + HEADER10_SIZE:
                raise ValueError(
                    f"Buffer too small to contain a DX10 extended header: "
                    f"expected at least {HEADER_SIZE + HEADER10_SIZE} bytes, got {len(buffer)}"
                )

            header10 = DDS_HEADER_DXT10.from_buffer(buffer, HEADER_SIZE)
            pixel_data_offset += HEADER10_SIZE

        pixel_data = buffer[pixel_data_offset:]
        return DdsFile(buffer, header, header10, pixel_data)


# DDS_HEADER.dwFlags
_DDSD_PITCH = 0x8
_DDSD_MIPMAPCOUNT = 0x20000
_DDSD_LINEARSIZE = 0x80000
# DDS_PIXELFORMAT.dwFlags
_DDPF_FOURCC = 0x4
# DDS_HEADER.dwCaps2
_DDSCAPS2_CUBEMAP = 0x200
_DDSCAPS2_VOLUME = 0x200000
# DDS_HEADER_DXT10.resourceDimension / miscFlag
_DDS_DIMENSION_TEXTURE3D = 4
_DDS_RESOURCE_MISC_TEXTURECUBE = 0x4

# Bytes per 4x4 block for the block-compressed legacy FourCC formats.
_FOURCC_BLOCK_SIZES = {
    b"DXT1": 8,
    b"DXT2": 16,
    b"DXT3": 16,
    b"DXT4": 16,
    b"DXT5": 16,
    b"ATI1": 8,
    b"BC4U": 8,
    b"BC4S": 8,
    b"ATI2": 16,
    b"BC5U": 16,
    b"BC5S": 16,
}


def _dxgi_block_size(dxgi_format: int) -> int | None:
    """Bytes per 4x4 block for block-compressed DXGI formats, `None` if not block-compressed.
    https://learn.microsoft.com/en-us/windows/win32/api/dxgiformat/ne-dxgiformat-dxgi_format
    """
    if 70 <= dxgi_format <= 72 or 79 <= dxgi_format <= 81:  # BC1, BC4
        return 8
    if 73 <= dxgi_format <= 78 or 82 <= dxgi_format <= 84 or 94 <= dxgi_format <= 99:  # BC2, BC3, BC5, BC6H, BC7
        return 16
    return None


def _dxgi_bits_per_pixel(dxgi_format: int) -> int | None:
    """Bits per pixel for plain uncompressed color DXGI formats."""
    if 1 <= dxgi_format <= 4:  # R32G32B32A32
        return 128
    if 5 <= dxgi_format <= 8:  # R32G32B32
        return 96
    if 9 <= dxgi_format <= 18:  # R16G16B16A16, R32G32
        return 64
    if 23 <= dxgi_format <= 43 or dxgi_format == 67 or 87 <= dxgi_format <= 93:
        # R10G10B10A2, R11G11B10, R8G8B8A8, R16G16, R32, R9G9B9E5, B8G8R8A8/B8G8R8X8
        return 32
    if 48 <= dxgi_format <= 59 or 85 <= dxgi_format <= 86 or dxgi_format == 115:
        # R8G8, R16, B5G6R5, B5G5R5A1, B4G4R4A4
        return 16
    if 60 <= dxgi_format <= 65:  # R8, A8
        return 8
    return None


def _format_layout(dds: DdsFile) -> tuple[int | None, int]:
    """Resolves the pixel format to `(block_size, bits_per_pixel)` for mip size math:
    `(block_size, 0)` for block-compressed formats, `(None, bits)` for plain uncompressed ones.
    Raises `ValueError` for formats whose mip layout we cannot compute.
    """
    pf = dds.header.ddspf
    if dds.header10 is not None:
        dxgi_format = int(dds.header10.dxgiFormat)
        block_size = _dxgi_block_size(dxgi_format)
        if block_size is not None:
            return block_size, 0
        bits = _dxgi_bits_per_pixel(dxgi_format)
        if bits is not None:
            return None, bits
        raise ValueError(f"Unsupported DXGI format {dxgi_format}")
    if pf.dwFlags & _DDPF_FOURCC:
        block_size = _FOURCC_BLOCK_SIZES.get(pf.dwFourCC)
        if block_size is None:
            raise ValueError(f"Unsupported FourCC {bytes(pf.dwFourCC)!r}")
        return block_size, 0
    bits = int(pf.dwRGBBitCount)
    if bits == 0:
        raise ValueError("Unsupported pixel format: no FourCC and dwRGBBitCount is 0")
    return None, bits


def _mip_size(width: int, height: int, block_size: int | None, bits_per_pixel: int) -> int:
    if block_size is not None:
        return max(1, (width + 3) // 4) * max(1, (height + 3) // 4) * block_size
    return ((width * bits_per_pixel + 7) // 8) * height
