from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum, auto
from functools import cache
from pathlib import Path
from typing import Literal, NamedTuple, overload

from ..assets import (
    Asset,
    AssetProvider,
)

# Reimport for backward compatibility for now
from ..assets import (  # noqa: F401
    AssetGame,
    AssetType,
    AssetWithDependencies,
)


class AssetFormat(Enum):
    CXXML = auto()
    """CodeX XML"""


class AssetVersion(Enum):
    DEFAULT = auto()


class AssetTarget(NamedTuple):
    format: AssetFormat
    version: AssetVersion

    @staticmethod
    def all() -> "Sequence[AssetTarget]":
        return (AssetTarget(AssetFormat.CXXML, AssetVersion.DEFAULT),)


@dataclass(slots=True)
class SaveOptions:
    tool_metadata: tuple[str, str] | None = None


@cache
def get_providers() -> dict[AssetTarget, AssetProvider]:
    from . import cxxml

    providers = ()
    if cxxml.IS_BACKEND_AVAILABLE:
        providers += (cxxml.CXProvider,)

    return {AssetTarget(cls.ASSET_FORMAT, cls.ASSET_VERSION): cls() for cls in providers}


def is_provider_available(target_or_format: AssetTarget | AssetFormat) -> bool:
    target = (
        target_or_format
        if isinstance(target_or_format, AssetTarget)
        else AssetTarget(target_or_format, AssetVersion.DEFAULT)
    )
    return target in get_providers()


@overload
def try_load_asset(path: Path, *, return_target: Literal[False] = ...) -> Asset | None: ...
@overload
def try_load_asset(path: Path, *, return_target: Literal[True]) -> tuple[Asset, AssetTarget] | None: ...


def try_load_asset(path: Path, *, return_target: bool = False) -> Asset | tuple[Asset, AssetTarget] | None:
    for t, p in get_providers().items():
        if p.supports_file(path):
            asset = p.load_file(path)
            return (asset, t) if return_target else asset

    return None


def save_asset(
    asset: Asset,
    targets: Sequence[AssetTarget],
    directory: Path,
    name: str,
    options: SaveOptions | None = None,
):
    providers = get_providers()

    for t in targets:
        if provider := providers.get(t, None):
            provider.save_asset(asset, directory, name, options.tool_metadata if options else None)
        else:
            raise ValueError(f"Unsupported target '{t}'")
