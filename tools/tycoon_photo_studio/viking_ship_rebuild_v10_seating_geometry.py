"""V10 seating realism pass for the City Horizon Viking ship ride.

Builds on the V9 hull/body overhaul and focuses almost entirely on the passenger
area.  The goal is a believable amusement-ride seating system at gameplay scale:
paired upholstered seats, shaped backrests, support pedestals, lap bars,
hand-grips and foot rails.  Geometry remains deliberately clean/stylized so it
matches City Horizon instead of becoming photorealistic noise.
"""
from __future__ import annotations

import math

import bpy

import build_ferris_wheel as fw
import viking_ship_rebuild_v9_ship_overhaul_geometry as v9
import viking_ship_rebuild_v5_geometry as v5

build_base = v9.build_base
build_supports = v9.build_supports
build_loading_zone = v9.build_loading_zone
beam_between = v9.beam_between
hull_sections = v9.hull_sections


def _seat_module(boat_root, mats, *, row: int, x: float, y: float, side: int):
    """One stylized two-person amusement-ride seat module."""
    tag = f"R{row:02d}_{'N' if side < 0 else 'F'}"

    # Mechanical pedestal below the upholstered body.
    fw.box(
        f"CHR_V10_Pedestal_{tag}",
        (x + 0.02, y, -1.19),
        (0.34, 0.56, 0.16),
        mats["steelDark"],
        0.035,
        boat_root,
    )

    # Seat pan: thicker, shorter and clearly distinct from the structural rail.
    fw.box(
        f"CHR_V10_SeatPan_{tag}",
        (x, y, -0.99),
        (0.56, 0.68, 0.16),
        mats["seatRed"],
        0.075,
        boat_root,
    )

    # Backrest leans slightly rearward.  It is intentionally a separate volume,
    # so highlights/shadows read like a real padded ride seat at sprite scale.
    back = fw.box(
        f"CHR_V10_Backrest_{tag}",
        (x + 0.22, y, -0.67),
        (0.15, 0.68, 0.52),
        mats["seatRed"],
        0.085,
        boat_root,
    )
    back.rotation_euler[1] = math.radians(-8.0)

    # Dark shell behind the cushion prevents the seat from reading as a floating
    # red slab and provides the manufactured-ride silhouette.
    shell = fw.box(
        f"CHR_V10_BackShell_{tag}",
        (x + 0.265, y, -0.69),
        (0.09, 0.72, 0.56),
        mats["steelDark"],
        0.050,
        boat_root,
    )
    shell.rotation_euler[1] = math.radians(-8.0)

    # Lap bar pivots from the outside of each pair.  A transverse padded section
    # is more believable than the old single thin rod spanning the entire ship.
    pivot_y = y + side * 0.44
    fw.cylinder_between(
        f"CHR_V10_LapArm_{tag}",
        (x + 0.10, pivot_y, -0.64),
        (x - 0.10, pivot_y, -0.78),
        0.040,
        mats["steelLight"],
        boat_root,
        vertices=12,
    )
    fw.cylinder_between(
        f"CHR_V10_LapBar_{tag}",
        (x - 0.10, y - 0.34, -0.78),
        (x - 0.10, y + 0.34, -0.78),
        0.052,
        mats["steelLight"],
        boat_root,
        vertices=12,
    )
    fw.box(
        f"CHR_V10_LapPad_{tag}",
        (x - 0.11, y, -0.77),
        (0.16, 0.42, 0.10),
        mats["seatRed"],
        0.045,
        boat_root,
    )

    # Foot rail gives passengers a believable lower-body support without adding
    # tiny feet/character geometry to the asset itself.
    fw.cylinder_between(
        f"CHR_V10_FootRail_{tag}",
        (x - 0.34, y - 0.31, -1.15),
        (x - 0.34, y + 0.31, -1.15),
        0.034,
        mats["steelMid"],
        boat_root,
        vertices=10,
    )

    # Two subtle seat separators/headrest cues.  Large enough to survive the
    # gameplay render, but not so detailed that the visual language becomes 3D-realistic.
    for seat_i, offset in enumerate((-0.17, 0.17)):
        fw.box(
            f"CHR_V10_HeadPad_{tag}_{seat_i}",
            (x + 0.205, y + offset, -0.54),
            (0.09, 0.20, 0.15),
            mats["woodLight"],
            0.040,
            boat_root,
        )


def _build_realistic_seating(boat_root, g, mats):
    """Nine transverse rows split into paired modules with a narrow centre aisle."""
    rows = 9
    length = v9._ship_length(g)
    half_w = float(g["shipHalfWidth"])
    span = length * 0.52

    # Central spine/aisle reads as part of the ride chassis and visually separates
    # the two passenger banks.
    fw.box(
        "CHR_V10_CentreAisle",
        (0.0, 0.0, -1.13),
        (span * 1.05, 0.34, 0.055),
        mats["steelDark"],
        0.020,
        boat_root,
    )

    bank_y = half_w * 0.50
    for row in range(rows):
        x = -span * 0.5 + span * row / (rows - 1)
        # A visible crossmember under each row helps the seats feel mechanically
        # attached to the ship, rather than decorative bars laid on the deck.
        fw.box(
            f"CHR_V10_RowCrossmember_{row:02d}",
            (x + 0.01, 0.0, -1.25),
            (0.26, half_w * 1.56, 0.07),
            mats["steelDark"],
            0.018,
            boat_root,
        )
        _seat_module(boat_root, mats, row=row, x=x, y=-bank_y, side=-1)
        _seat_module(boat_root, mats, row=row, x=x, y= bank_y, side= 1)


def build_swing_group(root, g, mats):
    # V9 supplies the approved hull, prow/stern and shields.  Patch only its
    # seating hook so this pass remains narrowly focused and easy to compare.
    original = v5._build_city_horizon_seating
    try:
        v5._build_city_horizon_seating = _build_realistic_seating
        pivot = v9.build_swing_group(root, g, mats)
    finally:
        v5._build_city_horizon_seating = original

    boat_root = bpy.data.objects.get("BoatRoot")
    if boat_root is None:
        raise RuntimeError("CH_VIKING_V10_BOAT_ROOT_MISSING")
    boat_root["hullRevision"] = "CH_VIKING_SEATING_REALISM_V10"
    boat_root["seatingRevision"] = "paired_padded_ride_seats_with_lapbars_footrails"
    boat_root["visualGoal"] = "more_believable_amusement_seating_keep_city_horizon_stylization"
    return pivot
