import hashlib
import logging
import os
import pickle
from pathlib import Path
from typing import Sequence


def hash_data(data: bytes, seed: int = 0) -> int:
    h = seed

    for b in data:
        h += b
        h &= 0xFFFFFFFF
        h += (h << 10) & 0xFFFFFFFF
        h &= 0xFFFFFFFF
        h ^= (h >> 6) & 0xFFFFFFFF
        h &= 0xFFFFFFFF

    h += (h << 3) & 0xFFFFFFFF
    h &= 0xFFFFFFFF
    h ^= (h >> 11) & 0xFFFFFFFF
    h &= 0xFFFFFFFF
    h += (h << 15) & 0xFFFFFFFF
    h &= 0xFFFFFFFF

    return h


def hash_string(text: str, encoding: str = "utf-8", seed: int = 0) -> int:
    bts = text.lower().encode(encoding)
    return hash_data(bts, seed)


def name_to_hash(name: str) -> int:
    """Gets a hash from a string. If it starts with `hash_`, it parses the hexadecimal number afterwards;
    otherwise, it calculates the JOAAT hash of the string.
    """
    if name == "":
        return 0

    if name.startswith("hash_"):
        return int(name[5:], 16) & 0xFFFFFFFF
    else:
        return hash_string(name)


def hash_to_name(hash_value: int) -> str:
    if hash_value == 0:
        return ""

    s = try_resolve_hash(hash_value)
    if s is None:
        s = f"hash_{hash_value:08X}"

    return s


class HashResolver:
    """Default hash resolver. Implements some basic caching because loading
    many nametables with just Python can take too long.
    """

    def __init__(self):
        self._dict = {}
        self._cache = None

    def _get_cache_path(self) -> Path:
        from ...sollumz_preferences import get_config_directory_path

        return Path(get_config_directory_path()) / "nametable.cache"

    def load_cache(self, path: os.PathLike):
        if self._cache is not None:
            return

        cache = Path(path)
        if not cache.is_file():
            self._cache = {}
            return

        with cache.open("rb") as f:
            self._cache = pickle.load(f)

    def save_cache(self, path: os.PathLike):
        if self._cache is None:
            return

        cache = Path(path)

        with cache.open("wb") as f:
            pickle.dump(self._cache, f, protocol=5)

    def _nametable_id(self, nt: str) -> str:
        return hashlib.md5(nt.encode("utf-8")).hexdigest()

    def _load_nametable_from_cache(self, nt_id: str) -> bool:
        self.load_cache()
        if (cache_dict := self._cache.get(nt_id, None)) is None:
            return False

        self._dict.update(cache_dict)
        return True

    def _save_nametable_to_cache(self, nt_id: str, d: dict[int, str]):
        self.load_cache()
        self._cache[nt_id] = d

    def load_nametable(self, nt: str):
        nt_id = self._nametable_id(nt)
        if self._load_nametable_from_cache(nt_id):
            return

        # Strings in .nametable are separated by null chars
        strings = nt.split("\0")
        if len(strings) <= 1:
            # If we only got one string, it is probably just plain text, separated by new lines
            strings = nt.splitlines()

        d = {}
        for s in strings:
            d[hash_string(s)] = s
        self._save_nametable_to_cache(nt_id, d)
        self._dict.update(d)

    def resolve_string(self, hash_value: int) -> str | None:
        return self._dict.get(hash_value, None)


def _get_resolver():
    inst = _get_resolver._instance
    if inst is None:
        import time

        from . import native

        t = time.time()

        if native.IS_BACKEND_AVAILABLE:
            inst = native.NativeHashResolver()
        else:
            inst = HashResolver()

        cache_path = _get_resolver._cache_path
        if cache_path is not None:
            inst.load_cache(cache_path)

        nt_paths = _get_resolver._name_table_paths
        for nt in nt_paths:
            if nt.is_file():
                inst.load_nametable(nt.read_text(encoding="utf-8"))

        if cache_path is not None:
            inst.save_cache(cache_path)

        t = time.time() - t

        logging.getLogger(__name__).info(f"Loaded {len(nt_paths)} name table(s) in {t:.3f} seconds")

        _get_resolver._instance = inst

    return inst


_get_resolver._instance = None
_get_resolver._name_table_paths = []
_get_resolver._cache_path = None


def load_name_tables(name_table_paths: Sequence[os.PathLike], cache_path: os.PathLike | None):
    # Name tables will be lazy loaded when the resolver is accessed
    _get_resolver._name_table_paths = [Path(p) for p in name_table_paths]
    _get_resolver._cache_path = Path(cache_path) if cache_path is not None else None
    _get_resolver._instance = None


def try_resolve_hash(hash_value: int) -> str | None:
    """Lookup the string matching ``hash_value``. If not found, returns `None`."""
    return _get_resolver().resolve_string(hash_value)


def try_resolve_maybe_hashed_name(name: str) -> str:
    """If ``name`` starts with `hash_`, try to resolve the hash. Otherwise, return the same input string."""
    if name.startswith("hash_"):
        return try_resolve_hash(name_to_hash(name)) or name

    return name
