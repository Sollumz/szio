import functools
import operator
import sys
from enum import EnumMeta, Flag

import pytest

import szio.gta5  # noqa: F401
from szio.flags import FlagIterCompat


def _single_bit_members(flag_type: type[Flag]) -> set[Flag]:
    return {f for f in flag_type.__members__.values() if f.value and not f.value & (f.value - 1)}


def _szio_flag_types() -> list[type[Flag]]:
    found = set()
    for name, module in list(sys.modules.items()):
        if not name.startswith("szio."):
            continue
        for v in vars(module).values():
            # type(v), not isinstance: without pymateria, szio.gta5.native's stand-ins raise on any attribute access.
            if issubclass(type(v), EnumMeta) and issubclass(v, Flag) and v.__module__.startswith("szio."):
                found.add(v)
    return sorted((t for t in found if _single_bit_members(t)), key=lambda t: (t.__module__, t.__qualname__))


@pytest.mark.parametrize("flag_type", _szio_flag_types(), ids=lambda t: f"{t.__module__}.{t.__qualname__}")
def test_flag_values_iterate_their_single_bit_members(flag_type):
    assert issubclass(flag_type, FlagIterCompat)
    members = _single_bit_members(flag_type)
    assert set(functools.reduce(operator.or_, members)) == members
    assert list(flag_type(0)) == []
