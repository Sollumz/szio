"""VPath tests. Uses a fake RpfArchive."""

import io
import os
import pathlib

import pytest

from szio import VPath
from szio.types import DataSource
from szio.vfs import clear_archive_cache


class _FakeArchive:
    """In-memory RpfArchive test double keyed by dict[path, bytes]."""

    def __init__(self, entries: dict[str, bytes]):
        self._files: dict[str, bytes] = {}
        self._dirs: set[str] = {""}
        for path, content in entries.items():
            p = path.strip("/")
            self._files[p] = content
            parts = p.split("/")
            for i in range(len(parts)):
                self._dirs.add("/".join(parts[:i]))
        self.closed = False

    @staticmethod
    def _norm(p: str) -> str:
        return p.strip("/")

    def close(self):
        self.closed = True

    def exists(self, inner_path):
        p = self._norm(inner_path)
        return p in self._files or p in self._dirs

    def is_file(self, inner_path):
        return self._norm(inner_path) in self._files

    def is_dir(self, inner_path):
        return self._norm(inner_path) in self._dirs

    def list_dir(self, inner_path):
        p = self._norm(inner_path)
        prefix = p + "/" if p else ""
        seen: set[str] = set()
        for f in self._files:
            if f.startswith(prefix):
                rest = f[len(prefix) :]
                seen.add(rest.split("/")[0])
        for d in self._dirs:
            if d and d.startswith(prefix) and d != p:
                rest = d[len(prefix) :]
                seen.add(rest.split("/")[0])
        return sorted(seen)

    def read_bytes(self, inner_path):
        p = self._norm(inner_path)
        if p not in self._files:
            raise FileNotFoundError(p)
        return self._files[p]

    def open_bytes(self, inner_path):
        return io.BytesIO(self.read_bytes(inner_path))


class _FakeOpenRpf:
    """Replacement for szio.rpf.open_rpf. Resolves path-based or stream-based
    sources against a registry populated by the test."""

    def __init__(self):
        self.by_path: dict[str, _FakeArchive] = {}
        self.by_name: dict[str, _FakeArchive] = {}
        self.call_count = 0

    def register_path(self, path: pathlib.Path, archive: _FakeArchive) -> None:
        self.by_path[str(path.resolve())] = archive

    def register_name(self, name: str, archive: _FakeArchive) -> None:
        self.by_name[name] = archive

    def stream_marker(self, name: str) -> bytes:
        return b"FAKE:" + name.encode() + b"\n"

    def __call__(self, source, *, filename=None, owns_stream=False):
        self.call_count += 1
        if isinstance(source, (str, os.PathLike)):
            key = str(pathlib.Path(source).resolve())
            if key in self.by_path:
                return self.by_path[key]
            raise OSError(f"not a valid RPF archive: {source!r}")
        data = source.read()
        source.seek(0)
        if not data.startswith(b"FAKE:"):
            raise OSError(f"not a valid RPF archive: bad magic {data[:4]!r}")
        newline = data.index(b"\n")
        name = data[5:newline].decode()
        if name not in self.by_name:
            raise OSError(f"not a valid RPF archive: unknown {name!r}")
        return self.by_name[name]


@pytest.fixture
def fake_rpf(monkeypatch):
    fake = _FakeOpenRpf()
    monkeypatch.setattr("szio.rpf.open_rpf", fake)
    clear_archive_cache()
    yield fake
    clear_archive_cache()


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_archive_cache()
    yield
    clear_archive_cache()


def test_construct_from_str():
    assert VPath("a/b").parts[-2:] == ("a", "b")


def test_construct_from_path_and_vpath_equal():
    assert VPath("a/b") == VPath(pathlib.Path("a/b"))
    assert VPath("a/b") == VPath(VPath("a/b"))


def test_truediv_joins_components():
    assert VPath("a") / "b" / "c" == VPath("a/b/c")


def test_rtruediv():
    assert "a" / VPath("b") == VPath("a/b")


def test_bad_type_raises():
    with pytest.raises(TypeError):
        VPath(123)  # type: ignore[arg-type]


def test_dotdot_raises():
    with pytest.raises(ValueError):
        VPath("a/../b")


def test_absolute_join_raises():
    with pytest.raises(ValueError):
        VPath("a") / "/b"


def test_parts_name_stem_suffix_suffixes():
    p = VPath("dir/archive.tar.gz")
    assert p.name == "archive.tar.gz"
    assert p.stem == "archive.tar"
    assert p.suffix == ".gz"
    assert p.suffixes == [".tar", ".gz"]


def test_parent_across_mount_boundary():
    p = VPath("C:/x/a.rpf/inner/f.ydr") if os.name == "nt" else VPath("/x/a.rpf/inner/f.ydr")
    # Inside the RPF, parent strips "f.ydr"
    assert p.parent.name == "inner"
    # Parent of "inner" drops the RPF layer entirely, lands on the .rpf itself
    assert p.parent.parent == (VPath("C:/x/a.rpf") if os.name == "nt" else VPath("/x/a.rpf"))


def test_parents_ordering():
    p = VPath("a/b/c")
    names = [q.name for q in p.parents]
    assert names[0] == "b"
    assert names[1] == "a"


def test_is_inside_archive():
    assert not VPath("a/b").is_inside_archive()
    assert not VPath("a.rpf").is_inside_archive()
    assert VPath("a.rpf/b").is_inside_archive()
    assert VPath("a.rpf/b.rpf/c").is_inside_archive()


