"""Provides wrappers that implement the asset interfaces in szio.gta5 using CodeWalker XML."""

# flake8: noqa: F401
from .archetype import (
    load_map_types_from_cw,
    save_map_types_to_cw,
)
from .bound import (
    load_bound_from_cw,
    save_bound_to_cw,
)
from .cloth import (
    load_cloth_dictionary_from_cw,
    save_cloth_dictionary_to_cw,
)
from .drawable import (
    load_drawable_dictionary_from_cw,
    load_drawable_from_cw,
    load_frag_drawable_from_cw,
    load_txd_from_cw,
    save_drawable_dictionary_to_cw,
    save_drawable_to_cw,
    save_frag_drawable_to_cw,
    save_txd_to_cw,
)
from .fragment import (
    load_fragment_from_cw,
    save_fragment_to_cw,
)
