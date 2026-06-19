"""RPF7 archive reader backed by pymateria.rpf7.PackFile.

Implements the `szio.rpf.RpfArchive` Protocol. Lazily imported by `open_rpf`.
"""

import io
from collections import defaultdict
from typing import IO, Iterable

from pymateria.rpf7 import (
    PackFile,
    PackFileEntry,
    PackFileEntryArchive,
    PackFileEntryDirectory,
    PackFileEntryResource,
)

__all__ = ["_Rpf7Archive"]


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
        self._children: dict[str, list[str]] = defaultdict(list)
        self._build_index()

    def _build_index(self) -> None:
        files = self._files
        dirs = self._dirs
        children = self._children
        # Dedup per parent: an explicit dir entry and the backfill below must not
        # insert the same child twice.
        child_set: dict[str, set[str]] = defaultdict(set)

        def add_child(parent: str, name: str) -> None:
            if name not in child_set[parent]:
                child_set[parent].add(name)
                children[parent].append(name)

        # str(PurePosixPath) is ~20x faster than .as_posix() (skips a redundant
        # str-replace).
        for e in self._pf.entries:
            path = str(e.path)
            if path == "" or path == ".":
                continue
            sep = path.rfind("/")
            if sep == -1:
                parent = ""
                name = path
            else:
                parent = path[:sep]
                name = path[sep + 1 :]

            if isinstance(e, PackFileEntryDirectory):
                dirs.add(path)
            else:
                files[path] = e
            add_child(parent, name)

            # Backfill missing parent dirs (malformed/third-party archives).
            # Register each in BOTH _dirs and its parent's children so it stays
            # enumerable (list_dir/iterdir/glob), not just visible to is_dir.
            cursor = parent
            while cursor and cursor not in dirs:
                dirs.add(cursor)
                csep = cursor.rfind("/")
                if csep != -1:
                    cparent, cname = cursor[:csep], cursor[csep + 1 :]
                else:
                    cparent, cname = "", cursor
                add_child(cparent, cname)
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
        return list(self._children.get(p, []))

    def read_bytes(self, inner_path: str) -> bytes:
        entry = self._require_file(inner_path)
        if isinstance(entry, PackFileEntryResource):
            return bytes(entry.raw_buffer.raw)
        buf = io.BytesIO()
        entry.export(buf)
        return buf.getvalue()

    def open_bytes(self, inner_path: str) -> IO[bytes]:
        entry = self._require_file(inner_path)
        if isinstance(entry, PackFileEntryResource):
            # BytesIO copies the buffer once into its own storage; no intermediate
            # bytes() copy needed.
            return io.BytesIO(entry.raw_buffer.raw)
        buf = io.BytesIO()
        entry.export(buf)
        buf.seek(0)
        return buf

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
