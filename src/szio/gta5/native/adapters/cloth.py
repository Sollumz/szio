import math

import pymateria as pma
import pymateria.gta5 as pm

from ....types import Vector
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
from ._utils import (
    _h2s,
    _s2h,
    from_native_mat34,
    s2hs,
    to_native_mat34,
    to_native_vec3,
)
from .bound import (
    load_bound,
    save_bound_to_native,
)


def from_native_verlet_cloth_edge(e: pm.EdgeData) -> VerletClothEdge:
    return VerletClothEdge(
        vertex0=e.vert_index1,
        vertex1=e.vert_index2,
        length_sqr=e.edge_length,  # already squared
        weight0=e.weight,
        compression_weight=e.compression_weight,
    )


def from_native_bridge(b: pm.ClothBridgeSimGFX) -> ClothBridgeSimGfx:
    num_verts = b.verts
    return ClothBridgeSimGfx(
        vertex_count_high=num_verts[0] if num_verts else 0,
        pin_radius_high=b.pin_radius.get(0, []),
        vertex_weights_high=b.vertex_weight.get(0, []),
        inflation_scale_high=b.inflation_scale.get(0, []),
        display_map_high=b.cloth_display_map.get(0, []),
    )


def to_native_verlet_cloth_edge(edge: VerletClothEdge) -> pm.EdgeData:
    e = pm.EdgeData()
    e.vert_index1 = edge.vertex0
    e.vert_index2 = edge.vertex1
    e.edge_length = edge.length_sqr
    e.weight = edge.weight0
    e.compression_weight = edge.compression_weight
    return e


def to_native_bridge(bridge: ClothBridgeSimGfx) -> pm.ClothBridgeSimGFX:
    b = pm.ClothBridgeSimGFX()
    b.verts = [bridge.vertex_count_high]
    b.pin_radius = {0: bridge.pin_radius_high}
    b.vertex_weight = {0: bridge.vertex_weights_high}
    b.inflation_scale = {0: bridge.inflation_scale_high}
    b.cloth_display_map = {0: bridge.display_map_high}
    b.pinnable_verts = [0] * int(np.ceil(bridge.vertex_count_high / 32))
    return b


def to_native_morph_controller(controller: ClothController) -> pm.MorphController | None:
    if controller.morph_high_poly_count is None:
        return None

    d = pm.MorphMapData()
    d.count = controller.morph_high_poly_count
    c = pm.MorphController()
    c.map_data = {0: d}
    return c


# --- Standalone load/save functions ---


def _load_verlet_cloth_native(c: pm.VerletCloth) -> VerletCloth:
    return VerletCloth(
        bb_min=Vector(c.bb_min),
        bb_max=Vector(c.bb_max),
        vertex_positions=[Vector(p) for p in c.vert_positions],
        vertex_normals=[Vector(p) for p in c.vert_normals],
        pinned_vertices_count=c.num_pinned_verts,
        cloth_weight=c.cloth_weight,
        switch_distance_up=c.switch_distance_up,
        switch_distance_down=c.switch_distance_down,
        edges=[from_native_verlet_cloth_edge(e) for e in c.edge_data],
        custom_edges=[from_native_verlet_cloth_edge(e) for e in c.custom_edge_data],
        flags=c.flags,
        bounds=load_bound(c.custom_bound) if c.custom_bound else None,
    )


def _load_char_controller_native(c: pm.CharacterClothController) -> CharacterClothController:
    return CharacterClothController(
        name=_h2s(c.name),
        flags=c.flags,
        bridge=from_native_bridge(c.bridge_sim_gfx),
        cloth_high=_load_verlet_cloth_native(c.cloth[0]),
        morph_high_poly_count=c.morph_controller.map_data[0].count if c.morph_controller else None,
        pin_radius_scale=c.pinning_radius_scale,
        pin_radius_threshold=c.pin_radius_threshold,
        wind_scale=c.wind_scale,
        vertices=[Vector(v.to_vector3()) for v in c.position],
        indices=c.indices,
        bone_ids=c.bone_id,
        bone_indices=c.bone_index,
        bindings=[CharacterClothBinding(tuple(b.weights), b.indices) for b in c.binding_info],
    )