def test_is_archive_on_disk(tmp_path):
    archive_file = tmp_path / "thing.rpf"
    archive_file.write_bytes(b"FAKE:x\n")
    assert VPath(archive_file).is_archive() is True


def test_is_archive_false_for_nonexistent_rpf(tmp_path):
    assert VPath(tmp_path / "missing.rpf").is_archive() is False


def test_is_archive_false_for_non_rpf(tmp_path):
    other = tmp_path / "f.txt"
    other.write_text("hi")
    assert VPath(other).is_archive() is False


def test_os_read_write_bytes(tmp_path):
    p = VPath(tmp_path / "f.bin")
    p.write_bytes(b"abc123")
    assert p.read_bytes() == b"abc123"


def test_os_read_write_text(tmp_path):
    p = VPath(tmp_path / "f.txt")
    p.write_text("hello", encoding="utf-8")
    assert p.read_text(encoding="utf-8") == "hello"


def test_os_mkdir_and_unlink(tmp_path):
    d = VPath(tmp_path / "sub" / "deeper")
    d.mkdir(parents=True)
    assert d.is_dir()
    f = d / "x.bin"
    f.write_bytes(b"")
    assert f.exists()
    f.unlink()
    assert not f.exists()
    f.unlink(missing_ok=True)


def test_os_iterdir_yields_vpaths(tmp_path):
    (tmp_path / "a").write_text("")
    (tmp_path / "b").write_text("")
    names = sorted(child.name for child in VPath(tmp_path).iterdir())
    assert names == ["a", "b"]
    for child in VPath(tmp_path).iterdir():
        assert isinstance(child, VPath)


def test_mount_detection_reads_entry(tmp_path, fake_rpf):
    rpf_file = tmp_path / "pack.rpf"
    rpf_file.write_bytes(b"RPF7stub")
    fake_rpf.register_path(rpf_file, _FakeArchive({"data/foo.xml": b"<root/>"}))

    p = VPath(rpf_file) / "data" / "foo.xml"
    assert p.exists()
    assert p.read_bytes() == b"<root/>"


def test_iterdir_on_rpf_file_lists_root(tmp_path, fake_rpf):
    rpf_file = tmp_path / "pack.rpf"
    rpf_file.write_bytes(b"RPF7stub")
    fake_rpf.register_path(rpf_file, _FakeArchive({"a.bin": b"", "dir/b.bin": b""}))

    names = sorted(child.name for child in VPath(rpf_file).iterdir())
    assert names == ["a.bin", "dir"]


def test_iterdir_on_rpf_subdir(tmp_path, fake_rpf):
    rpf_file = tmp_path / "pack.rpf"
    rpf_file.write_bytes(b"RPF7stub")
    fake_rpf.register_path(rpf_file, _FakeArchive({"dir/b.bin": b"1", "dir/c.bin": b"2"}))

    names = sorted(child.name for child in (VPath(rpf_file) / "dir").iterdir())
    assert names == ["b.bin", "c.bin"]


def test_nested_rpf_read(tmp_path, fake_rpf):
    rpf_file = tmp_path / "outer.rpf"
    rpf_file.write_bytes(b"RPF7stub")
    inner_marker = fake_rpf.stream_marker("inner_archive")
    fake_rpf.register_path(rpf_file, _FakeArchive({"nested/inner.rpf": inner_marker}))
    fake_rpf.register_name("inner_archive", _FakeArchive({"deep/target.bin": b"payload"}))

    p = VPath(rpf_file) / "nested" / "inner.rpf" / "deep" / "target.bin"
    assert p.exists()
    assert p.read_bytes() == b"payload"


def test_iterdir_on_in_archive_rpf_lists_root(tmp_path, fake_rpf):
    rpf_file = tmp_path / "outer.rpf"
    rpf_file.write_bytes(b"RPF7stub")
    inner_marker = fake_rpf.stream_marker("inner_archive")
    fake_rpf.register_path(rpf_file, _FakeArchive({"nested/inner.rpf": inner_marker}))
    fake_rpf.register_name("inner_archive", _FakeArchive({"a.bin": b"x", "dir/b.bin": b"y"}))

    p = VPath(rpf_file) / "nested" / "inner.rpf"
    names = sorted(child.name for child in p.iterdir())
    assert names == ["a.bin", "dir"]


def test_in_archive_rpf_is_dir_true(tmp_path, fake_rpf):
    rpf_file = tmp_path / "outer.rpf"
    rpf_file.write_bytes(b"RPF7stub")
    inner_marker = fake_rpf.stream_marker("inner_archive")
    fake_rpf.register_path(rpf_file, _FakeArchive({"nested/inner.rpf": inner_marker}))
    fake_rpf.register_name("inner_archive", _FakeArchive({"a.bin": b""}))

    p = VPath(rpf_file) / "nested" / "inner.rpf"
    assert p.is_dir()
    assert p.is_file()


def test_fspath_works_for_os_path(tmp_path):
    f = tmp_path / "f.bin"
    f.write_bytes(b"xyz")
    with open(VPath(f), "rb") as fh:
        assert fh.read() == b"xyz"


def test_fspath_raises_for_in_rpf(tmp_path, fake_rpf):
    rpf_file = tmp_path / "pack.rpf"
    rpf_file.write_bytes(b"RPF7stub")
    fake_rpf.register_path(rpf_file, _FakeArchive({"a.bin": b""}))

    with pytest.raises(ValueError):
        os.fspath(VPath(rpf_file) / "a.bin")


