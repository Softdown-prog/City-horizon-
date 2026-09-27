"""V8 micro-detail pass for the approved tall City Horizon Viking ship.

V8 intentionally does not alter the V7/V6 mechanical proportions. It adds only
readable amusement-ride detail to the hull and loading platform: plank seams, studs,
rivets, top rails, tread strips, base plates, bolts, hatches and boarding-gate cues.
Runtime remains pre-rendered 2D RGBA and clearance is still enforced by the V6 gate.
"""
from __future__ import annotations

import json
from pathlib import Path

import bpy

import build_ferris_wheel as fw
import viking_ship_fairground_v7_geometry as v7
import viking_ship_imposing_geometry as legacy


_DETAIL_PATH = Path(__file__).resolve().parent / "assets/park_viking_ship_5x4.microdetail_v8.json"


def _details():
    return json.loads(_DETAIL_PATH.read_text(encoding="utf-8"))


hull_sections = v7.hull_sections


def _platform_microdetails(root, g, mats):
    cfg = _details()["platform"]
    deck_z = float(g.get("platformTopZ", 1.02)) + 0.125
    base_w = float(g["baseWidth"])
    base_d = float(g["baseDepth"])
    half_x = float(g["supportHalfWidth"])
    half_y = float(g["supportHalfDepth"])

    # Fine deck seams break the large flat white platform without changing silhouette.
    seam_count = int(cfg.get("deckSeams", 8))
    for i in range(seam_count):
        t = (i + 1) / (seam_count + 1)
        y = -base_d * 0.38 + t * (base_d * 0.76)
        fw.box(
            f"V8DeckSeam_{i:02d}",
            (0.0, y, deck_z),
            (base_w - 1.25, 0.028, 0.018),
            mats["steelMid"],
            0.006,
            root,
        )

    # Heavy bolted mounting plates visually explain how the tall A-frame is anchored.
    if cfg.get("supportBasePlates", True):
        for y_sign, side in ((-1.0, "Front"), (1.0, "Back")):
            for x_sign, label in ((-1.0, "L"), (1.0, "R")):
                x = x_sign * half_x
                y = y_sign * half_y
                fw.box(
                    f"V8SupportPlate_{side}_{label}",
                    (x, y, deck_z + 0.035),
                    (1.28, 1.08, 0.08),
                    mats["steelDark"],
                    0.035,
                    root,
                )
                bolt_offsets = ((-0.43, -0.34), (0.43, -0.34), (-0.43, 0.34), (0.43, 0.34))
                for j, (dx, dy) in enumerate(bolt_offsets):
                    fw.cylinder(
                        f"V8SupportBolt_{side}_{label}_{j}",
                        (x + dx, y + dy, deck_z + 0.095),
                        0.075,
                        0.06,
                        mats["steelLight"],
                        parent=root,
                        vertices=14,
                    )

    # Two recessed service hatches make the base feel like real ride machinery.
    hatch_y = base_d * 0.24
    for i, x in enumerate((-2.15, 2.15)):
        fw.box(
            f"V8ServiceHatch_{i}",
            (x, hatch_y, deck_z + 0.018),
            (1.35, 0.92, 0.045),
            mats["steelMid"],
            0.035,
            root,
        )
        fw.box(
            f"V8ServiceHatchInset_{i}",
            (x, hatch_y - 0.22, deck_z + 0.045),
            (0.48, 0.08, 0.035),
            mats["steelDark"],
            0.012,
            root,
        )

    # Red/white front-edge trim improves fairground readability at gameplay scale.
    if cfg.get("edgeTrimRedWhite", True):
        front_y = -(base_d * 0.5 - 0.34)
        segments = 10
        segment_w = (base_w - 1.4) / segments
        for i in range(segments):
            x = -(base_w - 1.4) * 0.5 + segment_w * (i + 0.5)
            fw.box(
                f"V8FrontEdgeStripe_{i:02d}",
                (x, front_y, deck_z + 0.08),
                (segment_w * 0.72, 0.10, 0.16),
                mats["red"] if i % 2 == 0 else mats["white"],
                0.018,
                root,
            )


