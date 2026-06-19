import errno
import fnmatch
import functools
import io
import os
import pathlib
import re
from collections import OrderedDict
from typing import IO, Iterator, TypeAlias

from . import rpf as _rpf
from .rpf import RpfArchive
from .types import DataSource, _DataSourceFile

__all__ = [
    "VPath",
    "clear_archive_cache",
]


class _OsLayer:
    """Frozen, hashable layer holding the OS root and path components."""

    __slots__ = ("root", "parts")

    def __init__(self, root: str, parts: tuple[str, ...]) -> None:
        self.root = root
        self.parts = parts

    def __hash__(self) -> int:
        return hash((self.root, self.parts))

    def __eq__(self, other: object) -> bool:
        return (
            other.__class__ is _OsLayer
            and self.root == other.root
            and self.parts == other.parts
        )

    def __repr__(self) -> str:
        return f"_OsLayer(root={self.root!r}, parts={self.parts!r})"


class _RpfLayer:
    __slots__ = ("parts",)

    def __init__(self, parts: tuple[str, ...]) -> None:
        self.parts = parts

    def __hash__(self) -> int:
        return hash(self.parts)

    def __eq__(self, other: object) -> bool:
        return other.__class__ is _RpfLayer and self.parts == other.parts

    def __repr__(self) -> str:
        return f"_RpfLayer(parts={self.parts!r})"


_Layer: TypeAlias = _OsLayer | _RpfLayer
_ArchiveKey: TypeAlias = tuple


class _OsResolved:
    """Resolution result: the path lives on the OS filesystem.

    `os_path` is the on-disk leaf path, even when it crossed `.rpf` *directories*.
    """

    __slots__ = ("os_path",)

    def __init__(self, os_path: pathlib.Path) -> None:
        self.os_path = os_path


class _ArchiveResolved:
    """Resolution result: the path is an entry inside an RPF archive.

    `archive` is the innermost archive containing the entry, `key` its
    `_ArchiveCache` key, and `inner` the archive-relative path within it.
    """

    __slots__ = ("archive", "key", "inner")

    def __init__(self, archive: "RpfArchive", key: "_ArchiveKey", inner: str) -> None:
        self.archive = archive
        self.key = key
        self.inner = inner


_Resolution: TypeAlias = "_OsResolved | _ArchiveResolved"


def _is_rpf_component(component: str) -> bool:
    # Lowercase only the suffix, not the whole component.
    return len(component) >= 4 and component[-4:].lower() == ".rpf"


# Like pathlib's `_ignore_error`: stat methods (exists/is_file/is_dir) swallow
# only "not found"-class errors and re-raise the rest (bad archive, EACCES, ...),
# so `exists() is False` means absent, not "present but unopenable".
_IGNORED_ERRNOS = frozenset((errno.ENOENT, errno.ENOTDIR, errno.EBADF, errno.ELOOP))
_IGNORED_WINERRORS = frozenset((21, 123, 1921))  # NOT_READY, INVALID_NAME, CANT_RESOLVE_FILENAME


def _ignore_error(exc: OSError) -> bool:
    return (
        getattr(exc, "errno", None) in _IGNORED_ERRNOS
        or getattr(exc, "winerror", None) in _IGNORED_WINERRORS
    )


def _normalize_segment(segment: "str | os.PathLike | VPath") -> tuple[str, list[str]]:
    if isinstance(segment, pathlib.PurePath):
        anchor = segment.anchor
        parts = segment.parts
        return anchor, list(parts[1:] if anchor else parts)
    if isinstance(segment, VPath):
        s = str(segment)
    elif isinstance(segment, str):
        s = segment
    elif isinstance(segment, os.PathLike):
        s = os.fspath(segment)
    else:
        raise TypeError(f"VPath expects str, os.PathLike or VPath, got {type(segment).__name__}")
    p = pathlib.PurePath(s)
    if p.anchor:
        return p.anchor, list(p.parts[1:])
    return "", list(p.parts)


def _build_layers(source, extra: tuple) -> tuple[_Layer, ...]:
    if not extra and isinstance(source, VPath):
        return source._layers

    anchor, parts = _normalize_segment(source)
    if extra:
        for e in extra:
            e_anchor, e_parts = _normalize_segment(e)
            if e_anchor:
                raise ValueError(f"cannot join absolute path {e!r} to existing VPath")
            parts.extend(e_parts)

    layers: list[_Layer] = []
    current: list[str] = []
    on_os = True
    for c in parts:
        if c == "." or c == "..":
            raise ValueError(f"VPath does not support '.' or '..' components: {c!r}")
        current.append(c)
        if _is_rpf_component(c):
            if on_os:
                layers.append(_OsLayer(anchor, tuple(current)))
            else:
                layers.append(_RpfLayer(tuple(current)))
            current = []
            on_os = False

    if current:
        if on_os:
            layers.append(_OsLayer(anchor, tuple(current)))
        else:
            layers.append(_RpfLayer(tuple(current)))
    elif not layers:
        layers.append(_OsLayer(anchor, ()))

    return tuple(layers)


