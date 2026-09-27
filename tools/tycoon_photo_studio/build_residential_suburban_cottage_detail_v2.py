"""High-detail CH Blender pass for residential_suburban_cottage_3x3_01.

This keeps the approved pilot massing and adds the richer game-readable detail
seen in the latest visual target: roof shingles/ridge caps, fascia/gutters,
corner trim, stronger window casings, door panels, porch light, foundation
courses, richer shrubs and flower clusters.

The guarded workflow remains unchanged: preflight -> SOUTH proxy -> approval ->
final four directions. This module decorates the existing guarded builder rather
than duplicating camera/studio/gate logic.
"""
from __future__ import annotations

import math
from pathlib import Path
import sys

import bpy

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import build_residential_suburban_cottage_guarded as base  # noqa: E402


def _box(name, loc, dims, mat, root, bevel=0.02):
    return base.box(name, loc, dims, mat, root, bevel)


def _sphere(name, loc, radius, mat, root, scale=(1, 1, 1), seg=14, rings=8):
    return base.sphere(name, loc, radius, mat, root, scale, seg, rings)


def _roof_shingles(root, mats, r):
    roof = r["roof"]
    rw = float(roof["width"])
    rd = float(roof["depth"])
    eave = float(roof["eaveZ"])
    ridge = float(roof["ridgeZ"])
    rows = max(8, int(roof.get("tileRows", 7)) + 2)
    cols = 14

    # Horizontal courses already carry the main read in v1. V2 adds staggered
    # short vertical joints so the roof reads as shingles rather than broad bands.
    for side, sign in (("S", -1), ("N", 1)):
        for row in range(rows):
            t0 = row / rows
            t1 = (row + 1) / rows
            y = sign * (rd / 2.0) * (1.0 - (t0 + t1) * 0.5)
            z = eave + (ridge - eave) * ((t0 + t1) * 0.5) + 0.028
            usable = rw - 0.22
            spacing = usable / cols
            offset = spacing * 0.5 if row % 2 else 0.0
            for col in range(cols - 1):
                x = -usable / 2.0 + spacing * (col + 1) + offset
                if x > usable / 2.0:
                    continue
                _box(
                    f"RoofJoint_{side}_{row}_{col}",
                    (x, y, z),
                    (0.022, max(0.12, rd / rows * 0.70), 0.018),
                    mats["roofEdge"], root, 0.003,
                )

    # Chunkier ridge caps give a strong miniature/game silhouette.
    cap_count = 14
    cap_w = (rw - 0.12) / cap_count
    for i in range(cap_count):
        x = -rw / 2.0 + 0.06 + cap_w * (i + 0.5)
        _box(f"MainRidgeCap_{i}", (x, 0, ridge + 0.072),
             (cap_w * 0.92, 0.18, 0.13), mats["roofEdge"], root, 0.018)


def _fascia_gutters_and_corners(root, mats, r):
    m = r["mass"]
    roof = r["roof"]
    bw, bd = float(m["bodyWidth"]), float(m["bodyDepth"])
    wh, z0 = float(m["wallHeight"]), float(m["wallBaseZ"])
    rw, rd = float(roof["width"]), float(roof["depth"])
    eave = float(roof["eaveZ"])

    # Cream fascia under dark roof, then a thinner dark gutter line.
    for sign, label in ((-1, "South"), (1, "North")):
        _box(f"{label}CreamFasciaV2", (0, sign * (rd / 2 + 0.035), eave - 0.10),
             (rw + 0.06, 0.13, 0.18), mats["trim"], root, 0.018)
        _box(f"{label}GutterV2", (0, sign * (rd / 2 + 0.115), eave - 0.04),
             (rw + 0.10, 0.085, 0.085), mats["roofEdge"], root, 0.018)

    # Oversized corner boards help every rotation read cleanly at gameplay scale.
    cz = z0 + wh * 0.5
    for x in (-bw / 2 - 0.035, bw / 2 + 0.035):
        for y in (-bd / 2 - 0.035, bd / 2 + 0.035):
            _box(f"CornerTrim_{'E' if x > 0 else 'W'}_{'N' if y > 0 else 'S'}",
                 (x, y, cz), (0.14, 0.14, wh + 0.08), mats["trim"], root, 0.014)


def _window_casing_details(root, mats, r):
    m = r["mass"]
    win = r["windows"]
    bw, bd = float(m["bodyWidth"]), float(m["bodyDepth"])
    front = -bd / 2.0
    z = float(win["frontCenterZ"])
    w = float(win["frontWidth"])
    h = float(win["frontHeight"])

    for i, xv in enumerate(win["frontCentersX"]):
        x = float(xv)
        y = front - 0.142
        _box(f"FrontWindowHeaderV2_{i}", (x, y, z + h / 2 + 0.16),
             (w + 0.34, 0.09, 0.11), mats["trim"], root, 0.012)
        _box(f"FrontWindowLeftCasingV2_{i}", (x - w / 2 - 0.12, y, z),
             (0.11, 0.09, h + 0.28), mats["trim"], root, 0.012)
        _box(f"FrontWindowRightCasingV2_{i}", (x + w / 2 + 0.12, y, z),
             (0.11, 0.09, h + 0.28), mats["trim"], root, 0.012)

    sx = bw / 2.0 + 0.142
    sy = float(win["sideCenterY"])
    sw = float(win["sideWidth"])
    sh = float(win["sideHeight"])
    sz = float(win["sideCenterZ"])
    _box("EastWindowHeaderV2", (sx, sy, sz + sh / 2 + 0.16),
         (0.09, sw + 0.34, 0.11), mats["trim"], root, 0.012)


