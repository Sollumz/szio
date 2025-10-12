import pymateria.gta5 as pm


class NativeHashResolver:
    def __init__(self):
        self._instance = pm.HashResolver.instance

    def load_cache(self, path):
        pass

    def save_cache(self, path):
        pass

    def load_nametable(self, nt: str):
        self._instance.load_nametable(nt)

    def resolve_string(self, hash_value: int) -> str | None:
        return self._instance.resolve_string(hash_value)
