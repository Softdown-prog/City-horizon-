"""Reference-grounded fairground Viking ship geometry pass.

The user-supplied real ride photos are treated as proportion/mechanism references only.
This module keeps deterministic CH Blender authoring while replacing the toy-like V2
silhouette with a tall A-frame fairground machine: blue square outer legs, yellow inner
bracing, a raised white loading deck, illuminated apex signage, a side artwork panel and
a deeper brown Viking longship. Runtime remains pre-rendered 2D RGBA.
"""
from __future__ import annotations

import math

import bpy
from mathutils import Vector

import build_ferris_wheel as fw


def _sphere(name, location, scale, material, parent=None, segments=20, rings=10):
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segments,
        ring_count=rings,
        location=tuple(location),
    )
    obj = bpy.context.object
    obj.name = name
    obj.scale = tuple(scale)
    obj.data.materials.append(material)
    bevel = obj.modifiers.new(name="EdgeSoftening", type="BEVEL")
    bevel.width = 0.025
    bevel.segments = 2
    if parent is not None:
        obj.parent = parent
    return obj


def beam_between(name, start, end, width, depth, material, parent=None, bevel=0.045):
    """Create a rectangular structural member whose local Z axis spans start->end."""
    a = Vector(start)
    b = Vector(end)
    delta = b - a
    if delta.length <= 1.0e-5:
        raise ValueError(f"Degenerate beam {name}")
    midpoint = (a + b) * 0.5
    obj = fw.box(
        name,
        (midpoint.x, midpoint.y, midpoint.z),
        (float(width), float(depth), float(delta.length)),
        material,
        bevel,
        parent,
    )
    obj.rotation_euler = delta.to_track_quat("Z", "Y").to_euler()
    return obj


def _triangle_panel(name, vertices, material, parent=None):
    mesh = bpy.data.meshes.new(f"{name}Mesh")
    mesh.from_pydata([tuple(v) for v in vertices], [], [(0, 1, 2)])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.append(material)
    if parent is not None:
        obj.parent = parent
    return obj


def hull_sections(g):
    """Deep fairground longship with lifted bow/stern and a broad passenger belly."""
    half_len = float(g["shipLength"]) * 0.5
    half_w = float(g["shipHalfWidth"])
    return [
        (-half_len, half_w * 0.20, -1.05, -1.85, -2.72),
        (-half_len * 0.88, half_w * 0.62, -1.35, -2.18, -3.25),
        (-half_len * 0.62, half_w * 0.92, -1.52, -2.44, -3.67),
        (-half_len * 0.28, half_w, -1.62, -2.55, -3.92),
        (0.0, half_w * 1.02, -1.66, -2.60, -4.02),
        (half_len * 0.28, half_w, -1.62, -2.55, -3.92),
        (half_len * 0.62, half_w * 0.92, -1.52, -2.44, -3.67),
        (half_len * 0.88, half_w * 0.62, -1.35, -2.18, -3.25),
        (half_len, half_w * 0.20, -1.05, -1.85, -2.72),
    ]


def _idle_overlay(root):
    overlay = bpy.data.objects.get("IdleLightOverlay")
    if overlay is None:
        overlay = fw.empty("IdleLightOverlay", (0.0, 0.0, 0.0), root)
        overlay["runtimeLayer"] = "idle_light_overlay"
        overlay["role"] = "attraction_idle_light_overlay"
        overlay["activeWhen"] = "ride_idle"
        overlay["disabledWhen"] = "ride_running"
        overlay["behavior"] = "blink"
        overlay["pattern"] = "alternating_groups_a_b"
    return overlay


def _lamp(root, overlay, name, position, normal_y, group, mats, radius=0.11):
    x, y, z = position
    housing_y = y + normal_y * 0.018
    bulb_y = y + normal_y * 0.075
    _sphere(
        f"{name}_Housing",
        (x, housing_y, z),
        (radius * 1.25, radius * 0.80, radius * 1.25),
        mats["steelDark"],
        root,
        segments=14,
        rings=7,
    )
    material = mats["lampCyan"] if group == "A" else mats["lampPink"]
    bulb = _sphere(
        f"{name}_Bulb",
        (x, bulb_y, z),
        (radius, radius * 0.68, radius),
        material,
        overlay,
        segments=14,
        rings=7,
    )
    bulb["blinkGroup"] = group
    bulb["runtimeLayer"] = "idle_light_overlay"
    return bulb


