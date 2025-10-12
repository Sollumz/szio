""""""

import importlib.util

__all__ = ["IS_BACKEND_AVAILABLE", "NativeProviderG8", "NativeProviderG9"]

IS_BACKEND_AVAILABLE = importlib.util.find_spec("pymateria") is not None

if IS_BACKEND_AVAILABLE:
    from .hash_resolver import NativeHashResolver
    from .provider_gen8 import NativeProviderG8
    from .provider_gen9 import NativeProviderG9

else:

    def _raise_missing():
        raise ImportError(
            "Native backend not available. Please ensure PyMateria is installed.\n"
            "  Install it with:\n"
            "    pip install szio[native]\n"
            "  or install PyMateria directly:\n"
            "    pip install pymateria\n"
        )

    class _UnavailableProxy:
        def __call__(self, *args, **kwargs):
            _raise_missing()

        def __getattribute__(self, *args, **kwargs):
            _raise_missing()

    NativeProviderG8 = _UnavailableProxy()
    NativeProviderG9 = _UnavailableProxy()
    NativeHashResolver = _UnavailableProxy()
