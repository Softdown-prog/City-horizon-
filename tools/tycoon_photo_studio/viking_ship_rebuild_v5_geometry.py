"""Original procedural geometry pass for the City Horizon Viking ship ride.

The RollerCoaster Tycoon screenshot is used only for park-scale readability, overall
footprint occupation and the classic suspended-ship ride silhouette.  The actual ship,
support detailing, prows, seating and suspension are authored for City Horizon.

Canonical footprint: 5 tiles lateral x 4 tiles frontal.
No legacy miniature/plastic/toy geometry is reused here.
"""
from __future__ import annotations

import math

import bpy
from mathutils import Vector

import build_ferris_wheel as fw


def beam_between(name, start, end, width, depth, material, parent=None, bevel=0.03):
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
    if bevel > 0.0:
        mod = obj.modifiers.new(name="EdgeBreak", type="BEVEL")
        mod.width = float(bevel)
        mod.segments = 1
    if parent is not None:
        obj.parent = parent
    return obj


def hull_sections(g):
    """City Horizon longship profile: long, low, pointed and visibly asymmetric in detail."""
    half_len = float(g["shipLength"]) * 0.5
    half_w = float(g["shipHalfWidth"])
    return [
        (-half_len,        half_w * 0.10, -0.05, -0.90, -2.10),
        (-half_len * 0.90, half_w * 0.46, -0.42, -1.32, -2.68),
        (-half_len * 0.68, half_w * 0.82, -0.78, -1.68, -3.08),
        (-half_len * 0.36, half_w * 0.98, -1.02, -1.94, -3.38),
        (0.0,              half_w * 1.03, -1.10, -2.02, -3.50),
        (half_len * 0.36,  half_w * 0.98, -1.02, -1.94, -3.38),
        (half_len * 0.68,  half_w * 0.82, -0.78, -1.68, -3.08),
        (half_len * 0.90,  half_w * 0.46, -0.42, -1.32, -2.68),
        (half_len,         half_w * 0.10, -0.05, -0.90, -2.10),
    ]


def _rail_line(name, a, b, g, mats, root):
    radius = float(g.get("railingRadius", 0.038))
    fw.cylinder_between(name, a, b, radius, mats["steelMid"], root, vertices=10)


def build_base(root, g, mats):
    """Thin integrated ride pad; deliberately not a tall glossy pedestal."""
    base_h = float(g["baseHeight"])
    deck_h = float(g["deckHeight"])
    fw.box("CHR_VikingPadFoundation", (0.0, 0.0, base_h * 0.5),
           (float(g["baseWidth"]), float(g["baseDepth"]), base_h),
           mats["steelDark"], 0.008, root)
    fw.box("CHR_VikingRidePad", (0.0, 0.0, base_h + deck_h * 0.5),
           (float(g["deckWidth"]), float(g["deckDepth"]), deck_h),
           mats["platformWhite"], 0.006, root)

    top_z = base_h + deck_h + 0.008
    for i in (-2, -1, 0, 1, 2):
        y = i * float(g["deckDepth"]) / 6.0
        fw.box(f"CHR_PadJoint_{i:+d}", (0.0, y, top_z),
               (float(g["deckWidth"]) - 0.45, 0.018, 0.012),
               mats["platform"], 0.002, root)
    return root


