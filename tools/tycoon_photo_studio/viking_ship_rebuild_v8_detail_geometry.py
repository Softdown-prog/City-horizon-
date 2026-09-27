"""V8 detail/identity refinement for the City Horizon Viking ship ride.

Builds on the approved curved V7 hull.  This pass keeps the same 5x4 site and
mechanical frame, but gives the longship a stronger authored identity: a more
pronounced bow/stern silhouette, curved side shield rhythm, clearer plank/read
separation, and a slightly fuller passenger body without returning to toy-like
chunky geometry.
"""
from __future__ import annotations

import math

import bpy

import build_ferris_wheel as fw
import viking_ship_rebuild_v7_curved_geometry as v7


build_base = v7.build_base
build_supports = v7.build_supports
build_loading_zone = v7.build_loading_zone
beam_between = v7.beam_between
hull_sections = v7.hull_sections


def _section_near_x(g, x):
    sections = hull_sections(g)
    return min(sections, key=lambda item: abs(item[0] - x))


def _add_side_shields(boat_root, g, mats):
    length = v7._ship_length(g)
    # Keep shields away from the extreme prow/stern so the arc stays readable.
    xs = [length * t for t in (-0.27, -0.135, 0.0, 0.135, 0.27)]
    palette = ("red", "white", "gold", "white", "red")
    for side, side_label in ((-1.0, "Near"), (1.0, "Far")):
        for i, (x, mat_key) in enumerate(zip(xs, palette)):
            _sx, width, top_z, mid_z, _keel = _section_near_x(g, x)
            y = side * (width + 0.11)
            z = top_z + (mid_z - top_z) * 0.44
            fw.cylinder(
                f"CHR_V8_Shield_{side_label}_{i:02d}",
                (x, y, z),
                0.34,
                0.075,
                mats[mat_key],
                rotation=(math.radians(90.0), 0.0, 0.0),
                parent=boat_root,
                vertices=20,
            )
            fw.cylinder(
                f"CHR_V8_ShieldBoss_{side_label}_{i:02d}",
                (x, y + side * 0.055, z),
                0.085,
                0.070,
                mats["steelMid"],
                rotation=(math.radians(90.0), 0.0, 0.0),
                parent=boat_root,
                vertices=14,
            )


def _add_end_ornaments(boat_root, g, mats):
    half_len = v7._ship_length(g) * 0.5
    # Stronger vertical continuation than V7, but deliberately asymmetric.
    v7.beam_between(
        "CHR_V8_BowCrest",
        (half_len * 1.02, 0.0, 1.05),
        (half_len * 1.09, 0.0, 2.08),
        0.15, 0.21, mats["woodDark"], boat_root, 0.012,
    )
    fw.box(
        "CHR_V8_BowHead",
        (half_len * 1.105, 0.0, 2.14),
        (0.48, 0.36, 0.28),
        mats["woodLight"], 0.014, boat_root,
    )
    v7.beam_between(
        "CHR_V8_BowSnout",
        (half_len * 1.11, 0.0, 2.13),
        (half_len * 1.16, -0.02, 2.05),
        0.12, 0.17, mats["gold"], boat_root, 0.010,
    )

    # Stern gets a shorter fork so bow and stern cannot be mistaken for mirrors.
    for side in (-1.0, 1.0):
        v7.beam_between(
            f"CHR_V8_SternFork_{'N' if side < 0 else 'F'}",
            (-half_len * 1.02, 0.0, 1.18),
            (-half_len * 1.085, side * 0.22, 1.72),
            0.12, 0.14, mats["woodDark"], boat_root, 0.010,
        )


def _add_deck_ribs(boat_root, g, mats):
    length = v7._ship_length(g)
    half_w = float(g["shipHalfWidth"])
    for i in range(7):
        x = -length * 0.24 + length * 0.48 * (i / 6.0)
        fw.box(
            f"CHR_V8_DeckRib_{i:02d}",
            (x, 0.0, float(g["shipDeckZ"]) + 0.105),
            (0.10, half_w * 1.36, 0.050),
            mats["woodLight"], 0.004, boat_root,
        )


def build_swing_group(root, g, mats):
    pivot = v7.build_swing_group(root, g, mats)
    boat_root = bpy.data.objects.get("BoatRoot")
    if boat_root is None:
        raise RuntimeError("CH_VIKING_V8_BOAT_ROOT_MISSING")

    _add_side_shields(boat_root, g, mats)
    _add_end_ornaments(boat_root, g, mats)
    _add_deck_ribs(boat_root, g, mats)

    boat_root["hullRevision"] = "CH_VIKING_LONGSHIP_DETAIL_V8"
    boat_root["detailPass"] = "curved_shields_asymmetric_end_ornaments_deck_ribs"
    boat_root["visualGoal"] = "clear_viking_park_ride_identity_at_gameplay_scale"
    return pivot
