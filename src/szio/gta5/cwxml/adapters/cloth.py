import numpy as np

from ....types import Vector
from ... import jenkhash
from ...assets import (
    AssetFormat,
    AssetType,
    AssetVersion,
    canonical_asset,
)
from ...cloths import (
    CharacterCloth,
    CharacterClothBinding,
    CharacterClothController,
    ClothBridgeSimGfx,
    ClothController,
    VerletCloth,
    VerletClothEdge,
)
from .. import cloth as cw
from ._utils import apply_target
from .bound import (
    CWBound,
)


def from_cw_verlet_cloth_edge(e: cw.VerletClothEdge) -> VerletClothEdge:
    return VerletClothEdge(
        vertex0=e.vertex0,
        vertex1=e.vertex1,
        length_sqr=e.length_sqr,
        weight0=e.weight0,
        compression_weight=e.compression_weight,
    )


def from_cw_verlet_cloth(c: cw.VerletCloth, parent_asset) -> VerletCloth:
    return VerletCloth(
        bb_min=c.bb_min,
        bb_max=c.bb_max,
        vertex_positions=c.vertex_positions,
        vertex_normals=c.vertex_normals,
        pinned_vertices_count=c.pinned_vertices_count,
        switch_distance_up=c.switch_distance_up,
        switch_distance_down=c.switch_distance_down,
        cloth_weight=c.cloth_weight,
        edges=[from_cw_verlet_cloth_edge(e) for e in c.edges],
        custom_edges=[from_cw_verlet_cloth_edge(e) for e in c.custom_edges],
        flags=c.flags,
        bounds=apply_target(parent_asset, CWBound(c.bounds)) if c.bounds is not None else None,
    )


def from_cw_bridge(b: cw.ClothBridgeSimGfx) -> ClothBridgeSimGfx:
    return ClothBridgeSimGfx(
        vertex_count_high=b.vertex_count_high,
        pin_radius_high=b.pin_radius_high,
        vertex_weights_high=b.vertex_weights_high,
        inflation_scale_high=b.inflation_scale_high,
        display_map_high=b.display_map_high,
    )


def from_cw_controller(c: cw.ClothController, parent_asset) -> ClothController:
    return ClothController(
        name=c.name,
        flags=c.flags,
        bridge=from_cw_bridge(c.bridge),
        cloth_high=from_cw_verlet_cloth(c.cloth_high, parent_asset),
        morph_high_poly_count=c.morph_controller.map_data_high.poly_count,
    )


def from_cw_char_controller(c: cw.CharacterClothController, parent_asset) -> CharacterClothController:
    return CharacterClothController(
        name=c.name,
        flags=c.flags,
        bridge=from_cw_bridge(c.bridge),
        cloth_high=from_cw_verlet_cloth(c.cloth_high, parent_asset),
        morph_high_poly_count=mc.map_data_high.poly_count if (mc := c.morph_controller) and mc.map_data_high else None,
        pin_radius_scale=c.pin_radius_scale,
        pin_radius_threshold=c.pin_radius_threshold,
        wind_scale=c.wind_scale,
        vertices=c.vertices,
        indices=c.indices,
        bone_ids=c.bone_ids,
        bone_indices=c.bone_indices,
        bindings=[CharacterClothBinding(tuple(b.weights), b.indices) for b in c.bindings],
    )


def to_cw_verlet_cloth_edge(edge: VerletClothEdge) -> cw.VerletClothEdge:
    e = cw.VerletClothEdge()
    e.vertex0 = edge.vertex0
    e.vertex1 = edge.vertex1
    e.length_sqr = edge.length_sqr
    e.weight0 = edge.weight0
    e.compression_weight = edge.compression_weight
    return e


def to_cw_verlet_cloth(cloth: VerletCloth, parent_asset) -> cw.VerletCloth:
    c = cw.VerletCloth("VerletCloth1")
    c.bb_min = cloth.bb_min
    c.bb_max = cloth.bb_max
    c.vertex_positions = cloth.vertex_positions if cloth.vertex_positions else None
    c.vertex_normals = cloth.vertex_normals if cloth.vertex_normals else None
    c.pinned_vertices_count = cloth.pinned_vertices_count
    c.cloth_weight = cloth.cloth_weight
    c.switch_distance_up = cloth.switch_distance_up
    c.switch_distance_down = cloth.switch_distance_down
    c.edges = [to_cw_verlet_cloth_edge(e) for e in cloth.edges]
    c.custom_edges = [to_cw_verlet_cloth_edge(e) for e in cloth.custom_edges]
    c.flags = cloth.flags
    c.bounds = canonical_asset(cloth.bounds, CWBound, parent_asset)._inner if cloth.bounds else None
    c.dynamic_pin_list_size = (len(cloth.vertex_positions) + 31) // 32
    return c


def to_cw_bridge(bridge: ClothBridgeSimGfx) -> cw.ClothBridgeSimGfx:
    b = cw.ClothBridgeSimGfx()
    b.vertex_count_high = bridge.vertex_count_high
    b.pin_radius_high = bridge.pin_radius_high if bridge.pin_radius_high else None
    b.vertex_weights_high = bridge.vertex_weights_high if bridge.vertex_weights_high else None
    b.inflation_scale_high = bridge.inflation_scale_high if bridge.inflation_scale_high else None
    b.display_map_high = bridge.display_map_high if bridge.display_map_high else None
    # just need to allocate space for the pinnable list, unused
    b.pinnable_list = [0] * int(np.ceil(bridge.vertex_count_high / 32))
    # Remove elements for other LODs for now
    b.pin_radius_med = None
    b.pin_radius_low = None
    b.pin_radius_vlow = None
    b.vertex_weights_med = None
    b.vertex_weights_low = None
    b.vertex_weights_vlow = None
    b.inflation_scale_med = None
    b.inflation_scale_low = None
    b.inflation_scale_vlow = None
    b.display_map_med = None
    b.display_map_low = None
    b.display_map_vlow = None
    return b


