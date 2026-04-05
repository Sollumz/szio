import pymateria.gta5.gen9 as pmg9

from ...fragments import AssetFragment
from .drawable_gen9 import (
    load_frag_drawable_from_native_g9,
    save_frag_drawable_to_native_g9,
)
from .fragment import (
    _load_fragment_from_native,
    _save_fragment_to_native,
)


def _create_glass_fvf_g9():
    C = pmg9.FvfChannel
    F = pmg9.BufferFormat
    fvf = pmg9.Fvf()
    fvf.vertex_data_size = 44
    fvf.enable_channel(C.POSITION0, 0, 44, F.R32G32B32_FLOAT)
    fvf.enable_channel(C.NORMAL0, 12, 44, F.R32G32B32_FLOAT)
    fvf.enable_channel(C.COLOR0, 24, 44, F.R8G8B8A8_UNORM)
    fvf.enable_channel(C.TEXCOORD0, 28, 44, F.R32G32_FLOAT)
    fvf.enable_channel(C.TEXCOORD1, 36, 44, F.R32G32_FLOAT)
    return fvf


def load_fragment_from_native_g9(f: pmg9.Fragment) -> AssetFragment:
    """Convert a native gen9 Fragment to an AssetFragment dataclass."""
    return _load_fragment_from_native(f, load_frag_drawable=load_frag_drawable_from_native_g9)


def save_fragment_to_native_g9(asset: AssetFragment) -> pmg9.Fragment:
    """Convert an AssetFragment dataclass to a native gen9 Fragment."""
    return _save_fragment_to_native(
        asset,
        gen=pmg9,
        save_frag_drawable=save_frag_drawable_to_native_g9,
        create_glass_fvf=_create_glass_fvf_g9,
    )
