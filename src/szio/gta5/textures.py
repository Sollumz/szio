from dataclasses import dataclass, field

from ..assets import AssetGame
from ..types import DataSource
from .assets import AssetType


@dataclass(slots=True)
class EmbeddedTexture:
    name: str
    width: int
    height: int
    data: DataSource | None


@dataclass(slots=True)
class AssetTextureDictionary:
    ASSET_GAME: AssetGame = AssetGame.GTA5
    ASSET_TYPE: AssetType = AssetType.TEXTURE_DICTIONARY

    textures: dict[str, EmbeddedTexture] = field(default_factory=dict)
