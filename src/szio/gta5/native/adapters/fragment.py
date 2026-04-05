import pymateria as pma
import pymateria.gta5 as pm
import pymateria.gta5.gen8 as pmg8
import pymateria.gta5.gen9 as pmg9

from ....types import Vector
from ...cloths import (
    ClothController,
    VerletCloth,
)
from ...drawables import (
    VertexDataType,
)
from ...fragments import (
    AssetFragment,
    EnvCloth,
    EnvClothTuning,
    FragGlassWindow,
    FragmentTemplateAsset,
    FragVehicleWindow,
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
    _h2s,
    _s2h,
    from_native_mat34,
    to_native_mat34,
    to_native_sphere,
    to_native_uv,
    to_native_vec3,
)
from .bound import (
    load_bound_from_native,
    save_bound_to_native,
)
from .cloth import (
    from_native_bridge,
    from_native_verlet_cloth_edge,
    to_native_bridge,
    to_native_morph_controller,
    to_native_verlet_cloth_edge,
)
from .drawable import (
    _map_light_from_native,
    _map_light_to_native,
    load_frag_drawable_from_native_g8,
    save_frag_drawable_to_native_g8,
)


def _get_vehicle_windows(vw: pmg8.VehicleWindow | pmg9.VehicleWindow) -> list[FragVehicleWindow]:
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