# ----- 7. Write forbidden in RPF -----


def _make_in_rpf_vpath(tmp_path, fake_rpf, name="a.bin"):
    rpf_file = tmp_path / "pack.rpf"
    rpf_file.write_bytes(b"RPF7stub")
    fake_rpf.register_path(rpf_file, _FakeArchive({name: b"data"}))
    return VPath(rpf_file) / name


def test_write_bytes_in_rpf_raises(tmp_path, fake_rpf):
    p = _make_in_rpf_vpath(tmp_path, fake_rpf)
    with pytest.raises(PermissionError):
        p.write_bytes(b"")


def test_write_text_in_rpf_raises(tmp_path, fake_rpf):
    p = _make_in_rpf_vpath(tmp_path, fake_rpf)
    with pytest.raises(PermissionError):
        p.write_text("")


def test_mkdir_in_rpf_raises(tmp_path, fake_rpf):
    p = _make_in_rpf_vpath(tmp_path, fake_rpf)
    with pytest.raises(PermissionError):
        p.mkdir()


def test_unlink_in_rpf_raises(tmp_path, fake_rpf):
    p = _make_in_rpf_vpath(tmp_path, fake_rpf)
    with pytest.raises(PermissionError):
        p.unlink()


def test_open_write_mode_in_rpf_raises(tmp_path, fake_rpf):
    p = _make_in_rpf_vpath(tmp_path, fake_rpf)
    for mode in ("w", "wb", "a", "ab", "x", "xb", "r+", "rb+"):
        with pytest.raises(PermissionError):
            p.open(mode)


def test_missing_in_rpf_raises_file_not_found(tmp_path, fake_rpf):
    rpf_file = tmp_path / "pack.rpf"
    rpf_file.write_bytes(b"RPF7stub")
    fake_rpf.register_path(rpf_file, _FakeArchive({"a.bin": b"x"}))
    with pytest.raises(FileNotFoundError):
        (VPath(rpf_file) / "nope.bin").read_bytes()


def test_bad_magic_raises_os_error(tmp_path, fake_rpf):
    bad = tmp_path / "bad.rpf"
    bad.write_bytes(b"NOPE")
    # not registered, _FakeOpenRpf raises OSError
    with pytest.raises(OSError):
        (VPath(bad) / "anything").read_bytes()


def test_iterdir_on_file_raises_not_a_directory(tmp_path, fake_rpf):
    rpf_file = tmp_path / "pack.rpf"
    rpf_file.write_bytes(b"RPF7stub")
    fake_rpf.register_path(rpf_file, _FakeArchive({"f.bin": b""}))
    with pytest.raises(NotADirectoryError):
        list((VPath(rpf_file) / "f.bin").iterdir())


def test_read_bytes_on_dir_raises_is_a_directory(tmp_path, fake_rpf):
    rpf_file = tmp_path / "pack.rpf"
    rpf_file.write_bytes(b"RPF7stub")
    fake_rpf.register_path(rpf_file, _FakeArchive({"dir/x.bin": b""}))
    with pytest.raises(IsADirectoryError):
        (VPath(rpf_file) / "dir").read_bytes()


def test_cache_reuses_archive(tmp_path, fake_rpf):
    rpf_file = tmp_path / "pack.rpf"
    rpf_file.write_bytes(b"RPF7stub")
    fake_rpf.register_path(rpf_file, _FakeArchive({"a.bin": b"", "b.bin": b""}))

    (VPath(rpf_file) / "a.bin").exists()
    (VPath(rpf_file) / "b.bin").exists()
    assert fake_rpf.call_count == 1


def test_clear_archive_cache_resets(tmp_path, fake_rpf):
    rpf_file = tmp_path / "pack.rpf"
    rpf_file.write_bytes(b"RPF7stub")
    fake_rpf.register_path(rpf_file, _FakeArchive({"a.bin": b""}))

    (VPath(rpf_file) / "a.bin").exists()
    clear_archive_cache()
    (VPath(rpf_file) / "a.bin").exists()
    assert fake_rpf.call_count == 2


def test_cache_evicts_beyond_capacity(tmp_path, fake_rpf, monkeypatch):
    monkeypatch.setattr("szio.vfs._ArchiveCache._MAX", 2)
    files = []
    for i in range(3):
        f = tmp_path / f"p{i}.rpf"
        f.write_bytes(b"RPF7stub")
        fake_rpf.register_path(f, _FakeArchive({"x.bin": b""}))
        files.append(f)

    (VPath(files[0]) / "x.bin").exists()
    (VPath(files[1]) / "x.bin").exists()
    (VPath(files[2]) / "x.bin").exists()
    # files[0] should be evicted; re-access re-opens
    (VPath(files[0]) / "x.bin").exists()
    # Calls: 3 initial + 1 reopen = 4
    assert fake_rpf.call_count == 4


def test_equality_hashable():
    s = {VPath("a/b"), VPath("a/b")}
    assert len(s) == 1


def test_equality_separator_normalization():
    # On Windows, / and \ are interchangeable; pathlib handles it.
    if os.name == "nt":
        assert VPath("a/b") == VPath("a\\b")


def test_distinct_paths_not_equal():
    assert VPath("a") != VPath("b")
    assert VPath("x.rpf") != VPath("x.rpf/y")


