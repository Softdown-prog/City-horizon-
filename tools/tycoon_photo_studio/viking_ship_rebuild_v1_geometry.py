"""From-scratch structural rebuild for the City Horizon Viking/pirate ship ride.

This module intentionally does not import or reuse any previous Viking-ship geometry
pass.  It reuses only generic CH Blender primitives/materials.  The first goal is a
very tall, open, mechanically believable fairground silhouette with long hangers and
a visibly suspended ship.  Decorative density is intentionally kept modest until the
proportion gate is approved.
"""
from __future__ import annotations

import math

import bpy
from mathutils import Vector

import build_ferris_wheel as fw


def _sphere(name, location, scale, material, parent=None, segments=18, rings=9):
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
    bevel.width = 0.03
    bevel.segments = 2
    if parent is not None:
        obj.parent = parent
    return obj


def beam_between(name, start, end, width, depth, material, parent=None, bevel=0.055):
    """Rectangular structural beam aligned between two world/local points."""
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
    mod = obj.modifiers.new(name="EdgeSoftening", type="BEVEL")
    mod.width = float(bevel)
    mod.segments = 2
    if parent is not None:
        obj.parent = parent
    return obj


def hull_sections(g):
    half_len = float(g["shipLength"]) * 0.5
    half_w = float(g["shipHalfWidth"])
    # x, half width, gunwale z, mid-side z, keel z.
    # Tall ends and a deep centre create a heavy fairground-ship silhouette.
    return [
        (-half_len, half_w * 0.22, -0.30, -1.25, -2.45),
        (-half_len * 0.90, half_w * 0.62, -0.72, -1.62, -2.92),
        (-half_len * 0.66, half_w * 0.91, -1.02, -1.92, -3.35),
        (-half_len * 0.32, half_w, -1.22, -2.12, -3.62),
        (0.0, half_w * 1.03, -1.30, -2.20, -3.75),
        (half_len * 0.32, half_w, -1.22, -2.12, -3.62),
        (half_len * 0.66, half_w * 0.91, -1.02, -1.92, -3.35),
        (half_len * 0.90, half_w * 0.62, -0.72, -1.62, -2.92),
        (half_len, half_w * 0.22, -0.30, -1.25, -2.45),
    ]


