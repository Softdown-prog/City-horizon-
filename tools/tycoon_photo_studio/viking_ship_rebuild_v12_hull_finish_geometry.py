"""V12 hull/prow finish pass for the City Horizon Viking ship ride.

Builds on the approved V11 passenger-cabin readability pass.  This revision
leaves the 5x4 footprint, A-frame, suspension and seating system intact and
concentrates on the suspended longship itself: stronger wood construction
rhythm, a layered upper gunwale, a more sculptural original prow/stern, and a
closer shield cadence that follows the sheer line.  Classic park-game assets
remain a readability reference only; no reference geometry is copied.
"""
from __future__ import annotations

import math

import bpy

import build_ferris_wheel as fw
import viking_ship_rebuild_v9_ship_overhaul_geometry as v9
import viking_ship_rebuild_v11_readability_geometry as v11

build_base = v11.build_base
build_supports = v11.build_supports
build_loading_zone = v11.build_loading_zone
beam_between = v11.beam_between
hull_sections = v11.hull_sections


def _remove_old_shields():
    """V9 shields were useful for exploration but are too sparse for the final rhythm."""
    prefixes = ("CHR_V9_Shield_", "CHR_V9_ShieldBoss_")
    for obj in list(bpy.data.objects):
        if obj.name.startswith(prefixes):
            bpy.data.objects.remove(obj, do_unlink=True)


def _section_at(g, x):
    return min(v9.hull_sections(g), key=lambda s: abs(s[0] - x))


def _add_layered_hull_finish(boat_root, g, mats):
    sections = v9.hull_sections(g)

    # Large, readable timber courses rather than tiny surface noise.  The bands
    # sit slightly proud of the hull and alternate values so the shell reads as
    # built timber at gameplay scale.
    for side, label in ((-1.0, "Near"), (1.0, "Far")):
        for i in range(len(sections) - 1):
            x0, w0, top0, mid0, keel0 = sections[i]
            x1, w1, top1, mid1, keel1 = sections[i + 1]

            # Dark lower lip beneath the bright V11 gunwale gives the rim depth.
            fw.cylinder_between(
                f"CHR_V12_GunwaleShadow_{label}_{i:02d}",
                (x0, side * (w0 + 0.025), top0 - 0.025),
                (x1, side * (w1 + 0.025), top1 - 0.025),
                0.125,
                mats["woodDark"],
                boat_root,
                vertices=12,
            )
            fw.cylinder_between(
                f"CHR_V12_GunwaleCap_{label}_{i:02d}",
                (x0, side * (w0 + 0.070), top0 + 0.145),
                (x1, side * (w1 + 0.070), top1 + 0.145),
                0.075,
                mats["woodLight"],
                boat_root,
                vertices=12,
            )

            # Three broad clinker/readability courses.  These are deliberately
            # fewer and thicker than realistic planking so they survive the 2D render.
            for course, frac in enumerate((0.30, 0.55, 0.78)):
                z0 = top0 + (keel0 - top0) * frac
                z1 = top1 + (keel1 - top1) * frac
                inset = 1.0 - course * 0.035
                mat = mats["woodLight"] if course == 1 else mats["woodDark"]
                fw.cylinder_between(
                    f"CHR_V12_TimberCourse_{label}_{course}_{i:02d}",
                    (x0, side * w0 * inset, z0),
                    (x1, side * w1 * inset, z1),
                    0.060 if course < 2 else 0.050,
                    mat,
                    boat_root,
                    vertices=10,
                )

            # A restrained red accent just under the cap helps separate inside/outside.
            fw.cylinder_between(
                f"CHR_V12_RedRim_{label}_{i:02d}",
                (x0, side * (w0 + 0.080), top0 - 0.10),
                (x1, side * (w1 + 0.080), top1 - 0.10),
                0.050,
                mats["red"],
                boat_root,
                vertices=10,
            )


def _add_close_shield_rhythm(boat_root, g, mats):
    """Nine shields per side, tucked under the gunwale and following the arc."""
    _remove_old_shields()
    length = v9._ship_length(g)
    xs = [length * t for t in (-0.32, -0.24, -0.16, -0.08, 0.0, 0.08, 0.16, 0.24, 0.32)]
    palette = ("red", "white", "gold", "red", "white", "gold", "red", "white", "gold")

    for side, label in ((-1.0, "Near"), (1.0, "Far")):
        for idx, (x, key) in enumerate(zip(xs, palette)):
            _sx, w, top, mid, _keel = _section_at(g, x)
            y = side * (w + 0.16)
            z = top + (mid - top) * 0.38
            fw.cylinder(
                f"CHR_V12_Shield_{label}_{idx:02d}",
                (x, y, z),
                0.40,
                0.080,
                mats[key],
                rotation=(math.radians(90.0), 0.0, 0.0),
                parent=boat_root,
                vertices=22,
            )
            fw.cylinder(
                f"CHR_V12_ShieldBoss_{label}_{idx:02d}",
                (x, y + side * 0.060, z),
                0.105,
                0.072,
                mats["steelMid"],
                rotation=(math.radians(90.0), 0.0, 0.0),
                parent=boat_root,
                vertices=14,
            )


