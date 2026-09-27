"""V9 finish-detail pass for the approved City Horizon Viking ship.

This pass keeps V8/V7/V6 proportions, clearance and footprint intact.  It adds
stronger amusement-ride identity to the rear artwork panel, pivot housings,
boat fascia and passenger/loading platform without changing the ride silhouette.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import bpy

import build_ferris_wheel as fw
import viking_ship_fairground_v8_geometry as v8
import viking_ship_imposing_geometry as legacy


_DETAIL_PATH = Path(__file__).resolve().parent / "assets/park_viking_ship_5x4.microdetail_v9.json"


def _details():
    return json.loads(_DETAIL_PATH.read_text(encoding="utf-8"))


hull_sections = v8.hull_sections


def _rear_panel_finish(root, g, mats):
    cfg = _details()["rearPanel"]
    half_x = float(g["supportHalfWidth"])
    half_y = float(g["supportHalfDepth"])
    pivot_z = float(g["pivotZ"])
    y = half_y + 0.50

    if cfg.get("darkBorder", True):
        legacy.beam_between("V9PanelBorderL", (-half_x * 0.78, y, 1.34), (0.0, y, pivot_z - 0.66),
                            0.16, 0.10, mats["steelDark"], root, 0.025)
        legacy.beam_between("V9PanelBorderR", (half_x * 0.78, y, 1.34), (0.0, y, pivot_z - 0.66),
                            0.16, 0.10, mats["steelDark"], root, 0.025)
        fw.box("V9PanelBorderBottom", (0.0, y, 1.35), (half_x * 1.55, 0.10, 0.16),
               mats["steelDark"], 0.025, root)

    center_z = 4.25
    if cfg.get("centralMedallion", True):
        fw.cylinder("V9RearMedallionOuter", (0.0, y - 0.08, center_z), 0.82, 0.10,
                    mats["steelDark"], rotation=(math.radians(90.0), 0.0, 0.0),
                    parent=root, vertices=28)
        fw.cylinder("V9RearMedallionRing", (0.0, y - 0.14, center_z), 0.63, 0.08,
                    mats["red"], rotation=(math.radians(90.0), 0.0, 0.0),
                    parent=root, vertices=28)
        fw.cylinder("V9RearMedallionBoss", (0.0, y - 0.20, center_z), 0.28, 0.08,
                    mats["gold"], rotation=(math.radians(90.0), 0.0, 0.0),
                    parent=root, vertices=24)

    # Graphic rays make the cream panel read as painted fairground artwork rather than blank canvas.
    ray_count = int(cfg.get("radialGraphicBars", 6))
    for i in range(ray_count):
        angle = -58.0 + i * (116.0 / max(1, ray_count - 1))
        length = 2.55 if i not in (0, ray_count - 1) else 2.15
        radians = math.radians(angle)
        end_x = math.cos(radians) * length
        end_z = center_z + math.sin(radians) * length
        legacy.beam_between(
            f"V9RearRay_{i:02d}",
            (0.0, y - 0.11, center_z),
            (end_x, y - 0.11, end_z),
            0.095,
            0.06,
            mats["red"] if i % 2 == 0 else mats["steelBlue"],
            root,
            0.018,
        )

    if cfg.get("redWhiteAccentBlocks", True):
        for i, x in enumerate((-3.55, -2.55, 2.55, 3.55)):
            fw.box(
                f"V9RearAccentBlock_{i}",
                (x, y - 0.13, 2.06 + (0.26 if i % 2 else 0.0)),
                (0.48, 0.07, 0.24),
                mats["white"] if i % 2 else mats["red"],
                0.018,
                root,
            )


def _support_finish(root, g, mats):
    cfg = _details()["support"]
    half_y = float(g["supportHalfDepth"])
    pivot_z = float(g["pivotZ"])

    if cfg.get("upperHubPlates", True):
        bolt_count = max(6, int(cfg.get("upperHubBolts", 8)))
        for y_sign, side in ((-1.0, "Front"), (1.0, "Back")):
            y = y_sign * (half_y + 0.58)
            fw.cylinder(
                f"V9PivotFace_{side}",
                (0.0, y, pivot_z),
                0.92,
                0.13,
                mats["steelDark"],
                rotation=(math.radians(90.0), 0.0, 0.0),
                parent=root,
                vertices=32,
            )
            fw.cylinder(
                f"V9PivotRing_{side}",
                (0.0, y + y_sign * 0.08, pivot_z),
                0.68,
                0.09,
                mats["yellow"],
                rotation=(math.radians(90.0), 0.0, 0.0),
                parent=root,
                vertices=28,
            )
            for i in range(bolt_count):
                a = (math.tau * i) / bolt_count
                legacy._sphere(
                    f"V9PivotBolt_{side}_{i:02d}",
                    (math.cos(a) * 0.73, y + y_sign * 0.17, pivot_z + math.sin(a) * 0.73),
                    (0.075, 0.045, 0.075),
                    mats["steelLight"],
                    root,
                    10,
                    5,
                )

    if cfg.get("footHardwareAccents", True):
        half_x = float(g["supportHalfWidth"])
        for y_sign, side in ((-1.0, "Front"), (1.0, "Back")):
            for x_sign, label in ((-1.0, "L"), (1.0, "R")):
                x = x_sign * half_x
                y = y_sign * half_y
                fw.box(f"V9FootRedCap_{side}_{label}", (x, y - y_sign * 0.48, 0.58),
                       (0.62, 0.08, 0.24), mats["red"], 0.025, root)
                fw.box(f"V9FootWhiteCap_{side}_{label}", (x, y - y_sign * 0.53, 0.58),
                       (0.27, 0.04, 0.12), mats["white"], 0.015, root)


def _platform_finish(root, g, mats):
    cfg = _details()["platform"]
    base_w = float(g["baseWidth"])
    base_d = float(g["baseDepth"])
    deck_z = float(g.get("platformTopZ", 1.02)) + 0.145

    if cfg.get("perimeterBlueTrim", True):
        fw.box("V9DeckTrimFront", (0.0, -(base_d * 0.5 - 0.22), deck_z),
               (base_w - 0.75, 0.085, 0.09), mats["steelBlue"], 0.015, root)
        fw.box("V9DeckTrimBack", (0.0, base_d * 0.5 - 0.22, deck_z),
               (base_w - 0.75, 0.085, 0.09), mats["steelBlue"], 0.015, root)
        fw.box("V9DeckTrimLeft", (-(base_w * 0.5 - 0.22), 0.0, deck_z),
               (0.085, base_d - 0.75, 0.09), mats["steelBlue"], 0.015, root)
        fw.box("V9DeckTrimRight", (base_w * 0.5 - 0.22, 0.0, deck_z),
               (0.085, base_d - 0.75, 0.09), mats["steelBlue"], 0.015, root)

    # Alternating blocks at the boarding edge give the platform a safety-zone read.
    block_count = max(6, int(cfg.get("boardingHazardBlocks", 8)))
    hazard_y = -(base_d * 0.5 - 0.74)
    span = 5.2
    for i in range(block_count):
        x = -span * 0.5 + span * (i / max(1, block_count - 1))
        fw.box(f"V9BoardingHazard_{i:02d}", (x, hazard_y, deck_z + 0.035),
               (0.46, 0.34, 0.07), mats["yellow"] if i % 2 == 0 else mats["steelDark"],
               0.018, root)

    # Two simple grated maintenance zones add plausible machinery access detail.
    grate_count = max(1, int(cfg.get("maintenanceGrates", 2)))
    grate_xs = (-3.05, 3.05)[:grate_count]
    for gi, x in enumerate(grate_xs):
        fw.box(f"V9GrateBase_{gi}", (x, 2.25, deck_z + 0.02),
               (1.45, 0.92, 0.045), mats["steelDark"], 0.02, root)
        for si in range(5):
            sy = 1.92 + si * 0.16
            fw.box(f"V9GrateSlat_{gi}_{si}", (x, sy, deck_z + 0.055),
                   (1.17, 0.055, 0.035), mats["steelLight"], 0.008, root)

    if cfg.get("railingFootBlocks", True):
        for x in (-5.35, -3.40, 3.40, 5.35):
            fw.box("V9RailFoot_%s" % str(x).replace("-", "m").replace(".", "p"),
                   (x, -(base_d * 0.5 - 0.46), deck_z + 0.08),
                   (0.22, 0.22, 0.16), mats["steelDark"], 0.025, root)

    if cfg.get("operatorConsoleAccents", True):
        # Small light/button cluster; no ticket booth is added.
        console_y = -(base_d * 0.5 - 1.60)
        console_x = 4.65
        for i, (dx, key) in enumerate(((-0.18, "red"), (0.0, "yellow"), (0.18, "teal"))):
            legacy._sphere(f"V9ConsoleButton_{i}", (console_x + dx, console_y - 0.36, 1.72),
                           (0.075, 0.045, 0.075), mats[key], root, 10, 5)


def build_base(root, g, mats):
    base = v8.build_base(root, g, mats)
    _platform_finish(root, g, mats)
    return base


def build_loading_zone(root, g, mats):
    return v8.build_loading_zone(root, g, mats)


def build_supports(root, g, mats):
    supports = v8.build_supports(root, g, mats)
    _support_finish(root, g, mats)
    _rear_panel_finish(root, g, mats)
    return supports


def _boat_finish(boat_root, g, mats):
    cfg = _details()["boat"]
    length = float(g["shipLength"])
    half_w = float(g["shipHalfWidth"])

    strakes = max(2, int(cfg.get("lowerWoodStrakesPerSide", 3)))
    for y_sign, side in ((-1.0, "Front"), (1.0, "Back")):
        y = y_sign * (half_w + 0.225)
        for i in range(strakes):
            z = -2.34 - i * 0.30
            fw.box(
                f"V9WoodStrake_{side}_{i:02d}",
                (0.0, y, z),
                (length * (0.65 - i * 0.055), 0.035, 0.085),
                mats["woodLight"] if i % 2 == 0 else mats["woodDark"],
                0.012,
                boat_root,
            )

        if cfg.get("decorativeGoldRail", True):
            fw.box(f"V9GoldHullRail_{side}", (0.0, y + y_sign * 0.035, -1.28),
                   (length * 0.72, 0.055, 0.075), mats["gold"], 0.018, boat_root)

        if cfg.get("shieldRingAccents", True):
            for i, x in enumerate((-4.45, -2.95, -1.48, 0.0, 1.48, 2.95, 4.45)):
                fw.cylinder(
                    f"V9ShieldRing_{side}_{i}",
                    (x, y + y_sign * 0.12, -1.86),
                    0.36,
                    0.035,
                    mats["red"] if i % 2 else mats["white"],
                    rotation=(math.radians(90.0), 0.0, 0.0),
                    parent=boat_root,
                    vertices=22,
                )

    if cfg.get("prowAccentBands", True):
        half_len = length * 0.5
        for x_sign, label in ((-1.0, "L"), (1.0, "R")):
            for j, (scale, key, z) in enumerate(((1.01, "red", -0.46), (1.055, "white", 0.08))):
                legacy._sphere(
                    f"V9ProwBand_{label}_{j}",
                    (x_sign * half_len * scale, 0.0, z),
                    (0.25, 0.31, 0.12),
                    mats[key],
                    boat_root,
                    14,
                    7,
                )

    if cfg.get("seatHardwareAccents", True):
        rows = max(6, int(g.get("seatRows", 8)))
        usable = length * 0.58
        for i in range(rows):
            x = -usable * 0.5 + usable * (i / max(1, rows - 1))
            fw.box(f"V9SeatLatch_{i}", (x - 0.16, -0.02, -0.94),
                   (0.12, 0.34, 0.09), mats["gold"] if i % 2 else mats["steelLight"],
                   0.015, boat_root)


def build_swing_group(root, g, mats, base):
    pivot = v8.build_swing_group(root, g, mats, base)
    boat_root = bpy.data.objects.get("BoatRoot")
    if boat_root is None:
        raise RuntimeError("CH_VIKING_V9_BOAT_ROOT_MISSING")
    _boat_finish(boat_root, g, mats)
    return pivot
