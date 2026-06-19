"""Tests for asset loading, game detection, and the AssetGame enum."""

import io
from pathlib import Path

import pytest

import szio
from szio import VPath
from szio.assets import AssetGame
from szio.gta5 import AssetFormat, AssetTarget, AssetVersion

# Minimal XML stubs for each game/format combination.
# Only the root element tag matters for detection.
GTA5_XMLS = {
    ".ydr": ("Drawable", "<Drawable />"),
    ".ydd": ("DrawableDictionary", "<DrawableDictionary />"),
    ".ybn": ("BoundsFile", '<BoundsFile><Bounds type="Composite" /></BoundsFile>'),
}


def _write_xml(tmp_path: Path, ext: str, content: str) -> Path:
    path = tmp_path / f"test{ext}.xml"
    path.write_text(content, encoding="utf-8")
    return path


class TestSupportsFile:
    """Tests that providers correctly identify which files they support."""

    @pytest.mark.parametrize("ext", [".ydr", ".ydd", ".ybn"])
    def test_gta5_provider_supports_gta5_xml(self, ext: str, tmp_path: Path):
        from szio.gta5.assets import get_providers

        _, content = GTA5_XMLS[ext]
        path = _write_xml(tmp_path, ext, content)

        assert any(p.supports_file(path) for p in get_providers().values())

    def test_supports_file_returns_false_for_missing_file(self, tmp_path: Path):
        from szio.gta5.assets import get_providers as gta5_providers

        missing = tmp_path / "nonexistent.ydr.xml"

        assert not any(p.supports_file(missing) for p in gta5_providers().values())

    @pytest.mark.parametrize("filename", ["test.txt", "test.ydr", "test.xml", "test.png.xml"])
    def test_supports_file_returns_false_for_unsupported_extensions(self, filename: str, tmp_path: Path):
        from szio.gta5.assets import get_providers as gta5_providers

        path = tmp_path / filename
        path.write_text("<Drawable />", encoding="utf-8")

        assert not any(p.supports_file(path) for p in gta5_providers().values())

    def test_supports_file_returns_false_for_wrong_root_element(self, tmp_path: Path):
        from szio.gta5.assets import get_providers as gta5_providers

        path = _write_xml(tmp_path, ".ydr", "<SomethingElse />")

        assert not any(p.supports_file(path) for p in gta5_providers().values())


class TestAssetGame:
    """Tests that loaded assets have the correct ASSET_GAME attribute."""

    @pytest.mark.parametrize("ext", [".ydr", ".ydd", ".ybn"])
    def test_gta5_asset_has_gta5_game(self, ext: str, tmp_path: Path):
        from szio.gta5.assets import try_load_asset

        _, content = GTA5_XMLS[ext]
        path = _write_xml(tmp_path, ext, content)

        asset = try_load_asset(path)
        assert asset is not None
        assert asset.ASSET_GAME == AssetGame.GTA5


class TestTryLoadAsset:
    """Tests for the top-level szio.try_load_asset auto-detection."""

    @pytest.mark.parametrize("ext", [".ydr", ".ydd", ".ybn"])
    def test_auto_detects_gta5(self, ext: str, tmp_path: Path):
        _, content = GTA5_XMLS[ext]
        path = _write_xml(tmp_path, ext, content)

        asset = szio.try_load_asset(path)
        assert asset is not None
        assert asset.ASSET_GAME == AssetGame.GTA5

    def test_returns_none_for_unsupported_file(self, tmp_path: Path):
        path = _write_xml(tmp_path, ".ydr", "<SomethingElse />")
        assert szio.try_load_asset(path) is None

    def test_returns_none_for_missing_file(self, tmp_path: Path):
        assert szio.try_load_asset(tmp_path / "nonexistent.ydr.xml") is None

    @pytest.mark.parametrize("ext", [".ydr", ".ydd", ".ybn"])
    def test_accepts_str_path(self, ext: str, tmp_path: Path):
        _, content = GTA5_XMLS[ext]
        path = _write_xml(tmp_path, ext, content)

        asset = szio.try_load_asset(str(path))
        assert asset is not None
        assert asset.ASSET_GAME == AssetGame.GTA5

    @pytest.mark.parametrize("ext", [".ydr", ".ydd", ".ybn"])
    def test_accepts_os_backed_vpath(self, ext: str, tmp_path: Path):
        _, content = GTA5_XMLS[ext]
        path = _write_xml(tmp_path, ext, content)

        asset = szio.try_load_asset(VPath(path))
        assert asset is not None
        assert asset.ASSET_GAME == AssetGame.GTA5


