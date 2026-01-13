from pathlib import Path

import pymateria as pma
import pymateria.gta5.gen8 as pmg8

from ..archetypes import AssetMapTypes
from ..assets import Asset, AssetFormat, AssetVersion, canonical_asset
from ..drawables import AssetDrawable, AssetDrawableDictionary
from ..fragments import AssetFragment
from .adapters import (
    NativeDrawable,
    NativeDrawableDictionary,
    NativeFragDrawable,
    NativeFragment,
    NativeMapTypes,
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
                textures_dir = path.parent / path.stem
                return NativeDrawable(drawable)
            case ".ydd":
                dwd = pmg8.DrawableDictionary.import_rsc(path).result
                textures_dir = path.parent / path.stem
                return NativeDrawableDictionary(dwd)
            case ".yft":
                fragment = pmg8.Fragment.import_rsc(path).result
                textures_dir = path.parent / path.stem
                return NativeFragment(fragment)
            case _:
                return super().load_file(path)

    def create_asset_drawable(
        self, is_frag: bool = False, parent_drawable: AssetDrawable | None = None
    ) -> AssetDrawable:
        if is_frag:
            parent_drawable = parent_drawable and canonical_asset(parent_drawable, NativeFragDrawable, self)._inner
            d = pmg8.FragmentDrawable()
            d.bound_matrix = pma.Matrix34(
                pma.Vector4f(1.0, 0.0, 0.0, 0.0),
                pma.Vector4f(0.0, 1.0, 0.0, 0.0),
                pma.Vector4f(0.0, 0.0, 1.0, 0.0),
                pma.Vector4f(0.0, 0.0, 0.0, 1.0),
            )
            return self._assert_target(NativeFragDrawable(d, parent_drawable))
        else:
            parent_drawable = parent_drawable and canonical_asset(parent_drawable, NativeDrawable, self)._inner
            return self._assert_target(NativeDrawable(pmg8.Drawable(), parent_drawable))

    def create_asset_drawable_dictionary(self) -> AssetDrawableDictionary:
        return self._assert_target(NativeDrawableDictionary(pmg8.DrawableDictionary()))

    def create_asset_fragment(self) -> AssetFragment:
        f = pmg8.Fragment()
        f.damaged_object_index = -1
        return self._assert_target(NativeFragment(f))

    def create_asset_map_types(self) -> AssetMapTypes:
        return self._assert_target(NativeMapTypes(pmg8.MapTypes()))

    def save_asset(self, asset: Asset, directory: Path, name: str, tool_metadata: tuple[str, str] | None = None):
        if isinstance(asset, NativeDrawable):
            path = directory / f"{name}.ydr"
            pmg8.Drawable.export_rsc(asset._inner, path, self._export_settings(tool_metadata))
        elif isinstance(asset, NativeDrawableDictionary):
            path = directory / f"{name}.ydd"
            pmg8.DrawableDictionary.export_rsc(asset._inner, path, self._export_settings(tool_metadata))
        elif isinstance(asset, NativeFragment):
            path = directory / f"{name}.yft"
            pmg8.Fragment.export_rsc(asset._inner, path, self._export_settings(tool_metadata))
        elif isinstance(asset, NativeMapTypes):
            path = directory / f"{name}.ytyp"
            pmg8.MapTypes.export_rsc(asset._inner, path, self._export_settings(tool_metadata))
        else:
            super().save_asset(asset, directory, name, tool_metadata)
