from abc import ABC
from pathlib import Path

from ...xml import get_xml_root_tag
from ..archetypes import AssetMapTypes
from ..assets import Asset, AssetFormat, AssetGame, AssetVersion
from ..bounds import AssetBound
from ..cloths import AssetClothDictionary
from ..drawables import AssetDrawable, AssetDrawableDictionary
from ..fragments import AssetFragment
from ..textures import AssetTextureDictionary
from . import bound as cwbnd
from . import cloth as cwcloth
from . import drawable as cwdr
from . import fragment as cwfr
from . import ytyp as cwtyp
from .adapters import (
    load_bound_from_cw,
    load_cloth_dictionary_from_cw,
    load_drawable_dictionary_from_cw,
    load_drawable_from_cw,
    load_fragment_from_cw,
    load_map_types_from_cw,
    load_txd_from_cw,
    save_bound_to_cw,
    save_cloth_dictionary_to_cw,
    save_drawable_dictionary_to_cw,
    save_drawable_to_cw,
    save_fragment_to_cw,
    save_map_types_to_cw,
    save_txd_to_cw,
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
        ".ytd": "TextureDictionary",
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
                return load_bound_from_cw(cwbnd.BoundFile.from_xml_file(path).composite)
            case ".ydr":
                return load_drawable_from_cw(cwdr.Drawable.from_xml_file(path))
            case ".ydd":
                return load_drawable_dictionary_from_cw(cwdr.DrawableDictionary.from_xml_file(path))
            case ".yft":
                return load_fragment_from_cw(cwfr.Fragment.from_xml_file(path))
            case ".yld":
                return load_cloth_dictionary_from_cw(cwcloth.ClothDictionary.from_xml_file(path))
            case ".ytyp":
                return load_map_types_from_cw(cwtyp.CMapTypes.from_xml_file(path))
            case ".ytd":
                return load_txd_from_cw(cwdr.TextureDictionaryList.from_xml_file(path))
            case _:
                raise ValueError(f"Unsupported file '{str(path)}'")

    def save_asset(self, asset: Asset, directory: Path, name: str, tool_metadata: tuple[str, str] | None = None):
        if isinstance(asset, AssetBound):
            path = directory / f"{name}.ybn.xml"
            bound_file = cwbnd.BoundFile()
            bound_file.composite = save_bound_to_cw(asset)
            bound_file.write_xml(path)
        elif isinstance(asset, AssetDrawable):
            path = directory / f"{name}.ydr.xml"
            save_drawable_to_cw(asset, self.ASSET_VERSION).write_xml(path)
        elif isinstance(asset, AssetDrawableDictionary):
            path = directory / f"{name}.ydd.xml"
            save_drawable_dictionary_to_cw(asset, self.ASSET_VERSION).write_xml(path)
        elif isinstance(asset, AssetFragment):
            path = directory / f"{name}.yft.xml"
            save_fragment_to_cw(asset, self.ASSET_VERSION).write_xml(path)
        elif isinstance(asset, AssetClothDictionary):
            path = directory / f"{name}.yld.xml"
            save_cloth_dictionary_to_cw(asset).write_xml(path)
        elif isinstance(asset, AssetMapTypes):
            path = directory / f"{name}.ytyp.xml"
            save_map_types_to_cw(asset).write_xml(path)
        elif isinstance(asset, AssetTextureDictionary):
            path = directory / f"{name}.ytd.xml"
            save_txd_to_cw(asset).write_xml(path)
        else:
            raise ValueError(f"Unsupported asset '{asset}' (name: '{name}', directory: '{str(directory)}')")


class CWProviderG8(CWProvider):
    ASSET_FORMAT = AssetFormat.CWXML
    ASSET_VERSION = AssetVersion.GEN8


class CWProviderG9(CWProvider):
    ASSET_FORMAT = AssetFormat.CWXML
    ASSET_VERSION = AssetVersion.GEN9
