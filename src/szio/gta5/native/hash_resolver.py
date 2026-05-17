import pymateria.gta5 as pm


class NativeHashResolver:
    def load_cache(self, path):
        pass

    def save_cache(self, path):
        pass

    def load_nametable(self, nt: str):
        pm.HashResolver.instance.load_nametable(nt)

    def resolve_string(self, hash_value: int) -> str | None:
        return pm.HashResolver.instance.resolve_string(hash_value)
