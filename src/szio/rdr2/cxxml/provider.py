from abc import ABC
from pathlib import Path

from ...xml import get_xml_root_tag
from ...assets import AssetGame, Asset
from ..assets import AssetFormat, AssetVersion

# from ..archetypes import AssetMapTypes
from ..bounds import AssetBound
# from ..cloths import AssetClothDictionary
# from ..drawables import AssetDrawable, AssetDrawableDictionary
# from ..fragments import AssetFragment
from . import bound as cxbnd

# from . import cloth as cwcloth
# from . import drawable as cwdr
# from . import fragment as cwfr
# from . import ytyp as cwtyp
from .adapters import (
    load_bound_from_cx,
    #     load_cloth_dictionary_from_cw,
    #     load_drawable_dictionary_from_cw,
    #     load_drawable_from_cw,
    #     load_fragment_from_cw,
    #     load_map_types_from_cw,
    save_bound_to_cx,
    #     save_cloth_dictionary_to_cw,
    #     save_drawable_dictionary_to_cw,
    #     save_drawable_to_cw,
    #     save_fragment_to_cw,
    #     save_map_types_to_cw,
)


class CXProvider:
    ASSET_GAME = AssetGame.RDR2
    ASSET_FORMAT = AssetFormat.CXXML
    ASSET_VERSION = AssetVersion.DEFAULT
    XML_EXTENSION = ".xml"
    RSC_EXTENSION = ".rsc"
    SUPPORTED_EXTENSIONS = {
        ".ybn": "RDR2Bounds",
        # ".ydr": "RDR2Drawable",
        # ".ydd": "RDR2DrawableDictionary",
        # ".yft": "RDR2Fragment",
        # ".yld": "RDR2ClothDictionary",
    }
    SUPPORTED_RSC_EXTENSIONS = {
        # ".ytyp": "CMapTypes",
    }

    def supports_file(self, path: Path) -> bool:
        suffixes = path.suffixes
        if (
            len(suffixes) >= 2
            and suffixes[-1].lower() == CXProvider.XML_EXTENSION
            and (ext := suffixes[-2].lower()) in CXProvider.SUPPORTED_EXTENSIONS
        ):
            expected_root_element_name = CXProvider.SUPPORTED_EXTENSIONS[ext]
            return get_xml_root_tag(path) == expected_root_element_name

        if (
            len(suffixes) >= 3
            and suffixes[-1].lower() == CXProvider.XML_EXTENSION
            and suffixes[-2].lower() == CXProvider.RSC_EXTENSION
            and (ext := suffixes[-3].lower()) in CXProvider.SUPPORTED_RSC_EXTENSIONS
        ):
            expected_root_element_name = CXProvider.SUPPORTED_EXTENSIONS[ext]
            return get_xml_root_tag(path) == expected_root_element_name

        return False

    def load_file(self, path: Path) -> Asset:
        suffixes = path.suffixes
        match suffixes[-2].lower():
            case ".ybn":
                return load_bound_from_cx(cxbnd.BoundAny.from_xml_file(path))
        #     case ".ydr":
        #         return load_drawable_from_cw(cwdr.Drawable.from_xml_file(path))
        #     case ".ydd":
        #         return load_drawable_dictionary_from_cw(cwdr.DrawableDictionary.from_xml_file(path))
        #     case ".yft":
        #         return load_fragment_from_cw(cwfr.Fragment.from_xml_file(path))
        #     case ".yld":
        #         return load_cloth_dictionary_from_cw(cwcloth.ClothDictionary.from_xml_file(path))
        #     case ".rsc":
        #         match suffixes[-3].lower():
        #             case ".ytyp":
        #                 return load_map_types_from_cw(cwtyp.CMapTypes.from_xml_file(path))

        raise ValueError(f"Unsupported file '{str(path)}'")

    def save_asset(self, asset: Asset, directory: Path, name: str, tool_metadata: tuple[str, str] | None = None):
        if isinstance(asset, AssetBound):
            path = directory / f"{name}.ybn.xml"
            save_bound_to_cx(asset).write_xml(path)
        # elif isinstance(asset, AssetDrawable):
        #     path = directory / f"{name}.ydr.xml"
        #     save_drawable_to_cw(asset, self.ASSET_VERSION).write_xml(path)
        # elif isinstance(asset, AssetDrawableDictionary):
        #     path = directory / f"{name}.ydd.xml"
        #     save_drawable_dictionary_to_cw(asset, self.ASSET_VERSION).write_xml(path)
        # elif isinstance(asset, AssetFragment):
        #     path = directory / f"{name}.yft.xml"
        #     save_fragment_to_cw(asset, self.ASSET_VERSION).write_xml(path)
        # elif isinstance(asset, AssetClothDictionary):
        #     path = directory / f"{name}.yld.xml"
        #     save_cloth_dictionary_to_cw(asset).write_xml(path)
        # elif isinstance(asset, AssetMapTypes):
        #     path = directory / f"{name}.ytyp.rsc.xml"
        #     save_map_types_to_cw(asset).write_xml(path)
        else:
            raise ValueError(f"Unsupported asset '{type(asset)}' (name: '{name}', directory: '{str(directory)}')")
