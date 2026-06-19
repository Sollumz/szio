import os
from enum import Enum, auto
from pathlib import Path
from typing import TypeAlias

from .vfs import VPath

# A path-like accepted by asset import. `VPath` is listed explicitly because an
# in-archive VPath is not `os.PathLike` (its `__fspath__` raises).
AssetPath: TypeAlias = str | os.PathLike | VPath


class AssetGame(Enum):
    GTA5 = auto()
    RDR2 = auto()


def try_load_asset(path: AssetPath, *, return_target: bool = False):
    """Try to load a RAGE asset file, auto-detecting the game from the asset format."""
    from .gta5.assets import try_load_asset as _gta5_try_load

    result = _gta5_try_load(path, return_target=return_target)
    if result is not None:
        return result

    return None


def save_asset(
    asset,
    targets,
    directory: Path,
    name: str,
    options=None,
):
    """Save a RAGE asset file, dispatching to the correct game module based on the asset's game."""
    from . import gta5

    match asset.ASSET_GAME:
        case AssetGame.GTA5:
            gta5.save_asset(asset, targets, directory, name, options)
        case _:
            raise ValueError(f"Unknown asset game '{asset.ASSET_GAME}'")