def test_as_data_source_os_path(tmp_path):
    f = tmp_path / "f.bin"
    f.write_bytes(b"hello")
    ds = VPath(f).as_data_source()
    assert isinstance(ds, DataSource)
    assert ds.read_bytes() == b"hello"


def test_as_data_source_in_rpf_returns_seekable_stream(tmp_path, fake_rpf):
    """In-RPF DataSource.open() returns a seekable in-memory stream of the whole
    entry (it is materialized up front, not windowed); reading a prefix works."""
    rpf_file = tmp_path / "pack.rpf"
    rpf_file.write_bytes(b"RPF7stub")
    big_blob = b"HEADER" + b"\x00" * 10_000
    fake_rpf.register_path(rpf_file, _FakeArchive({"big.bin": big_blob}))

    ds = (VPath(rpf_file) / "big.bin").as_data_source()
    assert isinstance(ds, DataSource)
    with ds.open() as stream:
        head = stream.read(6)
    assert head == b"HEADER"


def test_glob_simple_star_on_disk(tmp_path):
    (tmp_path / "a.txt").write_text("")
    (tmp_path / "b.txt").write_text("")
    (tmp_path / "c.bin").write_text("")
    matches = sorted(p.name for p in VPath(tmp_path).glob("*.txt"))
    assert matches == ["a.txt", "b.txt"]


def test_glob_double_star_recurses_on_disk(tmp_path):
    (tmp_path / "a.txt").write_text("")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("")
    (tmp_path / "sub" / "deep").mkdir()
    (tmp_path / "sub" / "deep" / "c.txt").write_text("")
    names = sorted(p.name for p in VPath(tmp_path).glob("**/*.txt"))
    assert names == ["a.txt", "b.txt", "c.txt"]


def test_glob_terminal_globstar_yields_files_and_dirs(tmp_path):
    (tmp_path / "a.txt").write_text("")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("")
    # Terminal `**` yields the start path itself plus every descendant
    # (files and directories), matching pathlib semantics.
    names = {p.name for p in VPath(tmp_path).glob("**")}
    assert names == {tmp_path.name, "a.txt", "b.txt", "sub"}


def test_rglob_equivalent_to_double_star(tmp_path):
    (tmp_path / "a.txt").write_text("")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("")
    by_glob = sorted(str(p) for p in VPath(tmp_path).glob("**/*.txt"))
    by_rglob = sorted(str(p) for p in VPath(tmp_path).rglob("*.txt"))
    assert by_glob == by_rglob


def test_glob_inside_rpf(tmp_path, fake_rpf):
    rpf_file = tmp_path / "pack.rpf"
    rpf_file.write_bytes(b"RPF7stub")
    fake_rpf.register_path(
        rpf_file,
        _FakeArchive({"data/a.xml": b"", "data/b.xml": b"", "data/sub/c.xml": b""}),
    )
    names = sorted(p.name for p in (VPath(rpf_file) / "data").glob("*.xml"))
    assert names == ["a.xml", "b.xml"]


def test_glob_double_star_crosses_rpf_boundary(tmp_path, fake_rpf):
    rpf_file = tmp_path / "pack.rpf"
    rpf_file.write_bytes(b"RPF7stub")
    fake_rpf.register_path(rpf_file, _FakeArchive({"pack/file.txt": b"hello"}))
    matches = list(VPath(tmp_path).glob("**/*.txt"))
    assert len(matches) == 1
    assert matches[0].name == "file.txt"
    assert matches[0].read_bytes() == b"hello"


def test_glob_double_star_through_nested_rpf(tmp_path, fake_rpf):
    rpf_file = tmp_path / "outer.rpf"
    rpf_file.write_bytes(b"RPF7stub")
    inner_marker = fake_rpf.stream_marker("inner_archive")
    fake_rpf.register_path(rpf_file, _FakeArchive({"nested/inner.rpf": inner_marker}))
    fake_rpf.register_name("inner_archive", _FakeArchive({"deep/payload.bin": b"x"}))
    matches = list(VPath(rpf_file).rglob("payload.bin"))
    assert len(matches) == 1
    assert matches[0].name == "payload.bin"
    assert matches[0].read_bytes() == b"x"


def test_glob_case_sensitivity_kwarg(tmp_path):
    (tmp_path / "A.TXT").write_text("")
    (tmp_path / "b.txt").write_text("")
    sensitive = sorted(p.name for p in VPath(tmp_path).glob("*.txt", case_sensitive=True))
    assert sensitive == ["b.txt"]
    insensitive = sorted(p.name for p in VPath(tmp_path).glob("*.txt", case_sensitive=False))
    assert insensitive == ["A.TXT", "b.txt"]


def test_glob_default_case_matches_os(tmp_path):
    (tmp_path / "A.TXT").write_text("")
    (tmp_path / "b.txt").write_text("")
    default = sorted(p.name for p in VPath(tmp_path).glob("*.txt"))
    if os.name == "nt":
        assert default == ["A.TXT", "b.txt"]
    else:
        assert default == ["b.txt"]


def test_match_simple_and_with_globstar():
    p = VPath("a/b/c.txt")
    assert p.match("c.txt", case_sensitive=True)
    assert p.match("b/c.txt", case_sensitive=True)
    assert not p.match("a/c.txt", case_sensitive=True)
    assert p.match("**/c.txt", case_sensitive=True)
    assert p.match("a/**/c.txt", case_sensitive=True)
    assert p.match("*/c.txt", case_sensitive=True)
    assert not p.match("*/*/*/c.txt", case_sensitive=True)
    assert p.match("**", case_sensitive=True)
    assert p.match("a/b/c.txt", case_sensitive=True)
    assert not p.match("d.txt", case_sensitive=True)


