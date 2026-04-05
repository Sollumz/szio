from enum import Enum, auto
from pathlib import Path
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Any, Protocol, overload, runtime_checkable


class AssetGame(Enum):
    GTA5 = auto()
    RDR2 = auto()


class AssetType(Enum):
    BOUND = auto()
    DRAWABLE = auto()
    DRAWABLE_DICTIONARY = auto()
    FRAGMENT = auto()
    CLOTH_DICTIONARY = auto()
    MAP_TYPES = auto()
    TEXTURE_DICTIONARY = auto()


@runtime_checkable
class Asset(Protocol):
    ASSET_GAME: AssetGame
    ASSET_TYPE: AssetType


@dataclass(slots=True)
class AssetWithDependencies:
    name: str
    main_asset: Asset
    dependencies: dict[str, Asset]


@runtime_checkable
class AssetTarget(Protocol):
    format: Any
    version: Any


@runtime_checkable
class AssetProvider(Protocol):
    ASSET_GAME: AssetGame
    ASSET_FORMAT: Any
    ASSET_VERSION: Any

    def supports_file(self, path: Path) -> bool: ...

    def load_file(self, path: Path) -> Asset: ...

    def save_asset(self, asset: Asset, directory: Path, name: str, tool_metadata: tuple[str, str] | None = None): ...


@runtime_checkable
class SaveOptions(Protocol):
    tool_metadata: tuple[str, str] | None


@overload
def try_load_asset(path: Path, *, return_target: Literal[False] = ...) -> Asset | None: ...
@overload
def try_load_asset(path: Path, *, return_target: Literal[True]) -> tuple[Asset, AssetTarget] | None: ...


def try_load_asset(path: Path, *, return_target: bool = False) -> Asset | tuple[Asset, AssetTarget] | None:
    """Try to load a RAGE asset file, auto-detecting the game from the asset format."""
    from .gta5.assets import try_load_asset as _gta5_try_load
    from .rdr2.assets import try_load_asset as _rdr2_try_load

    return _gta5_try_load(path, return_target=return_target) or _rdr2_try_load(path, return_target=return_target)


def save_asset(
    asset: Asset,
    targets: Sequence[AssetTarget],
    directory: Path,
    name: str,
    options: SaveOptions | None = None,
):
    """Save a RAGE asset file, dispatching to the correct game module based on the asset's game."""
    from . import gta5
    from . import rdr2

    match asset.ASSET_GAME:
        case AssetGame.GTA5:
            gta5.save_asset(asset, targets, directory, name, options)
        case AssetGame.RDR2:
            rdr2.save_asset(asset, targets, directory, name, options)
        case _:
            raise ValueError(f"Unknown asset game '{asset.ASSET_GAME}'")
