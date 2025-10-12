from collections.abc import Sequence
from enum import Enum, auto
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, NamedTuple, Protocol, TypeVar, runtime_checkable

if TYPE_CHECKING:
    from .archetypes import AssetMapTypes
    from .bounds import AssetBound, BoundType
    from .cloths import AssetClothDictionary
    from .drawables import AssetDrawable, AssetDrawableDictionary
    from .fragments import AssetFragment


class AssetFormat(Enum):
    NATIVE = auto()
    """Binary resource"""

    CWXML = auto()
    """CodeWalker XML"""

    MULTI_TARGET = auto()


class AssetVersion(Enum):
    GEN8 = auto()
    """Legacy"""

    GEN9 = auto()
    """Enhanced"""

    MULTI_TARGET = auto()


class AssetTarget(NamedTuple):
    format: AssetFormat
    version: AssetVersion


class AssetType(Enum):
    BOUND = auto()
    DRAWABLE = auto()
    DRAWABLE_DICTIONARY = auto()
    FRAGMENT = auto()
    CLOTH_DICTIONARY = auto()
    MAP_TYPES = auto()


@runtime_checkable
class Asset(Protocol):
    ASSET_FORMAT: AssetFormat
    ASSET_VERSION: AssetVersion
    ASSET_TYPE: AssetType


class AssetWithDependencies(NamedTuple):
    name: str
    main_asset: Asset
    dependencies: dict[str, Asset]


@runtime_checkable
class AssetProvider(Protocol):
    ASSET_FORMAT: AssetFormat
    ASSET_VERSION: AssetVersion

    def supports_file(self, path: Path) -> bool: ...

    def load_file(self, path: Path) -> Asset: ...

    def create_asset_bound(self, bound_type: "BoundType") -> "AssetBound": ...

    def create_asset_drawable(
        self, is_frag: bool = False, parent_drawable: "AssetDrawable | None" = None
    ) -> "AssetDrawable": ...

    def create_asset_drawable_dictionary(self) -> "AssetDrawableDictionary": ...

    def create_asset_fragment(self) -> "AssetFragment": ...

    def create_asset_cloth_dictionary(self) -> "AssetClothDictionary": ...

    def create_asset_map_types(self) -> "AssetMapTypes": ...

    def save_asset(self, asset: Asset, directory: Path, name: str, tool_metadata: tuple[str, str] | None = None): ...


class MultiAssetProxy:
    ASSET_FORMAT = AssetFormat.MULTI_TARGET
    ASSET_VERSION = AssetVersion.MULTI_TARGET

    # _ATTR_WITH_ASSET = {
    #    AssetType.DRAWABLE: {"bounds"},
    #    AssetType.FRAGMENT: {"drawable"},
    # }
    _ATTR_WITH_ASSET_LIST = {
        AssetType.BOUND: {"children"},
        # AssetType.FRAGMENT: {"extra_drawables"},
    }

    _assets: Sequence[Asset]
    # _attr_with_asset: list[set[str]]
    _attr_with_asset_list: list[set[str]]

    def __init__(self, assets: Sequence[Asset]):
        assets = tuple(assets)
        if not assets:
            raise ValueError("At least one asset is required!")
        asset_type = assets[0].ASSET_TYPE
        if any(asset.ASSET_TYPE != asset_type for asset in assets):
            raise ValueError("All assets must be of the same type!")

        self._assets = assets
        print(f"{self._assets=}")
        # self._attr_with_asset = MultiAssetProxy._ATTR_WITH_ASSET.get(asset_type, {})
        self._attr_with_asset_list = MultiAssetProxy._ATTR_WITH_ASSET_LIST.get(asset_type, {})

    def __getattr__(self, name: str) -> Any:
        # For now, we only need this special handling for bound composite children as we need to modify and sort the
        # children after they are created for exporting fragments.
        # Might be better to keep the original MultiAssetProxy around somehow, instead of trying to recreate it here
        # again (this doesn't work well with Assets nested in non-asset classes, or wouldn't behave the same (e.g.
        # bound composites in fragment physics archetype))
        # if name in self._attr_with_asset:
        #    # This attribute returns an asset, need to return a MultiAssetProxy
        #    return MultiAssetProxy(getattr(a, name) for a in self._assets)
        if name in self._attr_with_asset_list:
            # This attribute returns a list of assets, need to return a list of MultiAssetProxy
            all_asset_lists = []
            for a in self._assets:
                asset_list = getattr(a, name)
                assert not all_asset_lists or len(asset_list) == len(all_asset_lists[0])
                all_asset_lists.append(asset_list)
            return [
                None if any(a is None for a in asset_tuple) else MultiAssetProxy(asset_tuple)
                for asset_tuple in zip(*all_asset_lists)
            ]
        else:
            # Regular attribute, just return the value of the first asset. If everything is working correctly
            # all assets should have the same value.
            return getattr(self._assets[0], name)

    def __setattr__(self, name: str, value: Any):
        if name == "_assets" or name == "_attr_with_asset" or name == "_attr_with_asset_list":
            super().__setattr__(name, value)
        else:
            for asset in self._assets:
                # assert hasattr(asset, name), f"{type(asset)} does not have attribute '{name}'"
                setattr(asset, name, value)

    def with_format(self, asset_format: AssetFormat) -> Asset | None:
        for asset in self._assets:
            if asset.ASSET_FORMAT == asset_format:
                return asset

        return None

    def with_target(self, asset_target: AssetTarget) -> Asset | None:
        for asset in self._assets:
            if asset.ASSET_FORMAT == asset_target.format and asset.ASSET_VERSION == asset_target.version:
                return asset

        return None

    def discard_targets(self, targets_to_discard: Sequence[AssetTarget]):
        self._assets = tuple(
            asset
            for asset in self._assets
            if AssetTarget(asset.ASSET_FORMAT, asset.ASSET_VERSION) not in targets_to_discard
        )

    def target_versions(self) -> set[AssetVersion]:
        return set(inner_asset.ASSET_VERSION for inner_asset in self._assets)

    def target_formats(self) -> set[AssetFormat]:
        return set(inner_asset.ASSET_FORMAT for inner_asset in self._assets)

    def targets(self) -> set[AssetTarget]:
        return set(AssetTarget(inner_asset.ASSET_FORMAT, inner_asset.ASSET_VERSION) for inner_asset in self._assets)