def _os_path(layer: _OsLayer) -> pathlib.Path:
    if not layer.root and not layer.parts:
        return pathlib.Path(".")
    if layer.root:
        return pathlib.Path(layer.root, *layer.parts)
    return pathlib.Path(*layer.parts)


# LRU bound for the two process-global path caches below, so a long-running
# process touching many paths doesn't grow them without limit.
_PATH_CACHE_MAX = 4096

# Path.resolve() is a ~2ms Windows _getfinalpathname syscall. We only need a
# stable canonical form per layer (not strict symlink resolution), so cache it:
# each layer pays once. A relative layer folds os.getcwd() into its key, else an
# os.chdir() would return a stale, wrong-cwd resolution.
_resolved_layer_cache: "OrderedDict[object, pathlib.Path]" = OrderedDict()


def _resolve_os_layer(layer: _OsLayer) -> pathlib.Path:
    key: object = layer if layer.root else (layer, os.getcwd())
    cached = _resolved_layer_cache.get(key)
    if cached is not None:
        _resolved_layer_cache.move_to_end(key)
        return cached
    resolved = _os_path(layer).resolve()
    _resolved_layer_cache[key] = resolved
    if len(_resolved_layer_cache) > _PATH_CACHE_MAX:
        _resolved_layer_cache.popitem(last=False)
    return resolved


# A `.rpf` component is an archive boundary only when it's a file on disk (or
# missing, assume archive); a real OS directory just continues on the
# filesystem. The deciding stat is done lazily and cached, assumed stable per
# session (mutators must call `clear_archive_cache()`). Keyed by absolute path
# (see `_classify`) so a cwd change doesn't reuse the wrong result.
_rpf_dir_cache: "OrderedDict[pathlib.Path, bool]" = OrderedDict()


def _rpf_is_dir(path: pathlib.Path) -> bool:
    """True if `path` is a directory (so a `.rpf` name is a plain dir).

    False for a file or missing path, both mean "archive boundary".
    """
    cached = _rpf_dir_cache.get(path)
    if cached is not None:
        _rpf_dir_cache.move_to_end(path)
        return cached
    result = path.is_dir()
    _rpf_dir_cache[path] = result
    if len(_rpf_dir_cache) > _PATH_CACHE_MAX:
        _rpf_dir_cache.popitem(last=False)
    return result


# Sentinel for the lazily computed archive-boundary classification cached on
# each VPath. `None` is a valid result (pure-OS path), so it can't double as
# "not computed yet".
_UNSET: object = object()


def _classify(layers: tuple[_Layer, ...]) -> "int | None":
    """Locate the first `.rpf` component that is a real archive.

    Walks layers left-to-right, statting each `.rpf` boundary: one that's a
    directory is traversed on the OS, the first that's a file (or missing) is the
    archive root. Returns that layer's index, or `None` if the path is entirely
    on disk. Stat-only, never opens an archive.
    """
    root = layers[0].root
    acc: list[str] = []
    for i, layer in enumerate(layers):
        acc.extend(layer.parts)
        parts = layer.parts
        if parts and _is_rpf_component(parts[-1]):
            # Absolutize so the cwd-dependent is_dir() is cached under a
            # cwd-independent key (os.chdir() must not return a stale result).
            if root:
                p = pathlib.Path(root, *acc)
            else:
                p = pathlib.Path(os.path.abspath(os.path.join(*acc)))
            if not _rpf_is_dir(p):
                return i
    return None


_GLOBSTAR = "**"


def _yield_archive_children(
    archive: RpfArchive,
    key: "_ArchiveKey",
    inner: str,
    parent_layers: tuple["_Layer", ...],
    crossed_archive: bool,
) -> Iterator["VPath"]:
    """Hot-path child enumeration for archive-side iterdir.

    Skips `_appended()`: the per-child layer prefix is computed once outside the
    loop and VPath creation is inlined.

    `crossed_archive=True` means we just opened an archive (parent's tail is a
    .rpf file), so children live in a fresh `_RpfLayer` after `parent_layers`.
    Otherwise the parent is a dir inside the current archive and children extend
    its `_RpfLayer.parts`. The two cases differ only in the child layer's root,
    hoisted out of the loop below.
    """
    sep_inner = inner + "/" if inner else ""
    if crossed_archive:
        prefix = parent_layers
        base_parts: tuple[str, ...] = ()
    else:
        prefix = parent_layers[:-1]
        base_parts = parent_layers[-1].parts
    for name in archive.list_dir(inner):
        obj = VPath.__new__(VPath)
        obj._layers = prefix + (_RpfLayer(base_parts + (name,)),)
        obj._resolution = _ArchiveResolved(archive, key, sep_inner + name)
        obj._arch = _UNSET
        obj._top_is_rpf = _is_rpf_component(name)
        yield obj


