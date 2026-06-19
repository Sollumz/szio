import os
from pathlib import Path
from typing import IO, Iterable, Protocol, runtime_checkable

__all__ = [
    "RpfArchive",
    "open_rpf",
]


_RPF7_MAGIC = b"7FPR"
_RPF8_MAGIC = b"8FPR"
_MAGIC_LEN = 4


@runtime_checkable
class RpfArchive(Protocol):
    """Read-only view over an RPF archive.

    `inner_path` is forward-slash, archive-relative, no leading slash; `""` is
    the archive root.
    """

    def close(self) -> None:
        """Release the archive's resources.

        The cache may call this while resolved entries are still referenced, so
        already-resolved entries must stay readable afterwards: close() may only
        release re-openable resources (e.g. an owned stream).
        """
        ...

    def exists(self, inner_path: str) -> bool: ...

    def is_file(self, inner_path: str) -> bool: ...

    def is_dir(self, inner_path: str) -> bool: ...

    def list_dir(self, inner_path: str) -> Iterable[str]: ...

    def read_bytes(self, inner_path: str) -> bytes: ...

    def open_bytes(self, inner_path: str) -> IO[bytes]: ...

    def open_nested(self, inner_path: str) -> "RpfArchive | None":
        """Open a nested archive entry directly, skipping a bytes round-trip.

        Return None to make the caller fall back to `open_bytes` + `open_rpf`.
        """
        ...


def open_rpf(
    source: IO[bytes] | os.PathLike | str,
    *,
    filename: str | None = None,
    owns_stream: bool = False,
) -> RpfArchive:
    """Open an RPF archive, detecting the format (RPF7/RPF8) from the header magic.

    `filename` is a basename hint for backends that need one (pymateria's
    stream-mode constructor does). Derived from path-like sources; required for
    stream sources whose format needs it.

    `owns_stream` (stream sources only): when True the archive owns the stream
    and closes it on close(). Ignored for path sources. A stream must be
    seekable, the magic is peeked then rewound.
    """
    if isinstance(source, (str, os.PathLike)):
        path = Path(source)
        if filename is None:
            filename = path.name
        # Peek the magic, then hand RPF7 the *path* (not a stream) so it reads
        # the TOC via native I/O.
        with open(path, "rb") as f:
            magic = f.read(_MAGIC_LEN)
        if magic == _RPF7_MAGIC:
            return _make_rpf7_from_path(path, filename)
        if magic != _RPF8_MAGIC:
            raise OSError(f"not a valid RPF archive: bad magic {magic!r}")
        # RPF8: open a fresh stream for the (future) reader, which consumes it.
        # Bad magic short-circuited above without a second open.
        stream: IO[bytes] = open(path, "rb")
        try:
            return _make_rpf8(stream, filename, True)
        except BaseException:
            stream.close()
            raise

    stream = source
    magic = stream.read(_MAGIC_LEN)
    stream.seek(0)
    try:
        if magic == _RPF7_MAGIC:
            return _make_rpf7(stream, filename, owns_stream)
        if magic == _RPF8_MAGIC:
            return _make_rpf8(stream, filename, owns_stream)
    except BaseException:
        if owns_stream:
            stream.close()
        raise

    if owns_stream:
        stream.close()
    raise OSError(f"not a valid RPF archive: bad magic {magic!r}")


def _make_rpf7_from_path(path: Path, filename: str | None) -> RpfArchive:
    try:
        from .gta5.native.rpf7 import _Rpf7Archive
    except ImportError as e:
        raise ImportError("RPF7 support requires pymateria.") from e
    return _Rpf7Archive.from_path(path, filename)


def _make_rpf7(stream: IO[bytes], filename: str | None, owns_stream: bool) -> RpfArchive:
    try:
        from .gta5.native.rpf7 import _Rpf7Archive
    except ImportError as e:
        raise ImportError("RPF7 support requires pymateria.") from e
    if not filename:
        raise ValueError("opening an RPF7 from a stream requires a filename hint")
    return _Rpf7Archive(stream, filename, owns_stream=owns_stream)


def _make_rpf8(stream: IO[bytes], filename: str | None, owns_stream: bool) -> RpfArchive:
    raise NotImplementedError("RPF8 reading not yet implemented")