def _load_fragment_from_native(f: pmg8.Fragment | pmg9.Fragment, *, load_frag_drawable) -> AssetFragment:
    """Convert a native Fragment to an AssetFragment dataclass."""

    def _load_archetype(a: pm.FragmentPhArchetypeDamp | None) -> PhysArchetype | None:
        if not a:
            return None
        return PhysArchetype(
            name=a.filename,
            bounds=load_bound_from_native(a.bounds),
            gravity_factor=a.gravity_factor,
            max_speed=a.max_speed,
            max_ang_speed=a.max_ang_speed,
            buoyancy_factor=a.buoyancy_factor,
            mass=a.mass,
            mass_inv=a.inv_mass,
            inertia=Vector(a.ang_inertia),
            inertia_inv=Vector(a.inv_ang_inertia),
        )

    def _load_child(
        c: pmg8.FragmentTypeChild | pmg9.FragmentTypeChild,
        idx: int,
        lod: pmg8.FragmentPhysicsLod | pmg9.FragmentPhysicsLod,
        parent_shader_group: pmg8.ShaderGroup | pmg9.ShaderGroup,
    ) -> PhysChild:
        return PhysChild(
            bone_tag=c.bone_id,
            group_index=c.owner_group_pointer_index,
            pristine_mass=c.undamaged_mass,
            damaged_mass=c.damaged_mass,
            drawable=load_frag_drawable(c.undamaged_entity, parent_shader_group=parent_shader_group)
            if c.undamaged_entity
            else None,
            damaged_drawable=load_frag_drawable(c.damaged_entity, parent_shader_group=parent_shader_group)
            if c.damaged_entity
            else None,
            min_breaking_impulse=lod.min_breaking_impulses[idx],
            inertia=Vector(lod.damaged_ang_inertia[idx]),
            damaged_inertia=Vector(lod.undamaged_ang_inertia[idx]),
        )

    def _load_group(g: pm.FragmentTypeGroup, name: str) -> PhysGroup:
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

    def _load_lod(
        lod: pmg8.FragmentPhysicsLod | pmg9.FragmentPhysicsLod,
        parent_shader_group: pmg8.ShaderGroup | pmg9.ShaderGroup,
    ) -> PhysLod:
        d = lod.damping_constant
        return PhysLod(
            archetype=_load_archetype(lod.phys_damp_undamaged),
            damaged_archetype=_load_archetype(lod.phys_damp_damaged),
            children=[_load_child(c, i, lod, parent_shader_group) for i, c in enumerate(lod.children)],
            groups=[_load_group(g, gname) for g, gname in zip(lod.groups, lod.group_names)],
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

    def _load_glass_window(g: pmg8.BGPaneModelInfoBase | pmg9.BGPaneModelInfoBase) -> FragGlassWindow:
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

    def _load_tuning(t: pm.FragmentEnvClothTuning | None) -> EnvClothTuning | None:
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

    def _load_verlet_cloth(c: pm.VerletCloth) -> VerletCloth:
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
            bounds=load_bound_from_native(c.custom_bound) if c.custom_bound else None,
        )

    def _load_controller(c: pm.ClothController) -> ClothController:
        return ClothController(
            # TODO: investigate why c.name has null padding — bad asset or pymateria bug?
            name=_h2s(c.name).rstrip("\x00"),
            flags=c.flags,
            bridge=from_native_bridge(c.bridge_sim_gfx),
            cloth_high=_load_verlet_cloth(c.cloth[0]),
            morph_high_poly_count=c.morph_controller.map_data[0].count if c.morph_controller else None,
        )

    def _load_cloth(c: pmg8.FragmentEnvCloth | pmg9.FragmentEnvCloth) -> EnvCloth:
        return EnvCloth(
            drawable=load_frag_drawable(c.referenced_drawable),
            controller=_load_controller(c.controller),
            tuning=_load_tuning(c.tuning),
            user_data=list(c.user_data),
            flags=c.flags,
        )

    # Load main drawable
    d = f.drawable
    drawable = None
    if d is not None:
        if f.common_cloth_drawable is None and (cloths := f.environment_cloths) and cloths[0].referenced_drawable == d:
            drawable = None
        else:
            drawable = load_frag_drawable(d)

    # Load extra drawables (share the parent drawable's shader group)
    parent_sg = f.drawable.shader_group if f.drawable else None
    extra_drawables = [load_frag_drawable(ed, parent_shader_group=parent_sg) for ed in f.extra_drawables]

    # Load physics
    group = f.physics_lod_group
    physics = PhysLodGroup(_load_lod(group.high_lod, parent_sg)) if group and group.high_lod else None

    # Load glass windows
    glass_windows = [_load_glass_window(g) for g in f.glass_pane_model_infos]

    # Load vehicle windows
    vehicle_windows = _get_vehicle_windows(f.vehicle_window)

    # Load cloths
    cloths = [_load_cloth(cloth) for cloth in f.environment_cloths]

    # Load lights
    lights = [_map_light_from_native(light) for light in f.lights]

    return AssetFragment(
        name=f.tune_name,
        flags=f.flags,
        drawable=drawable,
        extra_drawables=extra_drawables,
        physics=physics,
        template_asset=FragmentTemplateAsset(f.art_asset_id & 0xFF),
        unbroken_elasticity=f.unbroken_elasticity,
        gravity_factor=f.gravity_factor,
        buoyancy_factor=f.buoyancy_factor,
        glass_windows=glass_windows,
        vehicle_windows=vehicle_windows,
        cloths=cloths,
        lights=lights,
    )


