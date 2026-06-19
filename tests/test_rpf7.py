"""End-to-end tests for the pymateria-backed RPF7 reader, exercised both
through `szio.rpf.open_rpf` directly and through `VPath`."""

import io
from pathlib import Path

import pytest

import szio
from szio import VPath
from szio.assets import AssetGame
from szio.gta5.native import IS_BACKEND_AVAILABLE
from szio.rpf import open_rpf
from szio.vfs import clear_archive_cache

DATA_DIR = Path(__file__).parent / "data" / "gta5"

pytestmark = pytest.mark.skipif(
    not IS_BACKEND_AVAILABLE,
    reason="Native backend (pymateria) not available",
)


# Imports that need pymateria are deferred to module-skip time.
if IS_BACKEND_AVAILABLE:
    from pymateria.rpf7 import (
        PackFile,
        PackFileEntryFile,
    )

    from szio.gta5.native.rpf7 import _Rpf7Archive


def _build_rpf(entries: dict[str, bytes]) -> bytes:
    """Build an RPF7 archive containing the given path -> bytes entries."""
    pf = PackFile.create()
    for path, data in entries.items():
        pf.add_entry(PackFileEntryFile.create(pf, path, data), False)
    buf = io.BytesIO()
    PackFile.export_rpf(pf, buf)
    return buf.getvalue()


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_archive_cache()
    yield
    clear_archive_cache()


def test_open_rpf_path_lists_root(tmp_path):
    rpf = tmp_path / "pack.rpf"
    rpf.write_bytes(_build_rpf({"a.bin": b"alpha", "dir/b.bin": b"beta"}))

    arc = open_rpf(rpf)
    try:
        assert arc.exists("a.bin")
        assert arc.is_file("a.bin")
        assert arc.is_dir("dir")
        assert sorted(arc.list_dir("")) == ["a.bin", "dir"]
        assert arc.read_bytes("a.bin") == b"alpha"
        assert arc.read_bytes("dir/b.bin") == b"beta"
    finally:
        arc.close()


def test_open_rpf_open_bytes_returns_seekable_stream(tmp_path):
    rpf = tmp_path / "pack.rpf"
    rpf.write_bytes(_build_rpf({"x.bin": b"0123456789"}))

    arc = open_rpf(rpf)
    try:
        with arc.open_bytes("x.bin") as stream:
            assert stream.read(3) == b"012"
            assert stream.read() == b"3456789"
    finally:
        arc.close()


def test_missing_entry_raises(tmp_path):
    rpf = tmp_path / "pack.rpf"
    rpf.write_bytes(_build_rpf({"a.bin": b""}))
    arc = open_rpf(rpf)
    try:
        with pytest.raises(FileNotFoundError):
            arc.read_bytes("missing.bin")
    finally:
        arc.close()


def test_list_dir_on_missing_dir_raises(tmp_path):
    rpf = tmp_path / "pack.rpf"
    rpf.write_bytes(_build_rpf({"a.bin": b""}))
    arc = open_rpf(rpf)
    try:
        with pytest.raises(FileNotFoundError):
            list(arc.list_dir("nope"))
    finally:
        arc.close()


def test_open_rpf_stream_requires_filename(tmp_path):
    rpf_bytes = _build_rpf({"a.bin": b""})
    with pytest.raises(ValueError):
        open_rpf(io.BytesIO(rpf_bytes))


def test_open_rpf_stream_with_filename(tmp_path):
    rpf_bytes = _build_rpf({"a.bin": b"hi"})
    arc = open_rpf(io.BytesIO(rpf_bytes), filename="pack.rpf")
    try:
        assert arc.read_bytes("a.bin") == b"hi"
    finally:
        arc.close()


def test_vpath_reads_through_rpf7(tmp_path):
    rpf = tmp_path / "pack.rpf"
    rpf.write_bytes(_build_rpf({"data/foo.xml": b"<root/>"}))

    p = VPath(rpf) / "data" / "foo.xml"
    assert p.exists()
    assert p.is_file()
    assert p.read_bytes() == b"<root/>"


