from pathlib import Path

import pymateria.gta5.gen8 as pmg8

from ..assets import Asset, AssetFormat, AssetVersion
from ..drawables import AssetDrawable, AssetDrawableDictionary, AssetFragDrawable
from ..fragments import AssetFragment
from ..textures import AssetTextureDictionary
from .adapters import (
    load_drawable_dictionary_from_native_g8,
    load_drawable_from_native_g8,
    load_fragment_from_native_g8,
    load_txd_from_native_g8,
    save_drawable_dictionary_to_native_g8,
    save_drawable_to_native_g8,
    save_fragment_to_native_g8,
    save_txd_to_native_g8,
)
from .provider import NativeProvider


class NativeProviderG8(NativeProvider):
    ASSET_FORMAT = AssetFormat.NATIVE
    ASSET_VERSION = AssetVersion.GEN8

    def get_supported_rsc_version(self, file_ext: str) -> int:
        match file_ext:
            case ".ydr":
                return pmg8.Drawable.RSC_VERSION
            case ".ydd":
                return pmg8.DrawableDictionary.RSC_VERSION
            case ".yft":
                return pmg8.Fragment.RSC_VERSION
            case ".ytd":
                return pmg8.TextureDictionary.RSC_VERSION
            case _:
                return super().get_supported_rsc_version(file_ext)

    def load_file(self, path: Path) -> Asset:
        match path.suffix.lower():
            case ".ydr":
                drawable = pmg8.Drawable.import_rsc(path).result
                return load_drawable_from_native_g8(drawable)
            case ".ydd":
                dwd = pmg8.DrawableDictionary.import_rsc(path).result
                return load_drawable_dictionary_from_native_g8(dwd)
            case ".yft":
                fragment = pmg8.Fragment.import_rsc(path).result
                return load_fragment_from_native_g8(fragment)
            case ".ytd":
                txd = pmg8.TextureDictionary.import_rsc(path).result
                return load_txd_from_native_g8(txd)
            case _:
                return super().load_file(path)

    def save_asset(self, asset: Asset, directory: Path, name: str, tool_metadata: tuple[str, str] | None = None):
        if isinstance(asset, AssetDrawableDictionary):
            path = directory / f"{name}.ydd"
            pmg8.DrawableDictionary.export_rsc(
                save_drawable_dictionary_to_native_g8(asset), path, self._export_settings(tool_metadata)
            )
        elif isinstance(asset, AssetDrawable) and not isinstance(asset, AssetFragDrawable):
            path = directory / f"{name}.ydr"
            pmg8.Drawable.export_rsc(save_drawable_to_native_g8(asset), path, self._export_settings(tool_metadata))
        elif isinstance(asset, AssetFragment):
            path = directory / f"{name}.yft"
            pmg8.Fragment.export_rsc(save_fragment_to_native_g8(asset), path, self._export_settings(tool_metadata))
        elif isinstance(asset, AssetTextureDictionary):
            path = directory / f"{name}.ytd"
            pmg8.TextureDictionary.export_rsc(save_txd_to_native_g8(asset), path, self._export_settings(tool_metadata))
        else:
            super().save_asset(asset, directory, name, tool_metadata)