def _save_fragment_to_native(
    asset: AssetFragment, *, gen, save_frag_drawable, create_glass_fvf
) -> pmg8.Fragment | pmg9.Fragment:
    """Convert an AssetFragment dataclass to a native Fragment."""

    f = gen.Fragment()
    f.tune_name = asset.name
    f.flags = asset.flags
    f.unbroken_elasticity = asset.unbroken_elasticity
    f.gravity_factor = asset.gravity_factor
    f.buoyancy_factor = asset.buoyancy_factor
    f.art_asset_id = asset.template_asset.value if asset.template_asset != FragmentTemplateAsset.NONE else -1
    f.damaged_object_index = -1

    # Save main drawable
    if asset.drawable is not None:
        f.drawable = save_frag_drawable(asset.drawable)
        d = f.drawable
        aabb = d.calculate_aabbs()
        bbmin = Vector(aabb.min)
        bbmax = Vector(aabb.max)
        bs_center = (bbmin + bbmax) * 0.5
        bs_radius = float((bbmax - bs_center).length)
        f.bounding_sphere = to_native_sphere(bs_center, bs_radius)
    else:
        f.bounding_sphere = to_native_sphere(Vector((0.0, 0.0, 0.0)), 0.0)

    # Save extra drawables
    if asset.extra_drawables:
        parent_sg = f.drawable.shader_group if f.drawable else None

        f.extra_drawables = [save_frag_drawable(d, parent_shader_group=parent_sg) for d in asset.extra_drawables]
        f.extra_drawable_names = [d.name for d in asset.extra_drawables]
        f.damaged_object_index = 0

    # Save matrix set
    if asset.matrix_set is not None:
        s = pm.MatrixSet()
        s.is_skinned = asset.matrix_set.is_skinned
        s.matrices = [pma.Matrix43(m) for m in asset.matrix_set.matrices]
        f.shared_matrix_set = s

    # Save physics
    if asset.physics is not None:

        def _save_archetype(arch: PhysArchetype | None) -> pm.FragmentPhArchetypeDamp | None:
            if arch is None:
                return None
            a = pm.FragmentPhArchetypeDamp()
            a.filename = arch.name
            a.bounds = save_bound_to_native(arch.bounds)
            a.gravity_factor = arch.gravity_factor
            a.max_speed = arch.max_speed
            a.max_ang_speed = arch.max_ang_speed
            a.buoyancy_factor = arch.buoyancy_factor
            a.mass = arch.mass
            a.inv_mass = arch.mass_inv
            a.ang_inertia = to_native_vec3(arch.inertia)
            a.inv_ang_inertia = to_native_vec3(arch.inertia_inv)
            return a

        parent_sg = f.drawable.shader_group if f.drawable else None

        def _save_child(child: PhysChild) -> pmg8.FragmentTypeChild | pmg9.FragmentTypeChild:
            c = gen.FragmentTypeChild()
            c.bone_id = child.bone_tag
            c.owner_group_pointer_index = child.group_index
            c.undamaged_mass = child.pristine_mass
            c.damaged_mass = child.damaged_mass
            c.flags = 0
            c.undamaged_entity = (
                save_frag_drawable(child.drawable, parent_shader_group=parent_sg) if child.drawable else None
            )
            c.damaged_entity = (
                save_frag_drawable(child.damaged_drawable, parent_shader_group=parent_sg)
                if child.damaged_drawable
                else None
            )
            return c

        def _save_group(group: PhysGroup) -> pm.FragmentTypeGroup:
            g = pm.FragmentTypeGroup()
            g.name = group.name
            g.parent_group_pointer_index = group.parent_group_index
            g.flags = group.flags
            g.total_undamaged_mass = group.total_mass
            g.total_damaged_mass = 0.0
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
            g.glass_model_and_type = 0xFF
            return g

        def _link_group_indices(
            groups: list[pm.FragmentTypeGroup],
            children: list[pmg8.FragmentTypeChild | pmg9.FragmentTypeChild],
        ) -> int:
            if not groups or not children:
                return 0

            group_child_index = [None] * len(groups)
            group_num_children = [0] * len(groups)
            group_child_groups_index = [None] * len(groups)
            group_num_child_groups = [0] * len(groups)
            for ci, c in enumerate(children):
                gi = c.owner_group_pointer_index
                if group_child_index[gi] is None:
                    group_child_index[gi] = ci
                group_num_children[gi] += 1

            num_root_groups = 0
            for gi, g in enumerate(groups):
                pgi = g.parent_group_pointer_index
                if pgi == 255:
                    num_root_groups += 1
                    continue
                if group_child_groups_index[pgi] is None:
                    group_child_groups_index[pgi] = gi
                group_num_child_groups[pgi] += 1

            for gi, g in enumerate(groups):
                g.child_index = group_child_index[gi] if group_child_index[gi] is not None else 255
                g.num_children = group_num_children[gi]
                g.child_groups_pointers_index = (
                    group_child_groups_index[gi] if group_child_groups_index[gi] is not None else 255
                )
                g.num_child_groups = group_num_child_groups[gi]

            return num_root_groups

        def _link_child_collisions(
            children: list[pmg8.FragmentTypeChild | pmg9.FragmentTypeChild],
            collisions: pm.BoundComposite | None,
            damaged_collisions: pm.BoundComposite | None,
        ):
            skel = f.drawable.skeleton if f.drawable else None
            bounds = collisions.bounds if collisions else ([None] * len(children))
            damaged_bounds = damaged_collisions.bounds if damaged_collisions else ([None] * len(children))
            for c, b, db in zip(children, bounds, damaged_bounds):
                e = c.undamaged_entity
                if e:
                    e.bound = b.bound if b else None
                    e.skeleton = skel
                d = c.damaged_entity
                if d:
                    d.bound = db.bound if db else None
                    d.skeleton = skel

        lod_data = asset.physics.lod1
        l = gen.FragmentPhysicsLod()
        l.smallest_ang_inertia = lod_data.smallest_ang_inertia
        l.largest_ang_inertia = lod_data.largest_ang_inertia
        l.min_move_force = lod_data.min_move_force
        l.root_cg_offset = to_native_vec3(lod_data.root_cg_offset)
        l.original_root_cg_offset = to_native_vec3(lod_data.original_root_cg_offset)
        l.unbroken_cg_offset = to_native_vec3(lod_data.unbroken_cg_offset)
        l.damping_constant = (
            to_native_vec3(lod_data.damping_linear_c),
            to_native_vec3(lod_data.damping_linear_v),
            to_native_vec3(lod_data.damping_linear_v2),
            to_native_vec3(lod_data.damping_angular_c),
            to_native_vec3(lod_data.damping_angular_v),
            to_native_vec3(lod_data.damping_angular_v2),
        )
        l.group_names = [g.name for g in lod_data.groups]
        groups = [_save_group(g) for g in lod_data.groups]
        children = [_save_child(c) for c in lod_data.children]
        num_root_groups = _link_group_indices(groups, children)
        l.groups = groups
        l.children = children
        l.min_breaking_impulses = [c.min_breaking_impulse for c in lod_data.children]
        l.undamaged_ang_inertia = [to_native_vec3(c.inertia) for c in lod_data.children]
        l.damaged_ang_inertia = [to_native_vec3(c.damaged_inertia) for c in lod_data.children]
        l.phys_damp_undamaged = _save_archetype(lod_data.archetype)
        l.phys_damp_damaged = _save_archetype(lod_data.damaged_archetype)
        l.composite_bounds = l.phys_damp_undamaged.bounds
        _link_child_collisions(
            children, l.phys_damp_undamaged.bounds, l.phys_damp_damaged.bounds if l.phys_damp_damaged else None
        )
        l.link_attachments = [to_native_mat34(a) for a in lod_data.link_attachments]
        l.root_group_count = num_root_groups
        l.num_root_damage_regions = 1
        l.num_bony_children = len(lod_data.children)
        l.body_type = None

        g = gen.FragmentPhysicsLodGroup()
        g.high_lod = l
        f.physics_lod_group = g

    # Save glass windows
    def _save_glass_window(gw: FragGlassWindow) -> pmg8.BGPaneModelInfoBase | pmg9.BGPaneModelInfoBase:
        fvf = create_glass_fvf()
        p = gen.BGPaneModelInfoBase()
        p.fvf = fvf
        p.glass_type = gw.glass_type
        p.shader_index = gw.shader_index
        p.pos_base = to_native_vec3(gw.pos_base)
        p.pos_width = to_native_vec3(gw.pos_width)
        p.pos_height = to_native_vec3(gw.pos_height)
        p.uv_min = to_native_uv(gw.uv_min)
        p.uv_max = to_native_uv(gw.uv_max)
        p.thickness = gw.thickness
        p.bounds_offset_front = gw.bounds_offset_front
        p.bounds_offset_back = gw.bounds_offset_back
        p.tangent = to_native_vec3(gw.tangent)
        return p

    f.glass_pane_model_infos = [_save_glass_window(gw) for gw in (asset.glass_windows or [])]

    # Save vehicle windows
    f.generate_vehicle_windows = False
    if asset.vehicle_windows:

        def _save_vehicle_window(window: FragVehicleWindow) -> pm.WindowProxy:
            w = pm.Window()
            w.component_id = window.component_id
            w.min = window.data_min
            w.max = window.data_max
            w.scale = window.scale
            w.geom_index = window.geometry_index
            basis_t = window.basis.transposed()
            w.basis = to_native_mat34(basis_t)
            w.data_rows = window.height
            w.data_cols = window.width
            w.data_rle = compress_shattermap(window.shattermap)
            p = pm.WindowProxy()
            p.basis = w.basis
            p.component_id = w.component_id
            p.window = w
            return p

        vw = gen.VehicleWindow()
        vw.window_proxies = [_save_vehicle_window(w) for w in asset.vehicle_windows]
        f.vehicle_window = vw
    else:
        f.vehicle_window = None

    # Save cloths
    def _save_tuning(tuning: EnvClothTuning | None) -> pm.FragmentEnvClothTuning | None:
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

    def _save_verlet_cloth(cloth) -> pm.VerletCloth:
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

    def _save_controller(controller) -> pm.ClothController:
        c = pm.ClothController()
        c.name = _s2h(controller.name)
        c.bridge_sim_gfx = to_native_bridge(controller.bridge)
        c.morph_controller = to_native_morph_controller(controller)
        c.cloth = [_save_verlet_cloth(controller.cloth_high)]
        c.flags = controller.flags
        return c

    def _save_cloth(cloth: EnvCloth) -> pmg8.FragmentEnvCloth | pmg9.FragmentEnvCloth:
        c = gen.FragmentEnvCloth()
        c.referenced_drawable = save_frag_drawable(cloth.drawable) if cloth.drawable else None
        c.controller = _save_controller(cloth.controller)
        c.tuning = _save_tuning(cloth.tuning)
        c.user_data = cloth.user_data
        c.flags = cloth.flags
        return c

    env_cloths = [_save_cloth(cloth) for cloth in (asset.cloths or [])]
    f.environment_cloths = env_cloths
    if env_cloths:
        cloth_drawable = env_cloths[0].referenced_drawable
        if f.drawable is None:
            f.drawable = cloth_drawable
            f.common_cloth_drawable = None
            aabb = cloth_drawable.calculate_aabbs()
            bbmin = Vector(aabb.min)
            bbmax = Vector(aabb.max)
            bs_center = (bbmin + bbmax) * 0.5
            bs_radius = float((bbmax - bs_center).length)
            f.bounding_sphere = to_native_sphere(bs_center, bs_radius)
        else:
            f.common_cloth_drawable = cloth_drawable

    # Save lights
    f.lights = [_map_light_to_native(li) for li in (asset.lights or [])]

    return f