def _add_original_prow(boat_root, g, mats):
    """Layered City Horizon beast-prow with broad forms, not tiny carving detail."""
    half = v9._ship_length(g) * 0.5

    # Forward stem becomes a sweeping stacked silhouette with a bright inner edge.
    prow_points = [
        (half * 0.91, 0.0, 0.60),
        (half * 1.00, 0.0, 1.45),
        (half * 1.06, 0.0, 2.28),
        (half * 1.105, 0.0, 2.92),
    ]
    for i in range(len(prow_points) - 1):
        beam_between(
            f"CHR_V12_ProwSpine_{i}",
            prow_points[i], prow_points[i + 1],
            0.23 - i * 0.025,
            0.30 - i * 0.025,
            mats["woodDark"], boat_root, 0.018,
        )
        # Lighter face on the stem makes the curve readable from the camera side.
        a = prow_points[i]
        b = prow_points[i + 1]
        beam_between(
            f"CHR_V12_ProwHighlight_{i}",
            (a[0] - 0.025, -0.055, a[2] + 0.02),
            (b[0] - 0.025, -0.055, b[2] + 0.02),
            0.090,
            0.105,
            mats["woodLight"], boat_root, 0.010,
        )

    # Original angular animal head: broad brow, muzzle and two swept horns.
    fw.box(
        "CHR_V12_ProwHead",
        (half * 1.135, -0.01, 2.96),
        (0.68, 0.52, 0.42),
        mats["woodLight"],
        0.055,
        boat_root,
    )
    beam_between(
        "CHR_V12_ProwMuzzle",
        (half * 1.16, -0.01, 2.94),
        (half * 1.235, -0.04, 2.78),
        0.15, 0.19, mats["gold"], boat_root, 0.018,
    )
    for side in (-1.0, 1.0):
        beam_between(
            f"CHR_V12_ProwHorn_{'N' if side < 0 else 'F'}",
            (half * 1.12, side * 0.18, 3.12),
            (half * 1.075, side * 0.42, 3.52),
            0.070, 0.085, mats["white"], boat_root, 0.010,
        )
        beam_between(
            f"CHR_V12_ProwCheek_{'N' if side < 0 else 'F'}",
            (half * 1.10, side * 0.20, 2.92),
            (half * 1.18, side * 0.24, 2.76),
            0.065, 0.080, mats["red"], boat_root, 0.008,
        )


def _add_stern_fan(boat_root, g, mats):
    """A tall fan-tail keeps stern identity distinct from the beast prow."""
    half = v9._ship_length(g) * 0.5
    base = (-half * 1.02, 0.0, 1.58)
    tips = (
        (-half * 1.11, -0.34, 2.72),
        (-half * 1.13, 0.00, 2.94),
        (-half * 1.11, 0.34, 2.72),
    )
    for i, tip in enumerate(tips):
        beam_between(
            f"CHR_V12_SternFan_{i}",
            base, tip,
            0.105, 0.125,
            mats["woodDark"], boat_root, 0.012,
        )
    fw.box(
        "CHR_V12_SternFanCap",
        (-half * 1.105, 0.0, 2.55),
        (0.36, 0.62, 0.18),
        mats["gold"], 0.025, boat_root,
    )


def build_swing_group(root, g, mats):
    pivot = v11.build_swing_group(root, g, mats)
    boat_root = bpy.data.objects.get("BoatRoot")
    if boat_root is None:
        raise RuntimeError("CH_VIKING_V12_BOAT_ROOT_MISSING")

    _add_layered_hull_finish(boat_root, g, mats)
    _add_close_shield_rhythm(boat_root, g, mats)
    _add_original_prow(boat_root, g, mats)
    _add_stern_fan(boat_root, g, mats)

    boat_root["hullRevision"] = "CH_VIKING_HULL_FINISH_V12"
    boat_root["finishPass"] = "layered_timber_gunwale_close_shields_original_prow_stern"
    boat_root["referenceUse"] = "readability_and_composition_only_not_geometry_copy"
    boat_root["visualGoal"] = "richer_original_longship_shell_matching_v11_passenger_quality"
    return pivot
