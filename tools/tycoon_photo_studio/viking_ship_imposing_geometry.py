"""Imposing square-steel geometry pass for the City Park Viking ship.

This module intentionally contains geometry/detail logic only. The guarded CH Blender
quality stages stay owned by build_viking_ship_guarded.py. Runtime remains pre-rendered
2D RGBA; the 3D scene is an offline deterministic authoring source.
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


def hull_sections(g):
    """V2 hull: preserve the V1 plan while increasing vertical presence."""
    half_len = float(g["shipLength"]) * 0.5
    half_w = float(g["shipHalfWidth"])
    scale = float(g.get("hullVerticalScale", 1.0))
    anchor = -1.38

    def z(value):
        return anchor + (float(value) - anchor) * scale

    return [
        (-half_len, half_w * 0.28, z(-0.82), z(-1.88), z(-2.72)),
        (-half_len * 0.82, half_w * 0.72, z(-1.14), z(-2.02), z(-3.12)),
        (-half_len * 0.48, half_w * 0.98, z(-1.36), z(-2.16), z(-3.50)),
        (0.0, half_w, z(-1.42), z(-2.20), z(-3.78)),
        (half_len * 0.48, half_w * 0.98, z(-1.36), z(-2.16), z(-3.50)),
        (half_len * 0.82, half_w * 0.72, z(-1.14), z(-2.02), z(-3.12)),
        (half_len, half_w * 0.28, z(-0.82), z(-1.88), z(-2.72)),
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


def _lamp(root, overlay, name, position, normal_y, group, mats, radius=0.115):
    """Create a permanent dark socket plus a separable colored idle-overlay bulb."""
    x, y, z = position
    housing_y = y + normal_y * 0.015
    bulb_y = y + normal_y * 0.075
    _sphere(
        f"{name}_Housing",
        (x, housing_y, z),
        (radius * 1.24, radius * 0.78, radius * 1.24),
        mats["steelDark"],
        root,
        segments=16,
        rings=8,
    )
    bulb = _sphere(
        f"{name}_Bulb",
        (x, bulb_y, z),
        (radius, radius * 0.66, radius),
        mats["lampWarm"] if group == "A" else mats["lampRed"],
        overlay,
        segments=16,
        rings=8,
    )
    bulb["blinkGroup"] = group
    bulb["runtimeLayer"] = "idle_light_overlay"
    return bulb


def build_supports(root, g, mats):
    pivot_z = float(g["pivotZ"])
    half_x = float(g["supportHalfWidth"])
    half_y = float(g["supportHalfDepth"])
    beam_w = float(g.get("supportBeamWidth", 0.56))
    beam_d = float(g.get("supportBeamDepth", 0.44))
    brace_w = float(g.get("innerBraceWidth", 0.32))
    brace_d = float(g.get("innerBraceDepth", 0.26))
    axle_depth = float(g["axleDepth"])
    support_objects = []
    overlay = _idle_overlay(root)

    for y_sign, side_name in ((-1.0, "Front"), (1.0, "Back")):
        y = y_sign * half_y
        leg_records = []
        for x_sign, label in ((-1.0, "L"), (1.0, "R")):
            start = (x_sign * half_x, y, 0.34)
            end = (0.0, y, pivot_z)
            support = beam_between(
                f"SquareSupport_{side_name}_{label}",
                start,
                end,
                beam_w,
                beam_d,
                mats["steelDark"],
                root,
                bevel=0.055,
            )
            support_objects.append(support)
            leg_records.append((start, end, label))

            fw.box(
                f"SquareSupportFoot_{side_name}_{label}",
                (x_sign * half_x, y, 0.28),
                (0.92, 0.78, 0.30),
                mats["steelDark"],
                0.055,
                root,
            )
            fw.box(
                f"FootAccent_{side_name}_{label}",
                (x_sign * half_x, y - y_sign * 0.40, 0.34),
                (0.58, 0.10, 0.16),
                mats["red"],
                0.020,
                root,
            )

            inset_start = (x_sign * (half_x - 0.28), y - y_sign * (beam_d * 0.48 + 0.018), 0.78)
            inset_end = (x_sign * 0.10, y - y_sign * (beam_d * 0.48 + 0.018), pivot_z - 0.56)
            beam_between(
                f"SupportInset_{side_name}_{label}",
                inset_start,
                inset_end,
                beam_w * 0.24,
                0.055,
                mats["steelLight"],
                root,
                bevel=0.020,
            )

        cross_z = 3.10
        fw.box(
            f"SupportCross_{side_name}",
            (0.0, y, cross_z),
            (half_x * 1.48, beam_d * 0.88, 0.40),
            mats["red"],
            0.050,
            root,
        )
        fw.box(
            f"SupportCrossWhite_{side_name}",
            (0.0, y - y_sign * (beam_d * 0.46), cross_z),
            (half_x * 1.16, 0.075, 0.12),
            mats["white"],
            0.018,
            root,
        )

        beam_between(
            f"InnerBraceRise_{side_name}_A",
            (-half_x * 0.66, y + y_sign * 0.035, 1.18),
            (half_x * 0.20, y + y_sign * 0.035, pivot_z * 0.67),
            brace_w,
            brace_d,
            mats["steelMid"],
            root,
            bevel=0.040,
        )
        beam_between(
            f"InnerBraceRise_{side_name}_B",
            (half_x * 0.66, y - y_sign * 0.035, 1.18),
            (-half_x * 0.20, y - y_sign * 0.035, pivot_z * 0.67),
            brace_w,
            brace_d,
            mats["steelMid"],
            root,
            bevel=0.040,
        )

        lamp_count = max(5, int(g.get("supportLampCount", 8)))
        normal_y = -1.0 if y_sign < 0.0 else 1.0
        lamp_face_y = y + normal_y * (beam_d * 0.5 + 0.095)
        for leg_index, (start, end, label) in enumerate(leg_records):
            a = Vector(start)
            b = Vector(end)
            for i in range(lamp_count):
                t = 0.12 + 0.76 * (i / max(1, lamp_count - 1))
                p = a.lerp(b, t)
                group = "A" if (i + leg_index) % 2 == 0 else "B"
                _lamp(
                    root,
                    overlay,
                    f"SupportLamp_{side_name}_{label}_{i:02d}",
                    (p.x, lamp_face_y, p.z),
                    normal_y,
                    group,
                    mats,
                    radius=0.115,
                )

        cross_lamps = max(5, int(g.get("crossLampCount", 9)))
        for i in range(cross_lamps):
            t = i / max(1, cross_lamps - 1)
            x = -half_x * 0.57 + (half_x * 1.14) * t
            group = "A" if i % 2 == 0 else "B"
            _lamp(
                root,
                overlay,
                f"CrossLamp_{side_name}_{i:02d}",
                (x, y + normal_y * (beam_d * 0.5 + 0.095), cross_z),
                normal_y,
                group,
                mats,
                radius=0.105,
            )

    fw.box(
        "TopCrosshead",
        (0.0, 0.0, pivot_z),
        (1.82, half_y * 2.0 + 0.92, 0.76),
        mats["steelDark"],
        0.075,
        root,
    )
    for y_sign, name in ((-1.0, "Front"), (1.0, "Back")):
        y = y_sign * (half_y + 0.47)
        fw.box(
            f"TopCrossheadPlate_{name}",
            (0.0, y, pivot_z),
            (1.42, 0.10, 0.48),
            mats["red"],
            0.025,
            root,
        )
        for i in range(5):
            x = -0.52 + 1.04 * (i / 4.0)
            group = "A" if i % 2 == 0 else "B"
            _lamp(
                root,
                overlay,
                f"TopLamp_{name}_{i:02d}",
                (x, y + y_sign * 0.08, pivot_z),
                y_sign,
                group,
                mats,
                radius=0.105,
            )

    fw.cylinder(
        "MainAxle",
        (0.0, 0.0, pivot_z),
        float(g["axleRadius"]),
        axle_depth,
        mats["steelMid"],
        rotation=(math.radians(90.0), 0.0, 0.0),
        parent=root,
        vertices=32,
    )
    for y_sign, name in ((-1.0, "Front"), (1.0, "Back")):
        y = y_sign * (half_y + 0.22)
        fw.cylinder(
            f"AxleCollar_{name}",
            (0.0, y, pivot_z),
            float(g["axleRadius"]) * 1.32,
            0.28,
            mats["red"],
            rotation=(math.radians(90.0), 0.0, 0.0),
            parent=root,
            vertices=28,
        )
        fw.cylinder(
            f"AxleCap_{name}",
            (0.0, y + y_sign * 0.18, pivot_z),
            float(g["axleRadius"]) * 0.82,
            0.18,
            mats["white"],
            rotation=(math.radians(90.0), 0.0, 0.0),
            parent=root,
            vertices=24,
        )

    return support_objects


def _boat_idle_lights(root, boat_root, pivot_z, boat_drop, g, mats):
    """Idle-only bulbs are baked separately from the moving boat overlay."""
    overlay = _idle_overlay(root)
    half_w = float(g["shipHalfWidth"])
    count = max(5, int(g.get("boatLampCount", 7)))
    x_span = float(g["shipLength"]) * 0.66
    local_z = -1.54
    world_z = pivot_z - boat_drop + local_z

    for side_index, (y_sign, side_name) in enumerate(((-1.0, "Front"), (1.0, "Back"))):
        local_y = y_sign * (half_w + 0.06)
        world_y = y_sign * (half_w + 0.17)
        for i in range(count):
            t = i / max(1, count - 1)
            x = -x_span * 0.5 + x_span * t
            group = "A" if (i + side_index) % 2 == 0 else "B"
            _sphere(
                f"BoatLamp_{side_name}_{i:02d}_Housing",
                (x, local_y, local_z),
                (0.13, 0.09, 0.13),
                mats["steelDark"],
                boat_root,
                segments=16,
                rings=8,
            )
            bulb = _sphere(
                f"BoatLamp_{side_name}_{i:02d}_Bulb",
                (x, world_y, world_z),
                (0.095, 0.07, 0.095),
                mats["lampWarm"] if group == "A" else mats["lampRed"],
                overlay,
                segments=16,
                rings=8,
            )
            bulb["blinkGroup"] = group
            bulb["runtimeLayer"] = "idle_light_overlay"


def build_swing_group(root, g, mats, base):
    pivot_z = float(g["pivotZ"])
    pivot = fw.empty("SwingPivot", (0.0, 0.0, pivot_z), root)
    pivot["animationReady"] = True
    pivot["rotationAxis"] = "Y"
    pivot["runtimeLayer"] = "motion_overlay"

    half_y = float(g["supportHalfDepth"])
    arm_w = float(g.get("swingArmWidth", 0.40))
    arm_d = float(g.get("swingArmDepth", 0.30))
    boat_drop = float(g.get("boatDrop", 0.0))
    joint_z = float(g.get("boatJointZ", -1.42))
    boat_root = fw.empty("BoatRoot", (0.0, 0.0, -boat_drop), pivot)
    boat_root["runtimeLayer"] = "motion_overlay"
    boat_root["role"] = "attraction.viking_ship_root"

    for x, x_label in ((-2.92, "L"), (2.92, "R")):
        for y_sign, side_label in ((-1.0, "Front"), (1.0, "Back")):
            start = (0.0, y_sign * (half_y - 0.30), 0.0)
            end = (x, y_sign * 1.28, -boat_drop + joint_z)
            beam_between(
                f"SquareSwingArm_{side_label}_{x_label}",
                start,
                end,
                arm_w,
                arm_d,
                mats["steelMid"],
                pivot,
                bevel=0.045,
            )
            accent_offset = y_sign * (arm_d * 0.52 + 0.022)
            beam_between(
                f"SwingArmAccent_{side_label}_{x_label}",
                (start[0], start[1] + accent_offset, start[2]),
                (end[0], end[1] + accent_offset, end[2]),
                arm_w * 0.28,
                0.055,
                mats["red"],
                pivot,
                bevel=0.018,
            )
            _sphere(
                f"SwingJoint_{side_label}_{x_label}",
                end,
                (0.25, 0.25, 0.25),
                mats["red"],
                pivot,
                segments=20,
                rings=10,
            )
            fw.box(
                f"SwingJointPlate_{side_label}_{x_label}",
                (x, y_sign * 1.28, -boat_drop + joint_z - 0.03),
                (0.62, 0.16, 0.48),
                mats["white"],
                0.035,
                pivot,
            )

    base.build_hull(boat_root, g, mats)
    base.build_viking_prows(boat_root, g, mats)
    base.build_shields(boat_root, g, mats)
    base.build_seats_and_restraints(boat_root, g, mats)

    half_w = float(g["shipHalfWidth"])
    fw.box(
        "HullUpperAccentFront",
        (0.0, -half_w - 0.035, -1.46),
        (float(g["shipLength"]) * 0.72, 0.10, 0.20),
        mats["red"],
        0.025,
        boat_root,
    )
    fw.box(
        "HullUpperAccentBack",
        (0.0, half_w + 0.035, -1.46),
        (float(g["shipLength"]) * 0.72, 0.10, 0.20),
        mats["red"],
        0.025,
        boat_root,
    )
    for y_sign, side_name in ((-1.0, "Front"), (1.0, "Back")):
        fw.box(
            f"HullWhiteBadge_{side_name}",
            (0.0, y_sign * (half_w + 0.09), -1.44),
            (1.48, 0.065, 0.34),
            mats["white"],
            0.035,
            boat_root,
        )
        fw.box(
            f"HullGoldBadge_{side_name}",
            (0.0, y_sign * (half_w + 0.13), -1.44),
            (0.56, 0.045, 0.22),
            mats["gold"],
            0.025,
            boat_root,
        )

    _boat_idle_lights(root, boat_root, pivot_z, boat_drop, g, mats)

    pivot.rotation_euler[1] = math.radians(float(g.get("previewSwingDegrees", 0.0)))
    return pivot