def build_supports(root, g, mats):
    """Tall open A-frame with restrained mechanical detail and large negative spaces."""
    pivot_z = float(g["pivotZ"])
    half_x = float(g["supportHalfWidth"])
    half_y = float(g["supportHalfDepth"])
    beam_w = float(g["supportBeamWidth"])
    beam_d = float(g["supportBeamDepth"])
    inner_w = float(g["innerBraceWidth"])
    inner_d = float(g["innerBraceDepth"])
    bevel = float(g["primaryBevel"])
    supports = []

    for y_sign, side in ((-1.0, "Front"), (1.0, "Back")):
        y = y_sign * half_y
        for x_sign, label in ((-1.0, "L"), (1.0, "R")):
            foot = (x_sign * half_x, y, 0.62)
            apex = (x_sign * 0.18, y, pivot_z - 0.20)
            supports.append(beam_between(
                f"CHR_MainLeg_{side}_{label}", foot, apex,
                beam_w, beam_d, mats["steelDark"], root, bevel))

            inner_foot = (x_sign * (half_x - 0.62), y, 0.78)
            inner_apex = (x_sign * 0.56, y, pivot_z * 0.78)
            beam_between(f"CHR_InnerBrace_{side}_{label}", inner_foot, inner_apex,
                         inner_w, inner_d, mats["steelMid"], root,
                         max(0.006, bevel * 0.55))

            fw.box(f"CHR_FootPlate_{side}_{label}", (foot[0], foot[1], 0.48),
                   (0.78, 0.66, 0.10), mats["steelMid"], 0.008, root)
            for bx in (-0.25, 0.25):
                for by in (-0.19, 0.19):
                    fw.cylinder(f"CHR_FootBolt_{side}_{label}_{bx:+.2f}_{by:+.2f}",
                                (foot[0] + bx, foot[1] + by, 0.56),
                                0.045, 0.075, mats["steelLight"],
                                parent=root, vertices=10)

        z = pivot_z * 0.28
        beam_between(f"CHR_LowCross_{side}", (-half_x * 0.80, y, z),
                     (half_x * 0.80, y, z),
                     float(g["lowerCrossBraceWidth"]),
                     float(g["lowerCrossBraceDepth"]),
                     mats["steelMid"], root, 0.008)

    fw.cylinder("CHR_MainAxle", (0.0, 0.0, pivot_z),
                float(g["axleRadius"]), float(g["axleDepth"]),
                mats["steelMid"], rotation=(math.radians(90.0), 0.0, 0.0),
                parent=root, vertices=16)
    return supports


def build_loading_zone(root, g, mats):
    """Broad queue and boarding area so the full 5x4 footprint reads at gameplay scale."""
    top_z = float(g["baseHeight"]) + float(g["deckHeight"])
    rail_z = top_z + float(g["railingHeight"])
    half_w = float(g["loadingPlatformWidth"]) * 0.5
    half_d = float(g["loadingPlatformDepth"]) * 0.5

    fw.box("CHR_BoardingStrip", (0.0, -1.35, top_z + 0.055),
           (float(g["loadingPlatformWidth"]), float(g["loadingPlatformDepth"]), 0.11),
           mats["panelCream"], 0.006, root)

    front_y = -half_d
    for x0, x1, idx in ((-half_w, -2.0, 0), (2.0, half_w, 1)):
        _rail_line(f"CHR_FrontRail_{idx}", (x0, front_y, rail_z),
                   (x1, front_y, rail_z), g, mats, root)
        for x in (x0, x1):
            _rail_line(f"CHR_FrontPost_{idx}_{x:+.2f}", (x, front_y, top_z),
                       (x, front_y, rail_z), g, mats, root)

    queue_y0 = front_y + 0.78
    queue_y1 = min(half_d - 0.55, queue_y0 + 3.0)
    for i, x in enumerate((-4.25, -1.42, 1.42, 4.25)):
        _rail_line(f"CHR_QueueTop_{i}", (x, queue_y0, rail_z),
                   (x, queue_y1, rail_z), g, mats, root)
        for y in (queue_y0, queue_y1):
            _rail_line(f"CHR_QueuePost_{i}_{y:+.2f}", (x, y, top_z),
                       (x, y, rail_z), g, mats, root)

    steps = int(g.get("stairSteps", 5))
    step_w = float(g["stairWidth"])
    step_d = float(g["stairDepth"]) / max(1, steps)
    for i in range(steps):
        h = (i + 1) * (top_z / max(1, steps))
        y = front_y - float(g["stairDepth"]) + (i + 0.5) * step_d
        fw.box(f"CHR_EntryStep_{i:02d}", (0.0, y, h * 0.5),
               (step_w, step_d + 0.02, h), mats["platformWhite"], 0.004, root)
    return root


