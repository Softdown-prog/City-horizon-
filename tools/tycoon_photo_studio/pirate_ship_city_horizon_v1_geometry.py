"""Original City Horizon Pirate Ship amusement-ride geometry.

This is a clean art-direction pass.  The old Viking longship remains available
for A/B comparison, but none of its shields, dragon heads or ornamental prow
are reused here.  Only the proven CH Blender ride mechanics (A-frame,
suspension/pivot conventions and guarded bake pipeline) are reused.

Reference photographs are used for mechanical/readability cues only: a long
open passenger boat, raised ends, large A-frame, transverse axle and visible
suspension.  Geometry and decoration are original to City Horizon.
"""
from __future__ import annotations

import math

import bpy

import build_ferris_wheel as fw
import viking_ship_rebuild_v5_geometry as mechanics

beam_between = mechanics.beam_between
build_base = mechanics.build_base
build_loading_zone = mechanics.build_loading_zone


def _ship_length(g):
    return float(g.get("pirateShipLength", float(g["shipLength"]) * 1.10))


def hull_sections(g):
    """Thirteen-station amusement-boat shell with raised, non-Viking ends."""
    half_len = _ship_length(g) * 0.5
    half_w = float(g["shipHalfWidth"]) * 1.04
    stations = (-1.0, -0.88, -0.72, -0.54, -0.34, -0.16, 0.0,
                0.16, 0.34, 0.54, 0.72, 0.88, 1.0)
    result = []
    for t in stations:
        a = abs(t)
        # Broad passenger belly, narrower ends and a controlled upward sheer.
        width = half_w * (0.16 + 0.84 * ((1.0 - a ** 2.15) ** 0.43))
        top = -1.18 + 1.72 * (a ** 2.25)
        mid = top - (0.78 + 0.26 * (1.0 - a))
        keel = -3.46 + 2.08 * (a ** 1.75)
        result.append((t * half_len, width, top, mid, keel))
    return result