def _resolve_case_sensitivity(case_sensitive: bool | None) -> bool:
    if case_sensitive is not None:
        return case_sensitive
    return os.name != "nt"


def _validate_mode(mode: str) -> None:
    """Reject malformed modes like `io.open` does, so OS-backed and in-archive
    paths fail identically with `ValueError` (rather than an in-archive path
    silently treating a typo'd mode as a read)."""
    modes = set(mode)
    if modes - set("rwxabt+") or len(mode) != len(modes):
        raise ValueError(f"invalid mode: {mode!r}")
    if "t" in modes and "b" in modes:
        raise ValueError("can't have text and binary mode at once")
    exclusive = ("r" in modes) + ("w" in modes) + ("x" in modes) + ("a" in modes)
    if exclusive > 1:
        raise ValueError("must have exactly one of create/read/write/append mode")
    if exclusive == 0:
        raise ValueError("Must have exactly one of create/read/write/append mode and at most one plus")


def _split_pattern(pattern: str) -> tuple[str, ...]:
    if not pattern:
        raise ValueError("empty pattern")
    # Fold backslash to slash only on Windows. On POSIX it's a legal filename
    # char (kept by the VPath constructor), so folding would make names unmatchable.
    norm = pattern.replace("\\", "/") if os.name == "nt" else pattern
    if norm.startswith("/"):
        raise NotImplementedError("Non-relative patterns are unsupported")
    segs = [s for s in norm.split("/") if s != ""]
    if not segs:
        raise ValueError(f"empty pattern: {pattern!r}")
    for s in segs:
        if s in (".", ".."):
            raise ValueError(f"VPath glob does not support '.' or '..' segments: {s!r}")
        if _GLOBSTAR in s and s != _GLOBSTAR:
            raise ValueError(
                f"Invalid pattern: '**' can only be an entire path component (got {s!r})"
            )
    return tuple(segs)


@functools.lru_cache(maxsize=512)
def _compile_segment(seg: str, case_sensitive: bool) -> re.Pattern:
    # Module-level cache: a segment compiles to the same regex regardless of
    # caller, reused across glob()/match().
    flags = 0 if case_sensitive else re.IGNORECASE
    return re.compile(fnmatch.translate(seg), flags)


def _walk_identity(path: "VPath") -> "tuple[int, int] | None":
    """Stable identity of an OS directory, for `**` symlink-cycle detection.
    In-archive paths can't cycle, so they return `None`."""
    if path.is_inside_archive():
        return None
    try:
        st = os.stat(path._os_leaf_path())
    except OSError:
        return None
    return (st.st_dev, st.st_ino)


def _walk_glob(
    path: "VPath",
    segments: tuple[str, ...],
    cs: bool,
    seen: frozenset = frozenset(),
) -> Iterator["VPath"]:
    if not segments:
        yield path
        return
    head, rest = segments[0], segments[1:]

    if head == _GLOBSTAR:
        # `**` matches zero-or-more components; combine both cases so we
        # iterdir(path) only once per level. Track visited OS-dir identities so a
        # symlink cycle is entered at most once (like pathlib).
        self_id = _walk_identity(path)
        sub_seen = seen | {self_id} if self_id is not None else seen
        try:
            children = list(path.iterdir())
        except OSError:
            children = ()

        if not rest:
            # Terminal `**`: yield path (only if a real dir, like pathlib) plus
            # every descendant.
            if path.is_dir():
                yield path
            for child in children:
                if child.is_dir():
                    cid = _walk_identity(child)
                    if cid is not None and cid in sub_seen:
                        continue
                    yield from _walk_glob(child, segments, cs, sub_seen)
                else:
                    yield child
            return

        # `**` matching zero components → match `rest` against the children.
        head2 = rest[0]
        rest_rest = rest[1:]
        if head2 == _GLOBSTAR:
            # Two consecutive `**` collapse to one.
            yield from _walk_glob(path, rest, cs, seen)
            for child in children:
                if child.is_dir():
                    cid = _walk_identity(child)
                    if cid is not None and cid in sub_seen:
                        continue
                    yield from _walk_glob(child, segments, cs, sub_seen)
            return

        regex = _compile_segment(head2, cs)
        for child in children:
            child_is_dir = child.is_dir()
            if regex.match(child.name) is not None:
                if rest_rest:
                    if child_is_dir:
                        yield from _walk_glob(child, rest_rest, cs, sub_seen)
                else:
                    yield child
            # `**` matching one-or-more: recurse with full segments.
            if child_is_dir:
                cid = _walk_identity(child)
                if cid is not None and cid in sub_seen:
                    continue
                yield from _walk_glob(child, segments, cs, sub_seen)
        return

    regex = _compile_segment(head, cs)
    try:
        children = list(path.iterdir())
    except OSError:
        return
    for child in children:
        if regex.match(child.name) is None:
            continue
        if rest:
            if child.is_dir():
                yield from _walk_glob(child, rest, cs, seen)
        else:
            yield child


