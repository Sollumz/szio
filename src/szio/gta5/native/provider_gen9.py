from pathlib import Path

import pymateria as pma
import pymateria.gta5.gen9 as pmg9

from ..archetypes import AssetMapTypes
from ..assets import Asset, AssetFormat, AssetVersion, canonical_asset
from ..drawables import AssetDrawable, AssetDrawableDictionary
from ..fragments import AssetFragment
from .adapters import (
    NativeDrawableDictionaryG9,
    NativeDrawableG9,
    NativeFragDrawableG9,
    NativeFragmentG9,
    NativeMapTypesG9,
)
from .provider import NativeProvider


class NativeProviderG9(NativeProvider):
    ASSET_FORMAT = AssetFormat.NATIVE
    ASSET_VERSION = AssetVersion.GEN9

    def get_supported_rsc_version(self, file_ext: str) -> int:
        match file_ext:
            case ".ydr":
                return pmg9.Drawable.RSC_VERSION
            case ".ydd":
                return pmg9.DrawableDictionary.RSC_VERSION
            case ".yft":
                return pmg9.Fragment.RSC_VERSION
            case _:
                return super().get_supported_rsc_version(file_ext)

    def load_file(self, path: Path) -> Asset:
        match path.suffix.lower():
            case ".ydr":
                drawable = pmg9.Drawable.import_rsc(path).result
                textures_dir = path.parent / path.stem
                return NativeDrawableG9(drawable)
            case ".ydd":
                dwd = pmg9.DrawableDictionary.import_rsc(path).result
                textures_dir = path.parent / path.stem
                return NativeDrawableDictionaryG9(dwd)
            case ".yft":
                fragment = pmg9.Fragment.import_rsc(path).result
                textures_dir = path.parent / path.stem
                return NativeFragmentG9(fragment)
            case _:
                return super().load_file(path)

    def create_asset_drawable(
        self, is_frag: bool = False, parent_drawable: AssetDrawable | None = None
    ) -> AssetDrawable:
        if is_frag:
            parent_drawable = parent_drawable and canonical_asset(parent_drawable, NativeFragDrawableG9, self)._inner
            d = pmg9.FragmentDrawable()
            d.bound_matrix = pma.Matrix34(
                pma.Vector4f(1.0, 0.0, 0.0, 0.0),
                pma.Vector4f(0.0, 1.0, 0.0, 0.0),
                pma.Vector4f(0.0, 0.0, 1.0, 0.0),
                pma.Vector4f(0.0, 0.0, 0.0, 1.0),
            )
            return self._assert_target(NativeFragDrawableG9(d, parent_drawable))
        else:
            parent_drawable = parent_drawable and canonical_asset(parent_drawable, NativeDrawableG9, self)._inner
            return self._assert_target(NativeDrawableG9(pmg9.Drawable(), parent_drawable))

    def create_asset_drawable_dictionary(self) -> AssetDrawableDictionary:
        return self._assert_target(NativeDrawableDictionaryG9(pmg9.DrawableDictionary()))

    def create_asset_fragment(self) -> AssetFragment:
        f = pmg9.Fragment()
        f.damaged_object_index = -1
        return self._assert_target(NativeFragmentG9(f))

    def create_asset_map_types(self) -> AssetMapTypes:
        return self._assert_target(NativeMapTypesG9(pmg9.MapTypes()))

    def save_asset(self, asset: Asset, directory: Path, name: str, tool_metadata: tuple[str, str] | None = None):
        if isinstance(asset, NativeDrawableG9):
            path = directory / f"{name}.ydr"
            pmg9.Drawable.export_rsc(asset._inner, path, self._export_settings(tool_metadata))
        elif isinstance(asset, NativeDrawableDictionaryG9):
            path = directory / f"{name}.ydd"
            pmg9.DrawableDictionary.export_rsc(asset._inner, path, self._export_settings(tool_metadata))
        elif isinstance(asset, NativeFragmentG9):
            path = directory / f"{name}.yft"
            pmg9.Fragment.export_rsc(asset._inner, path, self._export_settings(tool_metadata))
        elif isinstance(asset, NativeMapTypesG9):
            path = directory / f"{name}.ytyp"
            pmg9.MapTypes.export_rsc(asset._inner, path, self._export_settings(tool_metadata))
        else:
            super().save_asset(asset, directory, name, tool_metadata)
