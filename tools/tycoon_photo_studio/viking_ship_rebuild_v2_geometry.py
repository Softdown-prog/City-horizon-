"""From-scratch anti-toy structural rebuild for the City Horizon Viking ship ride.

This pass keeps the approved tall/open fairground proportion but deliberately removes
plastic/Lego/gumball-prize cues.  Ride-specific geometry is rebuilt from generic CH
Blender primitives only: restrained bevels, flange/plate logic, bolted feet, compact
bearings, long rectangular hangers, a faceted timber hull and an industrial loading deck.
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


def _mechanical_leg(name, foot, apex, width, depth, flange_depth, mats, parent, bevel):
    """Painted structural member with visible dark steel face plates, not a toy block."""
    main = beam_between(name, foot, apex, width, depth, mats["steelBlue"], parent, bevel)
    y = float(foot[1])
    for sign, suffix in ((-1.0, "Near"), (1.0, "Far")):
        offset = sign * (depth * 0.5 + flange_depth * 0.36)
        a = (float(foot[0]), y + offset, float(foot[2]))
        b = (float(apex[0]), y + offset, float(apex[2]))
        beam_between(f"{name}_Flange_{suffix}", a, b, width * 0.94, flange_depth,
                     mats["steelDark"], parent, max(0.012, bevel * 0.45))
    return main


def _bolt(name, location, mats, parent, radius=0.075, height=0.08):
    return fw.cylinder(name, location, radius, height, mats["steelLight"], parent=parent, vertices=12)


def hull_sections(g):
    half_len = float(g["shipLength"]) * 0.5
    half_w = float(g["shipHalfWidth"])
    return [
        (-half_len, half_w * 0.18, -0.20, -1.18, -2.38),
        (-half_len * 0.91, half_w * 0.58, -0.58, -1.52, -2.88),
        (-half_len * 0.67, half_w * 0.90, -0.92, -1.86, -3.32),
        (-half_len * 0.34, half_w, -1.12, -2.05, -3.58),
        (0.0, half_w * 1.02, -1.20, -2.13, -3.70),
        (half_len * 0.34, half_w, -1.12, -2.05, -3.58),
        (half_len * 0.67, half_w * 0.90, -0.92, -1.86, -3.32),
        (half_len * 0.91, half_w * 0.58, -0.58, -1.52, -2.88),
        (half_len, half_w * 0.18, -0.20, -1.18, -2.38),
    ]


def _build_hull(boat_root, g, mats):
    sections = hull_sections(g)
    vertices = []
    ring_count = 6
    for x, width, top_z, mid_z, bottom_z in sections:
        vertices.extend([
            (x, -width, top_z),
            (x, -width * 0.90, mid_z),
            (x, -width * 0.33, bottom_z),
            (x, width * 0.33, bottom_z),
            (x, width * 0.90, mid_z),
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

    mesh = bpy.data.meshes.new("VikingRebuildV2HullMesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    hull = bpy.data.objects.new("VikingHull", mesh)
    bpy.context.scene.collection.objects.link(hull)
    hull.data.materials.append(mats["wood"])
    hull.parent = boat_root
    bevel = hull.modifiers.new(name="HullEdgeBreak", type="BEVEL")
    bevel.width = 0.045
    bevel.segments = 1

    # Thin timber strakes create real wood separation instead of one smooth toy shell.
    half_w = float(g["shipHalfWidth"])
    length = float(g["shipLength"])
    for side, label in ((-1.0, "Front"), (1.0, "Back")):
        y = side * (half_w + 0.055)
        for i, z in enumerate((-1.48, -1.76, -2.04, -2.31)):
            fw.box(f"V2HullStrake_{label}_{i:02d}", (0.0, y, z),
                   (length * (0.73 - i * 0.025), 0.036, 0.060),
                   mats["woodDark"], 0.008, boat_root)
        fw.box(f"V2HullRedPinstripe_{label}", (0.0, y + side * 0.035, -1.36),
               (length * 0.70, 0.030, 0.075), mats["red"], 0.008, boat_root)
        # Dark mechanical rubbing rail breaks the all-wood silhouette.
        fw.box(f"V2HullSteelRail_{label}", (0.0, y + side * 0.020, -1.22),
               (length * 0.75, 0.045, 0.075), mats["steelDark"], 0.010, boat_root)

    # Gunwale is timber, with only a very small edge break.
    for side, label in ((-1.0, "Front"), (1.0, "Back")):
        for i in range(len(sections) - 1):
            x0, w0, z0, _, _ = sections[i]
            x1, w1, z1, _, _ = sections[i + 1]
            fw.cylinder_between(f"V2Gunwale_{label}_{i:02d}",
                                (x0, side * w0, z0 + 0.07),
                                (x1, side * w1, z1 + 0.07),
                                0.085, mats["woodLight"], boat_root, vertices=12)

    fw.box("ShipDeck", (0.0, 0.0, float(g["shipDeckZ"])),
           (length * 0.72, half_w * 1.42, 0.14), mats["woodDark"], 0.018, boat_root)
    # Narrow longitudinal seams on the deck stop it reading as one molded plastic slab.
    for y in (-0.62, -0.20, 0.20, 0.62):
        fw.box(f"V2DeckSeam_{y:+.2f}", (0.0, y, float(g["shipDeckZ"]) + 0.075),
               (length * 0.68, 0.018, 0.018), mats["wood"], 0.004, boat_root)
    return hull


def _build_prows(boat_root, g, mats):
    half_len = float(g["shipLength"]) * 0.5
    for sign, label in ((-1.0, "L"), (1.0, "R")):
        a = (sign * (half_len * 0.90), 0.0, -0.82)
        b = (sign * (half_len * 1.01), 0.0, 0.18)
        c = (sign * (half_len * 1.07), 0.0, 1.26)
        beam_between(f"V2ProwLower_{label}", a, b, 0.25, 0.31,
                     mats["woodLight"], boat_root, 0.022)
        beam_between(f"V2ProwUpper_{label}", b, c, 0.20, 0.27,
                     mats["woodDark"], boat_root, 0.018)
        # Angular carved head: boxes instead of spheres to avoid toy/cute silhouette.
        fw.box(f"V2ProwHead_{label}",
               (sign * (half_len * 1.085), 0.0, 1.34),
               (0.46, 0.44, 0.34), mats["woodLight"], 0.025, boat_root)
        fw.box(f"V2ProwBand_{label}",
               (sign * (half_len * 1.055), -0.01, 0.54),
               (0.16, 0.40, 0.20), mats["steelDark"], 0.010, boat_root)


def _build_seating(boat_root, g, mats):
    rows = int(g.get("seatRows", 8))
    span = float(g["shipLength"]) * 0.54
    half_w = float(g["shipHalfWidth"])
    for i in range(rows):
        x = -span * 0.5 + span * (i / max(1, rows - 1))
        # Steel underframe + restrained red seat surface; less chunky than earlier proxies.
        fw.box(f"V2SeatFrame_{i:02d}", (x, 0.0, -1.11),
               (0.58, half_w * 1.26, 0.10), mats["steelDark"], 0.012, boat_root)
        fw.box(f"V2SeatPad_{i:02d}", (x, 0.0, -1.03),
               (0.50, half_w * 1.20, 0.08), mats["seatRed"], 0.012, boat_root)
        fw.box(f"V2SeatBack_{i:02d}", (x + 0.18, 0.0, -0.82),
               (0.10, half_w * 1.18, 0.32), mats["steelMid"], 0.012, boat_root)
        fw.cylinder_between(f"V2SafetyBar_{i:02d}",
                            (x - 0.07, -half_w * 0.56, -0.73),
                            (x - 0.07, half_w * 0.56, -0.73),
                            0.032, mats["steelLight"], boat_root, vertices=10)


def _idle_overlay(root):
    overlay = bpy.data.objects.get("IdleLightOverlay")
    if overlay is None:
        overlay = fw.empty("IdleLightOverlay", (0.0, 0.0, 0.0), root)
    overlay["runtimeLayer"] = "idle_light_overlay"
    overlay["activeWhen"] = "ride_idle"
    overlay["disabledWhen"] = "ride_running"
    return overlay


def build_base(root, g, mats):
    base_h = float(g["baseHeight"])
    base = fw.box("RideBaseFrame", (0.0, 0.0, base_h * 0.5),
                  (float(g["baseWidth"]), float(g["baseDepth"]), base_h),
                  mats["steelDark"], 0.025, root)
    deck_z = base_h + float(g["deckHeight"]) * 0.5
    fw.box("RideDeck", (0.0, 0.0, deck_z),
           (float(g["deckWidth"]), float(g["deckDepth"]), float(g["deckHeight"])),
           mats["platformWhite"], 0.016, root)
    # Long panel seams and two service grates create an industrial deck.
    for i in range(1, 7):
        y = -float(g["deckDepth"]) * 0.42 + i * float(g["deckDepth"]) * 0.12
        fw.box(f"V2DeckPanelSeam_{i:02d}",
               (0.0, y, base_h + float(g["deckHeight"]) + 0.012),
               (float(g["deckWidth"]) - 0.55, 0.018, 0.020), mats["steelMid"], 0.003, root)
    for x in (-3.35, 3.35):
        fw.box(f"V2ServiceGrate_{x:+.2f}",
               (x, 2.75, base_h + float(g["deckHeight"]) + 0.020),
               (1.30, 0.72, 0.030), mats["steelDark"], 0.008, root)
        for j in range(5):
            fw.box(f"V2ServiceGrateBar_{x:+.2f}_{j}",
                   (x - 0.46 + j * 0.23, 2.75, base_h + float(g["deckHeight"]) + 0.045),
                   (0.045, 0.60, 0.020), mats["steelLight"], 0.002, root)
    return base


def build_supports(root, g, mats):
    pivot_z = float(g["pivotZ"])
    half_x = float(g["supportHalfWidth"])
    half_y = float(g["supportHalfDepth"])
    beam_w = float(g["supportBeamWidth"])
    beam_d = float(g["supportBeamDepth"])
    flange_d = float(g["supportFlangeDepth"])
    bevel = float(g["primaryBevel"])
    foot_w = float(g["footBlockWidth"])
    foot_d = float(g["footBlockDepth"])
    foot_h = float(g["footBlockHeight"])
    _idle_overlay(root)
    supports = []

    for y_sign, side in ((-1.0, "Front"), (1.0, "Back")):
        y = y_sign * half_y
        for x_sign, label in ((-1.0, "L"), (1.0, "R")):
            foot = (x_sign * half_x, y, 1.00)
            apex = (x_sign * 0.22, y, pivot_z - 0.22)
            leg = _mechanical_leg(f"V2MainLeg_{side}_{label}", foot, apex,
                                  beam_w, beam_d, flange_d, mats, root, bevel)
            supports.append(leg)

            # Flat anchor plate, four bolts and a short gusset make the foot credible.
            plate_z = 0.72
            fw.box(f"V2FootPlate_{side}_{label}",
                   (x_sign * half_x, y, plate_z),
                   (foot_w, foot_d, foot_h), mats["steelDark"], 0.018, root)
            for bx in (-0.55, 0.55):
                for by in (-0.38, 0.38):
                    _bolt(f"V2AnchorBolt_{side}_{label}_{bx:+.2f}_{by:+.2f}",
                          (x_sign * half_x + bx, y + by, plate_z + foot_h * 0.58),
                          mats, root, float(g["anchorBoltRadius"]), 0.085)
            beam_between(f"V2FootGusset_{side}_{label}",
                         (x_sign * (half_x - 0.12), y, 1.08),
                         (x_sign * (half_x - 0.92), y, 2.72),
                         0.30, 0.22, mats["steelMid"], root, 0.016)

            inset_foot = (x_sign * (half_x - 1.06), y, 1.42)
            inset_apex = (x_sign * 0.74, y, pivot_z - 1.52)
            beam_between(f"V2InnerBrace_{side}_{label}", inset_foot, inset_apex,
                         float(g["innerBraceWidth"]), float(g["innerBraceDepth"]),
                         mats["yellow"], root, float(g["secondaryBevel"]))

        tie_z = pivot_z * 0.39
        beam_between(f"V2LowerCross_{side}",
                     (-half_x * 0.64, y, tie_z), (half_x * 0.64, y, tie_z),
                     float(g["lowerCrossBraceWidth"]), float(g["lowerCrossBraceDepth"]),
                     mats["steelMid"], root, float(g["secondaryBevel"]))

        normal_y = -1.0 if y_sign < 0 else 1.0
        bearing_y = y + normal_y * 0.27
        fw.cylinder(f"V2BearingHousing_{side}", (0.0, bearing_y, pivot_z),
                    float(g["bearingRadius"]), float(g["bearingDepth"]), mats["steelDark"],
                    rotation=(math.radians(90.0), 0.0, 0.0), parent=root, vertices=28)
        fw.cylinder(f"V2BearingRace_{side}",
                    (0.0, bearing_y + normal_y * 0.16, pivot_z),
                    float(g["bearingRadius"]) * 0.68, 0.12, mats["steelLight"],
                    rotation=(math.radians(90.0), 0.0, 0.0), parent=root, vertices=24)
        fw.cylinder(f"V2BearingCap_{side}",
                    (0.0, bearing_y + normal_y * 0.24, pivot_z),
                    float(g["bearingRadius"]) * 0.31, 0.08, mats["red"],
                    rotation=(math.radians(90.0), 0.0, 0.0), parent=root, vertices=20)
        # Eight small bolts are a mechanical cue; no oversized candy ring.
        for i in range(8):
            angle = (math.tau * i) / 8.0
            r = float(g["bearingRadius"]) * 0.78
            _bolt(f"V2BearingBolt_{side}_{i:02d}",
                  (math.cos(angle) * r, bearing_y + normal_y * 0.32,
                   pivot_z + math.sin(angle) * r), mats, root, 0.065, 0.06)

    fw.cylinder("MainAxle", (0.0, 0.0, pivot_z), float(g["axleRadius"]),
                float(g["axleDepth"]), mats["steelMid"],
                rotation=(math.radians(90.0), 0.0, 0.0), parent=root, vertices=28)
    return supports


def build_loading_zone(root, g, mats):
    width = float(g["loadingPlatformWidth"])
    depth = float(g["loadingPlatformDepth"])
    height = float(g["loadingPlatformHeight"])
    base_d = float(g["baseDepth"])
    platform_y = -(base_d * 0.5 - depth * 0.5 - 0.32)
    fw.box("LoadingPlatform", (0.0, platform_y, 0.48 + height * 0.5),
           (width, depth, height), mats["platform"], 0.018, root)
    # Galvanized tread surface is a separate thin plate.
    fw.box("LoadingPlatformTread", (0.0, platform_y, 0.48 + height + 0.035),
           (width - 0.18, depth - 0.16, 0.07), mats["platformWhite"], 0.010, root)

    stair_w = float(g["stairWidth"])
    stair_d = float(g["stairDepth"])
    steps = int(g["stairSteps"])
    front = -(base_d * 0.5)
    for i in range(steps):
        t = (i + 1) / steps
        y = front - stair_d * (1.0 - t) + 0.18
        z = 0.08 + t * (0.42 + height)
        fw.box(f"V2StairFrame_{i:02d}", (0.0, y, z * 0.5),
               (stair_w, stair_d / steps * 1.08, z), mats["steelDark"], 0.010, root)
        fw.box(f"V2StairTread_{i:02d}", (0.0, y - 0.03, z + 0.025),
               (stair_w - 0.12, stair_d / steps * 0.88, 0.05), mats["platformWhite"], 0.008, root)

    rail_h = float(g["railingHeight"])
    rail_r = float(g["railingRadius"])
    side_x = width * 0.5 - 0.10
    front_y = platform_y - depth * 0.5 + 0.07
    back_y = platform_y + depth * 0.5 - 0.07
    fw.build_railing(root, "V2LoadRailL", (-side_x, front_y), (-side_x, back_y),
                     0.48 + height, rail_h, rail_r, mats["steelDark"], 4)
    fw.build_railing(root, "V2LoadRailR", (side_x, front_y), (side_x, back_y),
                     0.48 + height, rail_h, rail_r, mats["steelDark"], 4)


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

    for x_sign, label in ((-1.0, "L"), (1.0, "R")):
        for y_sign, side in ((-1.0, "Front"), (1.0, "Back")):
            start = (x_sign * 0.42, y_sign * (half_y - 0.28), -0.18)
            end = (x_sign * attach_x, y_sign * 1.49, -boat_drop + joint_z)
            beam_between(f"V2LongHanger_{side}_{label}", start, end,
                         arm_w, arm_d, mats["yellow"], pivot, float(g["secondaryBevel"]))
            # Clevis is two plates + a steel pin, not a decorative sphere.
            fw.box(f"V2ClevisPlateA_{side}_{label}",
                   (end[0], end[1] - 0.16 * y_sign, end[2]),
                   (0.44, 0.10, 0.52), mats["steelDark"], 0.012, pivot)
            fw.box(f"V2ClevisPlateB_{side}_{label}",
                   (end[0], end[1] + 0.16 * y_sign, end[2]),
                   (0.44, 0.10, 0.52), mats["steelDark"], 0.012, pivot)
            fw.cylinder(f"V2ClevisPin_{side}_{label}", end,
                        0.13, 0.46, mats["steelLight"],
                        rotation=(math.radians(90.0), 0.0, 0.0), parent=pivot, vertices=16)

    _build_hull(boat_root, g, mats)
    _build_prows(boat_root, g, mats)
    _build_seating(boat_root, g, mats)
    pivot.rotation_euler[1] = math.radians(float(g.get("previewSwingDegrees", 0.0)))
    return pivot
