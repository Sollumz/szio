import io
import struct

import numpy as np


def decompress_row(data_rle_reader: io.BytesIO) -> tuple[int, int, bytes, int, int | None, bytes | None]:
    start2 = None
    end2 = None
    data2 = None
    start1 = data_rle_reader.read(1)[0]
    end1 = data_rle_reader.read(1)[0]
    n = (end1 - start1) + 1
    data1 = data_rle_reader.read(n)
    if n > 0:
        start2 = data_rle_reader.read(1)[0]

        if start2 != 255:
            end2 = data_rle_reader.read(1)[0]

            n2 = (end2 - start2) + 1
            data2 = data_rle_reader.read(n2)

    return start1, end1, data1, start2, end2, data2


def decompress_shattermap(data_rle: bytes, cols: int, rows: int) -> np.ndarray:
    if not data_rle:
        return np.empty((0, 0), dtype=np.float32)

    data_rle_reader = io.BytesIO(data_rle)
    data_rle_reader.seek(2 * rows, io.SEEK_SET)

    out_data = np.empty((rows, cols), dtype=np.float32)
    for row in range(rows):
        start1, end1, data1, start2, end2, data2 = decompress_row(data_rle_reader)

        p = 0
        out_data_row = out_data[rows - 1 - row]
        if data1:
            for col in range(start1):
                out_data_row[col] = 0.0
            for i, b in enumerate(data1):
                col = start1 + i
                out_data_row[col] = b / 255
            p = start1 + len(data1)

        if data2:
            for col in range(p, start2):
                out_data_row[col] = 1.0
            for i, b in enumerate(data2):
                col = start2 + i
                out_data_row[col] = b / 255
            p = start2 + len(data2)

        for col in range(p, cols):
            out_data_row[col] = 0.0

    return out_data


def compress_row(data_row: np.ndarray) -> tuple[int, int, bytes, int, int | None, bytes | None]:
    cols = len(data_row)
    non_zeros = np.where(data_row != 0)[0]
    fulls = np.where(data_row == 255)[0]
    if len(fulls) > 0:
        # Split into contiguous chunks
        fulls_runs_split_points = np.where(np.diff(fulls) != 1)[0] + 1
        fulls_runs = np.split(fulls, fulls_runs_split_points)
        # Find the largest chunk
        longest_fulls_run = max(fulls_runs, key=len)
    else:
        longest_fulls_run = np.array([], dtype=np.int64)
    needs_split = len(longest_fulls_run) > 1

    start1 = non_zeros[0]
    end1 = (longest_fulls_run[0] - 1) if needs_split else non_zeros[-1]
    if end1 == -1:
        end1 = 0
    data1 = bytes(data_row[start1 : end1 + 1])

    if needs_split:
        start2 = longest_fulls_run[-1] + 1
        if start2 == cols:
            start2 -= 1
        end2 = non_zeros[-1]
        data2 = bytes(data_row[start2 : end2 + 1])
    else:
        start2 = 255
        end2 = None
        data2 = None

    return start1, end1, data1, start2, end2, data2


def compress_shattermap(shattermap: np.ndarray) -> bytes:
    if shattermap.shape == (0, 0):
        return bytes()

    rows, cols = shattermap.shape
    data = (shattermap.clip(0.0, 1.0) * 255).astype(np.uint8)
    data_rle_builder = io.BytesIO()

    # Space for row offsets (a 16-bit uint per row)
    data_rle_builder.write(b"\x00\x00" * rows)

    def _u8(v: int) -> bytes:
        return struct.pack("B", v)

    def _u16(v: int) -> bytes:
        return struct.pack("<H", v)

    # Compress each row
    rows_start = data_rle_builder.tell()
    row_offsets = []
    for data_row in reversed(data):
        row_offsets.append(data_rle_builder.tell() - rows_start)

        start1, end1, data1, start2, end2, data2 = compress_row(data_row)
        data_rle_builder.write(_u8(start1))
        data_rle_builder.write(_u8(end1))
        if ((end1 - start1) + 1) > 0:
            data_rle_builder.write(data1)
            data_rle_builder.write(_u8(start2))
            if start2 != 255:
                data_rle_builder.write(_u8(end2))
                data_rle_builder.write(data2)

    # Fill out row offsets
    data_rle_builder.seek(0, io.SEEK_SET)
    for row_offset in row_offsets:
        data_rle_builder.write(_u16(row_offset))

    return data_rle_builder.getvalue()


def shattermap_from_ascii(data_ascii: list[str], cols: int, rows: int) -> np.ndarray:
    def _get_value(value):
        if value == "##":
            return 0.0
        elif value == "--":
            return 1.0
        else:
            value = int(value, 16)
            return value / 255

    data = np.empty((rows, cols), dtype=np.float32)
    for row_idx, row in enumerate(reversed(data_ascii)):
        frow = [row[x : x + 2] for x in range(0, len(row), 2)]
        # Need to check for malformed shattermaps. ZModeler shattermaps seem to be missing a value of "--" when "--"
        # appears in a row. We check for this specific case and insert a "--" to the row.
        # We don't handle other malformed data, an error will be logged in the try/except below.
        if len(frow) == (cols - 1):
            try:
                idx = frow.index("--")
            except ValueError:
                idx = None
            if idx is not None:
                frow.insert(idx, "--")

        data_row = data[row_idx]
        for col_idx, value in enumerate(frow):
            data_row[col_idx] = _get_value(value)

    return data


def row_to_ascii(
    cols: int, start1: int, end1: int, data1: bytes, start2: int, end2: int | None, data2: bytes | None
) -> str:
    row_str = "##" * start1
    row_str += "".join(f"{v:02X}" for v in data1)
    if start2 != 255:
        row_str += "--" * (start2 - end1 - 1)
        row_str += "".join(f"{v:02X}" for v in data2)
        row_str += "##" * (cols - end2 - 1)
    else:
        row_str += "##" * (cols - end1 - 1)
    return row_str


def shattermap_to_ascii(shattermap: np.ndarray) -> list[str]:
    rows, cols = shattermap.shape
    data = (shattermap.clip(0.0, 1.0) * 255).astype(np.uint8)
    rows = [row_to_ascii(cols, *compress_row(data_row)) for data_row in reversed(data)]
    return rows


def shattermap_compressed_to_ascii(data_rle: bytes, cols: int, rows: int) -> list[str]:
    data_rle_reader = io.BytesIO(data_rle)
    data_rle_reader.seek(2 * rows, io.SEEK_SET)
    rows = [row_to_ascii(cols, *decompress_row(data_rle_reader)) for _ in range(rows)]
    return rows
