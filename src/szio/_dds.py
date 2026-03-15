"""
DDS file parsing utilities. Intended for internal use.
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
        if (pf.dwFlags & 0x4) != 0 and pf.dwFourCC == b"DX10":
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