def _build_open_hull(boat_root, g, mats):
    sections = hull_sections(g)
    ring_count = 6
    verts = []
    for x, w, top, mid, keel in sections:
        verts.extend([
            (x, -w, top),
            (x, -w * 0.94, top - 0.34),
            (x, -w * 0.70, mid),
            (x, -w * 0.24, keel),
            (x,  w * 0.24, keel),
            (x,  w * 0.70, mid),
            (x,  w * 0.94, top - 0.34),
            (x,  w, top),
        ])
    ring_count = 8

    # Deliberately do not close the top edge: the boat must read as an open
    # passenger vessel, not a solid canoe/longship block.
    faces = []
    for s in range(len(sections) - 1):
        a = s * ring_count
        b = (s + 1) * ring_count
        for r in range(ring_count - 1):
            faces.append((a + r, a + r + 1, b + r + 1, b + r))
    faces.append(tuple(range(ring_count - 1, -1, -1)))
    last = (len(sections) - 1) * ring_count
    faces.append(tuple(last + i for i in range(ring_count)))

    mesh = bpy.data.meshes.new("CHPirateShipHullV1Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    hull = bpy.data.objects.new("CHPirateShipHullV1", mesh)
    bpy.context.scene.collection.objects.link(hull)
    hull.data.materials.append(mats["woodDark"])
    hull.parent = boat_root
    bevel = hull.modifiers.new(name="HullEdgeBreak", type="BEVEL")
    bevel.width = 0.06
    bevel.segments = 2

    # Strong manufactured-ride silhouette: dark wood shell, red belt and a
    # restrained warm-metal cap.  Broad forms survive isometric downsampling.
    for side, label in ((-1.0, "Near"), (1.0, "Far")):
        for i in range(len(sections) - 1):
            x0, w0, t0, m0, _ = sections[i]
            x1, w1, t1, m1, _ = sections[i + 1]
            fw.cylinder_between(
                f"CHP_Gunwale_{label}_{i:02d}",
                (x0, side * (w0 + 0.035), t0 + 0.09),
                (x1, side * (w1 + 0.035), t1 + 0.09),
                0.10, mats["gold"], boat_root, vertices=12,
            )
            z0 = t0 + (m0 - t0) * 0.46
            z1 = t1 + (m1 - t1) * 0.46
            fw.cylinder_between(
                f"CHP_RedBelt_{label}_{i:02d}",
                (x0, side * (w0 + 0.045), z0),
                (x1, side * (w1 + 0.045), z1),
                0.075, mats["red"], boat_root, vertices=10,
            )

    deck_z = float(g["shipDeckZ"]) + 0.10
    fw.box(
        "CHP_PassengerFloor", (0.0, 0.0, deck_z),
        (_ship_length(g) * 0.58, float(g["shipHalfWidth"]) * 1.42, 0.16),
        mats["wood"], 0.018, boat_root,
    )
    return hull


def _build_raised_ends(boat_root, g, mats):
    """Original fairground bow/stern panels; no dragon heads or Viking shields."""
    half = _ship_length(g) * 0.5
    for sign, label in ((-1.0, "Stern"), (1.0, "Bow")):
        beam_between(
            f"CHP_{label}StemLower",
            (sign * half * 0.87, 0.0, -0.48),
            (sign * half * 1.015, 0.0, 0.78),
            0.22, 0.30, mats["woodLight"], boat_root, 0.018,
        )
        beam_between(
            f"CHP_{label}StemUpper",
            (sign * half * 1.015, 0.0, 0.78),
            (sign * half * 1.055, 0.0, 1.48),
            0.17, 0.25, mats["gold"], boat_root, 0.014,
        )
        fw.box(
            f"CHP_{label}CrestPanel",
            (sign * half * 1.04, 0.0, 1.58),
            (0.54, 0.82, 0.42), mats["red"], 0.045, boat_root,
        )
        fw.box(
            f"CHP_{label}CrestInset",
            (sign * (half * 1.04 + 0.015), -0.01, 1.60),
            (0.22, 0.62, 0.20), mats["gold"], 0.025, boat_root,
        )


def _build_seating(boat_root, g, mats):
    """Eight readable transverse benches with individual restraint bars."""
    rows = 8
    span = _ship_length(g) * 0.54
    half_w = float(g["shipHalfWidth"])
    for i in range(rows):
        x = -span * 0.5 + span * i / (rows - 1)
        fw.box(
            f"CHP_SeatBase_{i:02d}", (x, 0.0, -1.02),
            (0.44, half_w * 1.26, 0.14), mats["seatRed"], 0.025, boat_root,
        )
        fw.box(
            f"CHP_SeatBack_{i:02d}", (x + 0.14, 0.0, -0.73),
            (0.10, half_w * 1.24, 0.48), mats["woodLight"], 0.020, boat_root,
        )
        fw.cylinder_between(
            f"CHP_Restraint_{i:02d}",
            (x - 0.07, -half_w * 0.55, -0.61),
            (x - 0.07,  half_w * 0.55, -0.61),
            0.038, mats["steelLight"], boat_root, vertices=10,
        )


def _build_cabin_rails(boat_root, g, mats):
    length = _ship_length(g)
    half_w = float(g["shipHalfWidth"])
    for side, label in ((-1.0, "Near"), (1.0, "Far")):
        y = side * half_w * 0.78
        fw.cylinder_between(
            f"CHP_CabinRail_{label}",
            (-length * 0.29, y, -0.42), (length * 0.29, y, -0.42),
            0.052, mats["gold"], boat_root, vertices=10,
        )
        for idx, x in enumerate((-length * 0.29, -length * 0.10, length * 0.10, length * 0.29)):
            fw.cylinder_between(
                f"CHP_CabinPost_{label}_{idx}",
                (x, y, -1.05), (x, y, -0.42),
                0.040, mats["steelDark"], boat_root, vertices=10,
            )


def build_supports(root, g, mats):
    """Reuse proven A-frame mechanics, then strengthen axle readability."""
    supports = mechanics.build_supports(root, g, mats)
    pivot_z = float(g["pivotZ"])
    half_y = float(g["supportHalfDepth"])
    fw.cylinder(
        "CHP_AxleHubNear", (0.0, -half_y - 0.10, pivot_z),
        0.34, 0.24, mats["gold"],
        rotation=(math.radians(90.0), 0.0, 0.0), parent=root, vertices=18,
    )
    fw.cylinder(
        "CHP_AxleHubFar", (0.0, half_y + 0.10, pivot_z),
        0.34, 0.24, mats["gold"],
        rotation=(math.radians(90.0), 0.0, 0.0), parent=root, vertices=18,
    )
    return supports


def build_swing_group(root, g, mats):
    """Build moving ship under the established SwingPivot convention."""
    original_hull = mechanics._build_city_horizon_hull
    original_prows = mechanics._build_city_horizon_prows
    original_seating = mechanics._build_city_horizon_seating
    original_sections = mechanics.hull_sections
    try:
        mechanics.hull_sections = hull_sections
        mechanics._build_city_horizon_hull = _build_open_hull
        mechanics._build_city_horizon_prows = _build_raised_ends
        mechanics._build_city_horizon_seating = _build_seating
        pivot = mechanics.build_swing_group(root, g, mats)
    finally:
        mechanics.hull_sections = original_sections
        mechanics._build_city_horizon_hull = original_hull
        mechanics._build_city_horizon_prows = original_prows
        mechanics._build_city_horizon_seating = original_seating

    boat_root = bpy.data.objects.get("BoatRoot")
    if boat_root is None:
        raise RuntimeError("CH_PIRATE_SHIP_V1_BOAT_ROOT_MISSING")
    _build_cabin_rails(boat_root, g, mats)
    boat_root["designRevision"] = "CH_PIRATE_SHIP_CITY_HORIZON_V1"
    boat_root["designIntent"] = "original_fairground_pirate_ship_not_viking_longship"
    boat_root["movingAssembly"] = True
    boat_root["referenceUse"] = "mechanical_silhouette_and_readability_only"
    pivot["rotationAxis"] = "Y"
    pivot["motionProfile"] = "deterministic_pendulum_frames"
    return pivot
