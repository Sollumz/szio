from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

import numpy as np

from ..types import Matrix, Vector
from .assets import Asset, AssetType
from .bounds import AssetBound
from .cloths import ClothController
from .drawables import AssetDrawable, Light


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
    drawable: AssetDrawable | None
    damaged_drawable: AssetDrawable | None
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
    drawable: AssetDrawable | None
    controller: ClothController
    tuning: EnvClothTuning | None
    user_data: list[int]
    flags: int


@dataclass(slots=True)
class MatrixSet:
    is_skinned: bool
    matrices: list[Matrix]


@runtime_checkable
class AssetFragment(Asset, Protocol):
    ASSET_TYPE = AssetType.FRAGMENT

    @property
    def name(self) -> str: ...

    @name.setter
    def name(self, v: str): ...

    @property
    def flags(self) -> int: ...

    @flags.setter
    def flags(self, v: int): ...

    @property
    def drawable(self) -> AssetDrawable | None: ...

    @drawable.setter
    def drawable(self, v: AssetDrawable | None): ...

    @property
    def extra_drawables(self) -> list[AssetDrawable]: ...

    @extra_drawables.setter
    def extra_drawables(self, v: list[AssetDrawable]): ...

    @property
    def matrix_set(self) -> MatrixSet | None: ...

    @matrix_set.setter
    def matrix_set(self, v: MatrixSet | None): ...

    @property
    def physics(self) -> PhysLodGroup | None: ...

    @physics.setter
    def physics(self, v: PhysLodGroup | None): ...

    @property
    def template_asset(self) -> FragmentTemplateAsset: ...

    @template_asset.setter
    def template_asset(self, v: FragmentTemplateAsset): ...

    @property
    def unbroken_elasticity(self) -> float: ...

    @unbroken_elasticity.setter
    def unbroken_elasticity(self, v: float): ...

    @property
    def gravity_factor(self) -> float: ...

    @gravity_factor.setter
    def gravity_factor(self, v: float): ...

    @property
    def buoyancy_factor(self) -> float: ...

    @buoyancy_factor.setter
    def buoyancy_factor(self, v: float): ...

    @property
    def glass_windows(self) -> list[FragGlassWindow]: ...

    @glass_windows.setter
    def glass_windows(self, v: list[FragGlassWindow]): ...

    @property
    def vehicle_windows(self) -> list[FragVehicleWindow]: ...

    @vehicle_windows.setter
    def vehicle_windows(self, v: list[FragVehicleWindow]): ...

    @property
    def cloths(self) -> list[EnvCloth]: ...

    @cloths.setter
    def cloths(self, v: list[EnvCloth]): ...

    @property
    def lights(self) -> list[Light]: ...

    @lights.setter
    def lights(self, v: list[Light]): ...

    @property
    def base_drawable(self) -> AssetDrawable:
        """Get the drawable containing the shader group and skeleton of this fragment. This is only different from the
        main ``AssetFragment.drawable`` on fragments that only have a environment cloth drawable, and no main drawable.
        """
        ...

    def generate_vehicle_windows(self) -> list[FragVehicleWindow]: ...
