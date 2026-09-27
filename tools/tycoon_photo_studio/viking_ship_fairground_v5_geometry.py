"""V5 fairground Viking ship geometry focused on the real ride silhouette.

This pass deliberately removes the roof/gantry read from earlier proxies. The supplied
real ride photos are used only for proportion and mechanism: tall open A-frames, compact
bearing housings, long pendulum arms, a deep passenger ship, raised loading platform and
edge lighting. Runtime remains pre-rendered 2D RGBA.
"""
from __future__ import annotations

import math
import bpy
from mathutils import Vector

import build_ferris_wheel as fw
import viking_ship_imposing_geometry as legacy


def beam_between(name, start, end, width, depth, material, parent=None, bevel=0.04):
    return legacy.beam_between(name, start, end, width, depth, material, parent, bevel)


def _sphere(name, location, scale, material, parent=None, segments=18, rings=9):
    return legacy._sphere(name, location, scale, material, parent, segments, rings)


def hull_sections(g):
    """Long, deep fairground ship: high bow/stern, broad side wall hiding most seats."""
    half_len = float(g["shipLength"]) * 0.5
    half_w = float(g["shipHalfWidth"])
    return [
        (-half_len, half_w * 0.18, -0.55, -1.30, -2.45),
        (-half_len * 0.90, half_w * 0.58, -0.92, -1.72, -3.00),
        (-half_len * 0.68, half_w * 0.90, -1.28, -2.14, -3.52),
        (-half_len * 0.34, half_w, -1.48, -2.34, -3.92),
        (0.0, half_w * 1.03, -1.56, -2.42, -4.08),
        (half_len * 0.34, half_w, -1.48, -2.34, -3.92),
        (half_len * 0.68, half_w * 0.90, -1.28, -2.14, -3.52),
        (half_len * 0.90, half_w * 0.58, -0.92, -1.72, -3.00),
        (half_len, half_w * 0.18, -0.55, -1.30, -2.45),
    ]


def _idle_overlay(root):
    return legacy._idle_overlay(root)


def _lamp(root, overlay, name, position, normal_y, group, mats, radius=0.105):
    return legacy._lamp(root, overlay, name, position, normal_y, group, mats, radius)


def _lights_on_leg(root, overlay, name, start, end, face_y, normal_y, count, mats, offset=0):
    a = Vector(start)
    b = Vector(end)
    for i in range(max(4, count)):
        t = 0.08 + 0.84 * (i / max(1, count - 1))
        p = a.lerp(b, t)
        _lamp(root, overlay, f"{name}_{i:02d}", (p.x, face_y, p.z), normal_y,
              "A" if (i + offset) % 2 == 0 else "B", mats, 0.10)


def build_base(root, g, mats):
    return legacy.build_base(root, g, mats)


def build_loading_zone(root, g, mats):
    return legacy.build_loading_zone(root, g, mats)