def test_match_case_sensitivity():
    p = VPath("dir/A.TXT")
    assert not p.match("a.txt", case_sensitive=True)
    assert p.match("a.txt", case_sensitive=False)
    assert not p.match("**/a.txt", case_sensitive=True)
    assert p.match("**/a.txt", case_sensitive=False)


@pytest.mark.parametrize(
    "pattern,exc",
    [
        ("", ValueError),
        ("/abs", NotImplementedError),
        ("a/../b", ValueError),
        ("a**b", ValueError),
        ("./a", ValueError),
    ],
)
def test_glob_invalid_patterns_raise(tmp_path, pattern, exc):
    with pytest.raises(exc):
        list(VPath(tmp_path).glob(pattern))


@pytest.mark.parametrize(
    "pattern,exc",
    [
        ("", ValueError),
        ("/abs", NotImplementedError),
        ("a**b", ValueError),
    ],
)
def test_match_invalid_patterns_raise(pattern, exc):
    with pytest.raises(exc):
        VPath("a/b/c").match(pattern)


def test_glob_on_missing_path_yields_empty(tmp_path):
    assert list(VPath(tmp_path / "nope").glob("*")) == []
    assert list(VPath(tmp_path / "nope").rglob("*.bin")) == []


def test_glob_preserves_resolved_cache(tmp_path, fake_rpf):
    rpf_file = tmp_path / "pack.rpf"
    rpf_file.write_bytes(b"RPF7stub")
    fake_rpf.register_path(
        rpf_file,
        _FakeArchive({"a.bin": b"", "dir/b.bin": b"", "dir/sub/c.bin": b""}),
    )
    matches = sorted(p.name for p in VPath(rpf_file).rglob("*.bin"))
    assert matches == ["a.bin", "b.bin", "c.bin"]
    # A single archive open is enough to walk the whole tree because
    # iterdir() populates _resolved on the children it yields.
    assert fake_rpf.call_count == 1


def test_rpf_dir_is_not_inside_archive(tmp_path):
    d = tmp_path / "data.rpf"
    d.mkdir()
    assert not VPath(d).is_inside_archive()


def test_rpf_dir_child_is_not_inside_archive(tmp_path):
    d = tmp_path / "data.rpf"
    d.mkdir()
    (d / "file.txt").write_text("hi")
    assert not (VPath(d) / "file.txt").is_inside_archive()


def test_rpf_dir_is_dir_is_file_is_archive(tmp_path):
    d = tmp_path / "data.rpf"
    d.mkdir()
    p = VPath(d)
    assert p.is_dir()
    assert not p.is_file()
    assert not p.is_archive()
    assert p.exists()


def test_rpf_dir_child_stat_ops(tmp_path):
    d = tmp_path / "data.rpf"
    d.mkdir()
    (d / "f.bin").write_bytes(b"x")
    child = VPath(d) / "f.bin"
    assert child.exists()
    assert child.is_file()
    assert not child.is_dir()


def test_rpf_dir_read_through(tmp_path):
    d = tmp_path / "data.rpf"
    d.mkdir()
    (d / "f.bin").write_bytes(b"hello")
    assert (VPath(d) / "f.bin").read_bytes() == b"hello"


def test_rpf_dir_open_read(tmp_path):
    d = tmp_path / "data.rpf"
    d.mkdir()
    (d / "f.bin").write_bytes(b"abc")
    with (VPath(d) / "f.bin").open("rb") as fh:
        assert fh.read() == b"abc"


def test_rpf_dir_write_is_allowed(tmp_path):
    """Writing inside a *directory* named .rpf must not be gated as an archive."""
    d = tmp_path / "data.rpf"
    d.mkdir()
    p = VPath(d) / "out.bin"
    p.write_bytes(b"written")
    assert (d / "out.bin").read_bytes() == b"written"


def test_rpf_dir_write_text_and_mkdir_allowed(tmp_path):
    d = tmp_path / "data.rpf"
    d.mkdir()
    (VPath(d) / "note.txt").write_text("text", encoding="utf-8")
    assert (d / "note.txt").read_text(encoding="utf-8") == "text"
    (VPath(d) / "sub").mkdir()
    assert (d / "sub").is_dir()


def test_rpf_dir_unlink_allowed(tmp_path):
    d = tmp_path / "data.rpf"
    d.mkdir()
    (d / "f.bin").write_bytes(b"x")
    (VPath(d) / "f.bin").unlink()
    assert not (d / "f.bin").exists()


def test_rpf_dir_fspath(tmp_path):
    d = tmp_path / "data.rpf"
    d.mkdir()
    (d / "sub").mkdir()
    p = VPath(d) / "sub" / "f.bin"
    assert os.fspath(p) == str(d / "sub" / "f.bin")


def test_rpf_dir_iterdir(tmp_path):
    d = tmp_path / "data.rpf"
    d.mkdir()
    (d / "a.txt").write_text("")
    (d / "b.txt").write_text("")
    names = sorted(child.name for child in VPath(d).iterdir())
    assert names == ["a.txt", "b.txt"]


def test_rpf_dir_iterdir_from_child(tmp_path):
    d = tmp_path / "data.rpf"
    sub = d / "sub"
    sub.mkdir(parents=True)
    (sub / "c.bin").write_bytes(b"")
    names = sorted(child.name for child in (VPath(d) / "sub").iterdir())
    assert names == ["c.bin"]