def _door_and_porch_details(root, mats, r):
    m = r["mass"]
    ent = r["entry"]
    bd = float(m["bodyDepth"])
    z0 = float(m["wallBaseZ"])
    front = -bd / 2.0
    ex = float(ent["centerX"])
    dw = float(ent["doorWidth"])
    dh = float(ent["doorHeight"])

    # Four recessed door panels + raised rails.
    panel_w = dw * 0.58
    panel_h = dh * 0.25
    for row, z in enumerate((z0 + dh * 0.30, z0 + dh * 0.67)):
        _box(f"DoorPanel_{row}", (ex, front - 0.184, z),
             (panel_w, 0.026, panel_h), mats["frame"], root, 0.018)
        _box(f"DoorPanelInset_{row}", (ex, front - 0.202, z),
             (panel_w * 0.78, 0.018, panel_h * 0.72), mats["door"], root, 0.010)

    # Compact warm porch lamp: dark mount + amber lens.
    lamp_x = ex - dw * 0.72
    lamp_y = front - 0.19
    lamp_z = z0 + dh * 0.78
    _box("PorchLampMount", (lamp_x, lamp_y, lamp_z),
         (0.18, 0.12, 0.22), mats["frame"], root, 0.018)
    _box("PorchLampGlow", (lamp_x, lamp_y - 0.07, lamp_z),
         (0.105, 0.04, 0.13), mats["glass"], root, 0.010)

    # Cap/base blocks make the porch columns less primitive.
    pd = float(ent["porticoDepth"])
    py = front - pd * 0.47
    spacing = float(ent["columnSpacing"])
    for label, cx in (("L", ex - spacing / 2), ("R", ex + spacing / 2)):
        _box(f"EntryColumnCapital{label}", (cx, py - pd * 0.30, float(ent["porticoEaveZ"]) - 0.11),
             (0.30, 0.30, 0.14), mats["trim"], root, 0.020)
        _box(f"EntryColumnPlinth{label}", (cx, py - pd * 0.30, 0.54),
             (0.28, 0.28, 0.16), mats["trim"], root, 0.018)


def _foundation_courses(root, mats, r):
    m = r["mass"]
    fw, fd = float(m["foundationWidth"]), float(m["foundationDepth"])
    fh = float(m["foundationHeight"])
    for i in range(1, 3):
        z = fh * i / 3.0
        _box(f"FoundationCourseSouth_{i}", (0, -fd / 2 - 0.025, z),
             (fw - 0.08, 0.035, 0.025), mats["trim"], root, 0.004)
        _box(f"FoundationCourseEast_{i}", (fw / 2 + 0.025, 0, z),
             (0.035, fd - 0.08, 0.025), mats["trim"], root, 0.004)


def _garden_detail(root, mats, r):
    land = r["landscaping"]
    rad = float(land["shrubRadius"])
    all_shrubs = list(land["frontShrubs"]) + list(land["sideShrubs"])
    # Add a few small lobes around each existing sphere so bushes read leafy,
    # without increasing silhouette beyond the 3x3 footprint envelope.
    offsets = ((-0.14, -0.03), (0.13, -0.05), (-0.05, 0.11), (0.10, 0.10))
    for i, (xv, yv) in enumerate(all_shrubs):
        x, y = float(xv), float(yv)
        for j, (dx, dy) in enumerate(offsets):
            _sphere(f"ShrubLobe_{i}_{j}", (x + dx, y + dy, rad * 1.10), rad * 0.46,
                    mats["greenLight" if (i + j) % 3 == 0 else "green"], root,
                    (1.0, 0.88, 0.82), 12, 7)

    # Mulch strips sit only inside the private landscaping envelope.
    for i, (xv, yv) in enumerate(land["flowerBeds"]):
        x, y = float(xv), float(yv)
        _box(f"MulchStrip_{i}", (x, y + 0.02, 0.055),
             (1.20, 0.58, 0.055), mats["door"], root, 0.018)


def apply_detail_pass(root, mats, r):
    _roof_shingles(root, mats, r)
    _fascia_gutters_and_corners(root, mats, r)
    _window_casing_details(root, mats, r)
    _door_and_porch_details(root, mats, r)
    _foundation_courses(root, mats, r)
    _garden_detail(root, mats, r)
    root["detailPass"] = "residential_cottage_detail_v2"
    root["detailTarget"] = "latest_user_approved_generated_reference"


_original_build_house = base.build_house


def _detailed_build_house(root, mats, r):
    _original_build_house(root, mats, r)
    apply_detail_pass(root, mats, r)


base.build_house = _detailed_build_house


if __name__ == "__main__":
    base.main()