class TestSaveAsset:
    """Tests for the top-level szio.save_asset dispatch."""

    @pytest.mark.parametrize("ext", [".ydr", ".ydd", ".ybn"])
    def test_roundtrip_gta5(self, ext: str, tmp_path: Path):
        _, content = GTA5_XMLS[ext]
        path = _write_xml(tmp_path, ext, content)

        asset = szio.try_load_asset(path)
        assert asset is not None

        out_dir = tmp_path / "out"
        out_dir.mkdir()
        targets = [AssetTarget(AssetFormat.CWXML, AssetVersion.GEN8)]
        szio.save_asset(asset, targets, out_dir, "roundtrip")

        reloaded = szio.try_load_asset(out_dir / f"roundtrip{ext}.xml")
        assert reloaded is not None
        assert reloaded.ASSET_GAME == AssetGame.GTA5


class _InMemoryArchive:
    """Minimal in-memory RpfArchive double, mirroring tests/test_vfs.py.

    Only the methods VPath needs to resolve and read an in-archive entry
    are implemented, so the in-archive load path can be tested without the
    native backend.
    """

    def __init__(self, entries: dict[str, bytes]):
        self._files = {p.strip("/"): data for p, data in entries.items()}
        self._dirs = {""}
        for p in self._files:
            parts = p.split("/")
            for i in range(len(parts)):
                self._dirs.add("/".join(parts[:i]))

    def close(self):
        pass

    def exists(self, inner: str) -> bool:
        inner = inner.strip("/")
        return inner in self._files or inner in self._dirs

    def is_file(self, inner: str) -> bool:
        return inner.strip("/") in self._files

    def is_dir(self, inner: str) -> bool:
        return inner.strip("/") in self._dirs

    def list_dir(self, inner: str) -> list[str]:
        inner = inner.strip("/")
        prefix = inner + "/" if inner else ""
        return sorted({f[len(prefix):].split("/")[0] for f in self._files if f.startswith(prefix)})

    def read_bytes(self, inner: str) -> bytes:
        return self._files[inner.strip("/")]

    def open_bytes(self, inner: str) -> io.BytesIO:
        return io.BytesIO(self.read_bytes(inner))


class TestTryLoadAssetInsideArchive:
    """Load assets from inside an RPF archive via VPath, backend-independent."""

    def _vpath_in_archive(self, tmp_path: Path, monkeypatch, entry: str, content: bytes) -> VPath:
        from szio.vfs import clear_archive_cache

        archive = _InMemoryArchive({entry: content})
        rpf = tmp_path / "pack.rpf"
        rpf.write_bytes(b"RPF7stub")
        monkeypatch.setattr("szio.rpf.open_rpf", lambda *a, **k: archive)
        clear_archive_cache()
        return VPath(rpf) / entry

    @pytest.mark.parametrize("ext", [".ydr", ".ydd", ".ybn"])
    def test_loads_cwxml_asset_from_inside_archive(self, ext: str, tmp_path: Path, monkeypatch):
        _, content = GTA5_XMLS[ext]
        vpath = self._vpath_in_archive(tmp_path, monkeypatch, f"test{ext}.xml", content.encode("utf-8"))

        asset = szio.try_load_asset(vpath)
        assert asset is not None
        assert asset.ASSET_GAME == AssetGame.GTA5

    def test_wrong_root_inside_archive_returns_none(self, tmp_path: Path, monkeypatch):
        vpath = self._vpath_in_archive(tmp_path, monkeypatch, "test.ydr.xml", b"<SomethingElse />")

        assert szio.try_load_asset(vpath) is None