def test_rpf_dir_as_data_source(tmp_path):
    d = tmp_path / "data.rpf"
    d.mkdir()
    (d / "f.bin").write_bytes(b"payload")
    ds = (VPath(d) / "f.bin").as_data_source()
    assert isinstance(ds, DataSource)
    assert ds.read_bytes() == b"payload"


def test_rpf_dir_glob(tmp_path):
    d = tmp_path / "data.rpf"
    d.mkdir()
    (d / "a.txt").write_text("")
    (d / "sub").mkdir()
    (d / "sub" / "b.txt").write_text("")
    names = sorted(p.name for p in VPath(tmp_path).glob("**/*.txt"))
    assert names == ["a.txt", "b.txt"]


def test_deep_rpf_dir_chain(tmp_path):
    d1 = tmp_path / "outer.rpf"
    d2 = d1 / "inner.rpf"
    d2.mkdir(parents=True)
    (d2 / "file.bin").write_bytes(b"deep")
    p = VPath(tmp_path) / "outer.rpf" / "inner.rpf" / "file.bin"
    assert not p.is_inside_archive()
    assert p.read_bytes() == b"deep"
    assert os.fspath(p) == str(d2 / "file.bin")


def test_nonexistent_rpf_assumed_archive(tmp_path):
    """A .rpf component that does not exist is treated as an archive boundary."""
    p = VPath(tmp_path) / "missing.rpf" / "file.bin"
    assert p.is_inside_archive()
    assert not p.exists()


# ----- 14. Mixed chains: .rpf directory containing a real .rpf archive -----


def test_mixed_chain_rpf_dir_then_archive(tmp_path, fake_rpf):
    d = tmp_path / "dir.rpf"
    d.mkdir()
    rpf_file = d / "pack.rpf"
    rpf_file.write_bytes(b"RPF7stub")
    fake_rpf.register_path(rpf_file, _FakeArchive({"data/entry.bin": b"payload"}))

    p = VPath(tmp_path) / "dir.rpf" / "pack.rpf" / "data" / "entry.bin"
    assert p.is_inside_archive()
    assert p.exists()
    assert p.read_bytes() == b"payload"


def test_mixed_chain_two_dirs_then_archive(tmp_path, fake_rpf):
    d2 = tmp_path / "A.rpf" / "B.rpf"
    d2.mkdir(parents=True)
    rpf_file = d2 / "C.rpf"
    rpf_file.write_bytes(b"RPF7stub")
    fake_rpf.register_path(rpf_file, _FakeArchive({"deep.bin": b"deep"}))

    p = VPath(tmp_path) / "A.rpf" / "B.rpf" / "C.rpf" / "deep.bin"
    assert p.is_inside_archive()
    assert p.read_bytes() == b"deep"


def test_mixed_chain_write_into_archive_forbidden(tmp_path, fake_rpf):
    d = tmp_path / "dir.rpf"
    d.mkdir()
    rpf_file = d / "pack.rpf"
    rpf_file.write_bytes(b"RPF7stub")
    fake_rpf.register_path(rpf_file, _FakeArchive({"f.bin": b""}))

    p = VPath(tmp_path) / "dir.rpf" / "pack.rpf" / "f.bin"
    with pytest.raises(PermissionError):
        p.write_bytes(b"bad")


def test_mixed_chain_fspath_raises_inside_archive(tmp_path, fake_rpf):
    d = tmp_path / "dir.rpf"
    d.mkdir()
    rpf_file = d / "pack.rpf"
    rpf_file.write_bytes(b"RPF7stub")
    fake_rpf.register_path(rpf_file, _FakeArchive({"e.bin": b""}))

    with pytest.raises(ValueError):
        os.fspath(VPath(tmp_path) / "dir.rpf" / "pack.rpf" / "e.bin")


def test_archive_file_through_rpf_dir(tmp_path, fake_rpf):
    """A path pointing *at* a real .rpf inside a .rpf directory behaves like an archive."""
    d = tmp_path / "dir.rpf"
    d.mkdir()
    rpf_file = d / "pack.rpf"
    rpf_file.write_bytes(b"RPF7stub")
    fake_rpf.register_path(rpf_file, _FakeArchive({"a.bin": b"", "dir/b.bin": b""}))

    p = VPath(tmp_path) / "dir.rpf" / "pack.rpf"
    assert p.is_archive()
    assert not p.is_inside_archive()  # points at the archive, not inside it
    assert p.is_dir()  # iterable like a directory
    names = sorted(child.name for child in p.iterdir())
    assert names == ["a.bin", "dir"]


def test_mixed_chain_rglob_into_archive(tmp_path, fake_rpf):
    d = tmp_path / "dir.rpf"
    d.mkdir()
    rpf_file = d / "pack.rpf"
    rpf_file.write_bytes(b"RPF7stub")
    fake_rpf.register_path(rpf_file, _FakeArchive({"payload.bin": b"x"}))

    matches = list(VPath(tmp_path).rglob("payload.bin"))
    assert len(matches) == 1
    assert matches[0].name == "payload.bin"
    assert matches[0].read_bytes() == b"x"


def test_rpf_dir_boundary_cache_cleared(tmp_path):
    from szio.vfs import _rpf_dir_cache

    d = tmp_path / "data.rpf"
    d.mkdir()
    (VPath(d) / "f.txt").is_inside_archive()
    assert any(p.name == "data.rpf" for p in _rpf_dir_cache)
    clear_archive_cache()
    assert len(_rpf_dir_cache) == 0


