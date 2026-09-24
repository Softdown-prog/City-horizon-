"""Themed style pass for the shared City Horizon attraction entrance.

The mathematical blockout owns footprint, walking clearances and physical
proportions. This pass dresses that structure with reusable amusement-park
language while keeping the game runtime 2D and Blender authoring-only.
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
    """Create an extruded polygon in the XZ plane."""
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
    return _extruded_polygon_xz(root, scene_gate, name, pts, cy, depth, material, "attraction.entry_emblem")


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
    x = center_x + half_span * t
    z = spring_z + rise * math.cos(t * math.pi * 0.5)
    return x, z


def _arch_band_points(center_x, spring_z, half_span, rise, thickness, segments):
    outer = []
    inner = []
    half_t = thickness * 0.5
    for i in range(segments + 1):
        t = -1.0 + 2.0 * i / segments
        x, z = _arch_point(center_x, spring_z, half_span, rise, t)
        outer.append((x, z + half_t))
    for i in range(segments, -1, -1):
        t = -1.0 + 2.0 * i / segments
        x, z = _arch_point(center_x, spring_z, half_span, rise, t)
        inner.append((x, z - half_t))
    return outer + inner


def _crest_points(center_x, base_z, width, height, segments=12):
    half_w = width * 0.5
    pts = [(center_x - half_w, base_z)]
    for i in range(segments + 1):
        t = -1.0 + 2.0 * i / segments
        x = center_x + half_w * t
        z = base_z + height * (0.68 + 0.32 * math.cos(t * math.pi * 0.5))
        pts.append((x, z))
    pts.append((center_x + half_w, base_z))
    return pts


def _build_marquee(root, recipe, mats, fw, scene_gate):
    g = recipe["geometry"]
    center_x = float(g["gateCenterX"])
    y = float(g["gateCenterY"])
    clear_w = float(g["gateClearWidth"])
    col_w = float(g["gateColumnWidth"])
    col_d = float(g["gateColumnDepth"])
    base_h = float(g["baseHeight"])
    col_h = float(g["gateColumnHeight"])
    half_span = float(g.get("marqueeVisualHalfSpan", clear_w * 0.5 + col_w * 0.92))
    spring_z = float(g.get("archSpringZ", base_h + col_h - 0.10))
    rise = float(g.get("archRise", 0.72))
    segments = max(12, int(g.get("archSegments", 18)))
    depth = float(g.get("marqueeDepth", 0.30))
    outer_t = float(g.get("marqueeOuterThickness", 0.30))
    inner_t = float(g.get("marqueeInnerThickness", 0.19))

    # One continuous band instead of a row of chunky boxes. This is the main
    # silhouette correction for v3.
    gold_pts = _arch_band_points(center_x, spring_z, half_span, rise, outer_t, segments)
    blue_pts = _arch_band_points(center_x, spring_z, half_span, rise, inner_t, segments)
    _extruded_polygon_xz(root, scene_gate, "MarqueeGoldBand", gold_pts, y, depth, mats["parkGold"], "attraction.entry_marquee")
    _extruded_polygon_xz(root, scene_gate, "MarqueeBlueBand", blue_pts, y - depth * 0.40, depth * 0.62, mats["parkBlue"], "attraction.entry_marquee")

    # Short shoulder bars visually carry the wider marquee back into the
    # structural columns without changing the gate clearance datum.
    left_col_x = center_x - (clear_w * 0.5 + col_w * 0.5)
    right_col_x = center_x + (clear_w * 0.5 + col_w * 0.5)
    left_arch_x = center_x - half_span
    right_arch_x = center_x + half_span
    if left_col_x - left_arch_x > 0.05:
        _box(fw, root, scene_gate, "MarqueeShoulderLeft", ((left_col_x + left_arch_x) * 0.5, y, spring_z), (left_col_x - left_arch_x + 0.08, depth, outer_t), mats["parkGold"], 0.04, "attraction.entry_marquee_support")
    if right_arch_x - right_col_x > 0.05:
        _box(fw, root, scene_gate, "MarqueeShoulderRight", ((right_col_x + right_arch_x) * 0.5, y, spring_z), (right_arch_x - right_col_x + 0.08, depth, outer_t), mats["parkGold"], 0.04, "attraction.entry_marquee_support")

    bulb_count = max(7, int(g.get("marqueeBulbCount", 9)))
    bulb_r = float(g.get("marqueeBulbRadius", 0.068))
    for i in range(bulb_count):
        t = -0.78 + 1.56 * i / max(1, bulb_count - 1)
        x, z = _arch_point(center_x, spring_z, half_span, rise, t)
        _sphere(root, scene_gate, f"MarqueeBulb_{i:02d}", (x, y - depth * 0.59, z + 0.012), bulb_r, mats["parkBulb"], "attraction.entry_marquee_bulb")

    crown_z = spring_z + rise + 0.03
    _star(root, scene_gate, "MarqueeStar", (center_x, y - depth * 0.66, crown_z), 0.34, 0.15, depth * 0.22, mats["parkGold"])

    # Stronger towers with inset blue panels, gold collars and a small pennant
    # motif; proportions remain tied to the measured skeleton.
    for side, sign in (("Left", -1.0), ("Right", 1.0)):
        x = center_x + sign * (clear_w * 0.5 + col_w * 0.5)
        panel_z = base_h + col_h * 0.65
        _box(fw, root, scene_gate, f"PortalBluePanel{side}", (x, y - col_d * 0.54, panel_z), (col_w * 0.78, 0.075, 0.70), mats["parkBlue"], 0.025, "attraction.entry_portal_trim")
        tri = [(x - 0.11, panel_z + 0.12), (x + 0.11, panel_z + 0.12), (x, panel_z - 0.12)]
        _extruded_polygon_xz(root, scene_gate, f"PortalPennantMark{side}", tri, y - col_d * 0.63, 0.045, mats["parkGold"], "attraction.entry_portal_emblem")
        _box(fw, root, scene_gate, f"PortalGoldBandLow{side}", (x, y, base_h + 0.56), (col_w * 1.22, col_d * 1.18, 0.11), mats["parkGold"], 0.025, "attraction.entry_portal_trim")
        _box(fw, root, scene_gate, f"PortalGoldBandHigh{side}", (x, y, base_h + col_h - 0.28), (col_w * 1.22, col_d * 1.18, 0.11), mats["parkGold"], 0.025, "attraction.entry_portal_trim")
        _box(fw, root, scene_gate, f"PortalCap{side}", (x, y, base_h + col_h + 0.07), (col_w * 1.62, col_d * 1.55, 0.20), mats["parkCream"], 0.045, "attraction.entry_portal_cap")
        _box(fw, root, scene_gate, f"PortalCapGold{side}", (x, y, base_h + col_h + 0.19), (col_w * 1.34, col_d * 1.30, 0.08), mats["parkGold"], 0.03, "attraction.entry_portal_cap")
        _flag(root, scene_gate, f"PortalFlag{side}", x, y, base_h + col_h + 0.22, float(g.get("flagPoleHeight", 0.82)), float(g.get("flagPoleRadius", 0.040)), mats["parkGold"], mats["parkCoral"], fw)


def _build_kiosk(root, recipe, mats, fw, scene_gate):
    g = recipe["geometry"]
    base_h = float(g["baseHeight"])
    kw = float(g["kioskWidth"])
    kd = float(g["kioskDepth"])
    kh = float(g["kioskHeight"])
    kx = float(g["kioskCenterX"])
    ky = float(g["kioskCenterY"])
    front_y = ky - kd * 0.5

    frame_w = float(g.get("kioskFrameWidth", 0.10))
    for sign in (-1.0, 1.0):
        x = kx + sign * (kw * 0.5 - frame_w * 0.5)
        _box(fw, root, scene_gate, f"KioskFrontFrame_{'L' if sign < 0 else 'R'}", (x, front_y - 0.025, base_h + kh * 0.56), (frame_w, 0.10, kh * 0.78), mats["parkCream"], 0.02, "attraction.ticket_kiosk_trim")

    # Architectural bands reduce the large plain blue block in the previous proxy.
    _box(fw, root, scene_gate, "KioskBasePlinth", (kx, front_y - 0.035, base_h + 0.13), (kw * 0.92, 0.10, 0.18), mats["parkCream"], 0.025, "attraction.ticket_kiosk_trim")
    _box(fw, root, scene_gate, "KioskLowerGoldBand", (kx, front_y - 0.052, base_h + 0.45), (kw * 0.86, 0.075, 0.09), mats["parkGold"], 0.02, "attraction.ticket_kiosk_trim")
    _box(fw, root, scene_gate, "KioskRoofBlueFascia", (kx, front_y - 0.04, base_h + kh + 0.04), (kw * 1.08, 0.12, 0.18), mats["parkBlue"], 0.03, "attraction.ticket_kiosk_trim")

    window_w = kw * 0.67
    window_h = kh * 0.43
    window_z = base_h + kh * 0.60
    _box(fw, root, scene_gate, "KioskWindowFrame", (kx, front_y - 0.055, window_z), (window_w + 0.14, 0.08, window_h + 0.14), mats["parkCream"], 0.025, "attraction.ticket_window")
    _box(fw, root, scene_gate, "KioskWindowGlass", (kx, front_y - 0.102, window_z), (window_w, 0.045, window_h), mats["parkGlass"], 0.018, "attraction.ticket_window_glass")
    _box(fw, root, scene_gate, "KioskCounterLedge", (kx, front_y - 0.16, base_h + float(g["counterHeight"])), (kw * 0.76, 0.24, 0.11), mats["parkGold"], 0.025, "attraction.ticket_counter")

    awning_w = kw + float(g.get("awningSideOverhang", 0.26)) * 2.0
    awning_d = float(g.get("awningDepth", 0.55))
    awning_z = base_h + kh * 0.91
    stripe_count = max(5, int(g.get("awningStripeCount", 7)))
    stripe_w = awning_w / stripe_count
    valance_h = float(g.get("awningValanceHeight", 0.13))
    for i in range(stripe_count):
        x = kx - awning_w * 0.5 + stripe_w * (i + 0.5)
        mat = mats["parkCoral"] if i % 2 == 0 else mats["parkCream"]
        slat = _box(fw, root, scene_gate, f"AwningStripe_{i:02d}", (x, front_y - awning_d * 0.45, awning_z), (stripe_w * 1.02, awning_d, 0.10), mat, 0.025, "attraction.ticket_awning")
        slat.rotation_euler[0] = math.radians(-10.0)
        _box(fw, root, scene_gate, f"AwningValance_{i:02d}", (x, front_y - awning_d * 0.94, awning_z - valance_h * 0.42), (stripe_w * 0.96, 0.09, valance_h), mat, 0.03, "attraction.ticket_awning_valance")

    # Replace the old rectangular roof sign with a rounded crest silhouette.
    crest_w = kw * float(g.get("kioskCrestWidthScale", 1.10))
    crest_h = float(g.get("kioskCrestHeight", 0.68))
    inset = float(g.get("kioskCrestInset", 0.075))
    crest_base = base_h + kh + 0.12
    outer = _crest_points(kx, crest_base, crest_w, crest_h, 14)
    inner = _crest_points(kx, crest_base + inset, crest_w - inset * 2.0, crest_h - inset * 1.5, 14)
    _extruded_polygon_xz(root, scene_gate, "KioskCrestGold", outer, ky - 0.08, 0.22, mats["parkGold"], "attraction.ticket_sign")
    _extruded_polygon_xz(root, scene_gate, "KioskCrestBlue", inner, ky - 0.205, 0.10, mats["parkBlue"], "attraction.ticket_sign")
    star_z = crest_base + crest_h * 0.76
    _star(root, scene_gate, "KioskStar", (kx, ky - 0.27, star_z), 0.24, 0.105, 0.07, mats["parkGold"])
    for i in range(5):
        t = -0.72 + i * 0.36
        x = kx + t * crest_w * 0.42
        z = crest_base + crest_h * (0.72 + 0.18 * math.cos(t * math.pi * 0.5))
        _sphere(root, scene_gate, f"KioskBulb_{i:02d}", (x, ky - 0.275, z), 0.045, mats["parkBulb"], "attraction.ticket_sign_bulb")


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

    cap_r = float(g.get("queueFinialRadius", 0.078))
    points = ((q_right, q_front), (q_right, q_back), (q_left, q_back), (q_left, q_front + 0.35), (q_div, q_front + 0.30), (q_div, q_back - 0.18))
    for i, (x, y) in enumerate(points):
        _sphere(root, scene_gate, f"QueueFinial_{i:02d}", (x, y, base_h + rail_h + cap_r * 0.25), cap_r, mats["parkCream"], "attraction.queue_finial")
        _box(fw, root, scene_gate, f"QueuePostBase_{i:02d}", (x, y, base_h + 0.055), (0.17, 0.17, 0.11), mats["parkCream"], 0.025, "attraction.queue_post_base")

    turn_count = max(1, int(g["turnstileCount"]))
    usable = clear_w - 0.14
    th = float(g["turnstileHeight"])
    cap_h = float(g.get("turnstileCapHeight", 0.10))
    for i in range(turn_count):
        t = (i + 0.5) / turn_count - 0.5
        x = gx + t * usable
        y = gy - 0.40
        _box(fw, root, scene_gate, f"TurnstileBlueFace_{i:02d}", (x, y - float(g["turnstileDepth"]) * 0.535, base_h + th * 0.58), (0.24, 0.052, 0.42), mats["parkBlue"], 0.02, "attraction.entry_turnstile_trim")
        _box(fw, root, scene_gate, f"TurnstileIndicator_{i:02d}", (x, y - float(g["turnstileDepth"]) * 0.56, base_h + th * 0.68), (0.15, 0.038, 0.18), mats["parkGreen"], 0.018, "attraction.entry_turnstile_indicator")
        _box(fw, root, scene_gate, f"TurnstileCap_{i:02d}", (x, y, base_h + th + cap_h * 0.5), (0.34, float(g["turnstileDepth"]) * 1.08, cap_h), mats["parkCream"], 0.03, "attraction.entry_turnstile_trim")
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