def _lights_along_beam(root, overlay, prefix, start, end, face_y, normal_y, count, mats, offset=0):
    a = Vector(start)
    b = Vector(end)
    for i in range(max(2, count)):
        t = 0.06 + 0.88 * (i / max(1, count - 1))
        p = a.lerp(b, t)
        group = "A" if (i + offset) % 2 == 0 else "B"
        _lamp(
            root,
            overlay,
            f"{prefix}_{i:02d}",
            (p.x, face_y, p.z),
            normal_y,
            group,
            mats,
            radius=0.105,
        )


def build_base(root, g, mats):
    """Raised travelling-fair platform: dark chassis, light deck and colored fascia."""
    base_w = float(g["baseWidth"])
    base_d = float(g["baseDepth"])
    chassis_h = float(g.get("baseHeight", 0.42))
    deck_top = float(g.get("platformTopZ", 1.02))

    base = fw.box(
        "BaseFrame",
        (0.0, 0.0, chassis_h * 0.5),
        (base_w, base_d, chassis_h),
        mats["steelDark"],
        0.08,
        root,
    )
    fw.box(
        "RaisedFairDeck",
        (0.0, 0.0, (chassis_h + deck_top) * 0.5),
        (base_w - 0.44, base_d - 0.46, deck_top - chassis_h),
        mats["platformWhite"],
        0.055,
        root,
    )
    fw.box(
        "DeckTopPlate",
        (0.0, 0.0, deck_top + 0.055),
        (base_w - 0.62, base_d - 0.64, 0.11),
        mats["steelLight"],
        0.03,
        root,
    )

    for y_sign, side in ((-1.0, "Front"), (1.0, "Back")):
        y = y_sign * (base_d * 0.5 - 0.07)
        fw.box(
            f"BaseWhiteFascia_{side}",
            (0.0, y, 0.62),
            (base_w - 0.28, 0.14, 0.82),
            mats["white"],
            0.035,
            root,
        )
        fw.box(
            f"BaseBlueTrim_{side}",
            (0.0, y + y_sign * 0.075, 0.96),
            (base_w - 0.40, 0.055, 0.12),
            mats["steelBlue"],
            0.018,
            root,
        )
        for i, x in enumerate((-5.7, -4.0, -2.3, -0.6, 1.1, 2.8, 4.5, 5.9)):
            mat = mats["red"] if i % 2 == 0 else mats["steelDark"]
            fw.box(
                f"BaseBadge_{side}_{i:02d}",
                (x, y + y_sign * 0.085, 0.55),
                (0.78, 0.045, 0.34),
                mat,
                0.02,
                root,
            )

    return base


def _build_art_panel(root, g, mats):
    """Decorative side-panel inspired by real travelling-fair ride artwork, not copied."""
    half_y = float(g["supportHalfDepth"])
    half_x = float(g["supportHalfWidth"])
    pivot_z = float(g["pivotZ"])
    y = half_y + 0.16
    left = (-half_x * 0.76, y, 1.28)
    right = (half_x * 0.76, y, 1.28)
    apex = (0.0, y, pivot_z - 0.48)
    _triangle_panel("BackdropCream", (left, right, apex), mats["panelCream"], root)

    center = (0.0, y + 0.012, 1.42)
    slices = [
        ((-half_x * 0.73, y + 0.018, 1.34), (-half_x * 0.34, y + 0.018, 1.34), center, "red"),
        ((-half_x * 0.31, y + 0.020, 1.34), (0.0, y + 0.020, pivot_z - 0.52), center, "yellow"),
        ((0.0, y + 0.022, pivot_z - 0.52), (half_x * 0.32, y + 0.022, 1.34), center, "white"),
        ((half_x * 0.34, y + 0.024, 1.34), (half_x * 0.72, y + 0.024, 1.34), center, "red"),
    ]
    for i, (a, b, c, mat_key) in enumerate(slices):
        _triangle_panel(f"BackdropAccent_{i:02d}", (a, b, c), mats[mat_key], root)

    beam_between(
        "BackdropMast",
        (0.0, y - 0.04, 1.36),
        (0.0, y - 0.04, pivot_z - 0.62),
        0.18,
        0.10,
        mats["steelDark"],
        root,
        bevel=0.025,
    )
    beam_between(
        "BackdropRuneSlashL",
        (-half_x * 0.58, y - 0.05, 1.72),
        (half_x * 0.12, y - 0.05, pivot_z - 1.05),
        0.12,
        0.08,
        mats["steelDark"],
        root,
        bevel=0.02,
    )
    beam_between(
        "BackdropRuneSlashR",
        (half_x * 0.58, y - 0.06, 1.72),
        (-half_x * 0.12, y - 0.06, pivot_z - 1.05),
        0.12,
        0.08,
        mats["steelDark"],
        root,
        bevel=0.02,
    )


