import math

import numpy as np
import pymateria as pma
import pymateria.gta5 as pm

from ....types import Vector
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
from ._utils import (
    _h2s,
    _s2h,
    apply_target,
    from_native_mat34,
    s2hs,
    to_native_mat34,
    to_native_vec3,
)
from .bound import (
    NativeBound,
)


def from_native_verlet_cloth_edge(e: pm.EdgeData) -> VerletClothEdge:
    return VerletClothEdge(
        vertex0=e.vert_index1,
        vertex1=e.vert_index2,
        length_sqr=e.edge_length,  # already squared
        weight0=e.weight,
        compression_weight=e.compression_weight,
    )


def from_native_verlet_cloth(c: pm.VerletCloth, parent_asset) -> VerletCloth:
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
        bounds=apply_target(parent_asset, NativeBound(c.custom_bound)) if c.custom_bound else None,
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


def from_native_controller(c: pm.ClothController, parent_asset) -> ClothController:
    return ClothController(
        name=_h2s(c.name),
        flags=c.flags,
        bridge=from_native_bridge(c.bridge_sim_gfx),
        cloth_high=from_native_verlet_cloth(c.cloth[0], parent_asset),
        morph_high_poly_count=c.morph_controller.map_data[0].count if c.morph_controller else None,
    )


def from_native_char_controller(c: pm.CharacterClothController, parent_asset) -> CharacterClothController:
    return CharacterClothController(
        name=_h2s(c.name),
        flags=c.flags,
        bridge=from_native_bridge(c.bridge_sim_gfx),
        cloth_high=from_native_verlet_cloth(c.cloth[0], parent_asset),
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


def to_native_verlet_cloth_edge(edge: VerletClothEdge) -> pm.EdgeData:
    e = pm.EdgeData()
    e.vert_index1 = edge.vertex0
    e.vert_index2 = edge.vertex1
    e.edge_length = edge.length_sqr
    e.weight = edge.weight0
    e.compression_weight = edge.compression_weight
    return e


def to_native_verlet_cloth(cloth: VerletCloth, parent_asset) -> pm.VerletCloth:
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
    c.custom_bound = canonical_asset(cloth.bounds, NativeBound, parent_asset)._inner if cloth.bounds else None
    return c


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


def to_native_controller(
    controller: ClothController, parent_asset, cls: type = pm.ClothController
) -> pm.ClothController:
    c = cls()
    c.name = _s2h(controller.name)
    c.bridge_sim_gfx = to_native_bridge(controller.bridge)
    c.morph_controller = to_native_morph_controller(controller)
    c.cloth = [to_native_verlet_cloth(controller.cloth_high, parent_asset)]
    c.flags = controller.flags
    return c


def to_native_char_controller(controller: CharacterClothController, parent_asset) -> pm.CharacterClothController:
    c: pm.CharacterClothController = to_native_controller(controller, parent_asset, pm.CharacterClothController)
    c.pinning_radius_scale = controller.pin_radius_scale
    c.pin_radius_threshold = controller.pin_radius_threshold
    c.wind_scale = controller.wind_scale
    c.position = [to_native_vec3(v).to_vector4(math.nan) for v in controller.vertices]
    c.indices = controller.indices
    c.bone_id = controller.bone_ids
    c.bone_index = controller.bone_indices
    c.binding_info = [pm.BindingInfo(pma.Vector4f(b.weights), b.indices) for b in controller.bindings]
    return c


class NativeClothDictionary:
    ASSET_FORMAT = AssetFormat.NATIVE
    ASSET_VERSION = AssetVersion.GEN8
    ASSET_TYPE = AssetType.CLOTH_DICTIONARY

    def __init__(self, d: pm.ClothDictionary):
        self._inner = d

        self._cloths_cached = None

    @property
    def cloths(self) -> dict[str, CharacterCloth]:
        if self._cloths_cached is not None:
            return self._cloths_cached

        def _map_cloth(c: pm.CharacterCloth, name: str) -> CharacterCloth:
            return CharacterCloth(
                name=name,
                parent_matrix=from_native_mat34(c.parent_matrix),
                poses=[Vector(v) for v in c.poses],
                bounds_bone_ids=c.bone_id,
                bounds_bone_indices=c.bone_index,
                controller=from_native_char_controller(c.controller, self),
                bounds=apply_target(self, NativeBound(c.composite_bounds)) if c.composite_bounds else None,
            )

        d = {(name := _h2s(key)): _map_cloth(cloth, name) for key, cloth in self._inner.cloths.items()}
        self._cloths_cached = d
        return d

    @cloths.setter
    def cloths(self, d: dict[str, CharacterCloth]):
        self._cloths_cached = d

        def _map_cloth(cloth: CharacterCloth) -> pm.CharacterCloth:
            c = pm.CharacterCloth()
            c.parent_matrix = to_native_mat34(cloth.parent_matrix)
            c.poses = [to_native_vec3(v) for v in cloth.poses]
            c.bone_id = cloth.bounds_bone_ids
            c.bone_index = cloth.bounds_bone_indices
            c.controller = to_native_char_controller(cloth.controller, self)
            c.composite_bounds = canonical_asset(cloth.bounds, NativeBound, self)._inner if cloth.bounds else None
            return c

        self._inner.cloths = {s2hs(name): _map_cloth(cloth) for name, cloth in d.items()}
