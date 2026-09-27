"""V7 visual-detail pass for the City Horizon fairground Viking ship.

V6 fixed the ride's height and clearance. V7 keeps that approved mechanical scale and
adds the visual cues still missing from the proxy: a rear fairground artwork panel,
heavier illuminated fascia, and a much more distinctive Viking bow/stern silhouette.
The source remains deterministic CH Blender geometry; runtime remains pre-rendered 2D.
"""
from __future__ import annotations

import math
import bpy

import build_ferris_wheel as fw
import viking_ship_fairground_v5_geometry as v5
import viking_ship_imposing_geometry as legacy


hull_sections = v5.hull_sections
build_base = v5.build_base
build_loading_zone = v5.build_loading_zone


def _boat_root():
    obj = bpy.data.objects.get("BoatRoot")
    if obj is None:
        raise RuntimeError("CH_VIKING_V7_BOAT_ROOT_MISSING")
    return obj


def _rear_fairground_panel(root, g, mats):
    """Large rear decoration like a travelling fair ride, safely behind the swing plane."""
    half_x = float(g["supportHalfWidth"])
    half_y = float(g["supportHalfDepth"])
    pivot_z = float(g["pivotZ"])
    y = half_y + 0.42

    left = (-half_x * 0.78, y, 1.30)
    right = (half_x * 0.78, y, 1.30)
    apex = (0.0, y, pivot_z - 0.65)
    legacy._triangle_panel("V7RearPanelCream", (left, right, apex), mats["panelCream"], root)

    center = (0.0, y + 0.03, 2.05)
    accents = [
        ((-half_x * 0.74, y + 0.04, 1.38), (-half_x * 0.20, y + 0.04, 1.38), center, "red"),
        ((-half_x * 0.18, y + 0.05, 1.38), (0.0, y + 0.05, pivot_z - 0.76), center, "yellow"),
        ((0.0, y + 0.06, pivot_z - 0.76), (half_x * 0.18, y + 0.06, 1.38), center, "steelBlue"),
        ((half_x * 0.20, y + 0.07, 1.38), (half_x * 0.74, y + 0.07, 1.38), center, "red"),
    ]
    for i, (a, b, c, mat_key) in enumerate(accents):
        legacy._triangle_panel(f"V7RearPanelAccent_{i:02d}", (a, b, c), mats[mat_key], root)

    # Strong dark graphic strokes give a pirate/Viking fairground read at gameplay scale.
    legacy.beam_between("V7RearRuneL", (-half_x * 0.56, y - 0.04, 1.70),
                        (half_x * 0.10, y - 0.04, pivot_z - 1.20), 0.16, 0.10,
                        mats["steelDark"], root, 0.025)
    legacy.beam_between("V7RearRuneR", (half_x * 0.56, y - 0.05, 1.70),
                        (-half_x * 0.10, y - 0.05, pivot_z - 1.20), 0.16, 0.10,
                        mats["steelDark"], root, 0.025)


def build_supports(root, g, mats):
    supports = v5.build_supports(root, g, mats)
    _rear_fairground_panel(root, g, mats)

    # Add chunky lower gusset blocks so the tall legs read as engineered machinery.
    half_x = float(g["supportHalfWidth"])
    half_y = float(g["supportHalfDepth"])
    for y_sign, side in ((-1.0, "Front"), (1.0, "Back")):
        for x_sign, label in ((-1.0, "L"), (1.0, "R")):
            fw.box(
                f"V7FootGusset_{side}_{label}",
                (x_sign * (half_x - 0.30), y_sign * half_y, 1.12),
                (1.35, 0.88, 1.10),
                mats["steelBlue"],
                0.07,
                root,
            )
            fw.box(
                f"V7FootStripe_{side}_{label}",
                (x_sign * (half_x - 0.30), y_sign * (half_y + 0.47), 1.12),
                (0.82, 0.07, 0.28),
                mats["red"],
                0.025,
                root,
            )
    return supports


def _add_viking_end(boat_root, x_sign, label, g, mats):
    """Build a tall stylized Viking/pirate prow with visible neck/head and color bands."""
    half_len = float(g["shipLength"]) * 0.5
    x0 = x_sign * (half_len * 0.86)
    x1 = x_sign * (half_len * 1.03)
    x2 = x_sign * (half_len * 1.10)

    # Curved read made from three thick deterministic segments.
    v5.beam_between(f"V7ProwLower_{label}", (x0, 0.0, -1.45), (x1, 0.0, -0.55),
                    0.28, 0.34, mats["woodLight"], boat_root, 0.06)
    v5.beam_between(f"V7ProwNeck_{label}", (x1, 0.0, -0.55), (x2, 0.0, 0.38),
                    0.24, 0.30, mats["woodLight"], boat_root, 0.06)
    v5.beam_between(f"V7ProwDarkBand_{label}", (x0, -0.19, -1.40), (x1, -0.19, -0.50),
                    0.08, 0.08, mats["steelDark"], boat_root, 0.02)

    legacy._sphere(f"V7ProwHead_{label}", (x2, 0.0, 0.46), (0.42, 0.34, 0.34),
                   mats["gold"], boat_root, 18, 9)
    legacy._sphere(f"V7ProwEyeFront_{label}", (x2 + x_sign * 0.08, -0.28, 0.53),
                   (0.075, 0.045, 0.075), mats["red"], boat_root, 12, 6)
    legacy._sphere(f"V7ProwEyeBack_{label}", (x2 + x_sign * 0.08, 0.28, 0.53),
                   (0.075, 0.045, 0.075), mats["red"], boat_root, 12, 6)


def _add_hull_fascia(boat_root, g, mats):
    length = float(g["shipLength"])
    half_w = float(g["shipHalfWidth"])
    for y_sign, side in ((-1.0, "Front"), (1.0, "Back")):
        y = y_sign * (half_w + 0.14)
        # Broad red/white/black bands make the hull read as a decorated amusement ride.
        fw.box(f"V7HullRedBand_{side}", (0.0, y, -1.88),
               (length * 0.76, 0.08, 0.26), mats["red"], 0.035, boat_root)
        fw.box(f"V7HullWhiteBand_{side}", (0.0, y + y_sign * 0.05, -1.70),
               (length * 0.70, 0.045, 0.10), mats["white"], 0.018, boat_root)
        fw.box(f"V7HullBlackBand_{side}", (0.0, y + y_sign * 0.08, -2.05),
               (length * 0.64, 0.035, 0.09), mats["steelDark"], 0.018, boat_root)

        for i, x in enumerate((-4.45, -3.05, -1.55, 0.0, 1.55, 3.05, 4.45)):
            r = 0.36 if i in (0, 6) else 0.31
            fw.cylinder(f"V7Shield_{side}_{i:02d}", (x, y + y_sign * 0.09, -1.86),
                        r, 0.08, mats["white"] if i % 2 else mats["steelDark"],
                        rotation=(math.radians(90.0), 0.0, 0.0), parent=boat_root, vertices=20)
            fw.cylinder(f"V7ShieldBoss_{side}_{i:02d}", (x, y + y_sign * 0.15, -1.86),
                        r * 0.34, 0.05, mats["gold"],
                        rotation=(math.radians(90.0), 0.0, 0.0), parent=boat_root, vertices=16)


def build_swing_group(root, g, mats, base):
    pivot = v5.build_swing_group(root, g, mats, base)
    boat_root = _boat_root()
    _add_viking_end(boat_root, -1.0, "L", g, mats)
    _add_viking_end(boat_root, 1.0, "R", g, mats)
    _add_hull_fascia(boat_root, g, mats)
    return pivot