def build_supports(root, g, mats):
    """Two clean open A-frames with compact bearings instead of a roof-like top member."""
    pivot_z = float(g["pivotZ"])
    half_x = float(g["supportHalfWidth"])
    half_y = float(g["supportHalfDepth"])
    beam_w = float(g.get("supportBeamWidth", 0.58))
    beam_d = float(g.get("supportBeamDepth", 0.44))
    brace_w = float(g.get("innerBraceWidth", 0.26))
    brace_d = float(g.get("innerBraceDepth", 0.22))
    overlay = _idle_overlay(root)
    supports = []

    for y_sign, side in ((-1.0, "Front"), (1.0, "Back")):
        y = y_sign * half_y
        normal_y = -1.0 if y_sign < 0 else 1.0
        lamp_face_y = y + normal_y * (beam_d * 0.5 + 0.10)

        for x_sign, label in ((-1.0, "L"), (1.0, "R")):
            foot = (x_sign * half_x, y, 0.74)
            apex = (x_sign * 0.18, y, pivot_z - 0.18)
            leg = beam_between(f"MainAFrame_{side}_{label}", foot, apex, beam_w, beam_d,
                               mats["steelBlue"], root, 0.055)
            supports.append(leg)
            fw.box(f"MainAFrameFoot_{side}_{label}", (foot[0], foot[1], 0.48),
                   (1.02, 0.92, 0.58), mats["steelBlue"], 0.06, root)

            # A single inset yellow member follows each leg. This matches the real fairground
            # silhouette better than the criss-cross web used in the rejected proxies.
            inset_foot = (x_sign * (half_x - 0.72), y + y_sign * 0.035, 1.18)
            inset_apex = (x_sign * 0.62, y + y_sign * 0.035, pivot_z - 1.12)
            beam_between(f"InnerYellowLeg_{side}_{label}", inset_foot, inset_apex,
                         brace_w, brace_d, mats["yellow"], root, 0.03)

            _lights_on_leg(root, overlay, f"AFrameLamp_{side}_{label}", foot, apex,
                           lamp_face_y, normal_y, int(g.get("supportLampCount", 14)), mats,
                           0 if x_sign < 0 else 1)

        # Compact horizontal tie below the bearing. It stabilizes the silhouette without
        # becoming a roof over the ship.
        tie_z = pivot_z - 1.55
        fw.box(f"LowerApexTie_{side}", (0.0, y, tie_z),
               (3.35, beam_d * 0.82, 0.30), mats["yellow"], 0.04, root)

        # Large visible bearing disc on each side is a much stronger amusement-ride cue.
        bearing_y = y + normal_y * 0.26
        fw.cylinder(f"BearingHousing_{side}", (0.0, bearing_y, pivot_z),
                    0.78, 0.30, mats["steelBlue"],
                    rotation=(math.radians(90.0), 0.0, 0.0), parent=root, vertices=32)
        fw.cylinder(f"BearingRing_{side}", (0.0, bearing_y + normal_y * 0.18, pivot_z),
                    0.55, 0.14, mats["yellow"],
                    rotation=(math.radians(90.0), 0.0, 0.0), parent=root, vertices=28)
        fw.cylinder(f"BearingCap_{side}", (0.0, bearing_y + normal_y * 0.28, pivot_z),
                    0.28, 0.12, mats["red"],
                    rotation=(math.radians(90.0), 0.0, 0.0), parent=root, vertices=24)

        # Small lit header above each bearing, closer to the travelling-fair reference.
        fw.box(f"ApexSign_{side}", (0.0, y, pivot_z + 1.00),
               (2.15, 0.24, 0.95), mats["steelBlue"], 0.06, root)
        fw.box(f"ApexSignFace_{side}", (0.0, y + normal_y * 0.14, pivot_z + 1.00),
               (1.78, 0.05, 0.60), mats["white"], 0.025, root)
        for i, x in enumerate((-0.68, -0.34, 0.0, 0.34, 0.68)):
            _lamp(root, overlay, f"ApexLamp_{side}_{i}",
                  (x, y + normal_y * 0.22, pivot_z + 1.00), normal_y,
                  "A" if i % 2 == 0 else "B", mats, 0.09)

    # The real ride needs an axle, but it should not dominate like a giant black pipe.
    fw.cylinder("CompactMainAxle", (0.0, 0.0, pivot_z), float(g["axleRadius"]),
                float(g["axleDepth"]), mats["steelMid"],
                rotation=(math.radians(90.0), 0.0, 0.0), parent=root, vertices=28)
    return supports


def _build_fairground_boat_details(boat_root, g, mats):
    length = float(g["shipLength"])
    half_w = float(g["shipHalfWidth"])

    # Tall side fascia hides most of the benches, like the real travelling-fair ship.
    for y_sign, side in ((-1.0, "Front"), (1.0, "Back")):
        y = y_sign * (half_w + 0.06)
        fw.box(f"HighSideRed_{side}", (0.0, y, -1.72),
               (length * 0.76, 0.10, 0.62), mats["red"], 0.04, boat_root)
        fw.box(f"HighSideWhiteStripe_{side}", (0.0, y + y_sign * 0.06, -1.62),
               (length * 0.70, 0.045, 0.10), mats["white"], 0.02, boat_root)
        for i, x in enumerate((-4.45, -2.95, -1.48, 0.0, 1.48, 2.95, 4.45)):
            fw.cylinder(f"SideShield_{side}_{i}", (x, y + y_sign * 0.075, -1.80),
                        0.31, 0.08, mats["white"] if i % 2 else mats["steelDark"],
                        rotation=(math.radians(90.0), 0.0, 0.0), parent=boat_root, vertices=20)
            fw.cylinder(f"SideShieldBoss_{side}_{i}", (x, y + y_sign * 0.13, -1.80),
                        0.10, 0.05, mats["gold"],
                        rotation=(math.radians(90.0), 0.0, 0.0), parent=boat_root, vertices=16)

    # Lower, denser seating: visible enough to read as a ride but no longer dominates the hull.
    rows = max(6, int(g.get("seatRows", 8)))
    usable = length * 0.58
    for i in range(rows):
        x = -usable * 0.5 + usable * (i / max(1, rows - 1))
        fw.box(f"RideSeat_{i}", (x, 0.0, -1.34), (0.70, half_w * 1.34, 0.20),
               mats["seatRed"], 0.06, boat_root)
        fw.box(f"RideSeatBack_{i}", (x + 0.22, 0.0, -1.10), (0.16, half_w * 1.30, 0.34),
               mats["steelDark"], 0.04, boat_root)
        fw.cylinder_between(f"RideSafetyBar_{i}", (x - 0.08, -half_w * 0.58, -0.98),
                            (x - 0.08, half_w * 0.58, -0.98), 0.04, mats["white"], boat_root, vertices=12)