def build_supports(root, g, mats):
    """Tall A-frame fairground structure grounded in the supplied real ride photos."""
    pivot_z = float(g["pivotZ"])
    half_x = float(g["supportHalfWidth"])
    half_y = float(g["supportHalfDepth"])
    beam_w = float(g.get("supportBeamWidth", 0.52))
    beam_d = float(g.get("supportBeamDepth", 0.40))
    brace_w = float(g.get("innerBraceWidth", 0.26))
    brace_d = float(g.get("innerBraceDepth", 0.22))
    support_objects = []
    overlay = _idle_overlay(root)

    for y_sign, side_name in ((-1.0, "Front"), (1.0, "Back")):
        y = y_sign * half_y
        normal_y = -1.0 if y_sign < 0.0 else 1.0
        leg_face_y = y + normal_y * (beam_d * 0.52 + 0.10)

        for x_sign, label in ((-1.0, "L"), (1.0, "R")):
            start = (x_sign * half_x, y, 0.72)
            end = (0.0, y, pivot_z)
            support = beam_between(
                f"OuterAFrame_{side_name}_{label}",
                start,
                end,
                beam_w,
                beam_d,
                mats["steelBlue"],
                root,
                bevel=0.045,
            )
            support_objects.append(support)
            fw.box(
                f"AFrameFoot_{side_name}_{label}",
                (x_sign * half_x, y, 0.50),
                (0.96, 0.88, 0.54),
                mats["steelBlue"],
                0.055,
                root,
            )
            fw.box(
                f"AFrameFootWhite_{side_name}_{label}",
                (x_sign * half_x, y + normal_y * 0.45, 0.52),
                (0.68, 0.08, 0.22),
                mats["white"],
                0.02,
                root,
            )
            _lights_along_beam(
                root,
                overlay,
                f"LegLamp_{side_name}_{label}",
                start,
                end,
                leg_face_y,
                normal_y,
                int(g.get("supportLampCount", 12)),
                mats,
                offset=0 if x_sign < 0 else 1,
            )

        lower_z = 1.30
        mid_z = pivot_z * 0.52
        high_z = pivot_z * 0.78
        beam_between(f"YellowBrace_{side_name}_L1", (-half_x * 0.77, y + y_sign * 0.03, lower_z), (-half_x * 0.22, y + y_sign * 0.03, mid_z), brace_w, brace_d, mats["yellow"], root, bevel=0.03)
        beam_between(f"YellowBrace_{side_name}_L2", (-half_x * 0.22, y + y_sign * 0.03, mid_z), (-half_x * 0.58, y + y_sign * 0.03, mid_z + 1.35), brace_w, brace_d, mats["yellow"], root, bevel=0.03)
        beam_between(f"YellowBrace_{side_name}_R1", (half_x * 0.77, y - y_sign * 0.03, lower_z), (half_x * 0.22, y - y_sign * 0.03, mid_z), brace_w, brace_d, mats["yellow"], root, bevel=0.03)
        beam_between(f"YellowBrace_{side_name}_R2", (half_x * 0.22, y - y_sign * 0.03, mid_z), (half_x * 0.58, y - y_sign * 0.03, mid_z + 1.35), brace_w, brace_d, mats["yellow"], root, bevel=0.03)
        beam_between(f"YellowBrace_{side_name}_TopL", (-half_x * 0.58, y, mid_z + 1.35), (0.0, y, high_z), brace_w, brace_d, mats["yellow"], root, bevel=0.03)
        beam_between(f"YellowBrace_{side_name}_TopR", (half_x * 0.58, y, mid_z + 1.35), (0.0, y, high_z), brace_w, brace_d, mats["yellow"], root, bevel=0.03)

        for z, span in ((2.0, 7.8), (4.0, 5.25), (5.95, 2.8)):
            fw.box(
                f"FrameTie_{side_name}_{int(z*100):03d}",
                (0.0, y, z),
                (span, beam_d * 0.72, 0.24),
                mats["steelDark"],
                0.035,
                root,
            )

    _build_art_panel(root, g, mats)

    fw.cylinder(
        "MainAxle",
        (0.0, 0.0, pivot_z),
        float(g["axleRadius"]),
        float(g["axleDepth"]),
        mats["steelMid"],
        rotation=(math.radians(90.0), 0.0, 0.0),
        parent=root,
        vertices=32,
    )

    for y_sign, side in ((-1.0, "Front"), (1.0, "Back")):
        y = y_sign * (half_y + 0.20)
        fw.cylinder(
            f"AxleHub_{side}",
            (0.0, y, pivot_z),
            float(g["axleRadius"]) * 1.55,
            0.34,
            mats["steelBlue"],
            rotation=(math.radians(90.0), 0.0, 0.0),
            parent=root,
            vertices=28,
        )
        fw.cylinder(
            f"AxleHubGold_{side}",
            (0.0, y + y_sign * 0.20, pivot_z),
            float(g["axleRadius"]) * 0.78,
            0.16,
            mats["yellow"],
            rotation=(math.radians(90.0), 0.0, 0.0),
            parent=root,
            vertices=24,
        )

        sign_z = pivot_z + 0.82
        fw.box(f"ApexSignBorder_{side}", (0.0, y + y_sign * 0.03, sign_z), (2.55, 0.22, 1.24), mats["steelBlue"], 0.06, root)
        fw.box(f"ApexSignFace_{side}", (0.0, y + y_sign * 0.16, sign_z), (2.08, 0.05, 0.82), mats["white"], 0.025, root)
        fw.box(f"ApexSignRuneVertical_{side}", (0.0, y + y_sign * 0.20, sign_z), (0.20, 0.035, 0.62), mats["red"], 0.015, root)
        fw.box(f"ApexSignRuneHorizontal_{side}", (0.0, y + y_sign * 0.205, sign_z), (1.06, 0.030, 0.16), mats["steelDark"], 0.012, root)
        for i in range(10):
            angle = 2.0 * math.pi * i / 10.0
            x = math.cos(angle) * 1.08
            z = sign_z + math.sin(angle) * 0.47
            group = "A" if i % 2 == 0 else "B"
            _lamp(root, overlay, f"ApexLamp_{side}_{i:02d}", (x, y + y_sign * 0.24, z), y_sign, group, mats, radius=0.09)

    return support_objects