def load_cloth_dictionary(d: pm.ClothDictionary) -> AssetClothDictionary:
    def _load_cloth(c: pm.CharacterCloth, name: str) -> CharacterCloth:
        return CharacterCloth(
            name=name,
            parent_matrix=from_native_mat34(c.parent_matrix),
            poses=[Vector(v) for v in c.poses],
            bounds_bone_ids=c.bone_id,
            bounds_bone_indices=c.bone_index,
            controller=_load_char_controller_native(c.controller),
            bounds=load_bound(c.composite_bounds) if c.composite_bounds else None,
        )

    cloths = {(name := _h2s(key)): _load_cloth(cloth, name) for key, cloth in d.cloths.items()}
    return AssetClothDictionary(cloths=cloths)


def _save_verlet_cloth_native(cloth: VerletCloth) -> pm.VerletCloth:
    c = pm.VerletCloth()
    c.niterations = 3
    c.bb_min = to_native_vec3(cloth.bb_min).to_vector4(0.0)
    c.bb_max = to_native_vec3(cloth.bb_max).to_vector4(0.0)
    c.vert_positions = [to_native_vec3(p) for p in cloth.vertex_positions]
    c.vert_normals = [to_native_vec3(p) for p in cloth.vertex_normals]
    c.num_pinned_verts = cloth.pinned_vertices_count
    c.cloth_weight = cloth.cloth_weight
    c.switch_distance_up = cloth.switch_distance_up
    c.switch_distance_down = cloth.switch_distance_down
    c.edge_data = [to_native_verlet_cloth_edge(e) for e in cloth.edges]
    c.custom_edge_data = [to_native_verlet_cloth_edge(e) for e in cloth.custom_edges]
    c.flags = cloth.flags
    c.custom_bound = save_bound_to_native(cloth.bounds) if cloth.bounds else None
    return c


def _save_char_controller_native(controller: CharacterClothController) -> pm.CharacterClothController:
    c = pm.CharacterClothController()
    c.name = _s2h(controller.name)
    c.bridge_sim_gfx = to_native_bridge(controller.bridge)
    c.morph_controller = to_native_morph_controller(controller)
    c.cloth = [_save_verlet_cloth_native(controller.cloth_high)]
    c.flags = controller.flags
    c.pinning_radius_scale = controller.pin_radius_scale
    c.pin_radius_threshold = controller.pin_radius_threshold
    c.wind_scale = controller.wind_scale
    c.position = [to_native_vec3(v).to_vector4(math.nan) for v in controller.vertices]
    c.indices = controller.indices
    c.bone_id = controller.bone_ids
    c.bone_index = controller.bone_indices
    c.binding_info = [pma.gta5.BindingInfo(pma.Vector4f(b.weights), b.indices) for b in controller.bindings]
    return c


def save_cloth_dictionary_to_native(asset: AssetClothDictionary) -> pm.ClothDictionary:
    def _save_cloth(cloth: CharacterCloth) -> pm.CharacterCloth:
        c = pm.CharacterCloth()
        c.parent_matrix = to_native_mat34(cloth.parent_matrix)
        c.poses = [to_native_vec3(v) for v in cloth.poses]
        c.bone_id = cloth.bounds_bone_ids
        c.bone_index = cloth.bounds_bone_indices
        c.controller = _save_char_controller_native(cloth.controller)
        c.composite_bounds = save_bound_to_native(cloth.bounds) if cloth.bounds else None
        return c

    d = pm.ClothDictionary()
    d.cloths = {s2hs(name): _save_cloth(cloth) for name, cloth in asset.cloths.items()}
    return d
