import os
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Iterator

from ..vfs import VPath


@contextmanager
def import_source(path: Path | VPath) -> Iterator[str | os.PathLike | IO[bytes]]:
    """Yield a source both pymateria's `import_rsc(...)` and `ET.parse(...)` accept.

    In-archive VPath -> an open binary stream, closed on exit. Plain `Path` or
    OS-backed VPath -> the path itself, so native path I/O is used unchanged.
    """
    if isinstance(path, VPath) and path.is_inside_archive():
        with path.open("rb") as stream:
            yield stream
    else:
        yield path if isinstance(path, Path) else os.fspath(path)