def _build_city_horizon_hull(boat_root, g, mats):
    sections = hull_sections(g)
    vertices = []
    ring_count = 6
    for x, width, top_z, mid_z, bottom_z in sections:
        vertices.extend([
            (x, -width, top_z),
            (x, -width * 0.88, mid_z),
            (x, -width * 0.30, bottom_z),
            (x,  width * 0.30, bottom_z),
            (x,  width * 0.88, mid_z),
            (x,  width, top_z),
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

    mesh = bpy.data.meshes.new("CityHorizonVikingHullMesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    hull = bpy.data.objects.new("CityHorizonVikingHull", mesh)
    bpy.context.scene.collection.objects.link(hull)
    hull.data.materials.append(mats["wood"])
    hull.parent = boat_root
    bevel = hull.modifiers.new(name="HullEdgeBreak", type="BEVEL")
    bevel.width = 0.038
    bevel.segments = 1

    half_w = float(g["shipHalfWidth"])
    length = float(g["shipLength"])

    # Long clinker-like bands are intentionally sparse and angular for game readability.
    for side, label in ((-1.0, "Near"), (1.0, "Far")):
        y = side * (half_w + 0.045)
        for i, z in enumerate((-1.40, -1.72, -2.03, -2.34)):
            span = length * (0.78 - i * 0.045)
            fw.box(f"CHR_HullBand_{label}_{i:02d}", (0.0, y, z),
                   (span, 0.034, 0.065), mats["woodDark"], 0.006, boat_root)
        fw.box(f"CHR_GunwaleAccent_{label}", (0.0, y + side * 0.028, -1.17),
               (length * 0.78, 0.035, 0.085), mats["red"], 0.006, boat_root)

    # Deck uses alternating timber strips rather than a single molded slab.
    deck_z = float(g["shipDeckZ"])
    fw.box("CHR_ShipDeck", (0.0, 0.0, deck_z),
           (length * 0.72, half_w * 1.42, 0.14), mats["woodDark"], 0.012, boat_root)
    for y in (-0.70, -0.35, 0.0, 0.35, 0.70):
        fw.box(f"CHR_DeckPlank_{y:+.2f}", (0.0, y, deck_z + 0.08),
               (length * 0.68, 0.20, 0.025), mats["woodLight"], 0.003, boat_root)
    return hull


def _build_city_horizon_prows(boat_root, g, mats):
    half_len = float(g["shipLength"]) * 0.5

    # Bow: taller carved animal-head silhouette, kept angular and original.
    bow = 1.0
    beam_between("CHR_BowStemLower", (bow * half_len * 0.90, 0.0, -0.72),
                 (bow * half_len * 1.02, 0.0, 0.32), 0.22, 0.30,
                 mats["woodLight"], boat_root, 0.018)
    beam_between("CHR_BowStemUpper", (bow * half_len * 1.02, 0.0, 0.32),
                 (bow * half_len * 1.08, 0.0, 1.38), 0.18, 0.25,
                 mats["woodDark"], boat_root, 0.014)
    fw.box("CHR_BowCarvedHead", (bow * half_len * 1.105, 0.0, 1.48),
           (0.52, 0.40, 0.30), mats["woodLight"], 0.018, boat_root)
    fw.box("CHR_BowSnout", (bow * half_len * 1.15, -0.01, 1.42),
           (0.30, 0.30, 0.16), mats["woodDark"], 0.012, boat_root)

    # Stern: shorter forked ornament so the City Horizon boat is not a mirrored copy.
    stern = -1.0
    beam_between("CHR_SternStem", (stern * half_len * 0.91, 0.0, -0.72),
                 (stern * half_len * 1.04, 0.0, 0.78), 0.22, 0.30,
                 mats["woodLight"], boat_root, 0.018)
    for y_sign in (-1.0, 1.0):
        beam_between(f"CHR_SternFork_{'N' if y_sign < 0 else 'F'}",
                     (stern * half_len * 1.04, 0.0, 0.72),
                     (stern * half_len * 1.09, y_sign * 0.28, 1.20),
                     0.14, 0.16, mats["woodDark"], boat_root, 0.012)


def _build_city_horizon_seating(boat_root, g, mats):
    rows = int(g.get("seatRows", 8))
    span = float(g["shipLength"]) * 0.54
    half_w = float(g["shipHalfWidth"])
    for i in range(rows):
        x = -span * 0.5 + span * (i / max(1, rows - 1))
        fw.box(f"CHR_SeatFrame_{i:02d}", (x, 0.0, -1.10),
               (0.55, half_w * 1.24, 0.09), mats["steelDark"], 0.010, boat_root)
        fw.box(f"CHR_SeatBench_{i:02d}", (x, 0.0, -1.01),
               (0.48, half_w * 1.18, 0.07), mats["seatRed"], 0.010, boat_root)
        fw.box(f"CHR_SeatBack_{i:02d}", (x + 0.17, 0.0, -0.80),
               (0.09, half_w * 1.16, 0.34), mats["woodLight"], 0.010, boat_root)
        fw.cylinder_between(f"CHR_SafetyBar_{i:02d}",
                            (x - 0.08, -half_w * 0.54, -0.70),
                            (x - 0.08,  half_w * 0.54, -0.70),
                            0.030, mats["steelLight"], boat_root, vertices=10)


def build_swing_group(root, g, mats):
    """Original CH suspension + longship; no V2/V3 ship geometry is reused."""
    pivot_z = float(g["pivotZ"])
    pivot = fw.empty("SwingPivot", (0.0, 0.0, pivot_z), root)
    pivot["animationReady"] = True
    pivot["rotationAxis"] = "Y"
    pivot["runtimeLayer"] = "motion_overlay"
    pivot["assetIdentity"] = "CITY_HORIZON_ORIGINAL_VIKING_LONGSHIP"

    boat_drop = float(g["boatDrop"])
    boat_root = fw.empty("BoatRoot", (0.0, 0.0, -boat_drop), pivot)
    boat_root["runtimeLayer"] = "motion_overlay"

    half_y = float(g["supportHalfDepth"])
    attach_x = float(g["boatAttachHalfX"])
    joint_y = float(g.get("boatJointHalfDepth", float(g["shipHalfWidth"]) * 0.84))
    arm_w = float(g["swingArmWidth"])
    arm_d = float(g["swingArmDepth"])
    joint_z = float(g["boatJointZ"])

    for x_sign, label in ((-1.0, "L"), (1.0, "R")):
        for y_sign, side in ((-1.0, "Front"), (1.0, "Back")):
            start = (x_sign * 0.42, y_sign * (half_y - 0.30), -0.18)
            end = (x_sign * attach_x, y_sign * joint_y, -boat_drop + joint_z)
            beam_between(f"CHR_LongHanger_{side}_{label}", start, end,
                         arm_w, arm_d, mats["yellow"], pivot,
                         float(g["secondaryBevel"]))
            fw.box(f"CHR_ClevisA_{side}_{label}",
                   (end[0], end[1] - 0.17 * y_sign, end[2]),
                   (0.44, 0.09, 0.50), mats["steelDark"], 0.010, pivot)
            fw.box(f"CHR_ClevisB_{side}_{label}",
                   (end[0], end[1] + 0.17 * y_sign, end[2]),
                   (0.44, 0.09, 0.50), mats["steelDark"], 0.010, pivot)
            fw.cylinder(f"CHR_ClevisPin_{side}_{label}", end,
                        0.12, 0.48, mats["steelLight"],
                        rotation=(math.radians(90.0), 0.0, 0.0),
                        parent=pivot, vertices=16)

    _build_city_horizon_hull(boat_root, g, mats)
    _build_city_horizon_prows(boat_root, g, mats)
    _build_city_horizon_seating(boat_root, g, mats)

    pivot.rotation_euler[1] = math.radians(float(g.get("previewSwingDegrees", 0.0)))
    return pivot
