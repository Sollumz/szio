"""Provides wrappers that implement the asset interfaces in szio.gta5 using binary resources (uses PyMateria)."""

# flake8: noqa: F401
from .archetype import (
    load_map_types_from_native,
    save_map_types_to_native_g8,
    save_map_types_to_native_g9,
)
from .bound import (
    load_bound_from_native,
    save_bound_to_native,
)
from .cloth import (
    load_cloth_dictionary_from_native,
    save_cloth_dictionary_to_native,
)
from .drawable import (
    load_drawable_dictionary_from_native_g8,
    load_drawable_from_native_g8,
    load_frag_drawable_from_native_g8,
    save_drawable_dictionary_to_native_g8,
    save_drawable_to_native_g8,
    save_frag_drawable_to_native_g8,
)
from .drawable_gen9 import (
    load_drawable_dictionary_from_native_g9,
    load_drawable_from_native_g9,
    load_frag_drawable_from_native_g9,
    save_drawable_dictionary_to_native_g9,
    save_drawable_to_native_g9,
    save_frag_drawable_to_native_g9,
)
from .fragment import (
    generate_vehicle_windows,
    load_fragment_from_native_g8,
    save_fragment_to_native_g8,
)
from .fragment_gen9 import (
    load_fragment_from_native_g9,
    save_fragment_to_native_g9,
)