def to_cw_morph_controller(controller: ClothController) -> cw.MorphController | None:
    if controller.morph_high_poly_count is None:
        return None

    c = cw.MorphController()
    c.map_data_high.poly_count = controller.morph_high_poly_count
    # Remove elements for other LODs for now
    c.map_data_high.morph_map_high_weights = None
    c.map_data_high.morph_map_high_vertex_index = None
    c.map_data_high.morph_map_high_index0 = None
    c.map_data_high.morph_map_high_index1 = None
    c.map_data_high.morph_map_high_index2 = None
    c.map_data_high.morph_map_med_weights = None
    c.map_data_high.morph_map_med_vertex_index = None
    c.map_data_high.morph_map_med_index0 = None
    c.map_data_high.morph_map_med_index1 = None
    c.map_data_high.morph_map_med_index2 = None
    c.map_data_high.morph_map_low_weights = None
    c.map_data_high.morph_map_low_vertex_index = None
    c.map_data_high.morph_map_low_index0 = None
    c.map_data_high.morph_map_low_index1 = None
    c.map_data_high.morph_map_low_index2 = None
    c.map_data_high.morph_map_vlow_weights = None
    c.map_data_high.morph_map_vlow_vertex_index = None
    c.map_data_high.morph_map_vlow_index0 = None
    c.map_data_high.morph_map_vlow_index1 = None
    c.map_data_high.morph_map_vlow_index2 = None
    c.map_data_high.index_map_high = None
    c.map_data_high.index_map_med = None
    c.map_data_high.index_map_low = None
    c.map_data_high.index_map_vlow = None
    c.map_data_med = None
    c.map_data_low = None
    c.map_data_vlow = None
    return c


def to_cw_controller(controller: ClothController, parent_asset, cls: type = cw.ClothController) -> cw.ClothController:
    c = cls()
    c.name = controller.name
    c.bridge = to_cw_bridge(controller.bridge)
    c.morph_controller = to_cw_morph_controller(controller)
    c.cloth_high = to_cw_verlet_cloth(controller.cloth_high, parent_asset)
    c.cloth_med = None
    c.cloth_low = None
    c.flags = controller.flags
    return c


def to_cw_char_controller(controller: CharacterClothController, parent_asset) -> cw.CharacterClothController:
    def _map_binding(binding: CharacterClothBinding) -> cw.CharacterClothBinding:
        b = cw.CharacterClothBinding()
        b.weights = Vector(binding.weights)
        b.indices = binding.indices
        return b

    c: cw.CharacterClothController = to_cw_controller(controller, parent_asset, cw.CharacterClothController)
    c.pin_radius_scale = controller.pin_radius_scale
    c.pin_radius_threshold = controller.pin_radius_threshold
    c.wind_scale = controller.wind_scale
    c.vertices = controller.vertices
    c.indices = controller.indices
    c.bone_ids = controller.bone_ids if controller.bone_ids else None
    c.bone_indices = controller.bone_indices if controller.bone_indices else None
    c.bindings = [_map_binding(b) for b in controller.bindings]
    return c


class CWClothDictionary:
    ASSET_FORMAT = AssetFormat.CWXML
    ASSET_VERSION = AssetVersion.GEN8
    ASSET_TYPE = AssetType.CLOTH_DICTIONARY

    def __init__(self, d: cw.ClothDictionary):
        self._inner = d

        self._cloths_cached = None

    @property
    def cloths(self) -> dict[str, CharacterCloth]:
        if self._cloths_cached is not None:
            return self._cloths_cached

        def _map_cloth(c: cw.CharacterCloth) -> CharacterCloth:
            return CharacterCloth(
                name=jenkhash.try_resolve_maybe_hashed_name(c.name),
                parent_matrix=c.parent_matrix,
                poses=c.poses,
                bounds_bone_ids=c.bounds_bone_ids,
                bounds_bone_indices=c.bounds_bone_indices,
                controller=from_cw_char_controller(c.controller, self),
                bounds=apply_target(self, CWBound(c.bounds)) if c.bounds else None,
            )

        cld = self._inner
        d = {jenkhash.try_resolve_maybe_hashed_name(cloth.name): _map_cloth(cloth) for cloth in cld}
        self._cloths_cached = d
        return d

    @cloths.setter
    def cloths(self, d: dict[str, CharacterCloth]):
        self._cloths_cached = d

        def _map_cloth(cloth: CharacterCloth) -> cw.CharacterCloth:
            c = cw.CharacterCloth()
            c.name = cloth.name
            c.parent_matrix = cloth.parent_matrix
            c.poses = cloth.poses
            c.bounds_bone_ids = cloth.bounds_bone_ids if cloth.bounds_bone_ids else None
            c.bounds_bone_indices = cloth.bounds_bone_indices if cloth.bounds_bone_indices else None
            c.controller = to_cw_char_controller(cloth.controller, self)
            c.bounds = canonical_asset(cloth.bounds, CWBound, self)._inner if cloth.bounds else None
            return c

        cld = self._inner
        cld.clear()
        cld.extend(_map_cloth(cloth) for cloth in d.values())
        cld.sort(key=lambda cloth: jenkhash.name_to_hash(cloth.name))
