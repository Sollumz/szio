import pymateria as pma
import pymateria.gta5 as pm
import pymateria.gta5.gen8 as pmg8

from ....types import Vector
from ...assets import (
    AssetFormat,
    AssetType,
    AssetVersion,
    canonical_asset,
)
from ...drawables import (
    Light,
    VertexDataType,
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
    compress_shattermap,
    decompress_shattermap,
)
from ._utils import (
    apply_target,
    from_native_mat34,
    to_native_mat34,
    to_native_sphere,
    to_native_uv,
    to_native_vec3,
)
from .bound import (
    NativeBound,
)
from .cloth import (
    from_native_controller,
    to_native_controller,
)
from .drawable import (
    NativeFragDrawable,
    _map_light_from_native,
    _map_light_to_native,
)


def _get_vehicle_windows(vw: pmg8.VehicleWindow) -> list[FragVehicleWindow]:
    def _map_window(w: pm.Window) -> FragVehicleWindow:
        return FragVehicleWindow(
            basis=from_native_mat34(w.basis).transposed(),
            component_id=w.component_id,
            geometry_index=w.geom_index,
            width=w.data_cols,
            height=w.data_rows,
            scale=w.scale,
            flags=w.flags,
            data_min=w.min,
            data_max=w.max,
            shattermap=decompress_shattermap(w.data_rle, w.data_cols, w.data_rows),
        )

    return [_map_window(p.window) for p in vw.window_proxies] if vw else []