def build_loading_zone(root, g, mats):
    """Raised front loading platform with side staircase and open boarding gate."""
    base_d = float(g["baseDepth"])
    top_z = float(g.get("platformTopZ", 1.02))
    platform_y = -base_d * 0.5 + 1.42
    platform_w = float(g.get("loadingPlatformWidth", 11.8))
    platform_d = float(g.get("loadingPlatformDepth", 2.25))

    fw.box("LoadingPlatform", (0.0, platform_y, top_z - 0.08), (platform_w, platform_d, 0.22), mats["platformWhite"], 0.045, root)
    fw.box("LoadingPlatformBlueEdge", (0.0, platform_y - platform_d * 0.5 - 0.02, top_z - 0.02), (platform_w, 0.12, 0.22), mats["steelBlue"], 0.025, root)

    rail_h = float(g.get("railingHeight", 0.92))
    rail_r = float(g.get("railingRadius", 0.045))
    left_x = -platform_w * 0.5 + 0.08
    right_x = platform_w * 0.5 - 0.08
    front_y = platform_y - platform_d * 0.5 + 0.05
    back_y = platform_y + platform_d * 0.5 - 0.05
    fw.build_railing(root, "LoadRailBack", (left_x, back_y), (right_x, back_y), top_z, rail_h, rail_r, mats["white"], 8)
    fw.build_railing(root, "LoadRailFrontL", (left_x, front_y), (2.10, front_y), top_z, rail_h, rail_r, mats["white"], 7)
    fw.build_railing(root, "LoadRailLeft", (left_x, front_y), (left_x, back_y), top_z, rail_h, rail_r, mats["white"], 4)
    fw.build_railing(root, "LoadRailRight", (right_x, front_y), (right_x, back_y), top_z, rail_h, rail_r, mats["white"], 4)

    stair_w = float(g.get("stairWidth", 2.6))
    stair_steps = max(5, int(g.get("stairSteps", 6)))
    stair_x = 3.95
    step_depth = 0.44
    for i in range(stair_steps):
        frac = (i + 1) / stair_steps
        h = top_z * frac
        y = front_y - (stair_steps - i - 0.5) * step_depth
        fw.box(f"BoardingStep_{i:02d}", (stair_x, y, h * 0.5), (stair_w, step_depth * 1.03, h), mats["platformWhite"], 0.025, root)
        fw.box(f"BoardingStepBlueEdge_{i:02d}", (stair_x, y - step_depth * 0.47, h + 0.02), (stair_w, 0.07, 0.08), mats["steelBlue"], 0.012, root)

    fw.box("OperatorConsole", (-4.85, platform_y + 0.18, top_z + 0.52), (0.80, 0.64, 1.04), mats["steelBlue"], 0.055, root)
    fw.box("OperatorConsoleFace", (-4.85, platform_y - 0.15, top_z + 0.59), (0.54, 0.035, 0.30), mats["red"], 0.02, root)


