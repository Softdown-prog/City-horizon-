"""Fresh full-scale Viking/pirate ship ride geometry for City Horizon V5.

This module intentionally DOES NOT import or reuse Viking rebuild V2/V3/V4 geometry.
It is authored from generic CH Blender primitives only and follows the user's real
amusement-park pirate-ship references for proportion and mechanical layout.
"""
from __future__ import annotations

import math
import bpy
from mathutils import Vector
import build_ferris_wheel as fw


def beam_between(name, start, end, width, depth, material, parent=None, bevel=0.018):
    a = Vector(start)
    b = Vector(end)
    direction = b - a
    length = direction.length
    if length <= 1e-6:
        raise ValueError(f"Zero-length beam: {name}")
    midpoint = (a + b) * 0.5
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=midpoint)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = (float(width), float(depth), float(length))
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = direction.to_track_quat("Z", "Y")
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    if bevel > 0:
        mod = obj.modifiers.new(name="EdgeBreak", type="BEVEL")
        mod.width = float(bevel)
        mod.segments = 1
    if parent is not None:
        obj.parent = parent
    return obj


def hull_sections(g):
    half_len = float(g["shipLength"]) * 0.5
    half_w = float(g["shipHalfWidth"])
    # Long, deep fairground passenger hull with strongly raised bow/stern.
    return [
        (-half_len, half_w * 0.18, 1.15, -0.25, -2.65),
        (-half_len * 0.90, half_w * 0.48, 0.55, -0.78, -3.05),
        (-half_len * 0.70, half_w * 0.82, -0.15, -1.22, -3.42),
        (-half_len * 0.40, half_w * 0.98, -0.62, -1.54, -3.66),
        (0.0, half_w, -0.78, -1.67, -3.78),
        (half_len * 0.40, half_w * 0.98, -0.62, -1.54, -3.66),
        (half_len * 0.70, half_w * 0.82, -0.15, -1.22, -3.42),
        (half_len * 0.90, half_w * 0.48, 0.55, -0.78, -3.05),
        (half_len, half_w * 0.18, 1.15, -0.25, -2.65),
    ]


