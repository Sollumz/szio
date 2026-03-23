import math
from abc import ABC, abstractmethod
from pathlib import Path

import pymateria as pma
import pymateria.gta5 as pm
import pymateria.rsc7 as pmrsc

from ..archetypes import AssetMapTypes
from ..assets import Asset, AssetGame
from ..bounds import AssetBound, BoundType
from ..cloths import AssetClothDictionary
from ..drawables import AssetDrawable, AssetDrawableDictionary
from ..fragments import AssetFragment
from .adapters.archetype import (
    load_map_types,
    save_map_types_to_native,
)
from .adapters.bound import (
    load_bound,
    save_bound_to_native,
)
from .adapters.cloth import (
    load_cloth_dictionary,
    save_cloth_dictionary_to_native,
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
    }

    def supports_file(self, path: Path) -> bool:
        ext = path.suffix.lower()
        if ext in NativeProvider.SUPPORTED_EXTENSIONS:
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
            case _:
                raise ValueError(f"Unsupported file extension '{file_ext}'")

    def load_file(self, path: Path) -> Asset:
        match path.suffix.lower():
            case ".ybn":
                return load_bound(pm.Bound.import_rsc(path).result)
            case ".yld":
                return load_cloth_dictionary(pm.ClothDictionary.import_rsc(path).result)
            case ".ytyp":
                # gen9 map types has some minimal differences (made some padding explicit fields, doesn't really affect anything)
                # gen8 import can read both
                return load_map_types(pm.gen8.MapTypes.import_rsc(path).result)
            case _:
                raise ValueError(f"Unsupported file '{str(path)}'")

    def create_asset_bound(self, bound_type: BoundType) -> AssetBound:
        return AssetBound(bound_type=bound_type)

    @abstractmethod
    def create_asset_drawable(
        self, is_frag: bool = False, parent_drawable: AssetDrawable | None = None
    ) -> AssetDrawable: ...

    @abstractmethod
    def create_asset_drawable_dictionary(self) -> AssetDrawableDictionary: ...

    @abstractmethod
    def create_asset_fragment(self) -> AssetFragment: ...

    def create_asset_cloth_dictionary(self) -> AssetClothDictionary:
        return AssetClothDictionary()

    @abstractmethod
    def create_asset_map_types(self) -> AssetMapTypes: ...

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
            pm.gen8.MapTypes.export_rsc(save_map_types_to_native(asset), path, self._export_settings(tool_metadata))
        else:
            raise ValueError(f"Unsupported asset '{asset}' (name: '{name}', directory: '{str(directory)}')")

    def _export_settings(self, tool_metadata: tuple[str, str] | None = None) -> pma.ExportSettings:
        s = pma.ExportSettings()
        if tool_metadata is not None:
            name, version = tool_metadata
            s.metadata = pma.UserMetadata(name, version)
        return s
