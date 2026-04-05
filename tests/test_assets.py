"""Tests for asset loading, game detection, and the AssetGame enum."""

from pathlib import Path

import pytest

import szio
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
