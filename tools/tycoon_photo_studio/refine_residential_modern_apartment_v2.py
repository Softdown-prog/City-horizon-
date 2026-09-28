"""Second-pass visual refinement for residential_modern_apartment_4x4_01.

This module deliberately wraps the approved guarded builder instead of duplicating it.
It preserves the approved massing/footprint and adds small-scale facade, balcony,
entrance and rooftop detail for the next SOUTH validation pass.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import build_residential_modern_apartment_guarded as base

_original_build_apartment = base.build_apartment


def _add_wall_sconce(root, mats, name, loc, axis="front"):
    x, y, z = loc
    if axis == "front":
        base.box(name + "Back", (x, y, z), (0.13, 0.055, 0.30), mats["darkMetal"], root, 0.018)
        base.box(name + "Glow", (x, y - 0.038, z), (0.085, 0.030, 0.18), mats["glass"], root, 0.012)
    else:
        base.box(name + "Back", (x, y, z), (0.055, 0.13, 0.30), mats["darkMetal"], root, 0.018)
        base.box(name + "Glow", (x + 0.038, y, z), (0.030, 0.085, 0.18), mats["glass"], root, 0.012)


def _add_planter_trough(root, mats, name, center_x, y, z, width):
    base.box(name + "Box", (center_x, y, z + 0.15), (width, 0.28, 0.30), mats["charcoalMid"], root, 0.025)
    count = max(3, int(width / 0.42))
    for i in range(count):
        t = i / max(1, count - 1)
        x = center_x - width * 0.40 + width * 0.80 * t
        base.sphere(name + f"Leaf{i}", (x, y - 0.01, z + 0.43 + 0.04 * (i % 2)), 0.18,
                    mats["greenLight" if i % 3 == 0 else "green"], root,
                    (0.90, 0.65, 1.05), 12, 6)


def _add_roof_detail(root, mats, roof_z, bw, bd):
    front = -bd / 2
    east = bw / 2
    # Slim coping caps sharpen the silhouette without changing the approved massing.
    cap_z = roof_z + 0.74
    base.box("ParapetCapSouthV2", (0, front + 0.075, cap_z), (bw + 0.08, 0.31, 0.10), mats["darkMetal"], root, 0.015)
    base.box("ParapetCapNorthV2", (0, bd / 2 - 0.075, cap_z), (bw + 0.08, 0.31, 0.10), mats["darkMetal"], root, 0.015)
    base.box("ParapetCapEastV2", (east - 0.075, 0, cap_z), (0.31, bd + 0.08, 0.10), mats["darkMetal"], root, 0.015)
    base.box("ParapetCapWestV2", (-east + 0.075, 0, cap_z), (0.31, bd + 0.08, 0.10), mats["darkMetal"], root, 0.015)

    # Small service conduits and condenser feet make rooftop equipment read as functional.
    for i, yy in enumerate((-0.48, -0.20, 0.08, 0.36)):
        base.box(f"HVACSideLouverV2_{i}", (3.205, yy, roof_z + 0.58), (0.032, 0.16, 0.055),
                 mats["darkMetal"], root, 0.004)
    for i, xx in enumerate((1.98, 2.28, 2.58, 2.88)):
        base.box(f"HVACFootV2_{i}", (xx, -0.14, roof_z + 0.16), (0.12, 0.18, 0.12),
                 mats["darkMetal"], root, 0.006)
    base.box("RoofUtilityConduitV2", (1.58, 0.36, roof_z + 0.25), (1.20, 0.10, 0.10), mats["metal"], root, 0.018)


def _refined_build_apartment(root, mats, recipe):
    _original_build_apartment(root, mats, recipe)

    d = recipe["dimensions"]
    bw = float(d["bodyWidth"])
    bd = float(d["bodyDepth"])
    fh = float(d["foundationHeight"])
    floor_h = float(d["floorHeight"])
    floors = int(d["floors"])
    body_h = floor_h * floors
    front = -bd / 2
    east = bw / 2

    # Narrow reveal strips reproduce the panelized facade rhythm visible in the approved reference.
    for floor in range(floors):
        z0 = fh + floor * floor_h
        z_mid = z0 + floor_h * 0.52
        for x in (-3.62, -2.10, 0.72, 3.48):
            base.box(f"FrontRevealV2_{floor}_{x:+.2f}", (x, front - 0.142, z_mid),
                     (0.045, 0.030, floor_h - 0.30), mats["charcoalMid"], root, 0.004)
        base.box(f"EastRevealV2_{floor}", (east + 0.142, 0.05, z_mid),
                 (0.030, bd - 0.55, 0.045), mats["charcoalMid"], root, 0.004)

    # Dark lintels and shallow sill plates give windows a more finished architectural frame.
    for floor in range(floors):
        z = fh + floor * floor_h + 1.08
        for idx, (x, width) in enumerate(((-2.72, 0.88), (-0.98, 0.68), (-0.15, 0.68), (1.70, 0.84), (2.63, 0.70))):
            base.box(f"WindowLintelV2_{floor}_{idx}", (x, front - 0.155, z + 0.69),
                     (width + 0.20, 0.045, 0.07), mats["darkMetal"], root, 0.007)
            base.box(f"WindowSillV2_{floor}_{idx}", (x, front - 0.155, z - 0.69),
                     (width + 0.18, 0.055, 0.06), mats["darkMetal"], root, 0.007)

    # Long integrated planter troughs make the balcony stacks closer to the reference.
    for level in range(1, floors):
        slab_z = fh + level * floor_h + 0.08
        _add_planter_trough(root, mats, f"LeftTroughV2_{level}", -2.64, front - 1.02, slab_z + 0.02, 1.34)
        _add_planter_trough(root, mats, f"RightTroughV2_{level}", 2.03, front - 1.06, slab_z + 0.02, 1.48)

    # Warm sconces on the timber side strip and entrance, matching the visual language of the reference.
    for floor in range(floors):
        z = fh + floor * floor_h + 1.18
        _add_wall_sconce(root, mats, f"EastSconceV2_{floor}", (east + 0.155, 1.33, z), "east")
    _add_wall_sconce(root, mats, "EntranceSconceV2L", (-0.43, front - 0.175, fh + 1.22), "front")
    _add_wall_sconce(root, mats, "EntranceSconceV2R", (1.43, front - 0.175, fh + 1.22), "front")

    # Entrance trim, transom and canopy edge make the ground floor less flat.
    base.box("EntryTransomV2", (0.50, front - 0.300, fh + 2.00), (1.18, 0.035, 0.16), mats["glass"], root, 0.005)
    base.box("CanopyFrontEdgeV2", (0.50, front - 1.10, fh + 2.13), (2.18, 0.09, 0.30), mats["darkMetal"], root, 0.018)
    for x in (-0.34, 1.34):
        base.box(f"CanopySupportV2_{x:+.2f}", (x, front - 0.72, fh + 1.05), (0.09, 0.09, 1.82), mats["darkMetal"], root, 0.014)

    # Small private foundation planters only: no sidewalk/curb/street furniture is introduced.
    for i, x in enumerate((-3.15, 2.95)):
        base.box(f"FoundationPlanterV2_{i}", (x, front - 0.30, 0.24), (1.15, 0.46, 0.36), mats["concrete"], root, 0.025)
        for j in range(4):
            base.sphere(f"FoundationPlanterLeafV2_{i}_{j}",
                        (x - 0.35 + j * 0.23, front - 0.32, 0.55 + 0.05 * (j % 2)),
                        0.22, mats["greenLight" if (i + j) % 2 else "green"], root,
                        (0.85, 0.70, 1.05), 12, 6)

    roof_z = fh + body_h
    _add_roof_detail(root, mats, roof_z, bw, bd)


base.build_apartment = _refined_build_apartment

if __name__ == "__main__":
    base.main()
