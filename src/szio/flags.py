import sys


class FlagIterCompat:
    """Mixin, listed before `Flag`/`IntFlag`, that backports 3.11's iteration over a flag's single-bit members."""

    if sys.version_info < (3, 11):

        def __iter__(self):
            for flag in type(self):
                value = flag.value
                if value and not value & (value - 1) and flag in self:
                    yield flag