def _dedupe(it: Iterator["VPath"]) -> Iterator["VPath"]:
    seen: set = set()
    for p in it:
        if p._layers in seen:
            continue
        seen.add(p._layers)
        yield p


def _match_segments(parts: tuple[str, ...], segs: tuple[str, ...], cs: bool) -> bool:
    n = len(parts)
    min_len = sum(1 for s in segs if s != _GLOBSTAR)
    if n < min_len:
        return False
    # Memoize on (pi, si): without it, multiple `**` make the recursion
    # exponential. Shared across the right-alignment start offsets.
    memo: dict[tuple[int, int], bool] = {}
    for start in range(n - min_len, -1, -1):
        if _try_match(parts, start, segs, 0, cs, memo):
            return True
    return False


def _try_match(
    parts: tuple[str, ...],
    pi: int,
    segs: tuple[str, ...],
    si: int,
    cs: bool,
    memo: dict[tuple[int, int], bool],
) -> bool:
    key = (pi, si)
    cached = memo.get(key)
    if cached is not None:
        return cached
    result = _try_match_compute(parts, pi, segs, si, cs, memo)
    memo[key] = result
    return result


def _try_match_compute(
    parts: tuple[str, ...],
    pi: int,
    segs: tuple[str, ...],
    si: int,
    cs: bool,
    memo: dict[tuple[int, int], bool],
) -> bool:
    if si == len(segs):
        return pi == len(parts)
    seg = segs[si]
    if seg == _GLOBSTAR:
        for k in range(len(parts) - pi + 1):
            if _try_match(parts, pi + k, segs, si + 1, cs, memo):
                return True
        return False
    if pi >= len(parts):
        return False
    if _compile_segment(seg, cs).match(parts[pi]) is None:
        return False
    return _try_match(parts, pi + 1, segs, si + 1, cs, memo)


