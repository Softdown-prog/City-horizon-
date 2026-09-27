"""V11 readability pass for the City Horizon Viking ship ride.

This revision keeps the approved V9/V10 hull and amusement-ride mechanics, but
pushes the lessons that make classic isometric park assets readable from far away:
stronger upper gunwales, a framed passenger well, slightly raised/compacted seat
banks, and broad interior colour separation.  The goal is not to copy any RCT
asset; it is to improve hierarchy and gameplay-scale readability while keeping
City Horizon's cleaner stylized rendering language.
"""
from __future__ import annotations

import bpy

import build_ferris_wheel as fw
import viking_ship_rebuild_v9_ship_overhaul_geometry as v9
import viking_ship_rebuild_v10_seating_geometry as v10

build_base = v10.build_base
build_supports = v10.build_supports
build_loading_zone = v10.build_loading_zone
beam_between = v10.beam_between
hull_sections = v10.hull_sections

_ORIGINAL_V10_SEATING = v10._build_realistic_seating


def _build_raised_compact_seating(boat_root, g, mats):
    """Reuse the proven V10 seats as one lifted, slightly denser passenger bank."""
    group = bpy.data.objects.new("CHR_V11_PassengerBank", None)
    bpy.context.scene.collection.objects.link(group)
    group.parent = boat_root
    # Lift seats enough to read over the gunwale at isometric gameplay scale,
    # while keeping them clearly inside the hull.
    group.location = (0.0, 0.0, 0.20)
    group.scale = (0.96, 0.92, 1.0)
    _ORIGINAL_V10_SEATING(group, g, mats)
    group["seatPresentation"] = "raised_compact_passenger_mass_v11"


def _add_passenger_well_frame(boat_root, g, mats):
    """Frame the seat area so it reads as an intentional ride cabin, not loose furniture."""
    sections = v9.hull_sections(g)

    # Broad upper rim: stronger than V9's decorative line, but still slim enough
    # to preserve the elegant longship arc.
    for side, label in ((-1.0, "Near"), (1.0, "Far")):
        for i in range(len(sections) - 1):
            x0, w0, t0, m0, _ = sections[i]
            x1, w1, t1, m1, _ = sections[i + 1]
            fw.cylinder_between(
                f"CHR_V11_UpperGunwale_{label}_{i:02d}",
                (x0, side * (w0 + 0.045), t0 + 0.105),
                (x1, side * (w1 + 0.045), t1 + 0.105),
                0.105,
                mats["woodLight"],
                boat_root,
                vertices=12,
            )

            # Inner coloured rail separates the passenger area from the shell and
            # creates the bold value rhythm that survives downsampling.
            inner0_y = side * w0 * 0.73
            inner1_y = side * w1 * 0.73
            z0 = t0 + (m0 - t0) * 0.30
            z1 = t1 + (m1 - t1) * 0.30
            fw.cylinder_between(
                f"CHR_V11_InnerRail_{label}_{i:02d}",
                (x0, inner0_y, z0),
                (x1, inner1_y, z1),
                0.070,
                mats["red"],
                boat_root,
                vertices=12,
            )

    # End bulkheads visually close the passenger well without boxing in the ship.
    length = v9._ship_length(g)
    half_w = float(g["shipHalfWidth"])
    for sign, label in ((-1.0, "Stern"), (1.0, "Bow")):
        x = sign * length * 0.285
        fw.box(
            f"CHR_V11_{label}SeatBulkhead",
            (x, 0.0, -0.70),
            (0.16, half_w * 1.48, 0.62),
            mats["woodLight"],
            0.035,
            boat_root,
        )
        fw.box(
            f"CHR_V11_{label}BulkheadAccent",
            (x - sign * 0.09, 0.0, -0.60),
            (0.055, half_w * 1.34, 0.42),
            mats["red"],
            0.022,
            boat_root,
        )


def _add_seat_bank_endrails(boat_root, g, mats):
    """Add simple manufactured-ride side rails around the denser seat bank."""
    length = v9._ship_length(g)
    half_w = float(g["shipHalfWidth"])
    x0 = -length * 0.27
    x1 = length * 0.27
    y = half_w * 0.78
    z = -0.55

    for side, label in ((-1.0, "Near"), (1.0, "Far")):
        yy = side * y
        fw.cylinder_between(
            f"CHR_V11_CabinTopRail_{label}",
            (x0, yy, z), (x1, yy, z),
            0.055, mats["gold"], boat_root, vertices=12,
        )
        for idx, x in enumerate((x0, -length * 0.09, length * 0.09, x1)):
            fw.cylinder_between(
                f"CHR_V11_CabinPost_{label}_{idx}",
                (x, yy, -1.12), (x, yy, z),
                0.046, mats["steelDark"], boat_root, vertices=10,
            )


def build_swing_group(root, g, mats):
    # Patch only the seat builder used by V10.  V9 hull/prow/shields and all
    # mechanical suspension remain the approved canonical base.
    original = v10._build_realistic_seating
    try:
        v10._build_realistic_seating = _build_raised_compact_seating
        pivot = v10.build_swing_group(root, g, mats)
    finally:
        v10._build_realistic_seating = original

    boat_root = bpy.data.objects.get("BoatRoot")
    if boat_root is None:
        raise RuntimeError("CH_VIKING_V11_BOAT_ROOT_MISSING")

    _add_passenger_well_frame(boat_root, g, mats)
    _add_seat_bank_endrails(boat_root, g, mats)

    boat_root["hullRevision"] = "CH_VIKING_READABILITY_V11"
    boat_root["readabilityPass"] = "raised_compact_seats_framed_passenger_well_stronger_gunwale"
    boat_root["referenceUse"] = "hierarchy_and_gameplay_readability_only_not_geometry_copy"
    boat_root["visualGoal"] = "complete_themed_ride_cabin_inside_original_city_horizon_longship"
    return pivot