def _build_hull(boat_root, g, mats):
    sections = hull_sections(g)
    vertices = []
    ring_count = 6
    for x, width, top_z, mid_z, bottom_z in sections:
        vertices.extend([
            (x, -width, top_z),
            (x, -width * 0.94, mid_z),
            (x, -width * 0.30, bottom_z),
            (x, width * 0.30, bottom_z),
            (x, width * 0.94, mid_z),
            (x, width, top_z),
        ])
    faces = []
    for s in range(len(sections) - 1):
        a = s * ring_count
        b = (s + 1) * ring_count
        for r in range(ring_count):
            n = (r + 1) % ring_count
            faces.append((a + r, a + n, b + n, b + r))
    faces.append(tuple(range(ring_count - 1, -1, -1)))
    last = (len(sections) - 1) * ring_count
    faces.append(tuple(last + i for i in range(ring_count)))

    mesh = bpy.data.meshes.new("VikingV5FreshHullMesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    hull = bpy.data.objects.new("VikingV5FreshHull", mesh)
    bpy.context.scene.collection.objects.link(hull)
    hull.data.materials.append(mats["wood"])
    hull.parent = boat_root
    bevel = hull.modifiers.new(name="HullEdgeBreak", type="BEVEL")
    bevel.width = 0.055
    bevel.segments = 1

    # Long gunwale and structural side rail: full-size fairground machine, not toy ornament.
    for side, label in ((-1.0, "Front"), (1.0, "Back")):
        for i in range(len(sections) - 1):
            x0, w0, z0, _, _ = sections[i]
            x1, w1, z1, _, _ = sections[i + 1]
            fw.cylinder_between(
                f"V5Gunwale_{label}_{i:02d}",
                (x0, side * w0, z0 + 0.08),
                (x1, side * w1, z1 + 0.08),
                0.10, mats["woodLight"], boat_root, vertices=14,
            )
        y = side * (float(g["shipHalfWidth"]) + 0.04)
        fw.box(f"V5HullSteelRail_{label}", (0.0, y, -1.15),
               (float(g["shipLength"]) * 0.72, 0.055, 0.11), mats["steelDark"], 0.01, boat_root)
        fw.box(f"V5HullRedTrim_{label}", (0.0, y + side * 0.03, -1.34),
               (float(g["shipLength"]) * 0.69, 0.035, 0.12), mats["red"], 0.01, boat_root)

    fw.box("V5ShipDeck", (0.0, 0.0, float(g["shipDeckZ"])),
           (float(g["shipLength"]) * 0.74, float(g["shipHalfWidth"]) * 1.55, 0.16),
           mats["woodDark"], 0.018, boat_root)
    return hull


def _build_seating(boat_root, g, mats):
    rows = int(g.get("seatRows", 10))
    span = float(g["shipLength"]) * 0.60
    half_w = float(g["shipHalfWidth"])
    for i in range(rows):
        t = i / max(1, rows - 1)
        x = -span * 0.5 + span * t
        fw.box(f"V5SeatFrame_{i:02d}", (x, 0.0, -0.72),
               (0.56, half_w * 1.38, 0.10), mats["steelDark"], 0.01, boat_root)
        fw.box(f"V5SeatPad_{i:02d}", (x, 0.0, -0.63),
               (0.50, half_w * 1.32, 0.10), mats["seatRed"], 0.01, boat_root)
        fw.box(f"V5SeatBack_{i:02d}", (x + 0.18, 0.0, -0.34),
               (0.10, half_w * 1.30, 0.46), mats["steelMid"], 0.01, boat_root)
        fw.cylinder_between(f"V5SafetyBar_{i:02d}",
                            (x - 0.06, -half_w * 0.61, -0.20),
                            (x - 0.06, half_w * 0.61, -0.20),
                            0.035, mats["steelLight"], boat_root, vertices=10)


def _build_end_towers(boat_root, g, mats):
    half_len = float(g["shipLength"]) * 0.5
    for sign, label in ((-1.0, "L"), (1.0, "R")):
        beam_between(f"V5ProwSpine_{label}",
                     (sign * (half_len * 0.88), 0.0, 0.20),
                     (sign * (half_len * 1.03), 0.0, 2.55),
                     0.22, 0.34, mats["woodDark"], boat_root, 0.015)
        fw.box(f"V5ProwCap_{label}", (sign * (half_len * 1.04), 0.0, 2.65),
               (0.72, 0.74, 0.46), mats["woodLight"], 0.03, boat_root)
        fw.box(f"V5ProwPanel_{label}", (sign * (half_len * 0.995), -0.01, 1.55),
               (0.48, 0.90, 0.72), mats["red"], 0.02, boat_root)


def build_base(root, g, mats):
    base_h = float(g["baseHeight"])
    fw.box("V5RideBase", (0.0, 0.0, base_h * 0.5),
           (float(g["baseWidth"]), float(g["baseDepth"]), base_h), mats["steelDark"], 0.02, root)
    fw.box("V5RideDeck", (0.0, 0.0, base_h + float(g["deckHeight"]) * 0.5),
           (float(g["deckWidth"]), float(g["deckDepth"]), float(g["deckHeight"])), mats["platformWhite"], 0.015, root)
    return bpy.data.objects.get("V5RideBase")


def build_supports(root, g, mats):
    pivot_z = float(g["pivotZ"])
    hx = float(g["supportHalfWidth"])
    hy = float(g["supportHalfDepth"])
    bw = float(g["supportBeamWidth"])
    bd = float(g["supportBeamDepth"])
    supports = []
    # Two widely spaced A-frame planes, as in full-size fairground pirate ships.
    for y_sign, side in ((-1.0, "Front"), (1.0, "Back")):
        y = y_sign * hy
        for x_sign, label in ((-1.0, "L"), (1.0, "R")):
            foot = (x_sign * hx, y, 0.80)
            apex = (x_sign * 0.40, y, pivot_z - 0.25)
            supports.append(beam_between(f"V5MainLeg_{side}_{label}", foot, apex, bw, bd, mats["steelBlue"], root, 0.025))
            # Secondary outer brace reinforces the full-scale industrial silhouette.
            foot2 = (x_sign * (hx - 1.25), y, 0.85)
            apex2 = (x_sign * 0.75, y, pivot_z - 2.8)
            beam_between(f"V5SecondaryLeg_{side}_{label}", foot2, apex2, bw * 0.48, bd * 0.55, mats["steelDark"], root, 0.018)
        # Lower cross member only; preserve large open upper triangle.
        beam_between(f"V5LowerCross_{side}", (-hx * 0.66, y, 5.6), (hx * 0.66, y, 5.6),
                     0.34, 0.30, mats["steelDark"], root, 0.012)
    # High pivot shaft spanning front/back frame planes.
    fw.cylinder("V5PivotShaft", (0.0, 0.0, pivot_z), 0.42, hy * 2.0 + 0.7,
                mats["steelDark"], rotation=(math.radians(90.0), 0.0, 0.0), parent=root, vertices=20)
    for y, label in ((-hy, "Front"), (hy, "Back")):
        fw.cylinder(f"V5Bearing_{label}", (0.0, y, pivot_z), 0.95, 0.36,
                    mats["steelMid"], rotation=(math.radians(90.0), 0.0, 0.0), parent=root, vertices=20)
    return supports


def build_loading_zone(root, g, mats):
    z = float(g["platformTopZ"])
    width = float(g["loadingPlatformWidth"])
    depth = float(g["loadingPlatformDepth"])
    h = float(g["loadingPlatformHeight"])
    # Large side platform, offset toward the viewer/front for readable boarding relation.
    y = -float(g["baseDepth"]) * 0.5 + depth * 0.58
    fw.box("V5LoadingPlatform", (0.0, y, z - h * 0.5), (width, depth, h), mats["platform"], 0.02, root)
    rail_h = float(g["railingHeight"])
    rr = float(g["railingRadius"])
    for x in (-width * 0.48, width * 0.48):
        fw.cylinder_between(f"V5PlatformRailSide_{x:+.2f}", (x, y-depth*0.45, z), (x, y+depth*0.45, z), rr, mats["steelLight"], root, vertices=10)
        fw.cylinder_between(f"V5PlatformRailPost_{x:+.2f}", (x, y-depth*0.45, z), (x, y-depth*0.45, z+rail_h), rr, mats["steelLight"], root, vertices=10)
    fw.cylinder_between("V5PlatformFrontRail", (-width*0.48, y-depth*0.45, z+rail_h), (width*0.48, y-depth*0.45, z+rail_h), rr, mats["steelLight"], root, vertices=10)
    return bpy.data.objects.get("V5LoadingPlatform")


def build_swing_group(root, g, mats):
    pivot_z = float(g["pivotZ"])
    pivot = fw.empty("SwingPivot", (0.0, 0.0, pivot_z), root)
    pivot["animationReady"] = True
    pivot["rotationAxis"] = "Y"
    pivot["runtimeLayer"] = "motion_overlay"

    boat_drop = float(g["boatDrop"])
    boat_root = fw.empty("BoatRoot", (0.0, 0.0, -boat_drop), pivot)
    boat_root["runtimeLayer"] = "motion_overlay"

    hx = float(g["boatAttachHalfX"])
    hy = float(g["boatJointHalfDepth"])
    support_hy = float(g["supportHalfDepth"])
    arm_w = float(g["swingArmWidth"])
    arm_d = float(g["swingArmDepth"])
    # Four long suspension members, one to each side/depth corner of the ship.
    for x_sign, xl in ((-1.0, "L"), (1.0, "R")):
        for y_sign, yl in ((-1.0, "Front"), (1.0, "Back")):
            start = (x_sign * 0.55, y_sign * (support_hy - 0.35), -0.20)
            end = (x_sign * hx, y_sign * hy, -boat_drop + 0.10)
            beam_between(f"V5Suspension_{yl}_{xl}", start, end, arm_w, arm_d, mats["yellow"], pivot, 0.016)
            fw.cylinder(f"V5Clevis_{yl}_{xl}", end, 0.18, 0.56, mats["steelLight"],
                        rotation=(math.radians(90.0), 0.0, 0.0), parent=pivot, vertices=12)

    _build_hull(boat_root, g, mats)
    _build_end_towers(boat_root, g, mats)
    _build_seating(boat_root, g, mats)
    pivot.rotation_euler[1] = math.radians(float(g.get("previewSwingDegrees", 0.0)))
    return pivot