def _loading_microdetails(root, g, mats):
    cfg = _details()["platform"]
    base_d = float(g["baseDepth"])
    stair_w = float(g.get("stairWidth", 2.65))
    stair_d = float(g.get("stairDepth", 2.65))
    stair_steps = int(g.get("stairSteps", 6))
    deck_z = float(g.get("platformTopZ", 1.02))

    # Anti-slip tread noses on the visible front staircase.
    count = min(stair_steps, int(cfg.get("stairTreadStrips", stair_steps)))
    for i in range(count):
        t = (i + 0.5) / max(1, stair_steps)
        y = -(base_d * 0.5) - t * stair_d
        z = 0.12 + t * max(0.12, deck_z - 0.14)
        fw.box(
            f"V8StairTread_{i:02d}",
            (0.0, y, z),
            (stair_w * 0.88, 0.09, 0.045),
            mats["steelDark"],
            0.012,
            root,
        )

    # Gate posts at the top of the embarkation stair add a clear boarding cue.
    if cfg.get("boardingGatePosts", True):
        gate_y = -(base_d * 0.5 - 0.18)
        for x_sign, label in ((-1.0, "L"), (1.0, "R")):
            x = x_sign * stair_w * 0.47
            fw.box(
                f"V8BoardingGatePost_{label}",
                (x, gate_y, deck_z + 0.46),
                (0.12, 0.12, 0.92),
                mats["steelBlue"],
                0.025,
                root,
            )
            fw.box(
                f"V8BoardingGateCap_{label}",
                (x, gate_y, deck_z + 0.94),
                (0.20, 0.20, 0.10),
                mats["red"],
                0.025,
                root,
            )


def build_base(root, g, mats):
    base = v7.build_base(root, g, mats)
    _platform_microdetails(root, g, mats)
    return base


def build_loading_zone(root, g, mats):
    zone = v7.build_loading_zone(root, g, mats)
    _loading_microdetails(root, g, mats)
    return zone


def build_supports(root, g, mats):
    return v7.build_supports(root, g, mats)


def _boat_microdetails(boat_root, g, mats):
    cfg = _details()["ship"]
    length = float(g["shipLength"])
    half_w = float(g["shipHalfWidth"])

    # Long wood plank seams and a dark top rail add depth to the hull side.
    seam_count = int(cfg.get("sidePlankSeams", 4))
    for y_sign, side in ((-1.0, "Front"), (1.0, "Back")):
        side_y = y_sign * (half_w + 0.205)
        for i in range(seam_count):
            z = -1.56 - i * 0.29
            fw.box(
                f"V8PlankSeam_{side}_{i:02d}",
                (0.0, side_y, z),
                (length * (0.74 - i * 0.035), 0.026, 0.034),
                mats["woodDark"],
                0.008,
                boat_root,
            )

        fw.box(
            f"V8HullTopRail_{side}",
            (0.0, side_y, -1.37),
            (length * 0.78, float(cfg.get("topRailThickness", 0.10)), 0.12),
            mats["woodLight"],
            0.025,
            boat_root,
        )

        # Vertical studs and paired rivets break the long side fascia into engineered panels.
        stud_count = int(cfg.get("verticalHullStuds", 9))
        span = length * 0.67
        for i in range(stud_count):
            x = -span * 0.5 + span * (i / max(1, stud_count - 1))
            fw.box(
                f"V8HullStud_{side}_{i:02d}",
                (x, side_y + y_sign * 0.018, -1.90),
                (0.055, 0.032, 0.68),
                mats["gold"] if i % 3 == 1 else mats["steelDark"],
                0.01,
                boat_root,
            )

        rivet_count = int(cfg.get("rivetPairsPerSide", 11))
        rivet_span = length * 0.70
        for i in range(rivet_count):
            x = -rivet_span * 0.5 + rivet_span * (i / max(1, rivet_count - 1))
            for z_index, z in enumerate((-1.56, -2.18)):
                legacy._sphere(
                    f"V8HullRivet_{side}_{i:02d}_{z_index}",
                    (x, side_y + y_sign * 0.055, z),
                    (0.052, 0.032, 0.052),
                    mats["gold"],
                    boat_root,
                    10,
                    5,
                )

    # Small metallic caps at seat ends improve readability without exposing the bench stack.
    if cfg.get("seatEndCaps", True):
        usable = length * 0.58
        rows = max(6, int(g.get("seatRows", 8)))
        for i in range(rows):
            x = -usable * 0.5 + usable * (i / max(1, rows - 1))
            for y_sign, side in ((-1.0, "F"), (1.0, "B")):
                legacy._sphere(
                    f"V8SeatEndCap_{i:02d}_{side}",
                    (x, y_sign * half_w * 0.69, -1.11),
                    (0.085, 0.055, 0.085),
                    mats["steelLight"],
                    boat_root,
                    10,
                    5,
                )


def build_swing_group(root, g, mats, base):
    pivot = v7.build_swing_group(root, g, mats, base)
    boat_root = bpy.data.objects.get("BoatRoot")
    if boat_root is None:
        raise RuntimeError("CH_VIKING_V8_BOAT_ROOT_MISSING")
    _boat_microdetails(boat_root, g, mats)
    return pivot