def build_swing_group(root, g, mats, base):
    pivot_z = float(g["pivotZ"])
    pivot = fw.empty("SwingPivot", (0.0, 0.0, pivot_z), root)
    pivot["animationReady"] = True
    pivot["rotationAxis"] = "Y"
    pivot["runtimeLayer"] = "motion_overlay"

    boat_drop = float(g["boatDrop"])
    half_y = float(g["supportHalfDepth"])
    attach_x = float(g.get("boatAttachHalfX", 4.20))
    arm_w = float(g.get("swingArmWidth", 0.38))
    arm_d = float(g.get("swingArmDepth", 0.30))
    joint_z = float(g.get("boatJointZ", -1.30))
    boat_root = fw.empty("BoatRoot", (0.0, 0.0, -boat_drop), pivot)
    boat_root["runtimeLayer"] = "motion_overlay"

    # Two long hanger pairs descend from the bearing area to widely-spaced ship joints.
    # Their steep profile is the defining mechanical silhouette of the real ride.
    for x_sign, label in ((-1.0, "L"), (1.0, "R")):
        x = x_sign * attach_x
        for y_sign, side in ((-1.0, "Front"), (1.0, "Back")):
            start = (x_sign * 0.40, y_sign * (half_y - 0.26), -0.18)
            end = (x, y_sign * 1.36, -boat_drop + joint_z)
            beam_between(f"LongHanger_{side}_{label}", start, end, arm_w, arm_d,
                         mats["yellow"], pivot, 0.045)
            _sphere(f"BoatJoint_{side}_{label}", end, (0.26, 0.26, 0.26), mats["steelBlue"], pivot)

    base.build_hull(boat_root, g, mats)
    base.build_viking_prows(boat_root, g, mats)
    _build_fairground_boat_details(boat_root, g, mats)

    # Idle bulbs live on their own overlay; housings remain attached to the boat.
    overlay = _idle_overlay(root)
    half_w = float(g["shipHalfWidth"])
    count = max(7, int(g.get("boatLampCount", 11)))
    span = float(g["shipLength"]) * 0.72
    world_z = pivot_z - boat_drop - 1.54
    for side_index, (y_sign, side) in enumerate(((-1.0, "Front"), (1.0, "Back"))):
        for i in range(count):
            t = i / max(1, count - 1)
            x = -span * 0.5 + span * t
            _sphere(f"BoatLampHousing_{side}_{i}", (x, y_sign * (half_w + 0.08), -1.54),
                    (0.12, 0.08, 0.12), mats["steelDark"], boat_root, 14, 7)
            bulb = _sphere(f"BoatLampBulb_{side}_{i}",
                           (x, y_sign * (half_w + 0.18), world_z),
                           (0.09, 0.065, 0.09),
                           mats["lampCyan"] if (i + side_index) % 2 == 0 else mats["lampPink"],
                           overlay, 14, 7)
            bulb["blinkGroup"] = "A" if (i + side_index) % 2 == 0 else "B"
            bulb["runtimeLayer"] = "idle_light_overlay"

    pivot.rotation_euler[1] = math.radians(float(g.get("previewSwingDegrees", 0.0)))
    return pivot
