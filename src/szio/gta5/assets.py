from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum, auto
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Literal, NamedTuple, Protocol, overload, runtime_checkable

from ..assets import AssetGame

if TYPE_CHECKING:
    from .archetypes import AssetMapTypes
    from .bounds import AssetBound, BoundType
    from .cloths import AssetClothDictionary
    from .drawables import AssetDrawable, AssetDrawableDictionary, AssetFragDrawable
    from .fragments import AssetFragment


class AssetFormat(Enum):
    NATIVE = auto()
    """Binary resource"""

    CWXML = auto()
    """CodeWalker XML"""


class AssetVersion(Enum):
    GEN8 = auto()
    """Legacy"""

    GEN9 = auto()
    """Enhanced"""


class AssetTarget(NamedTuple):
    format: AssetFormat
    version: AssetVersion

    @staticmethod
    def all() -> "Sequence[AssetTarget]":
        return (
            AssetTarget(AssetFormat.NATIVE, AssetVersion.GEN8),
            AssetTarget(AssetFormat.NATIVE, AssetVersion.GEN9),
            AssetTarget(AssetFormat.CWXML, AssetVersion.GEN8),
            AssetTarget(AssetFormat.CWXML, AssetVersion.GEN9),
        )


class AssetType(Enum):
    BOUND = auto()
    DRAWABLE = auto()
    DRAWABLE_DICTIONARY = auto()
    FRAGMENT = auto()
    CLOTH_DICTIONARY = auto()
    MAP_TYPES = auto()


@dataclass(slots=True)
class SaveOptions:
    gen8_directory: Path | None = None
    gen9_directory: Path | None = None


@runtime_checkable
class Asset(Protocol):
    ASSET_GAME: AssetGame
    ASSET_TYPE: AssetType


class AssetWithDependencies(NamedTuple):
    name: str
    main_asset: Asset
    dependencies: dict[str, Asset]


@runtime_checkable
class AssetProvider(Protocol):
    ASSET_GAME: AssetGame
    ASSET_FORMAT: AssetFormat
    ASSET_VERSION: AssetVersion

    def supports_file(self, path: Path) -> bool: ...

    def load_file(self, path: Path) -> Asset: ...

    def create_asset_bound(self, bound_type: "BoundType") -> "AssetBound": ...

    @overload
    def create_asset_drawable(
        self, is_frag: Literal[True], parent_drawable: "AssetDrawable | None" = None
    ) -> "AssetFragDrawable": ...

    @overload
    def create_asset_drawable(
        self, is_frag: bool = ..., parent_drawable: "AssetDrawable | None" = None
    ) -> "AssetDrawable": ...

    def create_asset_drawable(
        self, is_frag: bool = False, parent_drawable: "AssetDrawable | None" = None
    ) -> "AssetDrawable": ...

    def create_asset_drawable_dictionary(self) -> "AssetDrawableDictionary": ...

    def create_asset_fragment(self) -> "AssetFragment": ...

    def create_asset_cloth_dictionary(self) -> "AssetClothDictionary": ...

    def create_asset_map_types(self) -> "AssetMapTypes": ...

    def save_asset(self, asset: Asset, directory: Path, name: str, tool_metadata: tuple[str, str] | None = None): ...


@cache
def get_providers() -> dict[AssetTarget, AssetProvider]:
    from . import cwxml, native

    providers = ()
    if native.IS_BACKEND_AVAILABLE:
        providers += (native.NativeProviderG8, native.NativeProviderG9)
    if cwxml.IS_BACKEND_AVAILABLE:
        providers += (cwxml.CWProviderG8, cwxml.CWProviderG9)

    return {AssetTarget(cls.ASSET_FORMAT, cls.ASSET_VERSION): cls() for cls in providers}


def is_provider_available(target_or_format: AssetTarget | AssetFormat) -> bool:
    target = (
        target_or_format
        if isinstance(target_or_format, AssetTarget)
        else AssetTarget(target_or_format, AssetVersion.GEN8)
    )
    return target in get_providers()


def try_load_asset(path: Path) -> Asset | None:
    for p in get_providers().values():
        if p.supports_file(path):
            return p.load_file(path)

    return None


def create_asset_bound(targets: Sequence[AssetTarget], bound_type: "BoundType") -> "AssetBound":
    from .bounds import AssetBound as AssetBoundCls

    return AssetBoundCls(bound_type=bound_type)


@overload
def create_asset_drawable(
    targets: Sequence[AssetTarget], is_frag: Literal[True], parent_drawable: "AssetDrawable | None" = None
) -> "AssetFragDrawable": ...


@overload
def create_asset_drawable(
    targets: Sequence[AssetTarget], is_frag: bool = ..., parent_drawable: "AssetDrawable | None" = None
) -> "AssetDrawable": ...


def create_asset_drawable(
    targets: Sequence[AssetTarget], is_frag: bool = False, parent_drawable: "AssetDrawable | None" = None
) -> "AssetDrawable":
    if is_frag:
        from .drawables import AssetFragDrawable as AssetFragDrawableCls

        return AssetFragDrawableCls()

    from .drawables import AssetDrawable as AssetDrawableCls

    return AssetDrawableCls()


def create_asset_drawable_dictionary(targets: Sequence[AssetTarget]) -> "AssetDrawableDictionary":
    from .drawables import AssetDrawableDictionary as AssetDrawableDictionaryCls

    return AssetDrawableDictionaryCls()


def create_asset_fragment(targets: Sequence[AssetTarget]) -> "AssetFragment":
    from .fragments import AssetFragment as AssetFragmentCls

    return AssetFragmentCls()


def create_asset_cloth_dictionary(targets: Sequence[AssetTarget]) -> "AssetClothDictionary":
    from .cloths import AssetClothDictionary as AssetClothDictionaryCls

    return AssetClothDictionaryCls()


def create_asset_map_types(targets: Sequence[AssetTarget]) -> "AssetMapTypes":
    from .archetypes import AssetMapTypes as AssetMapTypesCls

    return AssetMapTypesCls()


def save_asset(
    asset: Asset,
    directory: Path,
    name: str,
    tool_metadata: tuple[str, str] | None = None,
    options: SaveOptions | None = None,
    targets: Sequence[AssetTarget] = (),
):
    providers = get_providers()
    asset_directories = {t.version: directory for t in targets}
    versions = {t.version for t in targets}
    if AssetVersion.GEN8 in versions and AssetVersion.GEN9 in versions:
        gen8_directory = (options.gen8_directory if options else None) or (directory / "gen8")
        gen9_directory = (options.gen9_directory if options else None) or (directory / "gen9")
        gen8_directory.mkdir(exist_ok=True)
        gen9_directory.mkdir(exist_ok=True)
        asset_directories[AssetVersion.GEN8] = gen8_directory
        asset_directories[AssetVersion.GEN9] = gen9_directory

    for t in targets:
        if provider := providers.get(t, None):
            provider.save_asset(asset, asset_directories[t.version], name, tool_metadata)
        else:
            raise ValueError(f"Unsupported target '{t}'")