TAsset = TypeVar("TAsset", bound=Asset)


def canonical_asset(asset: Asset, cls: type[TAsset], parent: AssetProvider | Asset) -> TAsset:
    """Asserts that `asset` is of the expected asset type, format and version. If `asset` is a `MultiAssetProxy`, it extracts
    the asset matching the format/version of `parent`.
    """
    if isinstance(asset, MultiAssetProxy):
        asset = asset.with_target(AssetTarget(parent.ASSET_FORMAT, parent.ASSET_VERSION))

    assert asset is not None
    assert asset.ASSET_FORMAT == parent.ASSET_FORMAT
    assert asset.ASSET_VERSION == parent.ASSET_VERSION
    assert asset.ASSET_TYPE == cls.ASSET_TYPE
    assert isinstance(asset, cls)
    return asset


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


def _create_asset(targets: Sequence[AssetTarget], create_callback: Callable[[AssetProvider], TAsset]) -> TAsset:
    providers = get_providers()
    assets = []
    for t in targets:
        provider = providers.get(t, None)
        if provider:
            assets.append(create_callback(provider))
        else:
            raise ValueError(f"Unsupported target '{t}'")

    return MultiAssetProxy(assets) if len(assets) > 1 else assets[0]


def create_asset_bound(targets: Sequence[AssetTarget], bound_type: "BoundType") -> "AssetBound":
    return _create_asset(targets, lambda provider: provider.create_asset_bound(bound_type))


def create_asset_drawable(
    targets: Sequence[AssetTarget], is_frag: bool = False, parent_drawable: "AssetDrawable | None" = None
) -> "AssetDrawable":
    return _create_asset(targets, lambda provider: provider.create_asset_drawable(is_frag, parent_drawable))


def create_asset_drawable_dictionary(targets: Sequence[AssetTarget]) -> "AssetDrawableDictionary":
    return _create_asset(targets, lambda provider: provider.create_asset_drawable_dictionary())


def create_asset_fragment(targets: Sequence[AssetTarget]) -> "AssetFragment":
    return _create_asset(targets, lambda provider: provider.create_asset_fragment())


def create_asset_cloth_dictionary(targets: Sequence[AssetTarget]) -> "AssetClothDictionary":
    return _create_asset(targets, lambda provider: provider.create_asset_cloth_dictionary())


def create_asset_map_types(targets: Sequence[AssetTarget]) -> "AssetMapTypes":
    return _create_asset(targets, lambda provider: provider.create_asset_map_types())


def save_asset(
    asset: Asset,
    directory: Path,
    name: str,
    tool_metadata: tuple[str, str] | None = None,
    gen8_directory: Path | None = None,
    gen9_directory: Path | None = None,
):
    if asset.ASSET_FORMAT == AssetFormat.MULTI_TARGET:
        versions = asset.target_versions()
        asset_directories = {v: directory for v in versions}
        if AssetVersion.GEN8 in versions and AssetVersion.GEN9 in versions:
            # gen8 and gen9 use the same file extensions so if both are enabled during export we need to save them
            # to separate directories.
            gen8_directory = gen8_directory or (directory / "gen8")
            gen9_directory = gen9_directory or (directory / "gen9")
            gen8_directory.mkdir(exist_ok=True)
            gen9_directory.mkdir(exist_ok=True)
            asset_directories[AssetVersion.GEN8] = gen8_directory
            asset_directories[AssetVersion.GEN9] = gen9_directory

        for inner_asset in asset._assets:
            save_asset(inner_asset, asset_directories[inner_asset.ASSET_VERSION], name, tool_metadata)
    else:
        providers = get_providers()
        target = AssetTarget(asset.ASSET_FORMAT, asset.ASSET_VERSION)
        if provider := providers.get(target, None):
            provider.save_asset(asset, directory, name, tool_metadata)
        else:
            raise ValueError(f"Unsupported target '{target}'")
