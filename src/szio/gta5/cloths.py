from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ..types import Matrix, Vector
from .assets import Asset, AssetType
from .bounds import AssetBound


@dataclass(slots=True)
class VerletClothEdge:
    vertex0: int
    vertex1: int
    length_sqr: float
    weight0: float
    compression_weight: float


@dataclass(slots=True)
class VerletCloth:
    bb_min: Vector
    bb_max: Vector
    vertex_positions: list[Vector]
    vertex_normals: list[Vector]
    pinned_vertices_count: int
    cloth_weight: float
    switch_distance_up: float
    switch_distance_down: float
    edges: list[VerletClothEdge]
    custom_edges: list[VerletClothEdge]
    flags: int
    bounds: AssetBound | None


@dataclass(slots=True)
class ClothBridgeSimGfx:
    vertex_count_high: int
    pin_radius_high: list[float]
    vertex_weights_high: list[float]
    inflation_scale_high: list[float]
    display_map_high: list[int]
    # We don't support other cloth LODs for now


@dataclass(slots=True)
class ClothController:
    name: str
    flags: int
    bridge: ClothBridgeSimGfx
    cloth_high: VerletCloth
    # We don't support other cloth LODs for now, so we only need the poly
    # count for the morph controller
    morph_high_poly_count: int | None


@dataclass(slots=True)
class CharacterClothBinding:
    weights: tuple[float, float, float, float]
    indices: tuple[int, int, int, int]


@dataclass(slots=True)
class CharacterClothController(ClothController):
    pin_radius_scale: float
    pin_radius_threshold: float
    wind_scale: float
    vertices: list[Vector]
    indices: list[int]
    bone_ids: list[int]
    bone_indices: list[int]
    bindings: list[CharacterClothBinding]


@dataclass(slots=True)
class CharacterCloth:
    name: str
    parent_matrix: Matrix
    poses: list[Vector]
    bounds_bone_ids: list[int]
    bounds_bone_indices: list[int]
    controller: CharacterClothController
    bounds: AssetBound | None


@runtime_checkable
class AssetClothDictionary(Asset, Protocol):
    ASSET_TYPE = AssetType.CLOTH_DICTIONARY

    @property
    def cloths(self) -> dict[str, CharacterCloth]: ...

    @cloths.setter
    def cloths(self, v: dict[str, CharacterCloth]): ...