def test_archive_file_through_rpf_dir_reads_raw_bytes(tmp_path, fake_rpf):
    """A path pointing AT a .rpf file inside a .rpf dir reads the raw file bytes
    (OS read), not the archive contents."""
    d = tmp_path / "dir.rpf"
    d.mkdir()
    rpf_file = d / "pack.rpf"
    rpf_file.write_bytes(b"RPF7stub-rawbytes")
    fake_rpf.register_path(rpf_file, _FakeArchive({"a.bin": b""}))

    p = VPath(tmp_path) / "dir.rpf" / "pack.rpf"
    assert not p.is_inside_archive()
    assert p.read_bytes() == b"RPF7stub-rawbytes"


def test_is_archive_false_for_missing_rpf_through_rpf_dir(tmp_path):
    d = tmp_path / "dir.rpf"
    d.mkdir()
    p = VPath(tmp_path) / "dir.rpf" / "missing.rpf"
    assert p.is_archive() is False
    assert not p.exists()


def test_rpf_dir_path_ops_are_syntactic(tmp_path):
    """parent/parts/name/equality across a .rpf dir stay purely syntactic:
    no filesystem access even when nothing exists on disk."""
    from szio.vfs import _rpf_dir_cache

    p = VPath(tmp_path) / "data.rpf" / "sub" / "f.bin"
    assert p.parts[-3:] == ("data.rpf", "sub", "f.bin")
    assert p.name == "f.bin"
    assert p.parent == VPath(tmp_path) / "data.rpf" / "sub"
    assert p == VPath(tmp_path) / "data.rpf" / "sub" / "f.bin"
    assert hash(p) == hash(VPath(tmp_path) / "data.rpf" / "sub" / "f.bin")
    assert len(_rpf_dir_cache) == 0


def test_glob_case_insensitive_across_rpf_dir(tmp_path):
    d = tmp_path / "data.rpf"
    d.mkdir()
    (d / "A.TXT").write_text("")
    (d / "b.txt").write_text("")
    names = sorted(p.name for p in VPath(tmp_path).glob("**/*.txt", case_sensitive=False))
    assert names == ["A.TXT", "b.txt"]


def test_mixed_chain_three_deep_opens_archive_once(tmp_path, fake_rpf):
    """dir.rpf/dir2.rpf (dirs) -> pack.rpf (archive): one open for the whole walk."""
    d2 = tmp_path / "A.rpf" / "B.rpf"
    d2.mkdir(parents=True)
    rpf_file = d2 / "C.rpf"
    rpf_file.write_bytes(b"RPF7stub")
    fake_rpf.register_path(rpf_file, _FakeArchive({"x/y.bin": b"deep"}))

    matches = list(VPath(tmp_path).rglob("y.bin"))
    assert len(matches) == 1
    assert matches[0].read_bytes() == b"deep"
    assert fake_rpf.call_count == 1