def _build_reference_prows(boat_root, g, mats):
    half_len = float(g["shipLength"]) * 0.5
    for sign, label in ((-1.0, "Left"), (1.0, "Right")):
        base_x = sign * (half_len - 0.12)
        beam_between(f"ProwStem_{label}", (base_x, 0.0, -1.55), (sign * (half_len + 0.34), 0.0, 0.30), 0.22, 0.22, mats["woodLight"], boat_root, bevel=0.045)
        beam_between(f"ProwGoldTip_{label}", (sign * (half_len + 0.31), 0.0, 0.22), (sign * (half_len + 0.52), 0.0, 0.72), 0.16, 0.16, mats["yellow"], boat_root, bevel=0.035)
        _sphere(f"ProwHead_{label}", (sign * (half_len + 0.58), 0.0, 0.78), (0.30, 0.26, 0.25), mats["yellow"], boat_root, segments=18, rings=9)
        fw.box(f"ProwRedCrest_{label}", (sign * (half_len + 0.46), 0.0, 0.46), (0.18, 0.30, 0.42), mats["red"], 0.03, boat_root)


def _boat_idle_lights(root, boat_root, pivot_z, boat_drop, g, mats):
    overlay = _idle_overlay(root)
    half_w = float(g["shipHalfWidth"])
    count = max(7, int(g.get("boatLampCount", 9)))
    x_span = float(g["shipLength"]) * 0.76
    local_z = -1.52
    world_z = pivot_z - boat_drop + local_z

    for side_index, (y_sign, side_name) in enumerate(((-1.0, "Front"), (1.0, "Back"))):
        local_y = y_sign * (half_w + 0.05)
        world_y = y_sign * (half_w + 0.17)
        for i in range(count):
            t = i / max(1, count - 1)
            x = -x_span * 0.5 + x_span * t
            group = "A" if (i + side_index) % 2 == 0 else "B"
            _sphere(f"BoatLamp_{side_name}_{i:02d}_Housing", (x, local_y, local_z), (0.13, 0.09, 0.13), mats["steelDark"], boat_root, segments=14, rings=7)
            bulb = _sphere(f"BoatLamp_{side_name}_{i:02d}_Bulb", (x, world_y, world_z), (0.095, 0.07, 0.095), mats["lampCyan"] if group == "A" else mats["lampPink"], overlay, segments=14, rings=7)
            bulb["blinkGroup"] = group
            bulb["runtimeLayer"] = "idle_light_overlay"


