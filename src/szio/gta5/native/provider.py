import math
from abc import ABC, abstractmethod
from pathlib import Path

import pymateria as pma
import pymateria.gta5 as pm
import pymateria.rsc7 as pmrsc

from ..archetypes import AssetMapTypes
from ..assets import Asset
from ..bounds import AssetBound, BoundType
from ..cloths import AssetClothDictionary
from ..drawables import AssetDrawable, AssetDrawableDictionary
from ..fragments import AssetFragment
from .adapters import NativeBound, NativeClothDictionary, NativeMapTypes


class NativeProvider(ABC):
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
                return NativeBound(pm.Bound.import_rsc(path).result)
            case ".yld":
                return NativeClothDictionary(pm.ClothDictionary.import_rsc(path).result)
            case ".ytyp":
                # gen9 map types has some minimal differences (made some padding explicit fields, doesn't really affect anything)
                # gen8 import can read both
                return NativeMapTypes(pm.gen8.MapTypes.import_rsc(path).result)
            case _:
                raise ValueError(f"Unsupported file '{str(path)}'")

    def create_asset_bound(self, bound_type: BoundType) -> AssetBound:
        match bound_type:
            case BoundType.COMPOSITE:
                b = NativeBound(pm.BoundComposite())
            case BoundType.SPHERE:
                b = NativeBound(pm.BoundSphere())
            case BoundType.BOX:
                b = NativeBound(pm.BoundBox())
            case BoundType.CAPSULE:
                b = NativeBound(pm.BoundCapsule())
            case BoundType.CYLINDER:
                b = NativeBound(pm.BoundCylinder())
            case BoundType.DISC:
                b = NativeBound(pm.BoundDisc())
            case BoundType.GEOMETRY:
                b = NativeBound(pm.BoundGeometry())
            case BoundType.BVH:
                bvh = pm.BoundGeometry()
                bvh.generate_bvh = True
                b = NativeBound(bvh)
            case BoundType.PLANE:
                b = NativeBound(pm.BoundPlane())
            case _:
                raise ValueError(f"Unsupported bound type '{bound_type.name}'")

        return self._apply_target(b)

    @abstractmethod
    def create_asset_drawable(
        self, is_frag: bool = False, parent_drawable: AssetDrawable | None = None
    ) -> AssetDrawable: ...

    @abstractmethod
    def create_asset_drawable_dictionary(self) -> AssetDrawableDictionary: ...

    @abstractmethod
    def create_asset_fragment(self) -> AssetFragment: ...

    def create_asset_cloth_dictionary(self) -> AssetClothDictionary:
        return self._apply_target(NativeClothDictionary(pm.ClothDictionary()))

    @abstractmethod
    def create_asset_map_types(self) -> AssetMapTypes: ...

    def save_asset(self, asset: Asset, directory: Path, name: str, tool_metadata: tuple[str, str] | None = None):
        if isinstance(asset, NativeBound):
            path = directory / f"{name}.ybn"
            pm.Bound.export_rsc(asset._inner, path, self._export_settings(tool_metadata))
        elif isinstance(asset, NativeClothDictionary):
            path = directory / f"{name}.yld"
            pm.ClothDictionary.export_rsc(asset._inner, path, self._export_settings(tool_metadata))
        elif isinstance(asset, NativeMapTypes):
            path = directory / f"{name}.ytyp"
            pm.gen8.MapTypes.export_rsc(asset._inner, path, self._export_settings(tool_metadata))
        else:
            raise ValueError(f"Unsupported asset '{asset}' (name: '{name}', directory: '{str(directory)}')")

    def _export_settings(self, tool_metadata: tuple[str, str] | None = None) -> pma.ExportSettings:
        s = pma.ExportSettings()
        if tool_metadata is not None:
            name, version = tool_metadata
            s.metadata = pma.UserMetadata(name, version)
        return s

    def _apply_target(self, asset):
        asset.ASSET_FORMAT = self.ASSET_FORMAT
        asset.ASSET_VERSION = self.ASSET_VERSION
        return asset

    def _assert_target(self, asset):
        assert asset.ASSET_FORMAT == self.ASSET_FORMAT
        assert asset.ASSET_VERSION == self.ASSET_VERSION
        return asset