def test_vpath_iterdir_lists_rpf_root(tmp_path):
    rpf = tmp_path / "pack.rpf"
    rpf.write_bytes(_build_rpf({"a.bin": b"", "dir/b.bin": b""}))

    names = sorted(child.name for child in VPath(rpf).iterdir())
    assert names == ["a.bin", "dir"]


def test_vpath_iterdir_lists_subdir(tmp_path):
    rpf = tmp_path / "pack.rpf"
    rpf.write_bytes(_build_rpf({"dir/b.bin": b"1", "dir/c.bin": b"2"}))

    names = sorted(child.name for child in (VPath(rpf) / "dir").iterdir())
    assert names == ["b.bin", "c.bin"]


def test_vpath_read_dir_raises_is_a_directory(tmp_path):
    rpf = tmp_path / "pack.rpf"
    rpf.write_bytes(_build_rpf({"dir/x.bin": b""}))
    with pytest.raises(IsADirectoryError):
        (VPath(rpf) / "dir").read_bytes()


def test_vpath_iterdir_on_file_raises(tmp_path):
    rpf = tmp_path / "pack.rpf"
    rpf.write_bytes(_build_rpf({"f.bin": b""}))
    with pytest.raises(NotADirectoryError):
        list((VPath(rpf) / "f.bin").iterdir())


def test_vpath_missing_in_rpf_raises_file_not_found(tmp_path):
    rpf = tmp_path / "pack.rpf"
    rpf.write_bytes(_build_rpf({"a.bin": b"x"}))
    with pytest.raises(FileNotFoundError):
        (VPath(rpf) / "nope.bin").read_bytes()


def test_vpath_reads_through_nested_rpf(tmp_path):
    inner_bytes = _build_rpf({"deep/target.bin": b"payload"})

    outer_pf = PackFile.create()
    outer_pf.add_entry(PackFileEntryFile.create(outer_pf, "nested/inner.rpf", inner_bytes), False)
    outer_buf = io.BytesIO()
    PackFile.export_rpf(outer_pf, outer_buf)

    rpf = tmp_path / "outer.rpf"
    rpf.write_bytes(outer_buf.getvalue())

    p = VPath(rpf) / "nested" / "inner.rpf" / "deep" / "target.bin"
    assert p.exists()
    assert p.read_bytes() == b"payload"


def test_vpath_iterdir_descends_into_nested_rpf(tmp_path):
    inner_bytes = _build_rpf({"a.bin": b"alpha", "dir/b.bin": b"beta"})

    outer_pf = PackFile.create()
    outer_pf.add_entry(PackFileEntryFile.create(outer_pf, "nested/inner.rpf", inner_bytes), False)
    outer_buf = io.BytesIO()
    PackFile.export_rpf(outer_pf, outer_buf)

    rpf = tmp_path / "outer.rpf"
    rpf.write_bytes(outer_buf.getvalue())

    inner = VPath(rpf) / "nested" / "inner.rpf"
    assert inner.is_dir()
    names = sorted(child.name for child in inner.iterdir())
    assert names == ["a.bin", "dir"]
    assert (inner / "dir" / "b.bin").read_bytes() == b"beta"


# ----- Cache reuse -----


def test_cache_reuses_packfile(tmp_path, monkeypatch):
    rpf = tmp_path / "pack.rpf"
    rpf.write_bytes(_build_rpf({"a.bin": b"a", "b.bin": b"b"}))

    import szio.gta5.native.rpf7 as rpf7_mod

    real_import = rpf7_mod.PackFile.import_rpf
    counter = {"n": 0}

    def counting_import(stream, filename):
        counter["n"] += 1
        return real_import(stream, filename)

    monkeypatch.setattr(rpf7_mod.PackFile, "import_rpf", counting_import)

    (VPath(rpf) / "a.bin").read_bytes()
    (VPath(rpf) / "b.bin").read_bytes()
    assert counter["n"] == 1


def test_backend_read_dir_raises_is_a_directory(tmp_path):
    rpf = tmp_path / "pack.rpf"
    rpf.write_bytes(_build_rpf({"dir/x.bin": b""}))
    arc = open_rpf(rpf)
    try:
        with pytest.raises(IsADirectoryError):
            arc.read_bytes("dir")
        with pytest.raises(IsADirectoryError):
            arc.open_bytes("dir")
    finally:
        arc.close()