class VPath:
    """Path-like type unifying OS filesystem and RPF archive access.

    An `.rpf` component that is an archive *file* triggers transparent descent
    (nested RPFs included); one that is an OS *directory* is traversed normally.
    OS-backed paths behave like `pathlib.Path` and implement `os.PathLike`;
    in-archive paths are read-only (writes raise `PermissionError`).
    """

    __slots__ = ("_layers", "_resolution", "_top_is_rpf", "_arch")

    def __init__(self, source: "str | os.PathLike | VPath", *extra: "str | os.PathLike | VPath"):
        layers = _build_layers(source, extra)
        self._layers = layers
        self._resolution: "_Resolution | None" = None
        self._arch: object = _UNSET
        top_parts = layers[-1].parts
        self._top_is_rpf = bool(top_parts) and _is_rpf_component(top_parts[-1])

    @classmethod
    def _from_layers(
        cls,
        layers: tuple[_Layer, ...],
        resolution: "_Resolution | None" = None,
        top_is_rpf: bool | None = None,
    ) -> "VPath":
        obj = cls.__new__(cls)
        obj._layers = layers
        obj._resolution = resolution
        obj._arch = _UNSET
        if top_is_rpf is None:
            top_parts = layers[-1].parts
            top_is_rpf = bool(top_parts) and _is_rpf_component(top_parts[-1])
        obj._top_is_rpf = top_is_rpf
        return obj

    def __truediv__(self, other: "str | os.PathLike | VPath") -> "VPath":
        # Fast path: a bare name (no separators, not . or ..) just extends the
        # last layer, skipping _build_layers for the common iterdir case. ':' is
        # excluded so a Windows drive-anchored name ('C:', 'X:foo') falls through
        # to the constructor, which rejects it rather than corrupting the path.
        if (
            type(other) is str
            and other
            and "/" not in other
            and "\\" not in other
            and ":" not in other
            and other != "."
            and other != ".."
        ):
            return self._appended(other)
        return VPath(self, other)

    def _appended(
        self,
        name: str,
        resolution: "_Resolution | None" = None,
    ) -> "VPath":
        """Append one component (no separator validation).

        A `.rpf` last component starts a fresh `_RpfLayer`; otherwise the name
        extends the current last layer's parts.
        """
        layers = self._layers
        new_top_is_rpf = _is_rpf_component(name)
        if self._top_is_rpf:
            new_layers = layers + (_RpfLayer((name,)),)
        else:
            top = layers[-1]
            new_parts = top.parts + (name,)
            if top.__class__ is _OsLayer:
                new_layer: _Layer = _OsLayer(top.root, new_parts)
            else:
                new_layer = _RpfLayer(new_parts)
            new_layers = layers[:-1] + (new_layer,)
        obj = VPath.__new__(VPath)
        obj._layers = new_layers
        obj._resolution = resolution
        obj._arch = _UNSET
        obj._top_is_rpf = new_top_is_rpf
        return obj

    def __rtruediv__(self, other: "str | os.PathLike") -> "VPath":
        return VPath(other, self)

    def __fspath__(self) -> str:
        if self.is_inside_archive():
            raise ValueError("VPath inside RPF has no OS filesystem path")
        return str(self._os_leaf_path())

    def __str__(self) -> str:
        # Uniform forward slashes (OS layer via as_posix, archive layers already
        # '/'-joined). `__fspath__`, not this, carries the native-separator path.
        # Round-trips through the constructor (pathlib parses '/' everywhere).
        pieces: list[str] = []
        for i, layer in enumerate(self._layers):
            if i == 0:
                pieces.append(_os_path(layer).as_posix())
            else:
                pieces.append("/".join(layer.parts))
        return "/".join(pieces)

    def as_posix(self) -> str:
        """Return the path as a string with forward slashes (like `pathlib.PurePath.as_posix`)."""
        return str(self)

    def __repr__(self) -> str:
        return f"VPath({str(self)!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, VPath):
            return NotImplemented
        return self._layers == other._layers

    def __hash__(self) -> int:
        return hash(self._layers)

    @property
    def parts(self) -> tuple[str, ...]:
        result: list[str] = []
        first = self._layers[0]
        if first.root:
            result.append(first.root)
        for layer in self._layers:
            result.extend(layer.parts)
        return tuple(result)

    @property
    def anchor(self) -> str:
        return self._layers[0].root

    @property
    def name(self) -> str:
        for layer in reversed(self._layers):
            if layer.parts:
                return layer.parts[-1]
        return ""

    @property
    def stem(self) -> str:
        return pathlib.PurePosixPath(self.name).stem

    @property
    def suffix(self) -> str:
        return pathlib.PurePosixPath(self.name).suffix

    @property
    def suffixes(self) -> list[str]:
        return list(pathlib.PurePosixPath(self.name).suffixes)

    @property
    def parent(self) -> "VPath":
        top = self._layers[-1]
        if isinstance(top, _RpfLayer):
            new_parts = top.parts[:-1]
            if new_parts:
                return VPath._from_layers((*self._layers[:-1], _RpfLayer(new_parts)))
            return VPath._from_layers(self._layers[:-1])
        if not top.parts:
            return self
        new_parts = top.parts[:-1]
        return VPath._from_layers((_OsLayer(top.root, new_parts),))

    @property
    def parents(self) -> tuple["VPath", ...]:
        result: list[VPath] = []
        current = self
        while True:
            p = current.parent
            if p == current:
                break
            result.append(p)
            current = p
        return tuple(result)

    def is_absolute(self) -> bool:
        """True if absolute, like `pathlib.Path.is_absolute()`.

        On Windows this needs both a drive and a root: drive-relative (`C:foo`)
        or driveless-rooted (`\\x`) is not absolute, matching pathlib.
        """
        anchor = self.anchor
        return bool(anchor) and pathlib.PurePath(anchor).is_absolute()

    def absolute(self) -> "VPath":
        """Prepend the cwd to make this absolute, like `pathlib.Path.absolute()`.
        Already-absolute paths are returned unchanged. Does not resolve symlinks
        or normalize (VPath forbids `..`).
        """
        if self.is_absolute():
            return self
        if self.anchor:
            # Anchored-but-relative on Windows (`C:foo` or `\\x`). The constructor
            # rejects an anchored join segment, so re-anchor through the OS and
            # re-parse, which re-splits `.rpf` boundaries.
            return VPath(os.path.abspath(str(self)))
        # Route through the constructor so `_build_layers` re-splits on `.rpf`
        # boundaries, keeping the invariant that a `.rpf` ends its layer (matters
        # when os.getcwd() contains a `.rpf` *directory*). Relies on `__str__`
        # being a lossless inverse of `_build_layers`.
        return VPath(os.getcwd(), self)

    def _get_arch_boundary(self) -> "int | None":
        """Lazily classify (and cache) where this path crosses into an archive.

        Returns the archive root's layer index, or `None` for a pure-OS path.
        See `_classify`. Stat-only, never opens an archive.
        """
        b = self._arch
        if b is _UNSET:
            b = _classify(self._layers)
            self._arch = b
        return b  # type: ignore[return-value]

    def _os_leaf_path(self) -> pathlib.Path:
        """On-disk path of a pure-OS VPath (its `.rpf` components are dirs).

        Joins all layers' parts into one OS path.
        """
        layers = self._layers
        if len(layers) == 1:
            return _os_path(layers[0])
        root = layers[0].root
        acc: list[str] = []
        for layer in layers:
            acc.extend(layer.parts)
        return pathlib.Path(root, *acc) if root else pathlib.Path(*acc)

    def _resolve(self) -> "_Resolution":
        """Resolve this path against the filesystem, lazily and cached.

        `_ArchiveResolved` if the path descends into an archive, else
        `_OsResolved` with the on-disk leaf (covers paths that merely crossed
        `.rpf` dirs, or point *at* an `.rpf` file without descending). Opening the
        archive happens here, not in the stat-only `is_inside_archive`.
        """
        cached = self._resolution
        if cached is not None:
            return cached
        layers = self._layers
        b = self._get_arch_boundary() if len(layers) > 1 else None
        if b is None or b == len(layers) - 1:
            result: "_Resolution" = _OsResolved(self._os_leaf_path())
        else:
            result = self._open_archive(b)
        self._resolution = result
        return result

    def _open_archive(self, boundary: int) -> "_ArchiveResolved":
        """Open the archive chain whose root is at layer `boundary`.

        Layers `0..boundary` form the OS path of the archive *file*; later layers
        address entries within it and any nested archives below.
        """
        layers = self._layers
        if boundary == 0:
            archive_path = _resolve_os_layer(layers[0])
        else:
            root = layers[0].root
            acc: list[str] = []
            for k in range(boundary + 1):
                acc.extend(layers[k].parts)
            unresolved = pathlib.Path(root, *acc) if root else pathlib.Path(*acc)
            archive_path = unresolved.resolve()
        archive = _archive_cache.get_os(archive_path)
        key: _ArchiveKey = (archive_path,)
        for j in range(boundary + 1, len(layers) - 1):
            inner = "/".join(layers[j].parts)
            archive = _archive_cache.get_nested(archive, key, inner)
            key = key + (inner,)
        inner_top = "/".join(layers[-1].parts)
        return _ArchiveResolved(archive, key, inner_top)

    def is_inside_archive(self) -> bool:
        """True if this path descends into an RPF archive (resolved against disk)."""
        rp = self._resolution
        if rp is not None:
            return isinstance(rp, _ArchiveResolved)
        if len(self._layers) == 1:
            return False
        b = self._get_arch_boundary()
        return b is not None and b < len(self._layers) - 1

    def is_archive(self) -> bool:
        """True if this path points at an .rpf file (on disk, or as an entry in an outer RPF)."""
        if not self._top_is_rpf:
            return False
        top = self._layers[-1]
        if top.__class__ is _OsLayer:
            return _os_path(top).is_file()
        try:
            r = self._resolve()
        except OSError as e:
            if _ignore_error(e):
                return False
            raise
        if isinstance(r, _OsResolved):
            return r.os_path.is_file()
        return r.archive.is_file(r.inner)

    def exists(self) -> bool:
        top = self._layers[-1]
        if isinstance(top, _OsLayer):
            return _os_path(top).exists()
        try:
            r = self._resolve()
        except OSError as e:
            if _ignore_error(e):
                return False
            raise
        if isinstance(r, _OsResolved):
            return r.os_path.exists()
        return r.archive.exists(r.inner)

    def is_file(self) -> bool:
        top = self._layers[-1]
        if isinstance(top, _OsLayer):
            return _os_path(top).is_file()
        try:
            r = self._resolve()
        except OSError as e:
            if _ignore_error(e):
                return False
            raise
        if isinstance(r, _OsResolved):
            return r.os_path.is_file()
        return r.archive.is_file(r.inner)

    def is_dir(self) -> bool:
        top = self._layers[-1]
        if top.__class__ is _OsLayer:
            os_path = _os_path(top)
            if self._top_is_rpf and os_path.is_file():
                return True
            return os_path.is_dir()
        try:
            r = self._resolve()
        except OSError as e:
            if _ignore_error(e):
                return False
            raise
        if isinstance(r, _OsResolved):
            # Pure-OS path reached through `.rpf` dirs; a `.rpf` *file* at the leaf
            # is iterable like a dir (mirrors the single-OS-layer branch above).
            os_path = r.os_path
            if self._top_is_rpf and os_path.is_file():
                return True
            return os_path.is_dir()
        if r.archive.is_dir(r.inner):
            return True
        # An in-archive `.rpf` entry is iterable like a dir (mirrors the OS side).
        return self._top_is_rpf and r.archive.is_file(r.inner)

    def iterdir(self) -> Iterator["VPath"]:
        layers = self._layers
        top = layers[-1]
        if top.__class__ is _OsLayer:
            if self._top_is_rpf:
                # Skip the is_file() stat when the archive is already cached
                # (common during a glob walk revisiting it at different depths).
                resolved = _resolve_os_layer(top)
                archive = _archive_cache.peek_os(resolved)
                if archive is None:
                    if _os_path(top).is_file():
                        archive = _archive_cache.get_os(resolved)
                    # Neither cached nor a file → fall through to scandir: a
                    # directory named "*.rpf" is a rare but legitimate layout.
                if archive is not None:
                    key = (resolved,)
                    yield from _yield_archive_children(
                        archive, key, "", layers, crossed_archive=True
                    )
                    return
            # OS-side scandir; inline the per-child VPath build to skip _appended.
            # `with` releases the handle if the generator is abandoned (like
            # pathlib; avoids ResourceWarning).
            top_root = top.root
            top_parts = top.parts
            with os.scandir(_os_path(top)) as it:
                for entry in it:
                    name = entry.name
                    obj = VPath.__new__(VPath)
                    obj._layers = (_OsLayer(top_root, top_parts + (name,)),)
                    obj._resolution = None
                    obj._arch = _UNSET
                    obj._top_is_rpf = _is_rpf_component(name)
                    yield obj
            return
        # Multi-layer: resolve against disk. The path may merely have crossed
        # `.rpf` directories (pure OS) or actually descend into an archive.
        r = self._resolve()
        if isinstance(r, _OsResolved):
            os_path = r.os_path
            if self._top_is_rpf and os_path.is_file():
                # Leaf is an archive file reached through `.rpf` dirs; list its
                # root (mirrors the single-OS-layer branch).
                resolved = os_path.resolve()
                archive = _archive_cache.get_os(resolved)
                yield from _yield_archive_children(
                    archive, (resolved,), "", layers, crossed_archive=True
                )
                return
            with os.scandir(os_path) as it:
                for entry in it:
                    # `_appended` preserves the layer structure (like `/`), unlike
                    # re-parsing entry.path.
                    yield self._appended(entry.name)
            return
        archive, key, inner = r.archive, r.key, r.inner
        if archive.is_file(inner):
            if self._top_is_rpf:
                nested = _archive_cache.get_nested(archive, key, inner)
                nested_key = key + (inner,)
                yield from _yield_archive_children(
                    nested, nested_key, "", layers, crossed_archive=True
                )
                return
            raise NotADirectoryError(f"not a directory: {self}")
        if not archive.is_dir(inner):
            raise FileNotFoundError(f"no such directory: {self}")
        yield from _yield_archive_children(
            archive, key, inner, layers, crossed_archive=False
        )

    def match(self, pattern: str, *, case_sensitive: bool | None = None) -> bool:
        """True if this path matches the glob pattern, right-aligned.

        `**` matches zero or more path components.
        """
        segments = _split_pattern(pattern)
        cs = _resolve_case_sensitivity(case_sensitive)
        parts = self.parts
        if self.anchor:
            parts = parts[1:]
        return _match_segments(parts, segments, cs)

    def glob(self, pattern: str, *, case_sensitive: bool | None = None) -> Iterator["VPath"]:
        """Yield VPaths under this directory matching the relative pattern.

        `**` matches zero or more components and crosses RPF boundaries (like
        `iterdir()`). `iterdir()` errors during the walk (e.g. a corrupt nested
        archive) are silently skipped.
        """
        segments = _split_pattern(pattern)
        cs = _resolve_case_sensitivity(case_sensitive)
        walker = _walk_glob(self, segments, cs)
        # Multiple ** can yield the same path via different alignments; dedupe.
        if sum(1 for s in segments if s == _GLOBSTAR) > 1:
            return _dedupe(walker)
        return walker

    def rglob(self, pattern: str, *, case_sensitive: bool | None = None) -> Iterator["VPath"]:
        """Recursively yield VPaths matching `pattern`. Equivalent to `glob('**/' + pattern)`."""
        return self.glob(_GLOBSTAR + "/" + pattern, case_sensitive=case_sensitive)

    def read_bytes(self) -> bytes:
        top = self._layers[-1]
        if isinstance(top, _OsLayer):
            return _os_path(top).read_bytes()
        r = self._resolve()
        if isinstance(r, _OsResolved):
            return r.os_path.read_bytes()
        archive, inner = r.archive, r.inner
        if archive.is_dir(inner):
            raise IsADirectoryError(f"is a directory: {self}")
        if not archive.exists(inner):
            raise FileNotFoundError(f"no such entry in archive: {inner!r}")
        return archive.read_bytes(inner)

    def read_text(self, encoding: str | None = None, errors: str | None = None) -> str:
        with self.open("r", encoding=encoding, errors=errors) as f:
            return f.read()

    def open(
        self,
        mode: str = "rb",
        buffering: int = -1,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> IO:
        """Open the path. Like `pathlib.Path.open` but defaults to binary (`"rb"`,
        since RPF entries are binary). Text mode defaults to UTF-8 for both
        backends, so decoding is identical regardless of backend or host locale.
        """
        _validate_mode(mode)
        is_write = any(ch in mode for ch in ("w", "a", "x", "+"))
        if is_write and self.is_inside_archive():
            raise PermissionError("cannot write inside RPF archive")

        text = "b" not in mode
        enc = (encoding or "utf-8") if text else encoding

        top = self._layers[-1]
        if isinstance(top, _OsLayer):
            return _os_path(top).open(mode, buffering, encoding=enc, errors=errors, newline=newline)

        r = self._resolve()
        if isinstance(r, _OsResolved):
            return r.os_path.open(mode, buffering, encoding=enc, errors=errors, newline=newline)
        archive, inner = r.archive, r.inner
        if archive.is_dir(inner):
            raise IsADirectoryError(f"is a directory: {self}")
        if not archive.exists(inner):
            raise FileNotFoundError(f"no such entry in archive: {inner!r}")
        stream = archive.open_bytes(inner)
        if text:
            return io.TextIOWrapper(stream, encoding=enc, errors=errors, newline=newline)
        return stream

    def write_bytes(self, data: bytes) -> int:
        if self.is_inside_archive():
            raise PermissionError("cannot write inside RPF archive")
        return self._os_leaf_path().write_bytes(data)

    def write_text(
        self,
        data: str,
        encoding: str | None = None,
        errors: str | None = None,
    ) -> int:
        if self.is_inside_archive():
            raise PermissionError("cannot write inside RPF archive")
        # UTF-8 default, matching read_text()/open("r") so text round-trips.
        return self._os_leaf_path().write_text(data, encoding=encoding or "utf-8", errors=errors)

    def mkdir(self, parents: bool = False, exist_ok: bool = False) -> None:
        if self.is_inside_archive():
            raise PermissionError("cannot write inside RPF archive")
        self._os_leaf_path().mkdir(parents=parents, exist_ok=exist_ok)

    def unlink(self, missing_ok: bool = False) -> None:
        if self.is_inside_archive():
            raise PermissionError("cannot write inside RPF archive")
        self._os_leaf_path().unlink(missing_ok=missing_ok)

    def as_data_source(self) -> DataSource:
        """Return a `DataSource` view of this path."""
        if not self.is_inside_archive():
            return _DataSourceFile(None, self._os_leaf_path())
        return _DataSourceVPath(self)


class _DataSourceVPath(DataSource):
    __slots__ = ("_vpath",)

    def __init__(self, vpath: VPath):
        self._vpath = vpath
        self.name = vpath.name

    def open(self) -> IO[bytes]:
        stream = self._vpath.open("rb")
        return stream  # type: ignore[return-value]

    def read_bytes(self) -> bytes:
        return self._vpath.read_bytes()


class _ArchiveCache:
    _MAX = 256

    __slots__ = ("_data",)

    def __init__(self):
        self._data: OrderedDict[_ArchiveKey, RpfArchive] = OrderedDict()

    def get_os(self, resolved_path: pathlib.Path) -> RpfArchive:
        key: _ArchiveKey = (resolved_path,)
        archive = self._data.get(key)
        if archive is not None:
            self._data.move_to_end(key)
            return archive
        archive = _rpf.open_rpf(resolved_path)
        self._data[key] = archive
        self._evict_oldest()
        return archive

    def peek_os(self, resolved_path: pathlib.Path) -> "RpfArchive | None":
        """Return the cached archive for `resolved_path` without opening, or None."""
        key: _ArchiveKey = (resolved_path,)
        archive = self._data.get(key)
        if archive is not None:
            self._data.move_to_end(key)
        return archive

    def get_nested(self, outer: RpfArchive, outer_key: _ArchiveKey, inner_rel: str) -> RpfArchive:
        key: _ArchiveKey = outer_key + (inner_rel,)
        archive = self._data.get(key)
        if archive is not None:
            self._data.move_to_end(key)
            return archive
        archive = outer.open_nested(inner_rel) if hasattr(outer, "open_nested") else None
        if archive is None:
            # Fallback: open the nested entry from a stream, handing it ownership
            # so the stream is released on eviction/clear instead of leaking.
            stream = outer.open_bytes(inner_rel)
            try:
                archive = _rpf.open_rpf(
                    stream, filename=inner_rel.rsplit("/", 1)[-1], owns_stream=True
                )
            except BaseException:
                stream.close()
                raise
        self._data[key] = archive
        self._evict_oldest()
        return archive

    def clear(self) -> None:
        for archive in self._data.values():
            self._close_quiet(archive)
        self._data.clear()

    def _evict_oldest(self) -> None:
        while len(self._data) > self._MAX:
            _, archive = self._data.popitem(last=False)
            self._close_quiet(archive)

    @staticmethod
    def _close_quiet(archive: RpfArchive) -> None:
        try:
            archive.close()
        except Exception:
            pass


_archive_cache = _ArchiveCache()


def clear_archive_cache() -> None:
    """Clear all process-global VPath caches: open archives, resolved layer
    paths, and `.rpf` file/dir classification.

    Call after mutating the on-disk tree mid-session (adding/removing/replacing a
    `.rpf` file or directory) so stale results aren't reused. Also isolates tests.
    """
    _archive_cache.clear()
    _resolved_layer_cache.clear()
    _rpf_dir_cache.clear()