def test_absolute_makes_relative_os_path_absolute(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cwd = pathlib.Path.cwd()  # same source of truth absolute() reads (os.getcwd)
    assert VPath("a/b").absolute() == VPath(cwd) / "a" / "b"
    assert VPath("a/b").absolute().is_absolute()


def test_absolute_idempotent_on_absolute_path():
    p = VPath("C:/x/y") if os.name == "nt" else VPath("/x/y")
    assert p.absolute() == p  # equality, not identity


def test_absolute_on_empty_path_returns_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert VPath("").absolute() == VPath(pathlib.Path.cwd())


def test_absolute_through_archive_prefixes_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cwd = pathlib.Path.cwd()
    r = VPath("a.rpf/b/c").absolute()
    assert r == VPath(cwd) / "a.rpf" / "b" / "c"
    # The .rpf layer split survived the cwd-prefixing round-trip.
    assert r.parts[-3:] == ("a.rpf", "b", "c")


def test_absolute_with_rpf_directory_in_cwd(tmp_path, monkeypatch):
    # A real directory named "*.rpf" must stay a valid OS layer split, not be
    # mistaken for an archive boundary.
    sub = tmp_path / "dlc.rpf" / "sub"
    sub.mkdir(parents=True)
    monkeypatch.chdir(sub)
    r = VPath("x").absolute()
    assert r == VPath(pathlib.Path.cwd()) / "x"
    assert r.is_inside_archive() is False
    assert r.exists() is False


def test_absolute_preserves_equality_and_hash(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    a = VPath("a/b").absolute()
    assert a == a
    assert len({a, a}) == 1
    assert VPath(str(a)) == a


def test_is_absolute():
    assert VPath("a/b").is_absolute() is False
    p = VPath("C:/x/y") if os.name == "nt" else VPath("/x/y")
    assert p.is_absolute() is True


def test_glob_terminal_globstar_on_file_yields_empty(tmp_path):
    # Terminal `**` yields the start path only when it is a real directory
    # (pathlib parity), not when it is a file or missing.
    (tmp_path / "f.txt").write_text("")
    assert list((VPath(tmp_path) / "f.txt").glob("**")) == []


def test_glob_terminal_globstar_on_missing_yields_empty(tmp_path):
    assert list((VPath(tmp_path) / "nope").glob("**")) == []


def test_glob_terminal_globstar_in_archive_on_file_and_missing(tmp_path, fake_rpf):
    rpf_file = tmp_path / "pack.rpf"
    rpf_file.write_bytes(b"RPF7stub")
    fake_rpf.register_path(rpf_file, _FakeArchive({"a.bin": b"", "dir/b.bin": b""}))
    assert list((VPath(rpf_file) / "a.bin").glob("**")) == []
    assert list((VPath(rpf_file) / "nope").glob("**")) == []


def test_match_many_globstars_is_not_exponential():
    import time

    p = VPath("/".join(f"d{i}" for i in range(24)))
    pattern = "/".join(["**"] * 9 + ["zzz"])
    start = time.perf_counter()
    assert p.match(pattern, case_sensitive=True) is False
    assert time.perf_counter() - start < 1.0  # was ~29s before memoization
    # Positive multi-`**` matches still work.
    assert VPath("a/b/c.txt").match("**/**/c.txt", case_sensitive=True)


def test_iterdir_no_resource_warning_when_abandoned(tmp_path):
    import gc
    import warnings

    for i in range(5):
        (tmp_path / f"f{i}.txt").write_text("")
    with warnings.catch_warnings():
        warnings.simplefilter("error", ResourceWarning)
        gen = VPath(tmp_path).iterdir()
        next(gen)
        del gen
        gc.collect()  # must not raise ResourceWarning: unclosed scandir iterator


def test_text_default_encoding_is_utf8_on_os_and_in_archive(tmp_path, fake_rpf):
    data = "café".encode("utf-8")
    f = tmp_path / "f.txt"
    f.write_bytes(data)
    assert VPath(f).read_text() == "café"

    rpf_file = tmp_path / "pack.rpf"
    rpf_file.write_bytes(b"RPF7stub")
    fake_rpf.register_path(rpf_file, _FakeArchive({"f.txt": data}))
    assert (VPath(rpf_file) / "f.txt").read_text() == "café"


def test_write_text_then_read_text_roundtrips_utf8(tmp_path):
    p = VPath(tmp_path / "f.txt")
    p.write_text("café")  # default utf-8
    assert p.read_bytes() == "café".encode("utf-8")
    assert p.read_text() == "café"


def test_relative_vpath_is_cwd_stable_across_chdir(tmp_path, fake_rpf, monkeypatch):
    a = tmp_path / "dirA"
    b = tmp_path / "dirB"
    a.mkdir()
    b.mkdir()
    (a / "pack.rpf").write_bytes(b"RPF7stub")
    (b / "pack.rpf").write_bytes(b"RPF7stub")
    fake_rpf.register_path(a / "pack.rpf", _FakeArchive({"f.bin": b"AAA"}))
    fake_rpf.register_path(b / "pack.rpf", _FakeArchive({"f.bin": b"BBB"}))
    clear_archive_cache()

    monkeypatch.chdir(a)
    assert (VPath("pack.rpf") / "f.bin").read_bytes() == b"AAA"
    monkeypatch.chdir(b)
    # No tree mutation and no explicit clear: must reflect the new cwd, not reuse
    # the classification/resolution computed under dirA.
    assert (VPath("pack.rpf") / "f.bin").read_bytes() == b"BBB"


def test_truediv_rejects_drive_anchored_name():
    if os.name != "nt":
        pytest.skip("Windows drive-letter semantics")
    # `/` must agree with the constructor, which rejects an anchored join.
    with pytest.raises(ValueError):
        VPath("foo") / "C:"
    with pytest.raises(ValueError):
        VPath("x") / "a:b"


def test_exists_propagates_unopenable_archive_error(tmp_path, fake_rpf):
    # A corrupt/bad-magic archive is "present but unopenable", surface the
    # error rather than silently reporting absence.
    bad = tmp_path / "bad.rpf"
    bad.write_bytes(b"NOPE")  # unregistered -> fake open_rpf raises OSError
    p = VPath(bad) / "x" / "f.bin"
    with pytest.raises(OSError):
        p.exists()


def test_open_accepts_buffering_and_newline(tmp_path):
    f = tmp_path / "f.txt"
    f.write_bytes(b"a\r\nb")
    # Positional buffering (pathlib idiom) and newline= must be accepted; with
    # newline="" no translation occurs so the bytes round-trip verbatim.
    with VPath(f).open("r", -1, newline="") as fh:
        assert fh.read() == "a\r\nb"


def test_open_invalid_mode_raises_valueerror(tmp_path, fake_rpf):
    rpf_file = tmp_path / "pack.rpf"
    rpf_file.write_bytes(b"RPF7stub")
    fake_rpf.register_path(rpf_file, _FakeArchive({"a.txt": b"hi"}))
    in_rpf = VPath(rpf_file) / "a.txt"
    os_path = VPath(tmp_path / "plain.txt")
    (tmp_path / "plain.txt").write_text("x")
    for bad in ("", "q", "rbt", "rw"):
        with pytest.raises(ValueError):
            in_rpf.open(bad)
        with pytest.raises(ValueError):
            os_path.open(bad)


def test_str_uses_forward_slashes_and_as_posix(tmp_path):
    p = VPath(tmp_path) / "x.rpf" / "data" / "f.bin"
    s = str(p)
    assert "\\" not in s
    assert p.as_posix() == s
    assert VPath(s) == p  # round-trip preserved


def test_is_absolute_drive_relative_is_not_absolute():
    if os.name != "nt":
        pytest.skip("Windows drive semantics")
    assert VPath("C:foo").is_absolute() is False
    assert VPath("C:/foo").is_absolute() is True
