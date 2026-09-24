"""Themed style pass for the shared City Horizon attraction entrance.

The mathematical blockout owns footprint, walking clearances and physical
proportions. This pass only dresses that approved structure with reusable park
language: a curved marquee arch, bulbs, pennants, kiosk facade, striped awning,
queue accents and readable turnstiles.

The game still consumes 2D prerendered sprites; Blender is authoring only.
"""
from __future__ import annotations

import math

import bpy


def _tag(obj, scene_gate, role, contact=False):
    scene_gate.tag(obj, role, ground_contact=contact)
    return obj


def _box(fw, root, scene_gate, name, location, dimensions, material, bevel=0.035, role="attraction.entry_detail"):
    return _tag(fw.box(name, location, dimensions, material, bevel, root), scene_gate, role)


def _sphere(root, scene_gate, name, location, radius, material, role="attraction.entry_light"):
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=20,
        ring_count=10,
        radius=float(radius),
        location=tuple(location),
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    obj.parent = root
    return _tag(obj, scene_gate, role)


def _extruded_polygon_xz(root, scene_gate, name, points, y, depth, material, role):
    """Create a small extruded sign/flag polygon lying in the XZ plane."""
    half = float(depth) * 0.5
    n = len(points)
    verts = [(float(x), float(y) - half, float(z)) for x, z in points]
    verts += [(float(x), float(y) + half, float(z)) for x, z in points]
    faces = [tuple(range(n - 1, -1, -1)), tuple(range(n, n * 2))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    mesh = bpy.data.meshes.new(f"{name}Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.append(material)
    obj.parent = root
    bevel = obj.modifiers.new(name="EdgeSoftening", type="BEVEL")
    bevel.width = min(0.035, float(depth) * 0.22)
    bevel.segments = 2
    return _tag(obj, scene_gate, role)


def _star(root, scene_gate, name, center, outer_r, inner_r, depth, material):
    cx, cy, cz = center
    pts = []
    for i in range(10):
        angle = math.radians(90.0) + i * math.pi / 5.0
        radius = outer_r if i % 2 == 0 else inner_r
        pts.append((cx + math.cos(angle) * radius, cz + math.sin(angle) * radius))
    return _extruded_polygon_xz(
        root, scene_gate, name, pts, cy, depth, material, "attraction.entry_emblem"
    )


def _flag(root, scene_gate, name, pole_x, pole_y, base_z, pole_h, pole_r, pole_mat, flag_mat, fw):
    pole = fw.cylinder(
        f"{name}Pole",
        (pole_x, pole_y, base_z + pole_h * 0.5),
        pole_r,
        pole_h,
        pole_mat,
        parent=root,
        vertices=18,
    )
    _tag(pole, scene_gate, "attraction.entry_flagpole")
    _sphere(root, scene_gate, f"{name}Finial", (pole_x, pole_y, base_z + pole_h), pole_r * 2.0, pole_mat, "attraction.entry_finial")
    flag_w = pole_h * 0.55
    flag_h = pole_h * 0.28
    pts = [
        (pole_x + pole_r * 0.8, base_z + pole_h * 0.84),
        (pole_x + pole_r * 0.8 + flag_w, base_z + pole_h * 0.68),
        (pole_x + pole_r * 0.8, base_z + pole_h * 0.56),
    ]
    _extruded_polygon_xz(root, scene_gate, f"{name}Pennant", pts, pole_y, pole_r * 1.3, flag_mat, "attraction.entry_flag")


def _arch_point(center_x, spring_z, half_span, rise, t):
    # t in [-1, 1]. Raised cosine gives a smooth amusement-park marquee arch.
    x = center_x + half_span * t
    z = spring_z + rise * math.cos(t * math.pi * 0.5)
    return x, z


def _arch_segment(fw, root, scene_gate, name, p0, p1, y, depth, thickness, material, role):
    x0, z0 = p0
    x1, z1 = p1
    dx = x1 - x0
    dz = z1 - z0
    length = math.hypot(dx, dz)
    obj = _box(
        fw,
        root,
        scene_gate,
        name,
        ((x0 + x1) * 0.5, y, (z0 + z1) * 0.5),
        (length + 0.025, depth, thickness),
        material,
        min(0.055, thickness * 0.22),
        role,
    )
    obj.rotation_euler[1] = -math.atan2(dz, dx)
    return obj


def _build_marquee(root, recipe, mats, fw, scene_gate):
    g = recipe["geometry"]
    center_x = float(g["gateCenterX"])
    y = float(g["gateCenterY"])
    clear_w = float(g["gateClearWidth"])
    col_w = float(g["gateColumnWidth"])
    half_span = clear_w * 0.5 + col_w * 0.92
    spring_z = float(g.get("archSpringZ", float(g["gateColumnHeight"]) + float(g["baseHeight"]) - 0.10))
    rise = float(g.get("archRise", 0.72))
    segments = max(8, int(g.get("archSegments", 14)))
    depth = float(g.get("marqueeDepth", 0.30))
    outer_t = float(g.get("marqueeOuterThickness", 0.40))
    inner_t = float(g.get("marqueeInnerThickness", 0.26))

    points = [_arch_point(center_x, spring_z, half_span, rise, -1.0 + 2.0 * i / segments) for i in range(segments + 1)]
    for i in range(segments):
        _arch_segment(fw, root, scene_gate, f"MarqueeGold_{i:02d}", points[i], points[i + 1], y - 0.015, depth, outer_t, mats["parkGold"], "attraction.entry_marquee")
        _arch_segment(fw, root, scene_gate, f"MarqueeBlue_{i:02d}", points[i], points[i + 1], y - depth * 0.34, depth * 0.60, inner_t, mats["parkBlue"], "attraction.entry_marquee")

    bulb_count = max(5, int(g.get("marqueeBulbCount", 7)))
    bulb_r = float(g.get("marqueeBulbRadius", 0.075))
    for i in range(bulb_count):
        t = -0.78 + 1.56 * i / max(1, bulb_count - 1)
        x, z = _arch_point(center_x, spring_z, half_span, rise, t)
        _sphere(root, scene_gate, f"MarqueeBulb_{i:02d}", (x, y - depth * 0.58, z + 0.015), bulb_r, mats["parkBulb"], "attraction.entry_marquee_bulb")

    crown_z = spring_z + rise + 0.05
    _star(root, scene_gate, "MarqueeStar", (center_x, y - depth * 0.64, crown_z), 0.31, 0.14, depth * 0.22, mats["parkGold"])

    # Dress the structural columns rather than replacing their mathematical datum.
    col_h = float(g["gateColumnHeight"])
    base_h = float(g["baseHeight"])
    for side, sign in (("Left", -1.0), ("Right", 1.0)):
        x = center_x + sign * (clear_w * 0.5 + col_w * 0.5)
        _box(fw, root, scene_gate, f"PortalBluePanel{side}", (x, y - float(g["gateColumnDepth"]) * 0.53, base_h + col_h * 0.66), (col_w * 0.78, 0.075, 0.64), mats["parkBlue"], 0.025, "attraction.entry_portal_trim")
        _box(fw, root, scene_gate, f"PortalGoldBandLow{side}", (x, y, base_h + 0.56), (col_w * 1.18, float(g["gateColumnDepth"]) * 1.18, 0.10), mats["parkGold"], 0.025, "attraction.entry_portal_trim")
        _box(fw, root, scene_gate, f"PortalGoldBandHigh{side}", (x, y, base_h + col_h - 0.28), (col_w * 1.18, float(g["gateColumnDepth"]) * 1.18, 0.10), mats["parkGold"], 0.025, "attraction.entry_portal_trim")
        _box(fw, root, scene_gate, f"PortalCap{side}", (x, y, base_h + col_h + 0.06), (col_w * 1.55, float(g["gateColumnDepth"]) * 1.52, 0.18), mats["parkCream"], 0.045, "attraction.entry_portal_cap")
        _flag(root, scene_gate, f"PortalFlag{side}", x, y, base_h + col_h + 0.15, float(g.get("flagPoleHeight", 0.72)), float(g.get("flagPoleRadius", 0.038)), mats["parkGold"], mats["parkCoral"], fw)


def _build_kiosk(root, recipe, mats, fw, scene_gate):
    g = recipe["geometry"]
    base_h = float(g["baseHeight"])
    kw = float(g["kioskWidth"])
    kd = float(g["kioskDepth"])
    kh = float(g["kioskHeight"])
    kx = float(g["kioskCenterX"])
    ky = float(g["kioskCenterY"])
    front_y = ky - kd * 0.5

    # Cream corner frames make the booth read as architecture instead of one blue box.
    frame_w = float(g.get("kioskFrameWidth", 0.10))
    for sign in (-1.0, 1.0):
        x = kx + sign * (kw * 0.5 - frame_w * 0.5)
        _box(fw, root, scene_gate, f"KioskFrontFrame_{'L' if sign < 0 else 'R'}", (x, front_y - 0.025, base_h + kh * 0.56), (frame_w, 0.10, kh * 0.78), mats["parkCream"], 0.02, "attraction.ticket_kiosk_trim")

    window_w = kw * 0.67
    window_h = kh * 0.43
    window_z = base_h + kh * 0.60
    _box(fw, root, scene_gate, "KioskWindowFrame", (kx, front_y - 0.055, window_z), (window_w + 0.14, 0.08, window_h + 0.14), mats["parkCream"], 0.025, "attraction.ticket_window")
    _box(fw, root, scene_gate, "KioskWindowGlass", (kx, front_y - 0.102, window_z), (window_w, 0.045, window_h), mats["parkGlass"], 0.018, "attraction.ticket_window_glass")
    _box(fw, root, scene_gate, "KioskCounterLedge", (kx, front_y - 0.16, base_h + float(g["counterHeight"])), (kw * 0.76, 0.24, 0.11), mats["parkGold"], 0.025, "attraction.ticket_counter")

    # Striped awning: broad readable stripes, not micro-detail.
    awning_w = kw + float(g.get("awningSideOverhang", 0.24)) * 2.0
    awning_d = float(g.get("awningDepth", 0.52))
    awning_z = base_h + kh * 0.91
    stripe_count = max(5, int(g.get("awningStripeCount", 7)))
    stripe_w = awning_w / stripe_count
    for i in range(stripe_count):
        x = kx - awning_w * 0.5 + stripe_w * (i + 0.5)
        mat = mats["parkCoral"] if i % 2 == 0 else mats["parkCream"]
        slat = _box(fw, root, scene_gate, f"AwningStripe_{i:02d}", (x, front_y - awning_d * 0.45, awning_z), (stripe_w * 1.02, awning_d, 0.10), mat, 0.025, "attraction.ticket_awning")
        slat.rotation_euler[0] = math.radians(-10.0)

    # Roof marquee repeats the same visual grammar as the main arch.
    roof_z = base_h + kh + 0.34
    plaque_w = kw * 0.95
    _box(fw, root, scene_gate, "KioskRoofSignGold", (kx, ky - 0.08, roof_z), (plaque_w + 0.16, 0.22, 0.56), mats["parkGold"], 0.07, "attraction.ticket_sign")
    _box(fw, root, scene_gate, "KioskRoofSignBlue", (kx, ky - 0.205, roof_z), (plaque_w, 0.10, 0.42), mats["parkBlue"], 0.06, "attraction.ticket_sign")
    _star(root, scene_gate, "KioskStar", (kx, ky - 0.27, roof_z), 0.24, 0.105, 0.07, mats["parkGold"])
    for i in range(5):
        x = kx - plaque_w * 0.38 + i * plaque_w * 0.19
        _sphere(root, scene_gate, f"KioskBulb_{i:02d}", (x, ky - 0.275, roof_z + 0.18), 0.045, mats["parkBulb"], "attraction.ticket_sign_bulb")


def _build_queue_accents(root, recipe, mats, fw, scene_gate):
    g = recipe["geometry"]
    base_h = float(g["baseHeight"])
    rail_h = float(g["railingHeight"])
    gx = float(g["gateCenterX"])
    gy = float(g["gateCenterY"])
    clear_w = float(g["gateClearWidth"])
    col_w = float(g["gateColumnWidth"])
    q_right = float(g["queueRightX"])
    q_div = float(g["queueDividerX"])
    q_front = gy - 0.12
    q_back = min(float(g["backY"]) - 0.12, q_front + float(g["queueDepth"]))
    q_left = gx + clear_w * 0.5 + col_w + 0.15

    # Large finials at the queue's structural turns keep the rails readable at game scale.
    cap_r = float(g.get("queueFinialRadius", 0.075))
    for i, (x, y) in enumerate(((q_right, q_front), (q_right, q_back), (q_left, q_back), (q_left, q_front + 0.35), (q_div, q_front + 0.30), (q_div, q_back - 0.18))):
        _sphere(root, scene_gate, f"QueueFinial_{i:02d}", (x, y, base_h + rail_h + cap_r * 0.25), cap_r, mats["parkCream"], "attraction.queue_finial")

    # Turnstile indicator faces and bars.
    turn_count = max(1, int(g["turnstileCount"]))
    usable = clear_w - 0.14
    th = float(g["turnstileHeight"])
    for i in range(turn_count):
        t = (i + 0.5) / turn_count - 0.5
        x = gx + t * usable
        y = gy - 0.40
        _box(fw, root, scene_gate, f"TurnstileIndicator_{i:02d}", (x, y - float(g["turnstileDepth"]) * 0.54, base_h + th * 0.66), (0.18, 0.055, 0.22), mats["parkGreen"], 0.02, "attraction.entry_turnstile_indicator")
        bar = fw.cylinder(
            f"TurnstileBar_{i:02d}",
            (x + 0.18, y, base_h + th * 0.58),
            0.025,
            0.52,
            mats["parkRail"],
            rotation=(0.0, math.radians(90.0), 0.0),
            parent=root,
            vertices=16,
        )
        _tag(bar, scene_gate, "attraction.entry_turnstile_bar")

    # Yellow safety nosings make the common entrance readable even when small.
    stair_w = float(g["stairWidth"])
    stair_d = float(g["stairDepth"])
    stair_steps = max(2, int(g["stairSteps"]))
    step_d = stair_d / stair_steps
    for i in range(stair_steps):
        h = base_h * (i + 1) / stair_steps
        y = float(g["frontY"]) - stair_d + step_d * (i + 1) - 0.035
        _box(fw, root, scene_gate, f"StepSafetyNosing_{i:02d}", (gx, y, h + 0.012), (stair_w * 0.92, 0.055, 0.025), mats["parkGold"], 0.01, "attraction.entry_step_nosing")


def apply_style_pass(root, recipe, mats, fw, scene_gate):
    before = set(bpy.context.scene.objects)
    _build_marquee(root, recipe, mats, fw, scene_gate)
    _build_kiosk(root, recipe, mats, fw, scene_gate)
    _build_queue_accents(root, recipe, mats, fw, scene_gate)
    return [obj for obj in bpy.context.scene.objects if obj not in before and obj.type == "MESH"]
