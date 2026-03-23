import numpy as np

from ....types import Matrix, Vector
from ...assets import (
    AssetVersion,
)
from ...fragments import (
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
    shattermap_from_ascii,
    shattermap_to_ascii,
)
from .. import cloth as cwcloth
from .. import fragment as cw
from .drawable import (
    _map_light_from_cw,
    _map_light_to_cw,
)


def load_fragment(f: cw.Fragment) -> "AssetFragment":
    from ...fragments import AssetFragment
    from .bound import load_bound
    from .cloth import _load_char_controller_cw
    from .drawable import load_frag_drawable

    def _load_archetype(a: cw.Archetype | None) -> PhysArchetype | None:
        if not a:
            return None
        return PhysArchetype(
            name=a.name,
            bounds=load_bound(a.bounds),
            gravity_factor=a.unknown_48,
            max_speed=a.unknown_4c,
            max_ang_speed=a.unknown_50,
            buoyancy_factor=a.unknown_54,
            mass=a.mass,
            mass_inv=a.mass_inv,
            inertia=Vector(a.inertia_tensor),
            inertia_inv=Vector(a.inertia_tensor_inv),
        )

    def _load_child(g: cw.PhysicsChild) -> PhysChild:
        return PhysChild(
            bone_tag=g.bone_tag,
            group_index=g.group_index,
            pristine_mass=g.pristine_mass,
            damaged_mass=g.damaged_mass,
            drawable=load_frag_drawable(g.drawable) if g.drawable else None,
            damaged_drawable=load_frag_drawable(g.damaged_drawable) if g.damaged_drawable else None,
            min_breaking_impulse=g.unk_float,
            inertia=Vector(g.inertia_tensor),
            damaged_inertia=Vector(g.damaged_inertia_tensor),
        )

    def _load_group(g: cw.PhysicsGroup) -> PhysGroup:
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

    def _load_lod(lod: cw.PhysicsLOD) -> PhysLod:
        return PhysLod(
            archetype=_load_archetype(lod.archetype),
            damaged_archetype=_load_archetype(lod.damaged_archetype),
            children=[_load_child(c) for c in lod.children],
            groups=[_load_group(g) for g in lod.groups],
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

    def _load_glass_window(g: cw.GlassWindow) -> FragGlassWindow:
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

    def _load_vehicle_window(w: cw.Window) -> FragVehicleWindow:
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

    def _load_tuning(t: cwcloth.ClothInstanceTuning | None) -> EnvClothTuning | None:
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

    def _load_verlet_cloth(vc: cwcloth.VerletCloth) -> "VerletCloth":
        from ...cloths import VerletCloth, VerletClothEdge

        return VerletCloth(
            bb_min=vc.bb_min,
            bb_max=vc.bb_max,
            vertex_positions=vc.vertex_positions,
            vertex_normals=vc.vertex_normals,
            pinned_vertices_count=vc.pinned_vertices_count,
            switch_distance_up=vc.switch_distance_up,
            switch_distance_down=vc.switch_distance_down,
            cloth_weight=vc.cloth_weight,
            edges=[
                VerletClothEdge(e.vertex0, e.vertex1, e.length_sqr, e.weight0, e.compression_weight) for e in vc.edges
            ],
            custom_edges=[
                VerletClothEdge(e.vertex0, e.vertex1, e.length_sqr, e.weight0, e.compression_weight)
                for e in vc.custom_edges
            ],
            flags=vc.flags,
            bounds=load_bound(vc.bounds) if vc.bounds is not None else None,
        )

    def _load_controller(c: cwcloth.ClothController) -> "ClothController":
        from ...cloths import ClothBridgeSimGfx, ClothController

        return ClothController(
            name=c.name,
            flags=c.flags,
            bridge=ClothBridgeSimGfx(
                vertex_count_high=c.bridge.vertex_count_high,
                pin_radius_high=c.bridge.pin_radius_high,
                vertex_map_high=c.bridge.vertex_map_high,
            ),
            cloth_high=_load_verlet_cloth(c.cloth_high),
            morph_high_poly_count=c.morph_controller.map_data_high.poly_count,
        )

    def _load_cloth(c: cwcloth.EnvironmentCloth) -> EnvCloth:
        return EnvCloth(
            drawable=load_frag_drawable(c.drawable) if c.drawable else None,
            controller=_load_controller(c.controller),
            tuning=_load_tuning(c.tuning),
            user_data=list(np.fromstring(c.user_data or "", dtype=int, sep=" ")),
            flags=c.flags,
        )

    physics = None
    if f.physics:
        physics = PhysLodGroup(_load_lod(f.physics.lod1))

    return AssetFragment(
        name=f.name,
        flags=f.flags,
        drawable=load_frag_drawable(f.drawable) if f.drawable else None,
        extra_drawables=[load_frag_drawable(d) for d in f.extra_drawables],
        physics=physics,
        template_asset=FragmentTemplateAsset((f.unknown_c0 >> 8) & 0xFF),
        unbroken_elasticity=f.unknown_cc,
        gravity_factor=f.gravity_factor,
        buoyancy_factor=f.buoyancy_factor,
        glass_windows=[_load_glass_window(g) for g in f.glass_windows],
        vehicle_windows=[_load_vehicle_window(w) for w in f.vehicle_glass_windows],
        cloths=[_load_cloth(c) for c in f.cloths],
        lights=[_map_light_from_cw(light) for light in f.lights],
    )


def save_fragment_to_cw(asset: "AssetFragment", version: AssetVersion = AssetVersion.GEN8) -> cw.Fragment:
    from .bound import save_bound_to_cw
    from .cloth import to_cw_bridge, to_cw_morph_controller, to_cw_verlet_cloth_edge
    from .drawable import save_frag_drawable_to_cw

    f = cw.Fragment()
    f.name = asset.name
    f.flags = asset.flags
    f.unknown_c0 = (asset.template_asset.value & 0xFF) << 8
    f.unknown_cc = asset.unbroken_elasticity
    f.gravity_factor = asset.gravity_factor
    f.buoyancy_factor = asset.buoyancy_factor

    # Drawable
    if asset.drawable:
        f.drawable = save_frag_drawable_to_cw(asset.drawable, version)
        f.bounding_sphere_center = f.drawable.bounding_sphere_center
        f.bounding_sphere_radius = f.drawable.bounding_sphere_radius
    else:
        f.drawable = None
        f.bounding_sphere_center = Vector((0.0, 0.0, 0.0))
        f.bounding_sphere_radius = 0.0

    # Extra drawables
    f.extra_drawables = [save_frag_drawable_to_cw(d, version) for d in (asset.extra_drawables or [])]

    # Matrix set
    if asset.matrix_set:
        s = f.get_element("bones_transforms")
        s.unk.value = 1 if asset.matrix_set.is_skinned else 0
        s.value = [cw.BoneTransform("Item", m) for m in asset.matrix_set.matrices]

    # Physics
    if asset.physics:

        def _save_archetype(arch: PhysArchetype | None, tag: str) -> cw.Archetype | None:
            if arch is None:
                return None
            a = cw.Archetype(tag)
            a.name = arch.name
            a.bounds = save_bound_to_cw(arch.bounds)
            a.unknown_48 = arch.gravity_factor
            a.unknown_4c = arch.max_speed
            a.unknown_50 = arch.max_ang_speed
            a.unknown_54 = arch.buoyancy_factor
            a.mass = arch.mass
            a.mass_inv = arch.mass_inv
            a.inertia_tensor = Vector(arch.inertia)
            a.inertia_tensor_inv = Vector(arch.inertia_inv)
            a.bounds.ref_count = 2
            for c in a.bounds.children:
                if c is not None:
                    c.ref_count = 2
            return a

        def _save_child(child: PhysChild) -> cw.PhysicsChild:
            c = cw.PhysicsChild()
            c.bone_tag = child.bone_tag
            c.group_index = child.group_index
            c.pristine_mass = child.pristine_mass
            c.damaged_mass = child.damaged_mass
            c.drawable = save_frag_drawable_to_cw(child.drawable, version) if child.drawable else None
            if c.drawable:
                c.drawable.tag_name = "Drawable"
            c.damaged_drawable = (
                save_frag_drawable_to_cw(child.damaged_drawable, version) if child.damaged_drawable else None
            )
            if c.damaged_drawable:
                c.damaged_drawable.tag_name = "Drawable2"
            c.unk_float = child.min_breaking_impulse
            c.inertia_tensor = Vector(child.inertia)
            c.damaged_inertia_tensor = Vector(child.damaged_inertia)
            return c

        def _save_group(group: PhysGroup) -> cw.PhysicsGroup:
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

        def _save_lod(lod: PhysLod, tag: str) -> cw.PhysicsLOD:
            l = cw.PhysicsLOD(tag)
            l.archetype = _save_archetype(lod.archetype, "Archetype")
            l.damaged_archetype = _save_archetype(lod.damaged_archetype, "Archetype2")
            l.children.extend(_save_child(c) for c in lod.children)
            l.groups.extend(_save_group(g) for g in lod.groups)
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
        p.lod1 = _save_lod(asset.physics.lod1, "LOD1")
        p.lod2 = None
        p.lod3 = None
        f.physics = p

    # Glass windows
    def _save_glass_window(glass: FragGlassWindow) -> cw.GlassWindow:
        g = cw.GlassWindow()
        g.layout = cw.VertexLayoutList(type="GTAV4", value=["Position", "Normal", "Colour0", "TexCoord0", "TexCoord1"])
        g.flags = (glass.glass_type & 0xFF) | ((glass.shader_index & 0xFF) << 8)
        g.projection_matrix = Matrix((glass.pos_base, glass.pos_width, glass.pos_height))
        g.unk_float_13, g.unk_float_14 = glass.uv_min
        g.unk_float_15, g.unk_float_16 = glass.uv_max
        g.thickness = glass.thickness
        g.unk_float_18 = glass.bounds_offset_front
        g.unk_float_19 = glass.bounds_offset_back
        g.tangent = glass.tangent
        return g

    f.glass_windows = [_save_glass_window(g) for g in (asset.glass_windows or [])]

    # Vehicle windows
    def _save_vehicle_window(window: FragVehicleWindow) -> cw.Window:
        w = cw.Window()
        w.item_id = window.component_id
        w.unk_float_17 = window.data_min
        w.unk_float_18 = window.data_max
        w.cracks_texture_tiling = window.scale
        w.unk_ushort_1 = window.geometry_index
        w.projection_matrix = window.basis
        w.shattermap = shattermap_to_ascii(window.shattermap)
        return w

    f.vehicle_glass_windows = [_save_vehicle_window(w) for w in (asset.vehicle_windows or [])]

    # Cloths
    def _save_tuning(tuning: EnvClothTuning | None) -> cwcloth.ClothInstanceTuning | None:
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

    def _save_verlet_cloth(cloth) -> cwcloth.VerletCloth:
        from ...cloths import VerletCloth

        vc = cwcloth.VerletCloth("VerletCloth1")
        vc.bb_min = cloth.bb_min
        vc.bb_max = cloth.bb_max
        vc.vertex_positions = cloth.vertex_positions if cloth.vertex_positions else None
        vc.vertex_normals = cloth.vertex_normals if cloth.vertex_normals else None
        vc.pinned_vertices_count = cloth.pinned_vertices_count
        vc.cloth_weight = cloth.cloth_weight
        vc.switch_distance_up = cloth.switch_distance_up
        vc.switch_distance_down = cloth.switch_distance_down
        vc.edges = [to_cw_verlet_cloth_edge(e) for e in cloth.edges]
        vc.custom_edges = [to_cw_verlet_cloth_edge(e) for e in cloth.custom_edges]
        vc.flags = cloth.flags
        vc.bounds = save_bound_to_cw(cloth.bounds) if cloth.bounds else None
        vc.dynamic_pin_list_size = (len(cloth.vertex_positions) + 31) // 32
        return vc

    def _save_controller(controller) -> cwcloth.ClothController:
        cc = cwcloth.ClothController()
        cc.name = controller.name
        cc.flags = controller.flags
        cc.bridge = to_cw_bridge(controller.bridge)
        cc.cloth_high = _save_verlet_cloth(controller.cloth_high)
        cc.morph_controller = to_cw_morph_controller(controller)
        return cc

    def _save_cloth(cloth: EnvCloth) -> cwcloth.EnvironmentCloth:
        c = cwcloth.EnvironmentCloth()
        c.drawable = save_frag_drawable_to_cw(cloth.drawable, version) if cloth.drawable else None
        c.controller = _save_controller(cloth.controller)
        c.tuning = _save_tuning(cloth.tuning)
        c.user_data = " ".join(map(str, cloth.user_data)) if cloth.user_data else None
        c.flags = cloth.flags
        return c

    f.cloths = [_save_cloth(cloth) for cloth in (asset.cloths or [])]
    if f.cloths and f.drawable is None:
        cloth_drawable = f.cloths[0].drawable
        f.bounding_sphere_center = cloth_drawable.bounding_sphere_center
        f.bounding_sphere_radius = cloth_drawable.bounding_sphere_radius

    # Lights
    f.lights = [_map_light_to_cw(light) for light in (asset.lights or [])]

    return f