def _build_hull(boat_root, g, mats):
    sections = hull_sections(g)
    vertices = []
    ring_count = 6
    for x, width, top_z, mid_z, bottom_z in sections:
        vertices.extend([
            (x, -width, top_z),
            (x, -width * 0.92, mid_z),
            (x, -width * 0.34, bottom_z),
            (x, width * 0.34, bottom_z),
            (x, width * 0.92, mid_z),
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

    mesh = bpy.data.meshes.new("VikingRebuildHullMesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    hull = bpy.data.objects.new("VikingHull", mesh)
    bpy.context.scene.collection.objects.link(hull)
    hull.data.materials.append(mats["wood"])
    hull.parent = boat_root
    bevel = hull.modifiers.new(name="HullEdgeSoftening", type="BEVEL")
    bevel.width = 0.13
    bevel.segments = 3

    # Curved top rails are structural enough to survive downscale.
    for side, label in ((-1.0, "Front"), (1.0, "Back")):
        for i in range(len(sections) - 1):
            x0, w0, z0, _, _ = sections[i]
            x1, w1, z1, _, _ = sections[i + 1]
            fw.cylinder_between(
                f"RebuildGunwale_{label}_{i:02d}",
                (x0, side * w0, z0 + 0.08),
                (x1, side * w1, z1 + 0.08),
                0.13,
                mats["woodLight"],
                boat_root,
                vertices=18,
            )

    # Strong amusement-ride fascia, but no dense micro-detail at this gate.
    for side, label in ((-1.0, "Front"), (1.0, "Back")):
        y = side * (float(g["shipHalfWidth"]) + 0.07)
        fw.box(f"RebuildHullRedBand_{label}", (0.0, y, -1.74),
               (float(g["shipLength"]) * 0.74, 0.10, 0.42), mats["red"], 0.04, boat_root)
        fw.box(f"RebuildHullWhiteBand_{label}", (0.0, y + side * 0.06, -1.61),
               (float(g["shipLength"]) * 0.69, 0.05, 0.10), mats["white"], 0.02, boat_root)

    fw.box("ShipDeck", (0.0, 0.0, float(g["shipDeckZ"])),
           (float(g["shipLength"]) * 0.72, float(g["shipHalfWidth"]) * 1.42, 0.20),
           mats["woodDark"], 0.06, boat_root)
    return hull


def _build_prows(boat_root, g, mats):
    half_len = float(g["shipLength"]) * 0.5
    for sign, label in ((-1.0, "L"), (1.0, "R")):
        a = (sign * (half_len * 0.90), 0.0, -0.92)
        b = (sign * (half_len * 1.02), 0.0, 0.02)
        c = (sign * (half_len * 1.08), 0.0, 1.02)
        beam_between(f"RebuildProwLower_{label}", a, b, 0.34, 0.40, mats["woodLight"], boat_root, 0.07)
        beam_between(f"RebuildProwUpper_{label}", b, c, 0.28, 0.34, mats["gold"], boat_root, 0.06)
        _sphere(f"RebuildProwHead_{label}",
                (sign * (half_len * 1.11), 0.0, 1.15),
                (0.48, 0.38, 0.36), mats["gold"], boat_root, 20, 10)


def _build_seating(boat_root, g, mats):
    rows = int(g.get("seatRows", 8))
    span = float(g["shipLength"]) * 0.55
    half_w = float(g["shipHalfWidth"])
    for i in range(rows):
        x = -span * 0.5 + span * (i / max(1, rows - 1))
        fw.box(f"RebuildSeat_{i:02d}", (x, 0.0, -1.08),
               (0.72, half_w * 1.32, 0.22), mats["seatRed"], 0.06, boat_root)
        fw.box(f"RebuildSeatBack_{i:02d}", (x + 0.22, 0.0, -0.82),
               (0.16, half_w * 1.28, 0.36), mats["steelDark"], 0.04, boat_root)
        fw.cylinder_between(f"RebuildSafetyBar_{i:02d}",
                            (x - 0.08, -half_w * 0.57, -0.71),
                            (x - 0.08, half_w * 0.57, -0.71),
                            0.045, mats["white"], boat_root, vertices=12)


def _idle_overlay(root):
    overlay = bpy.data.objects.get("IdleLightOverlay")
    if overlay is None:
        overlay = fw.empty("IdleLightOverlay", (0.0, 0.0, 0.0), root)
    overlay["runtimeLayer"] = "idle_light_overlay"
    overlay["activeWhen"] = "ride_idle"
    overlay["disabledWhen"] = "ride_running"
    return overlay


def build_base(root, g, mats):
    base = fw.box("RideBase", (0.0, 0.0, float(g["baseHeight"]) * 0.5),
                  (float(g["baseWidth"]), float(g["baseDepth"]), float(g["baseHeight"])),
                  mats["steelDark"], 0.10, root)
    fw.box("RideDeck", (0.0, 0.0, float(g["baseHeight"]) + float(g["deckHeight"]) * 0.5),
           (float(g["deckWidth"]), float(g["deckDepth"]), float(g["deckHeight"])),
           mats["platformWhite"], 0.06, root)
    return base


def build_supports(root, g, mats):
    pivot_z = float(g["pivotZ"])
    half_x = float(g["supportHalfWidth"])
    half_y = float(g["supportHalfDepth"])
    beam_w = float(g["supportBeamWidth"])
    beam_d = float(g["supportBeamDepth"])
    brace_w = float(g["innerBraceWidth"])
    brace_d = float(g["innerBraceDepth"])
    foot_w = float(g["footBlockWidth"])
    foot_d = float(g["footBlockDepth"])
    foot_h = float(g["footBlockHeight"])
    overlay = _idle_overlay(root)
    supports = []

    for y_sign, side in ((-1.0, "Front"), (1.0, "Back")):
        y = y_sign * half_y
        normal_y = -1.0 if y_sign < 0 else 1.0
        for x_sign, label in ((-1.0, "L"), (1.0, "R")):
            foot = (x_sign * half_x, y, 1.02)
            apex = (x_sign * 0.22, y, pivot_z - 0.20)
            leg = beam_between(f"RebuildMainLeg_{side}_{label}", foot, apex,
                               beam_w, beam_d, mats["steelBlue"], root, 0.075)
            supports.append(leg)
            fw.box(f"RebuildFootBlock_{side}_{label}",
                   (x_sign * half_x, y, 0.64),
                   (foot_w, foot_d, foot_h), mats["steelBlue"], 0.09, root)

            # Inset yellow member makes the tall leg read as engineered fairground steel.
            inset_foot = (x_sign * (half_x - 0.92), y + y_sign * 0.04, 1.44)
            inset_apex = (x_sign * 0.72, y + y_sign * 0.04, pivot_z - 1.36)
            beam_between(f"RebuildInnerLeg_{side}_{label}", inset_foot, inset_apex,
                         brace_w, brace_d, mats["yellow"], root, 0.045)

            # Sparse idle bulbs make scale obvious without becoming the focus of V1.
            start = Vector(foot)
            end = Vector(apex)
            for i in range(12):
                t = 0.09 + 0.80 * (i / 11.0)
                p = start.lerp(end, t)
                bulb = _sphere(f"RebuildLegBulb_{side}_{label}_{i:02d}",
                               (p.x, y + normal_y * (beam_d * 0.5 + 0.11), p.z),
                               (0.10, 0.075, 0.10),
                               mats["lampCyan"] if i % 2 == 0 else mats["lampPink"],
                               overlay, 12, 6)
                bulb["blinkGroup"] = "A" if i % 2 == 0 else "B"

        # A low cross brace stabilizes the huge A-frame without visually shortening it.
        tie_z = pivot_z * 0.43
        beam_between(f"RebuildLowerCross_{side}",
                     (-half_x * 0.66, y, tie_z), (half_x * 0.66, y, tie_z),
                     float(g["lowerCrossBraceWidth"]), float(g["lowerCrossBraceDepth"]),
                     mats["yellow"], root, 0.045)

        bearing_y = y + normal_y * 0.30
        fw.cylinder(f"RebuildBearingHousing_{side}", (0.0, bearing_y, pivot_z),
                    float(g["bearingRadius"]), float(g["bearingDepth"]), mats["steelBlue"],
                    rotation=(math.radians(90.0), 0.0, 0.0), parent=root, vertices=32)
        fw.cylinder(f"RebuildBearingRing_{side}",
                    (0.0, bearing_y + normal_y * 0.20, pivot_z),
                    float(g["bearingRadius"]) * 0.68, 0.16, mats["yellow"],
                    rotation=(math.radians(90.0), 0.0, 0.0), parent=root, vertices=28)
        fw.cylinder(f"RebuildBearingCap_{side}",
                    (0.0, bearing_y + normal_y * 0.31, pivot_z),
                    float(g["bearingRadius"]) * 0.34, 0.12, mats["red"],
                    rotation=(math.radians(90.0), 0.0, 0.0), parent=root, vertices=24)

    fw.cylinder("MainAxle", (0.0, 0.0, pivot_z), float(g["axleRadius"]),
                float(g["axleDepth"]), mats["steelMid"],
                rotation=(math.radians(90.0), 0.0, 0.0), parent=root, vertices=32)
    return supports


def build_loading_zone(root, g, mats):
    width = float(g["loadingPlatformWidth"])
    depth = float(g["loadingPlatformDepth"])
    height = float(g["loadingPlatformHeight"])
    base_d = float(g["baseDepth"])
    platform_y = -(base_d * 0.5 - depth * 0.5 - 0.36)
    fw.box("LoadingPlatform", (0.0, platform_y, 0.50 + height * 0.5),
           (width, depth, height), mats["platformWhite"], 0.05, root)

    stair_w = float(g["stairWidth"])
    stair_d = float(g["stairDepth"])
    steps = int(g["stairSteps"])
    front = -(base_d * 0.5)
    for i in range(steps):
        t = (i + 1) / steps
        y = front - stair_d * (1.0 - t) + 0.20
        z = 0.10 + t * (0.42 + height)
        fw.box(f"RebuildStair_{i:02d}", (0.0, y, z * 0.5),
               (stair_w, stair_d / steps * 1.10, z), mats["platformWhite"], 0.035, root)

    rail_h = float(g["railingHeight"])
    rail_r = float(g["railingRadius"])
    side_x = width * 0.5 - 0.10
    front_y = platform_y - depth * 0.5 + 0.07
    back_y = platform_y + depth * 0.5 - 0.07
    fw.build_railing(root, "RebuildLoadRailL", (-side_x, front_y), (-side_x, back_y),
                     0.50 + height, rail_h, rail_r, mats["steelLight"], 4)
    fw.build_railing(root, "RebuildLoadRailR", (side_x, front_y), (side_x, back_y),
                     0.50 + height, rail_h, rail_r, mats["steelLight"], 4)


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
    arm_w = float(g["swingArmWidth"])
    arm_d = float(g["swingArmDepth"])
    joint_z = float(g["boatJointZ"])

    # Four very long rectangular hangers are the visual priority of this rebuild.
    for x_sign, label in ((-1.0, "L"), (1.0, "R")):
        for y_sign, side in ((-1.0, "Front"), (1.0, "Back")):
            start = (x_sign * 0.46, y_sign * (half_y - 0.30), -0.16)
            end = (x_sign * attach_x, y_sign * 1.48, -boat_drop + joint_z)
            beam_between(f"RebuildLongHanger_{side}_{label}", start, end,
                         arm_w, arm_d, mats["yellow"], pivot, 0.055)
            _sphere(f"RebuildBoatJoint_{side}_{label}", end,
                    (0.31, 0.31, 0.31), mats["steelBlue"], pivot, 18, 9)

    _build_hull(boat_root, g, mats)
    _build_prows(boat_root, g, mats)
    _build_seating(boat_root, g, mats)

    pivot.rotation_euler[1] = math.radians(float(g.get("previewSwingDegrees", 0.0)))
    return pivot
