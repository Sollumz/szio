import numpy as np

from ....types import Matrix, Vector
from ...assets import (
    AssetFormat,
    AssetType,
    AssetVersion,
    canonical_asset,
)
from ...drawables import (
    Light,
)
from ...fragments import (
    EnvCloth,
    EnvClothTuning,
    FragGlassWindow,
    FragmentTemplateAsset,
    FragVehicleWindow,
    MatrixSet,
    PhysArchetype,
    PhysChild,
    PhysGroup,
    PhysLod,
    PhysLodGroup,
)
from ...shattermaps import (
    shattermap_from_ascii,
    shattermap_to_ascii,
)
from .. import cloth as cwcloth
from .. import fragment as cw
from ._utils import apply_target
from .bound import (
    CWBound,
)
from .cloth import (
    from_cw_controller,
    to_cw_controller,
)
from .drawable import (
    CWFragDrawable,
    _map_light_from_cw,
    _map_light_to_cw,
)


class CWFragment:
    ASSET_FORMAT = AssetFormat.CWXML
    ASSET_VERSION = AssetVersion.GEN8
    ASSET_TYPE = AssetType.FRAGMENT

    def __init__(self, f: cw.Fragment):
        self._inner = f

        self._physics_cached = None

    @property
    def name(self) -> str:
        return self._inner.name

    @name.setter
    def name(self, v: str):
        self._inner.name = v

    @property
    def flags(self) -> int:
        return self._inner.flags

    @flags.setter
    def flags(self, v: int):
        self._inner.flags = v

    @property
    def drawable(self) -> CWFragDrawable | None:
        return apply_target(self, CWFragDrawable(self._inner.drawable)) if self._inner.drawable else None

    @drawable.setter
    def drawable(self, v: CWFragDrawable | None):
        self._inner.drawable = d = canonical_asset(v, CWFragDrawable, self)._inner if v else None
        if d:
            self._inner.bounding_sphere_center = d.bounding_sphere_center
            self._inner.bounding_sphere_radius = d.bounding_sphere_radius
        else:
            self._inner.bounding_sphere_center = Vector((0.0, 0.0, 0.0))
            self._inner.bounding_sphere_radius = 0.0

    @property
    def extra_drawables(self) -> list[CWFragDrawable]:
        return [apply_target(self, CWFragDrawable(d)) for d in self._inner.extra_drawables]

    @extra_drawables.setter
    def extra_drawables(self, v: list[CWFragDrawable]):
        self._inner.extra_drawables = [canonical_asset(d, CWFragDrawable, self)._inner for d in v]

    @property
    def matrix_set(self) -> MatrixSet | None:
        raise NotImplementedError("matrix_set getter")

    @matrix_set.setter
    def matrix_set(self, v: MatrixSet | None):
        # need to get the underlying XML class to set 'unk', not the list
        s = self._inner.get_element("bones_transforms")
        s.unk.value = 1 if v.is_skinned else 0
        s.value = [cw.BoneTransform("Item", m) for m in v.matrices]

    @property
    def physics(self) -> PhysLodGroup | None:
        if self._physics_cached is not None:
            return self._physics_cached[0]

        def _map_archetype(a: cw.Archetype | None) -> PhysArchetype | None:
            if not a:
                return None

            return PhysArchetype(
                name=a.name,
                bounds=apply_target(self, CWBound(a.bounds)),
                gravity_factor=a.unknown_48,
                max_speed=a.unknown_4c,
                max_ang_speed=a.unknown_50,
                buoyancy_factor=a.unknown_54,
                mass=a.mass,
                mass_inv=a.mass_inv,
                inertia=Vector(a.inertia_tensor),
                inertia_inv=Vector(a.inertia_tensor_inv),
            )

        def _map_child(g: cw.PhysicsChild) -> PhysChild:
            return PhysChild(
                bone_tag=g.bone_tag,
                group_index=g.group_index,
                pristine_mass=g.pristine_mass,
                damaged_mass=g.damaged_mass,
                drawable=apply_target(self, CWFragDrawable(g.drawable)),
                damaged_drawable=apply_target(self, CWFragDrawable(g.damaged_drawable)),
                min_breaking_impulse=g.unk_float,
                inertia=Vector(g.inertia_tensor),
                damaged_inertia=Vector(g.damaged_inertia_tensor),
            )

        def _map_group(g: cw.PhysicsGroup) -> PhysGroup:
            return PhysGroup(
                name=g.name,
                parent_group_index=g.parent_index,
                flags=g.glass_flags,
                total_mass=g.mass,
                strength=g.strength,
                force_transmission_scale_up=g.force_transmission_scale_up,
                force_transmission_scale_down=g.force_transmission_scale_down,
                joint_stiffness=g.joint_stiffness,
                min_soft_angle_1=g.min_soft_angle_1,
                max_soft_angle_1=g.max_soft_angle_1,
                max_soft_angle_2=g.max_soft_angle_2,
                max_soft_angle_3=g.max_soft_angle_3,
                rotation_speed=g.rotation_speed,
                rotation_strength=g.rotation_strength,
                restoring_strength=g.restoring_strength,
                restoring_max_torque=g.restoring_max_torque,
                latch_strength=g.latch_strength,
                min_damage_force=g.min_damage_force,
                damage_health=g.damage_health,
                weapon_health=g.unk_float_5c,
                weapon_scale=g.unk_float_60,
                vehicle_scale=g.unk_float_64,
                ped_scale=g.unk_float_68,
                ragdoll_scale=g.unk_float_6c,
                explosion_scale=g.unk_float_70,
                object_scale=g.unk_float_74,
                ped_inv_mass_scale=g.unk_float_78,
                melee_scale=g.unk_float_a8,
                glass_window_index=g.glass_window_index,
            )

        def _map_lod(lod: cw.PhysicsLOD) -> PhysLod:
            return PhysLod(
                archetype=_map_archetype(lod.archetype),
                damaged_archetype=_map_archetype(lod.damaged_archetype),
                children=[_map_child(c) for c in lod.children],
                groups=[_map_group(g) for g in lod.groups],
                smallest_ang_inertia=lod.unknown_14,
                largest_ang_inertia=lod.unknown_18,
                min_move_force=lod.unknown_1c,
                root_cg_offset=Vector(lod.position_offset),
                original_root_cg_offset=Vector(lod.unknown_40),
                unbroken_cg_offset=Vector(lod.unknown_50),
                damping_linear_c=Vector(lod.damping_linear_c),
                damping_linear_v=Vector(lod.damping_linear_v),
                damping_linear_v2=Vector(lod.damping_linear_v2),
                damping_angular_c=Vector(lod.damping_angular_c),
                damping_angular_v=Vector(lod.damping_angular_v),
                damping_angular_v2=Vector(lod.damping_angular_v2),
                link_attachments=[t.value for t in lod.transforms],
            )

        p = PhysLodGroup(_map_lod(self._inner.physics.lod1))
        self._physics_cached = (p,)
        return p

    @physics.setter
    def physics(self, v: PhysLodGroup | None):
        self._physics_cached = (v,)
        if v is None:
            self._inner.physics = None
            return

        def _map_archetype(arch: PhysArchetype | None, tag: str) -> cw.Archetype | None:
            if arch is None:
                return None

            a = cw.Archetype(tag)
            a.name = arch.name
            a.bounds = canonical_asset(arch.bounds, CWBound, self)._inner
            a.unknown_48 = arch.gravity_factor
            a.unknown_4c = arch.max_speed
            a.unknown_50 = arch.max_ang_speed
            a.unknown_54 = arch.buoyancy_factor
            a.mass = arch.mass
            a.mass_inv = arch.mass_inv
            a.inertia_tensor = Vector(arch.inertia)
            a.inertia_tensor_inv = Vector(arch.inertia_inv)

            # In fragments, every bound is referenced twice:
            # - Composite: in the physLOD and the archetype
            # - Damaged composite: only in the damaged archetype, but the game still expects 2 refs (and does indeed release it
            #                      twice in the physics LOD destructor)
            # - All child bounds: in the composite and in the physics child drawable
            a.bounds.ref_count = 2
            for c in a.bounds.children:
                if c is not None:
                    c.ref_count = 2
            return a

        def _map_child(child: PhysChild) -> cw.PhysicsChild:
            c = cw.PhysicsChild()
            c.bone_tag = child.bone_tag
            c.group_index = child.group_index
            c.pristine_mass = child.pristine_mass
            c.damaged_mass = child.damaged_mass
            c.drawable = canonical_asset(child.drawable, CWFragDrawable, self)._inner
            c.drawable.tag_name = "Drawable"
            c.damaged_drawable = (
                canonical_asset(child.damaged_drawable, CWFragDrawable, self)._inner if child.damaged_drawable else None
            )
            if c.damaged_drawable:
                c.damaged_drawable.tag_name = "Drawable2"
            c.unk_float = child.min_breaking_impulse
            c.inertia_tensor = Vector(child.inertia)
            c.damaged_inertia_tensor = Vector(child.damaged_inertia)
            return c

        def _map_group(group: PhysGroup) -> cw.PhysicsGroup:
            g = cw.PhysicsGroup()
            g.name = group.name
            g.parent_index = group.parent_group_index
            g.glass_flags = group.flags
            g.mass = group.total_mass
            g.strength = group.strength
            g.force_transmission_scale_up = group.force_transmission_scale_up
            g.force_transmission_scale_down = group.force_transmission_scale_down
            g.joint_stiffness = group.joint_stiffness
            g.min_soft_angle_1 = group.min_soft_angle_1
            g.max_soft_angle_1 = group.max_soft_angle_1
            g.max_soft_angle_2 = group.max_soft_angle_2
            g.max_soft_angle_3 = group.max_soft_angle_3
            g.rotation_speed = group.rotation_speed
            g.rotation_strength = group.rotation_strength
            g.restoring_strength = group.restoring_strength
            g.restoring_max_torque = group.restoring_max_torque
            g.latch_strength = group.latch_strength
            g.min_damage_force = group.min_damage_force
            g.damage_health = group.damage_health
            g.unk_float_5c = group.weapon_health
            g.unk_float_60 = group.weapon_scale
            g.unk_float_64 = group.vehicle_scale
            g.unk_float_68 = group.ped_scale
            g.unk_float_6c = group.ragdoll_scale
            g.unk_float_70 = group.explosion_scale
            g.unk_float_74 = group.object_scale
            g.unk_float_78 = group.ped_inv_mass_scale
            g.unk_float_a8 = group.melee_scale
            g.glass_window_index = group.glass_window_index
            return g

        def _map_lod(lod: PhysLod, tag: str) -> cw.PhysicsLOD:
            l = cw.PhysicsLOD(tag)
            l.archetype = _map_archetype(lod.archetype, "Archetype")
            l.damaged_archetype = _map_archetype(lod.damaged_archetype, "Archetype2")
            l.children.extend(_map_child(c) for c in lod.children)
            l.groups.extend(_map_group(g) for g in lod.groups)
            l.unknown_14 = lod.smallest_ang_inertia
            l.unknown_18 = lod.largest_ang_inertia
            l.unknown_1c = lod.min_move_force
            l.position_offset = Vector(lod.root_cg_offset)
            l.unknown_40 = Vector(lod.original_root_cg_offset)
            l.unknown_50 = Vector(lod.unbroken_cg_offset)
            l.damping_linear_c = Vector(lod.damping_linear_c)
            l.damping_linear_v = Vector(lod.damping_linear_v)
            l.damping_linear_v2 = Vector(lod.damping_linear_v2)
            l.damping_angular_c = Vector(lod.damping_angular_c)
            l.damping_angular_v = Vector(lod.damping_angular_v)
            l.damping_angular_v2 = Vector(lod.damping_angular_v2)
            l.transforms.extend(cw.Transform("Item", a) for a in lod.link_attachments)
            return l

        p = cw.Physics()
        p.lod1 = _map_lod(v.lod1, "LOD1")
        p.lod2 = None
        p.lod3 = None
        self._inner.physics = p

    @property
    def template_asset(self) -> FragmentTemplateAsset:
        return FragmentTemplateAsset((self._inner.unknown_c0 >> 8) & 0xFF)

    @template_asset.setter
    def template_asset(self, v: FragmentTemplateAsset):
        self._inner.unknown_c0 = (v.value & 0xFF) << 8

    @property
    def unbroken_elasticity(self) -> float:
        return self._inner.unknown_cc

    @unbroken_elasticity.setter
    def unbroken_elasticity(self, v: float):
        self._inner.unknown_cc = v

    @property
    def gravity_factor(self) -> float:
        return self._inner.gravity_factor

    @gravity_factor.setter
    def gravity_factor(self, v: float):
        self._inner.gravity_factor = v

    @property
    def buoyancy_factor(self) -> float:
        return self._inner.buoyancy_factor

    @buoyancy_factor.setter
    def buoyancy_factor(self, v: float):
        self._inner.buoyancy_factor = v

    @property
    def glass_windows(self) -> list[FragGlassWindow]:
        def _map_window(g: cw.GlassWindow) -> FragGlassWindow:
            return FragGlassWindow(
                glass_type=g.flags & 0xFF,
                shader_index=(g.flags >> 8) & 0xFF,
                pos_base=Vector(g.projection_matrix[0]),
                pos_width=Vector(g.projection_matrix[1]),
                pos_height=Vector(g.projection_matrix[2]),
                uv_min=Vector((g.unk_float_13, g.unk_float_14)),
                uv_max=Vector((g.unk_float_15, g.unk_float_16)),
                thickness=g.thickness,
                bounds_offset_front=g.unk_float_18,
                bounds_offset_back=g.unk_float_19,
                tangent=Vector(g.tangent),
            )

        return [_map_window(g) for g in self._inner.glass_windows]

    @glass_windows.setter
    def glass_windows(self, v: list[FragGlassWindow]):
        def _map_window(glass: FragGlassWindow) -> cw.GlassWindow:
            g = cw.GlassWindow()
            g.layout = cw.VertexLayoutList(
                type="GTAV4", value=["Position", "Normal", "Colour0", "TexCoord0", "TexCoord1"]
            )
            g.flags = (glass.glass_type & 0xFF) | ((glass.shader_index & 0xFF) << 8)
            g.projection_matrix = Matrix((glass.pos_base, glass.pos_width, glass.pos_height))
            g.unk_float_13, g.unk_float_14 = glass.uv_min
            g.unk_float_15, g.unk_float_16 = glass.uv_max
            g.thickness = glass.thickness
            g.unk_float_18 = glass.bounds_offset_front
            g.unk_float_19 = glass.bounds_offset_back
            g.tangent = glass.tangent
            return g

        self._inner.glass_windows = [_map_window(glass) for glass in v]

    @property
    def vehicle_windows(self) -> list[FragVehicleWindow]:
        def _map_window(w: cw.Window) -> FragVehicleWindow:
            return FragVehicleWindow(
                basis=w.projection_matrix,
                component_id=w.item_id,
                geometry_index=w.unk_ushort_1,
                width=w.width // 2,
                height=w.height,
                scale=w.cracks_texture_tiling,
                flags=(w.unk_ushort_4 & 0xFFFF) | ((w.unk_ushort_5 << 16) & 0xFFFF),
                data_min=w.unk_float_17,
                data_max=w.unk_float_18,
                shattermap=shattermap_from_ascii(w.shattermap, w.width // 2, w.height),
            )

        return [_map_window(g) for g in self._inner.vehicle_glass_windows]

    @vehicle_windows.setter
    def vehicle_windows(self, windows: list[FragVehicleWindow]):
        def _map_window(window: FragVehicleWindow) -> cw.Window:
            w = cw.Window()
            w.item_id = window.component_id
            w.unk_float_17 = window.data_min
            w.unk_float_18 = window.data_max
            w.cracks_texture_tiling = window.scale
            w.unk_ushort_1 = window.geometry_index
            w.projection_matrix = window.basis
            w.shattermap = shattermap_to_ascii(window.shattermap)
            return w

        self._inner.vehicle_glass_windows = [_map_window(w) for w in windows]

    @property
    def cloths(self) -> list[EnvCloth]:
        def _map_tuning(t: cwcloth.ClothInstanceTuning | None) -> EnvClothTuning | None:
            if t is None:
                return None

            return EnvClothTuning(
                flags=t.flags,
                extra_force=Vector(t.extra_force),
                weight=t.weight,
                distance_threshold=t.distance_threshold,
                rotation_rate=t.rotation_rate,
                angle_threshold=t.angle_threshold,
                pin_vert=t.pin_vert,
                non_pin_vert0=t.non_pin_vert0,
                non_pin_vert1=t.non_pin_vert1,
            )

        def _map_cloth(c: cwcloth.EnvironmentCloth) -> EnvCloth:
            return EnvCloth(
                drawable=apply_target(self, CWFragDrawable(c.drawable)),
                controller=from_cw_controller(c.controller, self),
                tuning=_map_tuning(c.tuning),
                user_data=list(np.fromstring(c.user_data or "", dtype=int, sep=" ")),
                flags=c.flags,
            )

        return [_map_cloth(cloth) for cloth in self._inner.cloths]

    @cloths.setter
    def cloths(self, cloths: list[EnvCloth]):
        def _map_tuning(tuning: EnvClothTuning | None) -> cwcloth.ClothInstanceTuning | None:
            if tuning is None:
                return None

            t = cwcloth.ClothInstanceTuning()
            t.flags = tuning.flags
            t.extra_force = tuning.extra_force
            t.weight = tuning.weight
            t.distance_threshold = tuning.distance_threshold
            t.rotation_rate = tuning.rotation_rate
            t.angle_threshold = tuning.angle_threshold
            t.pin_vert = tuning.pin_vert
            t.non_pin_vert0 = tuning.non_pin_vert0
            t.non_pin_vert1 = tuning.non_pin_vert1
            return t

        def _map_cloth(cloth: EnvCloth) -> cwcloth.EnvironmentCloth:
            c = cwcloth.EnvironmentCloth()
            c.drawable = canonical_asset(cloth.drawable, CWFragDrawable, self)._inner
            c.controller = to_cw_controller(cloth.controller, self)
            c.tuning = _map_tuning(cloth.tuning)
            c.user_data = " ".join(map(str, cloth.user_data)) if cloth.user_data else None
            c.flags = cloth.flags
            return c

        self._inner.cloths = [_map_cloth(cloth) for cloth in cloths]
        if self._inner.cloths and self._inner.drawable is None:
            cloth_drawable = self._inner.cloths[0].drawable
            self._inner.bounding_sphere_center = cloth_drawable.bounding_sphere_center
            self._inner.bounding_sphere_radius = cloth_drawable.bounding_sphere_radius

    @property
    def lights(self) -> list[Light]:
        return [_map_light_from_cw(light) for light in self._inner.lights]

    @lights.setter
    def lights(self, v: list[Light]):
        self._inner.lights = [_map_light_to_cw(light) for light in v]

    @property
    def base_drawable(self) -> CWFragDrawable:
        drawable = self.drawable
        if drawable is None and (cloths := self._inner.cloths) and (cloth_drawable := cloths[0].drawable) is not None:
            drawable = CWFragDrawable(cloth_drawable)
        assert drawable is not None, "Fragment has no drawables"
        return drawable

    def generate_vehicle_windows(self) -> list[FragVehicleWindow]:
        raise NotImplementedError("CWXML cannot generate vehicle windows")