class NativeFragment:
    ASSET_FORMAT = AssetFormat.NATIVE
    ASSET_VERSION = AssetVersion.GEN8
    ASSET_TYPE = AssetType.FRAGMENT

    def __init__(self, f: pmg8.Fragment):
        self._inner = f

        # TODO(io): would be nice to have something for generic caching of properties of complex dataclasses like this.
        # Also makes the API more natural to use (in particular with MultiTargetProxy, and the inner instances of
        # different formats are kept cached, instead of only the instance that matches the format os this asset)
        #
        # This is currently required to add extra null bounds on cloth props in yftexport. Also done in CWFragment.
        self._physics_cached = None

    @property
    def name(self) -> str:
        return self._inner.tune_name

    @name.setter
    def name(self, v: str):
        self._inner.tune_name = v

    @property
    def flags(self) -> int:
        return self._inner.flags

    @flags.setter
    def flags(self, v: int):
        self._inner.flags = v

    @property
    def drawable(self) -> NativeFragDrawable | None:
        d = self._inner.drawable
        if (
            self._inner.common_cloth_drawable is None
            and (cloths := self._inner.environment_cloths)
            and cloths[0].referenced_drawable == d
        ):
            # If we only have a cloth drawable, we want to return None here. In these cases the common_cloth_drawable
            # is indeed None and the fragment drawable points to the cloth drawable, but we don't want that behaviour
            # because we want to differentiate a "main" drawable from a cloth drawable.
            # The base_drawable property should be used when it doesn't matter which drawable is needed
            d = None
        return apply_target(self, self._cls_NativeFragDrawable(d)) if d else None

    @drawable.setter
    def drawable(self, v: NativeFragDrawable | None):
        self._inner.drawable = d = canonical_asset(v, self._cls_NativeFragDrawable, self)._inner if v else None
        if d:
            aabb = d.calculate_aabbs()
            bbmin = Vector(aabb.min)
            bbmax = Vector(aabb.max)
            bs_center = (bbmin + bbmax) * 0.5
            bs_radius = (bbmax - bs_center).length
            self._inner.bounding_sphere = to_native_sphere(bs_center, bs_radius)
        else:
            self._inner.bounding_sphere = to_native_sphere(Vector((0.0, 0.0, 0.0)), 0.0)

    @property
    def extra_drawables(self) -> list[NativeFragDrawable]:
        return [
            apply_target(self, self._cls_NativeFragDrawable(d, drawable_with_shader_group=self._inner.drawable))
            for d in self._inner.extra_drawables
        ]

    @extra_drawables.setter
    def extra_drawables(self, v: list[NativeFragDrawable]):
        self._inner.extra_drawables = [canonical_asset(d, self._cls_NativeFragDrawable, self)._inner for d in v]
        self._inner.extra_drawable_names = [d.name for d in v]
        if self._inner.extra_drawables:
            # extra drawables are only used for the damaged model
            self._inner.damaged_object_index = 0

    @property
    def matrix_set(self) -> MatrixSet | None:
        raise NotImplementedError("matrix_set getter")

    @matrix_set.setter
    def matrix_set(self, v: MatrixSet | None):
        s = pm.MatrixSet()
        s.is_skinned = v.is_skinned
        s.matrices = [pma.Matrix43(m) for m in v.matrices]
        self._inner.shared_matrix_set = s

    @property
    def physics(self) -> PhysLodGroup | None:
        if self._physics_cached is not None:
            return self._physics_cached[0]

        def _map_archetype(a: pm.FragmentPhArchetypeDamp | None) -> PhysArchetype | None:
            if not a:
                return None

            return PhysArchetype(
                name=a.filename,
                bounds=apply_target(self, NativeBound(a.bounds)),
                gravity_factor=a.gravity_factor,
                max_speed=a.max_speed,
                max_ang_speed=a.max_ang_speed,
                buoyancy_factor=a.buoyancy_factor,
                mass=a.mass,
                mass_inv=a.inv_mass,
                inertia=Vector(a.ang_inertia),
                inertia_inv=Vector(a.inv_ang_inertia),
            )

        def _map_child(c: pmg8.FragmentTypeChild, idx: int, lod: pmg8.FragmentPhysicsLod) -> PhysChild:
            return PhysChild(
                bone_tag=c.bone_id,
                group_index=c.owner_group_pointer_index,
                pristine_mass=c.undamaged_mass,
                damaged_mass=c.damaged_mass,
                drawable=(
                    apply_target(
                        self,
                        self._cls_NativeFragDrawable(
                            c.undamaged_entity, drawable_with_shader_group=self._inner.drawable
                        ),
                    )
                    if c.undamaged_entity
                    else None
                ),
                damaged_drawable=(
                    apply_target(
                        self,
                        self._cls_NativeFragDrawable(c.damaged_entity, drawable_with_shader_group=self._inner.drawable),
                    )
                    if c.damaged_entity
                    else None
                ),
                min_breaking_impulse=lod.min_breaking_impulses[idx],
                inertia=Vector(lod.damaged_ang_inertia[idx]),
                damaged_inertia=Vector(lod.undamaged_ang_inertia[idx]),
            )

        def _map_group(g: pm.FragmentTypeGroup, name: str) -> PhysGroup:
            return PhysGroup(
                name=name or g.name,
                parent_group_index=g.parent_group_pointer_index,
                flags=g.flags,
                total_mass=g.total_undamaged_mass,
                strength=g.strength,
                force_transmission_scale_up=g.force_transmission_scale_up,
                force_transmission_scale_down=g.force_transmission_scale_down,
                joint_stiffness=g.joint_stiffness,
                min_soft_angle_1=g.min_soft_angle1,
                max_soft_angle_1=g.max_soft_angle1,
                max_soft_angle_2=g.max_soft_angle2,
                max_soft_angle_3=g.max_soft_angle3,
                rotation_speed=g.rotation_speed,
                rotation_strength=g.rotation_strength,
                restoring_strength=g.restoring_strength,
                restoring_max_torque=g.restoring_max_torque,
                latch_strength=g.latch_strength,
                min_damage_force=g.min_damage_force,
                damage_health=g.damage_health,
                weapon_health=g.weapon_health,
                weapon_scale=g.weapon_scale,
                vehicle_scale=g.vehicle_scale,
                ped_scale=g.ped_scale,
                ragdoll_scale=g.ragdoll_scale,
                explosion_scale=g.explosion_scale,
                object_scale=g.object_scale,
                ped_inv_mass_scale=g.ped_inv_mass_scale,
                melee_scale=g.melee_scale,
                glass_window_index=g.glass_pane_model_info_index,
            )

        def _map_lod(lod: pmg8.FragmentPhysicsLod) -> PhysLod:
            d = lod.damping_constant
            return PhysLod(
                archetype=_map_archetype(lod.phys_damp_undamaged),
                damaged_archetype=_map_archetype(lod.phys_damp_damaged),
                children=[_map_child(c, i, lod) for i, c in enumerate(lod.children)],
                groups=[_map_group(g, gname) for g, gname in zip(lod.groups, lod.group_names)],
                smallest_ang_inertia=lod.smallest_ang_inertia,
                largest_ang_inertia=lod.largest_ang_inertia,
                min_move_force=lod.min_move_force,
                root_cg_offset=Vector(lod.root_cg_offset),
                original_root_cg_offset=Vector(lod.original_root_cg_offset),
                unbroken_cg_offset=Vector(lod.unbroken_cg_offset),
                damping_linear_c=Vector(d[0]),
                damping_linear_v=Vector(d[1]),
                damping_linear_v2=Vector(d[2]),
                damping_angular_c=Vector(d[3]),
                damping_angular_v=Vector(d[4]),
                damping_angular_v2=Vector(d[5]),
                link_attachments=[from_native_mat34(a) for a in lod.link_attachments],
            )

        group = self._inner.physics_lod_group
        if group and group.high_lod:
            p = PhysLodGroup(_map_lod(group.high_lod))
        else:
            p = None
        self._physics_cached = (p,)
        return p

    @physics.setter
    def physics(self, v: PhysLodGroup | None):
        self._physics_cached = (v,)
        if v is None:
            self._inner.physics_lod_group = None
            return

        def _map_archetype(arch: PhysArchetype | None) -> pm.FragmentPhArchetypeDamp:
            if arch is None:
                return None

            a = pm.FragmentPhArchetypeDamp()
            a.filename = arch.name
            a.bounds = canonical_asset(arch.bounds, NativeBound, self)._inner
            a.gravity_factor = arch.gravity_factor
            a.max_speed = arch.max_speed
            a.max_ang_speed = arch.max_ang_speed
            a.buoyancy_factor = arch.buoyancy_factor
            a.mass = arch.mass
            a.inv_mass = arch.mass_inv
            a.ang_inertia = to_native_vec3(arch.inertia)
            a.inv_ang_inertia = to_native_vec3(arch.inertia_inv)
            return a

        def _map_child(child: PhysChild) -> pmg8.FragmentTypeChild:
            c = self._create_physics_child()
            c.bone_id = child.bone_tag
            c.owner_group_pointer_index = child.group_index
            c.undamaged_mass = child.pristine_mass
            c.damaged_mass = child.damaged_mass
            c.flags = 0
            c.undamaged_entity = (
                canonical_asset(child.drawable, self._cls_NativeFragDrawable, self)._inner if child.drawable else None
            )
            c.damaged_entity = (
                canonical_asset(child.damaged_drawable, self._cls_NativeFragDrawable, self)._inner
                if child.damaged_drawable
                else None
            )
            return c

        def _map_group(group: PhysGroup) -> pm.FragmentTypeGroup:
            g = pm.FragmentTypeGroup()
            g.name = group.name
            g.parent_group_pointer_index = group.parent_group_index
            g.flags = group.flags
            g.total_undamaged_mass = group.total_mass
            g.total_damaged_mass = 0.0  # this is always 0 in original assets
            g.strength = group.strength
            g.force_transmission_scale_up = group.force_transmission_scale_up
            g.force_transmission_scale_down = group.force_transmission_scale_down
            g.joint_stiffness = group.joint_stiffness
            g.min_soft_angle1 = group.min_soft_angle_1
            g.max_soft_angle1 = group.max_soft_angle_1
            g.max_soft_angle2 = group.max_soft_angle_2
            g.max_soft_angle3 = group.max_soft_angle_3
            g.rotation_speed = group.rotation_speed
            g.rotation_strength = group.rotation_strength
            g.restoring_strength = group.restoring_strength
            g.restoring_max_torque = group.restoring_max_torque
            g.latch_strength = group.latch_strength
            g.min_damage_force = group.min_damage_force
            g.damage_health = group.damage_health
            g.weapon_health = group.weapon_health
            g.weapon_scale = group.weapon_scale
            g.vehicle_scale = group.vehicle_scale
            g.ped_scale = group.ped_scale
            g.ragdoll_scale = group.ragdoll_scale
            g.explosion_scale = group.explosion_scale
            g.object_scale = group.object_scale
            g.ped_inv_mass_scale = group.ped_inv_mass_scale
            g.melee_scale = group.melee_scale
            g.glass_pane_model_info_index = group.glass_window_index
            g.glass_model_and_type = 0xFF  # always 0xFF
            return g

        def _link_group_indices(groups: list[pm.FragmentTypeGroup], children: list[pmg8.FragmentTypeChild]) -> int:
            if not groups or not children:
                return 0

            group_child_index = [None] * len(groups)
            group_num_children = [0] * len(groups)
            group_child_groups_index = [None] * len(groups)
            group_num_child_groups = [0] * len(groups)
            current_group_index = None
            for ci, c in enumerate(children):
                gi = c.owner_group_pointer_index
                if group_child_index[gi] is None:
                    group_child_index[gi] = ci
                    group_num_children[gi] += 1
                    current_group_index = gi
                else:
                    # assert current_group_index == gi, "Children of same group must be contiguous in list!"
                    group_num_children[gi] += 1

            current_group_index = None
            num_root_groups = 0
            for gi, g in enumerate(groups):
                pgi = g.parent_group_pointer_index
                if pgi == 255:
                    num_root_groups += 1
                    continue

                if group_child_groups_index[pgi] is None:
                    group_child_groups_index[pgi] = gi
                    group_num_child_groups[pgi] += 1
                    current_group_index = pgi
                else:
                    # assert current_group_index == pgi, "Children groups of same group must be contiguous in list!"
                    group_num_child_groups[pgi] += 1

            for gi, g in enumerate(groups):
                assert group_child_index[gi] is not None
                g.child_index = group_child_index[gi] if group_child_index[gi] is not None else 255
                g.num_children = group_num_children[gi]
                g.child_groups_pointers_index = (
                    group_child_groups_index[gi] if group_child_groups_index[gi] is not None else 255
                )
                g.num_child_groups = group_num_child_groups[gi]

            return num_root_groups

        def _link_child_collisions(
            children: list[pmg8.FragmentTypeChild],
            collisions: pm.BoundComposite | None,
            damaged_collisions: pm.BoundComposite | None,
        ):
            skel = self._inner.drawable.skeleton
            bounds = collisions.bounds if collisions else ([None] * len(children))
            damaged_bounds = damaged_collisions.bounds if damaged_collisions else ([None] * len(children))
            assert (
                (len(children) == len(bounds))
                or
                # special case for cloths with no collisions which creates a dummy physics LOD
                (len(children) == 1 and len(bounds) == 2 and all(b.bound is None for b in bounds))
            )
            for c, b, db in zip(children, bounds, damaged_bounds):
                e = c.undamaged_entity
                if e:
                    e.bound = b.bound if b else None
                    e.skeleton = skel

                d = c.damaged_entity
                if d:
                    d.bound = db.bound if db else None
                    d.skeleton = skel

        def _map_lod(lod: PhysLod) -> pmg8.FragmentPhysicsLod:
            l = self._create_physics_lod()
            l.smallest_ang_inertia = lod.smallest_ang_inertia
            l.largest_ang_inertia = lod.largest_ang_inertia
            l.min_move_force = lod.min_move_force
            l.root_cg_offset = to_native_vec3(lod.root_cg_offset)
            l.original_root_cg_offset = to_native_vec3(lod.original_root_cg_offset)
            l.unbroken_cg_offset = to_native_vec3(lod.unbroken_cg_offset)
            l.damping_constant = (
                to_native_vec3(lod.damping_linear_c),
                to_native_vec3(lod.damping_linear_v),
                to_native_vec3(lod.damping_linear_v2),
                to_native_vec3(lod.damping_angular_c),
                to_native_vec3(lod.damping_angular_v),
                to_native_vec3(lod.damping_angular_v2),
            )
            l.group_names = [g.name for g in lod.groups]
            groups = [_map_group(g) for g in lod.groups]
            children = [_map_child(c) for c in lod.children]
            num_root_groups = _link_group_indices(groups, children)
            l.groups = groups
            l.children = children
            # TODO: import/export phys child min breaking impulse
            l.min_breaking_impulses = [c.min_breaking_impulse for c in lod.children]
            l.undamaged_ang_inertia = [to_native_vec3(c.inertia) for c in lod.children]
            l.damaged_ang_inertia = [to_native_vec3(c.damaged_inertia) for c in lod.children]
            l.phys_damp_undamaged = _map_archetype(lod.archetype)
            l.phys_damp_damaged = _map_archetype(lod.damaged_archetype)
            l.composite_bounds = l.phys_damp_undamaged.bounds
            _link_child_collisions(
                children, l.phys_damp_undamaged.bounds, l.phys_damp_damaged.bounds if l.phys_damp_damaged else None
            )
            l.link_attachments = [to_native_mat34(a) for a in lod.link_attachments]

            l.root_group_count = num_root_groups
            l.num_root_damage_regions = 1
            l.num_bony_children = len(lod.children)

            # TODO: articulated bodies not supported by sollumz for now
            l.body_type = None
            # l.self_collisions
            return l

        g = self._create_physics_lod_group()
        g.high_lod = _map_lod(v.lod1)
        self._inner.physics_lod_group = g

    @property
    def template_asset(self) -> FragmentTemplateAsset:
        return FragmentTemplateAsset(self._inner.art_asset_id & 0xFF)

    @template_asset.setter
    def template_asset(self, v: FragmentTemplateAsset):
        self._inner.art_asset_id = v.value if v != FragmentTemplateAsset.NONE else -1

    @property
    def unbroken_elasticity(self) -> float:
        return self._inner.unbroken_elasticity

    @unbroken_elasticity.setter
    def unbroken_elasticity(self, v: float):
        self._inner.unbroken_elasticity = v

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
        def _map_window(g: pmg8.BGPaneModelInfoBase) -> FragGlassWindow:
            return FragGlassWindow(
                glass_type=g.glass_type,
                shader_index=g.shader_index,
                pos_base=Vector(g.pos_base),
                pos_width=Vector(g.pos_width),
                pos_height=Vector(g.pos_height),
                uv_min=Vector(g.uv_min),
                uv_max=Vector(g.uv_max),
                thickness=g.thickness,
                bounds_offset_front=g.bounds_offset_front,
                bounds_offset_back=g.bounds_offset_back,
                tangent=Vector(g.tangent),
            )

        return [_map_window(g) for g in self._inner.glass_pane_model_infos]

    @glass_windows.setter
    def glass_windows(self, v: list[FragGlassWindow]):
        def _map_window(g: FragGlassWindow) -> pmg8.BGPaneModelInfoBase:
            p = self._create_bg_pane_model_info()
            p.glass_type = g.glass_type
            p.shader_index = g.shader_index
            p.pos_base = to_native_vec3(g.pos_base)
            p.pos_width = to_native_vec3(g.pos_width)
            p.pos_height = to_native_vec3(g.pos_height)
            p.uv_min = to_native_uv(g.uv_min)
            p.uv_max = to_native_uv(g.uv_max)
            p.thickness = g.thickness
            p.bounds_offset_front = g.bounds_offset_front
            p.bounds_offset_back = g.bounds_offset_back
            p.tangent = to_native_vec3(g.tangent)
            return p

        self._inner.glass_pane_model_infos = [_map_window(g) for g in v]

    @property
    def vehicle_windows(self) -> list[FragVehicleWindow]:
        return _get_vehicle_windows(self._inner.vehicle_window)

    @vehicle_windows.setter
    def vehicle_windows(self, windows: list[FragVehicleWindow]):
        def _map_window(window: FragVehicleWindow) -> pm.WindowProxy:
            w = pm.Window()
            w.component_id = window.component_id
            w.min = window.data_min
            w.max = window.data_max
            w.scale = window.scale
            w.geom_index = window.geometry_index
            w.basis = to_native_mat34(window.basis.transposed())
            w.data_rows = window.height
            w.data_cols = window.width
            w.data_rle = compress_shattermap(window.shattermap)

            p = pm.WindowProxy()
            p.basis = w.basis
            p.component_id = w.component_id
            p.window = w
            return p

        self._inner.generate_vehicle_windows = False
        if windows:
            vw = self._create_vehicle_window()
            vw.window_proxies = [_map_window(w) for w in windows]
            self._inner.vehicle_window = vw
        else:
            self._inner.vehicle_window = None

    @property
    def cloths(self) -> list[EnvCloth]:
        def _map_tuning(t: pm.FragmentEnvClothTuning | None) -> EnvClothTuning | None:
            if t is None:
                return None

            return EnvClothTuning(
                flags=t.flags,
                extra_force=Vector(t.extra_force.to_vector3()),
                weight=t.weight,
                distance_threshold=t.distance_threshold,
                rotation_rate=t.rotation_rate,
                angle_threshold=t.angle_threshold,
                pin_vert=t.pin_vert,
                non_pin_vert0=t.non_pin_vert0,
                non_pin_vert1=t.non_pin_vert1,
            )

        def _map_cloth(c: pmg8.FragmentEnvCloth) -> EnvCloth:
            return EnvCloth(
                drawable=apply_target(self, self._cls_NativeFragDrawable(c.referenced_drawable)),
                controller=from_native_controller(c.controller, self),
                tuning=_map_tuning(c.tuning),
                user_data=list(c.user_data),
                flags=c.flags,
            )

        return [_map_cloth(cloth) for cloth in self._inner.environment_cloths]

    @cloths.setter
    def cloths(self, cloths: list[EnvCloth]):
        def _map_tuning(tuning: EnvClothTuning | None) -> pm.FragmentEnvClothTuning | None:
            if tuning is None:
                return None

            t = pm.FragmentEnvClothTuning()
            t.flags = tuning.flags
            t.extra_force = to_native_vec3(tuning.extra_force).to_vector4(0.0)
            t.weight = tuning.weight
            t.distance_threshold = tuning.distance_threshold
            t.rotation_rate = tuning.rotation_rate
            t.angle_threshold = tuning.angle_threshold
            t.pin_vert = tuning.pin_vert
            t.non_pin_vert0 = tuning.non_pin_vert0
            t.non_pin_vert1 = tuning.non_pin_vert1
            return t

        def _map_cloth(cloth: EnvCloth) -> pmg8.FragmentEnvCloth:
            c = self._create_env_cloth()
            c.referenced_drawable = canonical_asset(cloth.drawable, self._cls_NativeFragDrawable, self)._inner
            c.controller = to_native_controller(cloth.controller, self)
            c.tuning = _map_tuning(cloth.tuning)
            c.user_data = cloth.user_data
            c.flags = cloth.flags
            return c

        frag = self._inner
        frag.environment_cloths = [_map_cloth(cloth) for cloth in cloths]
        if frag.environment_cloths:
            cloth_drawable = frag.environment_cloths[0].referenced_drawable
            if frag.drawable is None:
                frag.drawable = cloth_drawable
                frag.common_cloth_drawable = None
                aabb = cloth_drawable.calculate_aabbs()
                bbmin = Vector(aabb.min)
                bbmax = Vector(aabb.max)
                bs_center = (bbmin + bbmax) * 0.5
                bs_radius = (bbmax - bs_center).length
                frag.bounding_sphere = to_native_sphere(bs_center, bs_radius)
            else:
                frag.common_cloth_drawable = cloth_drawable

    @property
    def lights(self) -> list[Light]:
        return [_map_light_from_native(light) for light in self._inner.lights]

    @lights.setter
    def lights(self, lights: list[Light]):
        self._inner.lights = [_map_light_to_native(li) for li in lights]

    @property
    def base_drawable(self) -> NativeFragDrawable:
        drawable = self._inner.drawable
        assert drawable is not None, "Fragment has no drawables"
        return self._cls_NativeFragDrawable(drawable)

    def generate_vehicle_windows(self) -> list[FragVehicleWindow]:
        frag = self._inner
        vw = self._create_vehicle_window()
        vw.generate_vehicle_windows(
            frag.drawable, frag.physics_lod_group.high_lod.composite_bounds, frag.physics_lod_group.high_lod.children
        )
        return _get_vehicle_windows(vw)

    # These functions are the gen8 specific code that needs to be overriden by the gen9 class
    def _create_physics_lod_group(self) -> pmg8.FragmentPhysicsLodGroup:
        return pmg8.FragmentPhysicsLodGroup()

    def _create_physics_lod(self) -> pmg8.FragmentPhysicsLod:
        return pmg8.FragmentPhysicsLod()

    def _create_physics_child(self) -> pmg8.FragmentTypeChild:
        return pmg8.FragmentTypeChild()

    def _create_bg_pane_model_info(self) -> pmg8.BGPaneModelInfoBase:
        # BGPaneModelInfo always uses the same FVF
        C = pmg8.FvfChannel
        fvf = pmg8.Fvf(
            {C.POSITION, C.NORMAL, C.DIFFUSE, C.TEXTURE0, C.TEXTURE1},
            size_signature=VertexDataType.BREAKABLE_GLASS.value,
        )
        p = pmg8.BGPaneModelInfoBase()
        p.fvf = fvf
        return p

    def _create_vehicle_window(self) -> pmg8.VehicleWindow:
        return pmg8.VehicleWindow()

    def _create_env_cloth(self) -> pmg8.FragmentEnvCloth:
        return pmg8.FragmentEnvCloth()

    @property
    def _cls_NativeFragDrawable(self) -> type:
        return NativeFragDrawable