def test_backend_backfills_children_for_missing_dir_entries():
    # Craft a PackFile whose TOC omits the intermediate directory entries (the
    # exact case the _build_index backfill targets). A backfilled dir must be
    # enumerable by list_dir, not merely visible to is_dir/exists.
    pf = PackFile.create()
    pf.add_entry(PackFileEntryFile.create(pf, "a/b/c.bin", b"deep"), False)
    deep = next(e for e in pf.entries if str(e.path) == "a/b/c.bin")

    class _FakePf:
        entries = [deep]

    arc = _Rpf7Archive.__new__(_Rpf7Archive)
    arc._pf = _FakePf()
    arc._init_index()

    assert arc.is_dir("a") and arc.exists("a")
    assert arc.is_dir("a/b")
    assert sorted(arc.list_dir("")) == ["a"]
    assert sorted(arc.list_dir("a")) == ["b"]
    assert sorted(arc.list_dir("a/b")) == ["c.bin"]
    assert arc.read_bytes("a/b/c.bin") == b"deep"


def test_backend_normal_archive_has_no_duplicate_children(tmp_path):
    # pymateria emits explicit dir entries; the dedup-aware backfill must not
    # double-insert names.
    rpf = tmp_path / "pack.rpf"
    rpf.write_bytes(_build_rpf({"a/b/c.bin": b"x", "a/d.bin": b"y"}))
    arc = open_rpf(rpf)
    try:
        assert sorted(arc.list_dir("a")) == ["b", "d.bin"]
        assert sorted(arc.list_dir("")) == ["a"]
    finally:
        arc.close()


# Minimal CWXML stubs; only the root element matters for detection/loading.
_CWXML_STUBS = {
    "test.ydr.xml": b"<Drawable />",
    "test.ydd.xml": b"<DrawableDictionary />",
    "test.ybn.xml": b'<BoundsFile><Bounds type="Composite" /></BoundsFile>',
}


@pytest.mark.parametrize("entry", sorted(_CWXML_STUBS))
def test_try_load_asset_cwxml_inside_rpf(entry, tmp_path):
    rpf = tmp_path / "pack.rpf"
    rpf.write_bytes(_build_rpf({entry: _CWXML_STUBS[entry]}))

    asset = szio.try_load_asset(VPath(rpf) / entry)
    assert asset is not None
    assert asset.ASSET_GAME == AssetGame.GTA5


def test_try_load_asset_native_inside_rpf(tmp_path):
    # Embed a real native resource and import it straight out of the archive.
    data = (DATA_DIR / "test_bounds.ybn").read_bytes()
    rpf = tmp_path / "pack.rpf"
    rpf.write_bytes(_build_rpf({"test_bounds.ybn": data}))

    asset = szio.try_load_asset(VPath(rpf) / "test_bounds.ybn")
    assert asset is not None
    assert asset.ASSET_GAME == AssetGame.GTA5


def test_try_load_asset_os_backed_vpath_native(tmp_path):
    # OS-backed VPath exercises the seam's path branch for the native backend.
    asset = szio.try_load_asset(VPath(DATA_DIR / "test_bounds.ybn"))
    assert asset is not None
    assert asset.ASSET_GAME == AssetGame.GTA5


def test_try_load_asset_missing_cwxml_entry_returns_none(tmp_path):
    rpf = tmp_path / "pack.rpf"
    rpf.write_bytes(_build_rpf({"test.ydr.xml": b"<Drawable />"}))

    assert szio.try_load_asset(VPath(rpf) / "missing.ydr.xml") is None


def test_try_load_asset_missing_native_entry_returns_none(tmp_path):
    rpf = tmp_path / "pack.rpf"
    rpf.write_bytes(_build_rpf({"a.ybn": b"not a real resource"}))

    # A missing in-archive entry must return None, not raise FileNotFoundError.
    assert szio.try_load_asset(VPath(rpf) / "missing.ybn") is None


def test_try_load_asset_wrong_root_inside_rpf_returns_none(tmp_path):
    rpf = tmp_path / "pack.rpf"
    rpf.write_bytes(_build_rpf({"test.ydr.xml": b"<SomethingElse />"}))

    assert szio.try_load_asset(VPath(rpf) / "test.ydr.xml") is None
