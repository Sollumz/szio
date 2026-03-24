from ....types import Vector
from ... import jenkhash
from ...cloths import (
    AssetClothDictionary,
    CharacterCloth,
    CharacterClothBinding,
    CharacterClothController,
    ClothBridgeSimGfx,
    ClothController,
    VerletCloth,
    VerletClothEdge,
)
from .. import cloth as cw
from .bound import (
    load_bound,
    save_bound_to_cw,
)


def from_cw_verlet_cloth_edge(e: cw.VerletClothEdge) -> VerletClothEdge:
    return VerletClothEdge(
        vertex0=e.vertex0,
        vertex1=e.vertex1,
        length_sqr=e.length_sqr,
        weight0=e.weight0,
        compression_weight=e.compression_weight,
    )


def from_cw_bridge(b: cw.ClothBridgeSimGfx) -> ClothBridgeSimGfx:
    return ClothBridgeSimGfx(
        vertex_count_high=b.vertex_count_high,
        pin_radius_high=b.pin_radius_high,
        vertex_weights_high=b.vertex_weights_high,
        inflation_scale_high=b.inflation_scale_high,
        display_map_high=b.display_map_high,
    )


def to_cw_verlet_cloth_edge(edge: VerletClothEdge) -> cw.VerletClothEdge:
    e = cw.VerletClothEdge()
    e.vertex0 = edge.vertex0
    e.vertex1 = edge.vertex1
    e.length_sqr = edge.length_sqr
    e.weight0 = edge.weight0
    e.compression_weight = edge.compression_weight
    return e


def to_cw_bridge(bridge: ClothBridgeSimGfx) -> cw.ClothBridgeSimGfx:
    b = cw.ClothBridgeSimGfx()
    b.vertex_count_high = bridge.vertex_count_high
    b.pin_radius_high = bridge.pin_radius_high if bridge.pin_radius_high else None
    b.vertex_weights_high = bridge.vertex_weights_high if bridge.vertex_weights_high else None
    b.inflation_scale_high = bridge.inflation_scale_high if bridge.inflation_scale_high else None
    b.display_map_high = bridge.display_map_high if bridge.display_map_high else None
    # just need to allocate space for the pinnable list, unused
    b.pinnable_list = [0] * ((bridge.vertex_count_high + 31) // 32)
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


# --- Standalone load/save functions ---


def _load_verlet_cloth_cw(c: cw.VerletCloth) -> VerletCloth:
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
        bounds=load_bound(c.bounds) if c.bounds is not None else None,
    )


def _load_char_controller_cw(c: cw.CharacterClothController) -> CharacterClothController:
    return CharacterClothController(
        name=c.name,
        flags=c.flags,
        bridge=from_cw_bridge(c.bridge),
        cloth_high=_load_verlet_cloth_cw(c.cloth_high),
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


def load_cloth_dictionary(d: cw.ClothDictionary) -> AssetClothDictionary:
    def _load_cloth(c: cw.CharacterCloth) -> CharacterCloth:
        return CharacterCloth(
            name=jenkhash.try_resolve_maybe_hashed_name(c.name),
            parent_matrix=c.parent_matrix,
            poses=c.poses,
            bounds_bone_ids=c.bounds_bone_ids,
            bounds_bone_indices=c.bounds_bone_indices,
            controller=_load_char_controller_cw(c.controller),
            bounds=load_bound(c.bounds) if c.bounds else None,
        )

    cloths = {jenkhash.try_resolve_maybe_hashed_name(cloth.name): _load_cloth(cloth) for cloth in d}
    return AssetClothDictionary(cloths=cloths)


def _save_verlet_cloth_cw(cloth: VerletCloth) -> cw.VerletCloth:
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
    c.bounds = save_bound_to_cw(cloth.bounds) if cloth.bounds else None
    c.dynamic_pin_list_size = (len(cloth.vertex_positions) + 31) // 32
    return c


def _save_char_controller_cw(controller: CharacterClothController) -> cw.CharacterClothController:
    c = cw.CharacterClothController()
    c.name = controller.name
    c.bridge = to_cw_bridge(controller.bridge)
    c.morph_controller = to_cw_morph_controller(controller)
    c.cloth_high = _save_verlet_cloth_cw(controller.cloth_high)
    c.cloth_med = None
    c.cloth_low = None
    c.flags = controller.flags
    c.pin_radius_scale = controller.pin_radius_scale
    c.pin_radius_threshold = controller.pin_radius_threshold
    c.wind_scale = controller.wind_scale
    c.vertices = controller.vertices
    c.indices = controller.indices
    c.bone_ids = controller.bone_ids if controller.bone_ids else None
    c.bone_indices = controller.bone_indices if controller.bone_indices else None
    c.bindings = [_map_binding_cw(b) for b in controller.bindings]
    return c


def _map_binding_cw(binding: CharacterClothBinding) -> cw.CharacterClothBinding:
    b = cw.CharacterClothBinding()
    b.weights = Vector(binding.weights)
    b.indices = binding.indices
    return b


def save_cloth_dictionary_to_cw(asset: AssetClothDictionary) -> cw.ClothDictionary:
    def _save_cloth(cloth: CharacterCloth) -> cw.CharacterCloth:
        c = cw.CharacterCloth()
        c.name = cloth.name
        c.parent_matrix = cloth.parent_matrix
        c.poses = cloth.poses
        c.bounds_bone_ids = cloth.bounds_bone_ids if cloth.bounds_bone_ids else None
        c.bounds_bone_indices = cloth.bounds_bone_indices if cloth.bounds_bone_indices else None
        c.controller = _save_char_controller_cw(cloth.controller)
        c.bounds = save_bound_to_cw(cloth.bounds) if cloth.bounds else None
        return c

    cld = cw.ClothDictionary()
    cld.extend(_save_cloth(cloth) for cloth in asset.cloths.values())
    cld.sort(key=lambda cloth: jenkhash.name_to_hash(cloth.name))
    return cld
