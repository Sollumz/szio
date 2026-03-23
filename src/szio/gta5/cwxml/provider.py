from abc import ABC
from pathlib import Path

from ...xml import get_xml_root_tag
from ..archetypes import AssetMapTypes
from ..assets import Asset, AssetFormat, AssetGame, AssetVersion
from ..bounds import AssetBound, BoundType
from ..cloths import AssetClothDictionary
from ..drawables import AssetDrawable, AssetDrawableDictionary
from ..fragments import AssetFragment
from . import bound as cw
from . import cloth as cwcloth
from . import drawable as cwdr
from . import fragment as cwfr
from . import ytyp as cwtyp
from .adapters import (
    CWBound,
    CWClothDictionary,
    CWDrawable,
    CWDrawableDictionary,
    CWFragDrawable,
    CWFragment,
    CWMapTypes,
)


class CWProvider(ABC):
    ASSET_GAME = AssetGame.GTA5
    ASSET_FORMAT = None
    ASSET_VERSION = None
    XML_EXTENSION = ".xml"
    SUPPORTED_EXTENSIONS = {
        ".ybn": "BoundsFile",
        ".ydr": "Drawable",
        ".ydd": "DrawableDictionary",
        ".yft": "Fragment",
        ".yld": "ClothDictionary",
        ".ytyp": "CMapTypes",
    }

    def supports_file(self, path: Path) -> bool:
        suffixes = path.suffixes
        if (
            len(suffixes) >= 2
            and suffixes[-1].lower() == CWProvider.XML_EXTENSION
            and (ext := suffixes[-2].lower()) in CWProvider.SUPPORTED_EXTENSIONS
        ):
            expected_root_element_name = CWProvider.SUPPORTED_EXTENSIONS[ext]
            return get_xml_root_tag(path) == expected_root_element_name

        return False

    def load_file(self, path: Path) -> Asset:
        suffixes = path.suffixes
        match suffixes[-2].lower():
            case ".ybn":
                return CWBound(cw.BoundFile.from_xml_file(path).composite)
            case ".ydr":
                return CWDrawable(cwdr.Drawable.from_xml_file(path))
            case ".ydd":
                return CWDrawableDictionary(cwdr.DrawableDictionary.from_xml_file(path))
            case ".yft":
                return CWFragment(cwfr.Fragment.from_xml_file(path))
            case ".yld":
                return CWClothDictionary(cwcloth.ClothDictionary.from_xml_file(path))
            case ".ytyp":
                return CWMapTypes(cwtyp.CMapTypes.from_xml_file(path))
            case _:
                raise ValueError(f"Unsupported file '{str(path)}'")

    def create_asset_bound(self, bound_type: BoundType) -> AssetBound:
        match bound_type:
            case BoundType.COMPOSITE:
                b = CWBound(cw.BoundComposite())
            case BoundType.SPHERE:
                b = CWBound(cw.BoundSphere())
            case BoundType.BOX:
                b = CWBound(cw.BoundBox())
            case BoundType.CAPSULE:
                b = CWBound(cw.BoundCapsule())
            case BoundType.CYLINDER:
                b = CWBound(cw.BoundCylinder())
            case BoundType.DISC:
                b = CWBound(cw.BoundDisc())
            case BoundType.GEOMETRY:
                b = CWBound(cw.BoundGeometry())
            case BoundType.BVH:
                b = CWBound(cw.BoundGeometryBVH())
            case BoundType.PLANE:
                b = CWBound(cw.BoundPlane())
            case _:
                raise ValueError(f"Unsupported bound type '{bound_type.name}'")

        return self._apply_target(b)

    def create_asset_drawable(
        self, is_frag: bool = False, parent_drawable: AssetDrawable | None = None
    ) -> AssetDrawable:
        # We don't need the parent drawable here as the shaders are referenced with indices and don't need the parent shader group
        d = cwdr.Drawable()
        if is_frag:
            return self._apply_target(CWFragDrawable(d))
        else:
            d.frag_bound_matrix = None
            return self._apply_target(CWDrawable(d))

    def create_asset_drawable_dictionary(self) -> AssetDrawableDictionary:
        return self._apply_target(CWDrawableDictionary(cwdr.DrawableDictionary()))

    def create_asset_fragment(self) -> AssetFragment:
        f = cwfr.Fragment()
        f.drawable = None
        f.physics = None
        return self._apply_target(CWFragment(f))

    def create_asset_cloth_dictionary(self) -> AssetClothDictionary:
        return self._apply_target(CWClothDictionary(cwcloth.ClothDictionary()))

    def create_asset_map_types(self) -> AssetMapTypes:
        return self._apply_target(CWMapTypes(cwtyp.CMapTypes()))

    def save_asset(self, asset: Asset, directory: Path, name: str, tool_metadata: tuple[str, str] | None = None):
        if isinstance(asset, CWBound):
            assert isinstance(asset._inner, cw.BoundComposite), "Can only save bound composites as .ybn"

            path = directory / f"{name}.ybn.xml"
            bound_file = cw.BoundFile()
            bound_file.composite = asset._inner
            bound_file.write_xml(path)
        elif isinstance(asset, CWDrawable):
            path = directory / f"{name}.ydr.xml"
            asset._inner.write_xml(path)
        elif isinstance(asset, CWDrawableDictionary):
            path = directory / f"{name}.ydd.xml"
            asset._inner.write_xml(path)
        elif isinstance(asset, CWFragment):
            path = directory / f"{name}.yft.xml"
            asset._inner.write_xml(path)
        elif isinstance(asset, CWClothDictionary):
            path = directory / f"{name}.yld.xml"
            asset._inner.write_xml(path)
        elif isinstance(asset, CWMapTypes):
            path = directory / f"{name}.ytyp.xml"
            asset._inner.write_xml(path)
        else:
            raise ValueError(f"Unsupported asset '{asset}' (name: '{name}', directory: '{str(directory)}')")

    def _apply_target(self, asset):
        asset.ASSET_GAME = self.ASSET_GAME
        asset.ASSET_FORMAT = self.ASSET_FORMAT
        asset.ASSET_VERSION = self.ASSET_VERSION
        return asset


class CWProviderG8(CWProvider):
    ASSET_FORMAT = AssetFormat.CWXML
    ASSET_VERSION = AssetVersion.GEN8


class CWProviderG9(CWProvider):
    ASSET_FORMAT = AssetFormat.CWXML
    ASSET_VERSION = AssetVersion.GEN9
