"""RPF7 archive reader backed by pymateria.rpf7.PackFile.

Implements the `szio.rpf.RpfArchive` Protocol. Lazily imported by `open_rpf`.
"""

import io
from typing import IO, Iterable

from pymateria import Buffer
from pymateria.rpf7 import (
    PackFile,
    PackFileEntry,
    PackFileEntryArchive,
    PackFileEntryDirectory,
    PackFileEntryResource,
)
from pymateria.rsc7 import Header

__all__ = ["_Rpf7Archive"]


class _BufferStream(io.BufferedIOBase):
    """Read-only stream for a pymateria Buffer, without intermediate copies."""

    __slots__ = ("_view", "_size", "_pos")

    def __init__(self, buffer: Buffer):
        self._view: memoryview | None = memoryview(buffer.raw)
        self._size = len(self._view)
        self._pos = 0

    def _loaded(self) -> memoryview:
        assert self._view is not None
        return self._view

    def _check_open(self) -> None:
        if self.closed:
            raise ValueError("I/O operation on closed file.")

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def read(self, size: int | None = -1) -> bytes:
        self._check_open()
        view = self._loaded()
        pos = self._pos
        end = len(view) if size is None or size < 0 else min(pos + size, len(view))
        if pos >= end:
            return b""
        self._pos = end
        return bytes(view[pos:end])

    def read1(self, size: int | None = -1) -> bytes:
        return self.read(size)

    def readinto(self, b) -> int:
        self._check_open()
        view = self._loaded()
        out = memoryview(b).cast("B")
        n = max(0, min(len(out), len(view) - self._pos))
        out[:n] = view[self._pos : self._pos + n]
        self._pos += n
        return n

    def readinto1(self, b) -> int:
        return self.readinto(b)

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        self._check_open()
        if whence == io.SEEK_SET:
            pos = offset
        elif whence == io.SEEK_CUR:
            pos = self._pos + offset
        elif whence == io.SEEK_END:
            pos = self._size + offset
        else:
            raise ValueError(f"invalid whence ({whence}, should be 0, 1 or 2)")
        if pos < 0:
            raise ValueError(f"negative seek value {pos}")
        self._pos = pos
        return pos

    def tell(self) -> int:
        self._check_open()
        return self._pos

    def close(self) -> None:
        if self._view is not None:
            self._view.release()
            self._view = None
        super().close()


class _ResourceStream(_BufferStream):
    """Stream over a resource entry that serves its RSC7 header from the archive
    TOC, loading the resource data only once a read goes past it.
    """

    __slots__ = ("_entry", "_header")

    def __init__(self, entry: PackFileEntryResource):
        self._entry = entry
        self._header: bytes | None = None
        self._view = None
        self._size = entry.size
        self._pos = 0

    def _loaded(self) -> memoryview:
        if self._view is None:
            self._view = memoryview(self._entry.raw_buffer.raw)
        return self._view

    def read(self, size: int | None = -1) -> bytes:
        self._check_open()
        pos = self._pos
        if self._view is None and size is not None and 0 <= size and pos + size <= Header.HEADER_SIZE:
            # Use the entry header if reading the starting bytes only
            if self._header is None:
                self._header = self._entry.header.to_bytes()
            self._pos = pos + size
            return self._header[pos : pos + size]
        return super().read(size)


