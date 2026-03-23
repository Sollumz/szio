from enum import Enum, auto
from pathlib import Path


class AssetGame(Enum):
    GTA5 = auto()
    RDR2 = auto()


def try_load_asset(path: Path):
    """Try to load a RAGE asset file, auto-detecting the game from the asset format."""
    from .gta5.assets import try_load_asset as _gta5_try_load

    asset = _gta5_try_load(path)
    if asset is not None:
        return asset

    return None


def save_asset(
    asset,
    directory: Path,
    name: str,
    tool_metadata: tuple[str, str] | None = None,
    options=None,
    targets=None,
):
    """Save a RAGE asset file, dispatching to the correct game module based on the asset's game."""
    from . import gta5

    match asset.ASSET_GAME:
        case AssetGame.GTA5:
            gta5.save_asset(asset, directory, name, tool_metadata, options, targets=targets)
        case _:
            raise ValueError(f"Unknown asset game '{asset.ASSET_GAME}'")
