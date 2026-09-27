"""Open-footprint geometry pass for the City Horizon Viking ship rebuild V3.

V3 keeps the approved V2 anti-toy material and hull language, but deliberately removes
the cramped site read.  Front/rear A-frame planes are farther apart, the structural
cross member is kept lower, the boarding zone uses more of the site, and hanger joints
land farther outboard on the boat.  The result should read as a full-size 5x4 ride with
visible negative space rather than a tall machine squeezed into a small pad.
"""
from __future__ import annotations

import math

import bpy

import build_ferris_wheel as fw
import viking_ship_rebuild_v2_geometry as v2


beam_between = v2.beam_between
hull_sections = v2.hull_sections
build_base = v2.build_base


def build_supports(root, g, mats):
    supports = v2.build_supports(root, g, mats)

    # V2's cross brace sat high enough to visually box in the ride.  Keep the same
    # mechanical member but move it down so the tall upper volume stays open.
    target_z = float(g["pivotZ"]) * float(g.get("lowerCrossBraceHeightRatio", 0.30))
    for side in ("Front", "Back"):
        obj = bpy.data.objects.get(f"V2LowerCross_{side}")
        if obj is None:
            raise RuntimeError(f"CH_VIKING_V3_CROSS_BRACE_MISSING:{side}")
        obj.location.z = target_z
        obj.name = f"V3LowerCross_{side}"

    return supports


def build_loading_zone(root, g, mats):
    # The V2 builder is parameter-driven; V3's wider/deeper recipe turns it into a
    # substantial operating deck while retaining the same industrial language.
    return v2.build_loading_zone(root, g, mats)


def build_swing_group(root, g, mats):
    pivot_z = float(g["pivotZ"])
    pivot = fw.empty("SwingPivot", (0.0, 0.0, pivot_z), root)
    pivot["animationReady"] = True
    pivot["rotationAxis"] = "Y"
    pivot["runtimeLayer"] = "motion_overlay"

    boat_drop = float(g["boatDrop"])
    boat_root = fw.empty("BoatRoot", (0.0, 0.0, -boat_drop), pivot)
    boat_root["runtimeLayer"] = "motion_overlay"

    half_y = float(g["supportHalfDepth"])
    attach_x = float(g["boatAttachHalfX"])
    joint_y = float(g.get("boatJointHalfDepth", float(g["shipHalfWidth"]) * 0.84))
    arm_w = float(g["swingArmWidth"])
    arm_d = float(g["swingArmDepth"])
    joint_z = float(g["boatJointZ"])

    # Wider front/back suspension geometry is the core V3 change: the hangers start
    # near the widely separated A-frame planes and terminate farther outboard on the
    # hull, leaving visible breathing room around the ship.
    for x_sign, label in ((-1.0, "L"), (1.0, "R")):
        for y_sign, side in ((-1.0, "Front"), (1.0, "Back")):
            start = (x_sign * 0.42, y_sign * (half_y - 0.30), -0.18)
            end = (x_sign * attach_x, y_sign * joint_y, -boat_drop + joint_z)
            beam_between(
                f"V3LongHanger_{side}_{label}",
                start,
                end,
                arm_w,
                arm_d,
                mats["yellow"],
                pivot,
                float(g["secondaryBevel"]),
            )

            # Retain V2's non-toy clevis language but slightly widen the hardware so
            # the larger site and joint spacing still read mechanically connected.
            fw.box(
                f"V3ClevisPlateA_{side}_{label}",
                (end[0], end[1] - 0.17 * y_sign, end[2]),
                (0.46, 0.10, 0.54),
                mats["steelDark"],
                0.012,
                pivot,
            )
            fw.box(
                f"V3ClevisPlateB_{side}_{label}",
                (end[0], end[1] + 0.17 * y_sign, end[2]),
                (0.46, 0.10, 0.54),
                mats["steelDark"],
                0.012,
                pivot,
            )
            fw.cylinder(
                f"V3ClevisPin_{side}_{label}",
                end,
                0.13,
                0.50,
                mats["steelLight"],
                rotation=(math.radians(90.0), 0.0, 0.0),
                parent=pivot,
                vertices=16,
            )

    v2._build_hull(boat_root, g, mats)
    v2._build_prows(boat_root, g, mats)
    v2._build_seating(boat_root, g, mats)
    pivot.rotation_euler[1] = math.radians(float(g.get("previewSwingDegrees", 0.0)))
    return pivot
