from pathlib import Path

import pymateria as pma
import pymateria.gta5.gen8 as pmg8

from ..archetypes import AssetMapTypes
from ..assets import Asset, AssetFormat, AssetVersion
from ..drawables import AssetDrawable, AssetDrawableDictionary, AssetFragDrawable
from ..fragments import AssetFragment
from .adapters.drawable import (
    load_drawable,
    load_drawable_dictionary,
    save_drawable_dictionary_to_native,
    save_drawable_to_native,
)
from .adapters.fragment import (
    load_fragment,
    save_fragment_to_native,
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
            case _:
                return super().get_supported_rsc_version(file_ext)

    def load_file(self, path: Path) -> Asset:
        match path.suffix.lower():
            case ".ydr":
                drawable = pmg8.Drawable.import_rsc(path).result
                return load_drawable(drawable)
            case ".ydd":
                dwd = pmg8.DrawableDictionary.import_rsc(path).result
                return load_drawable_dictionary(dwd)
            case ".yft":
                fragment = pmg8.Fragment.import_rsc(path).result
                return load_fragment(fragment)
            case _:
                return super().load_file(path)

    def create_asset_drawable(
        self, is_frag: bool = False, parent_drawable: AssetDrawable | None = None
    ) -> AssetDrawable:
        if is_frag:
            return AssetFragDrawable()
        else:
            return AssetDrawable()

    def create_asset_drawable_dictionary(self) -> AssetDrawableDictionary:
        return AssetDrawableDictionary()

    def create_asset_fragment(self) -> AssetFragment:
        return AssetFragment()

    def create_asset_map_types(self) -> AssetMapTypes:
        return AssetMapTypes()

    def save_asset(self, asset: Asset, directory: Path, name: str, tool_metadata: tuple[str, str] | None = None):
        if isinstance(asset, AssetDrawableDictionary):
            path = directory / f"{name}.ydd"
            pmg8.DrawableDictionary.export_rsc(
                save_drawable_dictionary_to_native(asset), path, self._export_settings(tool_metadata)
            )
        elif isinstance(asset, AssetDrawable) and not isinstance(asset, AssetFragDrawable):
            path = directory / f"{name}.ydr"
            pmg8.Drawable.export_rsc(save_drawable_to_native(asset), path, self._export_settings(tool_metadata))
        elif isinstance(asset, AssetFragment):
            path = directory / f"{name}.yft"
            pmg8.Fragment.export_rsc(save_fragment_to_native(asset), path, self._export_settings(tool_metadata))
        else:
            super().save_asset(asset, directory, name, tool_metadata)