def _create_glass_fvf_g8():
    C = pmg8.FvfChannel
    return pmg8.Fvf(
        {C.POSITION, C.NORMAL, C.DIFFUSE, C.TEXTURE0, C.TEXTURE1},
        size_signature=VertexDataType.BREAKABLE_GLASS.value,
    )


def load_fragment_from_native_g8(f: pmg8.Fragment) -> AssetFragment:
    """Convert a native gen8 Fragment to an AssetFragment dataclass."""
    return _load_fragment_from_native(f, load_frag_drawable=load_frag_drawable_from_native_g8)


def save_fragment_to_native_g8(asset: AssetFragment) -> pmg8.Fragment:
    """Convert an AssetFragment dataclass to a native gen8 Fragment."""
    return _save_fragment_to_native(
        asset,
        gen=pmg8,
        save_frag_drawable=save_frag_drawable_to_native_g8,
        create_glass_fvf=_create_glass_fvf_g8,
    )


def generate_vehicle_windows(asset: AssetFragment) -> list[FragVehicleWindow]:
    """Auto-generate vehicle windows from a fragment. Requires pymateria."""
    native_frag = save_fragment_to_native_g8(asset)
    vw = pmg8.VehicleWindow()
    vw.generate_vehicle_windows(
        native_frag.drawable,
        native_frag.physics_lod_group.high_lod.composite_bounds,
        native_frag.physics_lod_group.high_lod.children,
    )
    return _get_vehicle_windows(vw)