def build_swing_group(root, g, mats, base):
    pivot_z = float(g["pivotZ"])
    pivot = fw.empty("SwingPivot", (0.0, 0.0, pivot_z), root)
    pivot["animationReady"] = True
    pivot["rotationAxis"] = "Y"
    pivot["runtimeLayer"] = "motion_overlay"

    half_y = float(g["supportHalfDepth"])
    arm_w = float(g.get("swingArmWidth", 0.34))
    arm_d = float(g.get("swingArmDepth", 0.28))
    boat_drop = float(g.get("boatDrop", 2.35))
    joint_z = float(g.get("boatJointZ", -1.34))
    boat_root = fw.empty("BoatRoot", (0.0, 0.0, -boat_drop), pivot)
    boat_root["runtimeLayer"] = "motion_overlay"
    boat_root["role"] = "attraction.viking_ship_root"

    attach_x = float(g.get("boatAttachHalfX", 3.65))
    for x_sign, x_label in ((-1.0, "L"), (1.0, "R")):
        x = x_sign * attach_x
        for y_sign, side_label in ((-1.0, "Front"), (1.0, "Back")):
            start = (0.0, y_sign * (half_y - 0.28), 0.0)
            end = (x, y_sign * 1.22, -boat_drop + joint_z)
            beam_between(f"SwingArm_{side_label}_{x_label}", start, end, arm_w, arm_d, mats["yellow"], pivot, bevel=0.035)
            beam_between(f"SwingArmDarkStripe_{side_label}_{x_label}", (start[0], start[1] + y_sign * (arm_d * 0.50 + 0.018), start[2]), (end[0], end[1] + y_sign * (arm_d * 0.50 + 0.018), end[2]), arm_w * 0.24, 0.05, mats["steelDark"], pivot, bevel=0.015)
            _sphere(f"SwingJoint_{side_label}_{x_label}", end, (0.23, 0.23, 0.23), mats["steelBlue"], pivot, segments=18, rings=9)

    base.build_hull(boat_root, g, mats)
    _build_reference_prows(boat_root, g, mats)
    base.build_shields(boat_root, g, mats)
    base.build_seats_and_restraints(boat_root, g, mats)

    half_w = float(g["shipHalfWidth"])
    ship_len = float(g["shipLength"])
    for y_sign, side_name in ((-1.0, "Front"), (1.0, "Back")):
        y = y_sign * (half_w + 0.06)
        fw.box(f"HullBlackRail_{side_name}", (0.0, y, -1.38), (ship_len * 0.78, 0.09, 0.18), mats["steelDark"], 0.022, boat_root)
        fw.box(f"HullRedBand_{side_name}", (0.0, y + y_sign * 0.035, -1.63), (ship_len * 0.74, 0.055, 0.20), mats["red"], 0.018, boat_root)
        for i, x in enumerate((-3.9, -2.6, -1.3, 0.0, 1.3, 2.6, 3.9)):
            mat = mats["white"] if i % 2 == 0 else mats["red"]
            fw.box(f"HullPanel_{side_name}_{i:02d}", (x, y + y_sign * 0.045, -2.08), (0.82, 0.05, 0.62), mat, 0.025, boat_root)
            fw.cylinder(f"HullMedallion_{side_name}_{i:02d}", (x, y + y_sign * 0.09, -2.08), 0.19, 0.07, mats["yellow"], rotation=(math.radians(90.0), 0.0, 0.0), parent=boat_root, vertices=18)

    _boat_idle_lights(root, boat_root, pivot_z, boat_drop, g, mats)

    pivot.rotation_euler[1] = math.radians(float(g.get("previewSwingDegrees", 0.0)))
    return pivot
