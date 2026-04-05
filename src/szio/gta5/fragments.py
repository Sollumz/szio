from dataclasses import dataclass, field
from enum import Enum

import numpy as np

from ..types import Matrix, Vector
from .assets import AssetGame, AssetType
from .bounds import AssetBound
from .cloths import ClothController
from .drawables import AssetFragDrawable, Light


class FragmentTemplateAsset(Enum):
    NONE = 0xFF
    FRED = 0
    WILMA = 1
    FRED_LARGE = 2
    WILMA_LARGE = 3
    ALIEN = 4


@dataclass(slots=True)
class PhysArchetype:
    name: str
    bounds: AssetBound
    gravity_factor: float
    max_speed: float
    max_ang_speed: float
    buoyancy_factor: float
    mass: float
    mass_inv: float
    inertia: Vector
    inertia_inv: Vector


@dataclass(slots=True)
class PhysChild:
    bone_tag: int
    group_index: int
    pristine_mass: float
    damaged_mass: float
    drawable: AssetFragDrawable | None
    damaged_drawable: AssetFragDrawable | None
    min_breaking_impulse: float  # TODO(io): import/export phys child min breaking impulse
    inertia: Vector
    damaged_inertia: Vector


@dataclass(slots=True)
class PhysGroup:
    name: str
    parent_group_index: int
    flags: int
    total_mass: float
    strength: float
    force_transmission_scale_up: float
    force_transmission_scale_down: float
    joint_stiffness: float
    min_soft_angle_1: float
    max_soft_angle_1: float
    max_soft_angle_2: float
    max_soft_angle_3: float
    rotation_speed: float
    rotation_strength: float
    restoring_strength: float
    restoring_max_torque: float
    latch_strength: float
    min_damage_force: float
    damage_health: float
    weapon_health: float
    weapon_scale: float
    vehicle_scale: float
    ped_scale: float
    ragdoll_scale: float
    explosion_scale: float
    object_scale: float
    ped_inv_mass_scale: float
    melee_scale: float
    glass_window_index: int


@dataclass(slots=True)
class PhysLod:
    archetype: PhysArchetype
    damaged_archetype: PhysArchetype | None
    children: list[PhysChild]
    groups: list[PhysGroup]
    smallest_ang_inertia: float
    largest_ang_inertia: float
    min_move_force: float
    root_cg_offset: Vector
    original_root_cg_offset: Vector
    unbroken_cg_offset: Vector
    damping_linear_c: Vector
    damping_linear_v: Vector
    damping_linear_v2: Vector
    damping_angular_c: Vector
    damping_angular_v: Vector
    damping_angular_v2: Vector
    link_attachments: list[Matrix]


@dataclass(slots=True)
class PhysLodGroup:
    lod1: PhysLod


@dataclass(slots=True)
class FragGlassWindow:
    glass_type: int
    shader_index: int
    pos_base: Vector
    pos_width: Vector
    pos_height: Vector
    uv_min: Vector
    uv_max: Vector
    thickness: float
    bounds_offset_front: float
    bounds_offset_back: float
    tangent: Vector


@dataclass(slots=True)
class FragVehicleWindow:
    basis: Matrix
    component_id: int
    geometry_index: int
    width: int
    height: int
    scale: float
    flags: int
    data_min: float
    data_max: float
    shattermap: np.ndarray  # 2D array of floats, shape (height, width)


@dataclass(slots=True)
class EnvClothTuning:
    flags: int
    extra_force: Vector
    weight: float
    distance_threshold: float
    rotation_rate: float
    angle_threshold: float
    pin_vert: int
    non_pin_vert0: int
    non_pin_vert1: int


@dataclass(slots=True)
class EnvCloth:
    drawable: AssetFragDrawable | None
    controller: ClothController
    tuning: EnvClothTuning | None
    user_data: list[int]
    flags: int


@dataclass(slots=True)
class MatrixSet:
    is_skinned: bool
    matrices: list[Matrix]


@dataclass(slots=True)
class AssetFragment:
    ASSET_GAME: AssetGame = AssetGame.GTA5
    ASSET_TYPE: AssetType = AssetType.FRAGMENT

    name: str = ""
    flags: int = 0
    drawable: AssetFragDrawable | None = None
    extra_drawables: list[AssetFragDrawable] = field(default_factory=list)
    matrix_set: MatrixSet | None = None
    physics: PhysLodGroup | None = None
    template_asset: FragmentTemplateAsset = FragmentTemplateAsset.NONE
    unbroken_elasticity: float = 0.0
    gravity_factor: float = 1.0
    buoyancy_factor: float = 1.0
    glass_windows: list[FragGlassWindow] = field(default_factory=list)
    vehicle_windows: list[FragVehicleWindow] = field(default_factory=list)
    cloths: list[EnvCloth] = field(default_factory=list)
    lights: list[Light] = field(default_factory=list)

    @property
    def base_drawable(self) -> AssetFragDrawable:
        """Get the drawable containing the shader group and skeleton of this fragment. This is only different from the
        main ``AssetFragment.drawable`` on fragments that only have a environment cloth drawable, and no main drawable.
        """
        if self.drawable is not None:
            return self.drawable
        for cloth in self.cloths:
            if cloth.drawable is not None:
                return cloth.drawable
        return None