class _Rpf7Archive:
    """RPF7 archive reader (GTA5)."""

    __slots__ = ("_pf", "_stream", "_owns_stream", "_files", "_dirs", "_children")

    def __init__(self, stream: IO[bytes], filename: str, *, owns_stream: bool):
        # Real stream here; None-stream constructors (from_path / _from_packfile)
        # bypass __init__ via cls.__new__.
        self._stream = stream
        self._owns_stream = owns_stream
        assert filename is not None
        self._pf = PackFile.import_rpf(stream, filename)
        self._init_index()

    @classmethod
    def from_path(cls, path, filename: str | None = None) -> "_Rpf7Archive":
        """Open a top-level RPF7 from a path via native lazy I/O.

        Passing the path (not a Python stream) lets pymateria read the TOC and
        load entries through native file access, far faster and cheaper on
        memory than streaming a multi-GB TOC back through Python.
        """
        obj = cls.__new__(cls)
        obj._stream = None
        obj._owns_stream = False
        obj._pf = PackFile.import_rpf(str(path), filename or "")
        obj._init_index()
        return obj

    @classmethod
    def _from_packfile(cls, pf: PackFile) -> "_Rpf7Archive":
        obj = cls.__new__(cls)
        obj._stream = None
        obj._owns_stream = False
        obj._pf = pf
        obj._init_index()
        return obj

    def _init_index(self) -> None:
        """Build the in-memory file/dir index from `self._pf` (shared by all
        constructors)."""
        self._files: dict[str, PackFileEntry] = {}
        self._dirs: set[str] = {""}
        self._children: dict[str, dict[str, None]] = {}  # ordered set of child names of each directory
        self._build_index()

    def _build_index(self) -> None:
        files = self._files
        dirs = self._dirs
        children = self._children

        # str(PurePosixPath) is ~20x faster than .as_posix() (skips a redundant
        # str-replace).
        for e in self._pf.entries:
            path = str(e.path)
            if path == "" or path == ".":
                continue
            parent, _, name = path.rpartition("/")

            if isinstance(e, PackFileEntryDirectory):
                dirs.add(path)
            else:
                files[path] = e
            children.setdefault(parent, {})[name] = None

            # Backfill missing parent dirs (malformed/third-party archives).
            # Register each in BOTH _dirs and its parent's children so it stays
            # enumerable (list_dir/iterdir/glob), not just visible to is_dir.
            cursor = parent
            while cursor and cursor not in dirs:
                dirs.add(cursor)
                cparent, _, cname = cursor.rpartition("/")
                children.setdefault(cparent, {})[cname] = None
                cursor = cparent

    @staticmethod
    def _norm(p: str) -> str:
        return p.strip("/")

    def close(self) -> None:
        if self._owns_stream:
            try:
                self._stream.close()
            finally:
                self._owns_stream = False

    def exists(self, inner_path: str) -> bool:
        p = self._norm(inner_path)
        return p in self._files or p in self._dirs

    def is_file(self, inner_path: str) -> bool:
        return self._norm(inner_path) in self._files

    def is_dir(self, inner_path: str) -> bool:
        return self._norm(inner_path) in self._dirs

    def list_dir(self, inner_path: str) -> Iterable[str]:
        p = self._norm(inner_path)
        if p not in self._dirs:
            raise FileNotFoundError(f"no such directory in archive: {inner_path!r}")
        return list(self._children.get(p, ()))

    def read_bytes(self, inner_path: str) -> bytes:
        entry = self._require_file(inner_path)
        if isinstance(entry, PackFileEntryResource):
            return bytes(entry.raw_buffer.raw)
        return bytes(entry.export().raw)

    def open_bytes(self, inner_path: str) -> IO[bytes]:
        entry = self._require_file(inner_path)
        if isinstance(entry, PackFileEntryResource):
            return _ResourceStream(entry)
        return _BufferStream(entry.export())

    def open_nested(self, inner_path: str) -> "_Rpf7Archive | None":
        entry = self._require_file(inner_path)
        if not isinstance(entry, PackFileEntryArchive):
            return None
        return _Rpf7Archive._from_packfile(entry.archive)

    def _require_file(self, inner_path: str) -> PackFileEntry:
        p = self._norm(inner_path)
        entry = self._files.get(p)
        if entry is None:
            if p in self._dirs:
                raise IsADirectoryError(f"is a directory: {inner_path!r}")
            raise FileNotFoundError(f"no such entry in archive: {inner_path!r}")
        return entry
