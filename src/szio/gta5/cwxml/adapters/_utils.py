def apply_target(parent_asset, asset):
    asset.ASSET_FORMAT = parent_asset.ASSET_FORMAT
    asset.ASSET_VERSION = parent_asset.ASSET_VERSION
    return asset
