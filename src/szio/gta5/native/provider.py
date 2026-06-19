from abc import ABC
from pathlib import Path

import pymateria as pma
import pymateria.gta5 as pm
import pymateria.rsc7 as pmrsc

from .._import_source import import_source
from ..archetypes import AssetMapTypes
from ..assets import Asset, AssetGame, ProviderPath
from ..bounds import AssetBound
from ..cloths import AssetClothDictionary
from ..maps import AssetMapData
from .adapters import (
    load_bound_from_native,
    load_cloth_dictionary_from_native,
    load_map_types_from_native,
    load_map_data_from_native,
    save_bound_to_native,
    save_cloth_dictionary_to_native,
    save_map_types_to_native_g8,
    save_map_data_to_native,
)


class NativeProvider(ABC):
    ASSET_GAME = AssetGame.GTA5
    ASSET_FORMAT = None
    ASSET_VERSION = None
    SUPPORTED_EXTENSIONS = {
        ".ybn",
        ".ydr",
        ".ydd",
        ".yft",
        ".yld",
        ".ytyp",
        ".ymap",
        ".ytd",
    }

    def supports_file(self, path: ProviderPath) -> bool:
        ext = path.suffix.lower()
        if ext in NativeProvider.SUPPORTED_EXTENSIONS and path.is_file():
            with path.open("rb") as f:
                if header_data := f.read(pmrsc.Header.HEADER_SIZE):
                    header = pmrsc.Header(header_data) if len(header_data) == pmrsc.Header.HEADER_SIZE else None
                    return header and header.version == self.get_supported_rsc_version(ext)

        return False

    def get_supported_rsc_version(self, file_ext: str) -> int:
        match file_ext:
            case ".ybn":
                return pm.Bound.RSC_VERSION
            case ".yld":
                return pm.ClothDictionary.RSC_VERSION
            case ".ytyp":
                return pm.gen8.MapTypes.RSC_VERSION
            case ".ymap":
                return pm.MapData.RSC_VERSION
            case _:
                raise ValueError(f"Unsupported file extension '{file_ext}'")

    def load_file(self, path: ProviderPath) -> Asset:
        match path.suffix.lower():
            case ".ybn":
                with import_source(path) as src:
                    result = pm.Bound.import_rsc(src).result
                return load_bound_from_native(result)
            case ".yld":
                with import_source(path) as src:
                    result = pm.ClothDictionary.import_rsc(src).result
                return load_cloth_dictionary_from_native(result)
            case ".ytyp":
                # gen9 map types has some minimal differences (made some padding explicit fields, doesn't really affect anything)
                # gen8 import can read both
                with import_source(path) as src:
                    result = pm.gen8.MapTypes.import_rsc(src).result
                return load_map_types_from_native(result)
            case ".ymap":
                with import_source(path) as src:
                    result = pm.MapData.import_rsc(src).result
                return load_map_data_from_native(result)
            case _:
                raise ValueError(f"Unsupported file '{str(path)}'")

    def save_asset(self, asset: Asset, directory: Path, name: str, tool_metadata: tuple[str, str] | None = None):
        if isinstance(asset, AssetBound):
            path = directory / f"{name}.ybn"
            pm.Bound.export_rsc(save_bound_to_native(asset), path, self._export_settings(tool_metadata))
        elif isinstance(asset, AssetClothDictionary):
            path = directory / f"{name}.yld"
            pm.ClothDictionary.export_rsc(
                save_cloth_dictionary_to_native(asset), path, self._export_settings(tool_metadata)
            )
        elif isinstance(asset, AssetMapTypes):
            path = directory / f"{name}.ytyp"
            pm.gen8.MapTypes.export_rsc(save_map_types_to_native_g8(asset), path, self._export_settings(tool_metadata))
        elif isinstance(asset, AssetMapData):
            path = directory / f"{name}.ymap"
            pm.MapData.export_rsc(save_map_data_to_native(asset), path, self._export_settings(tool_metadata))
        else:
            raise ValueError(f"Unsupported asset '{asset}' (name: '{name}', directory: '{str(directory)}')")

    def _export_settings(self, tool_metadata: tuple[str, str] | None = None) -> pma.ExportSettings:
        s = pma.ExportSettings()
        if tool_metadata is not None:
            name, version = tool_metadata
            s.metadata = pma.UserMetadata(name, version)
        return s
