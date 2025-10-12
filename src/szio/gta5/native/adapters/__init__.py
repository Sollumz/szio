"""Provides wrappers that implement the asset interfaces in szio.gta5 using binary resources (uses PyMateria)."""

# flake8: noqa: F401
from .archetype import (
    NativeMapTypes,
    NativeMapTypesG9,
)
from .bound import (
    NativeBound,
)
from .cloth import (
    NativeClothDictionary,
)
from .drawable import (
    NativeDrawable,
    NativeDrawableDictionary,
    NativeFragDrawable,
)
from .drawable_gen9 import (
    NativeDrawableDictionaryG9,
    NativeDrawableG9,
    NativeFragDrawableG9,
)
from .fragment import (
    NativeFragment,
)
from .fragment_gen9 import (
    NativeFragmentG9,
)
