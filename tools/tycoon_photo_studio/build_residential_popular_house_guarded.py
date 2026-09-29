"""Guarded CH Blender authoring for Casa popular.

Original City Horizon residence using the user supplied image as art direction only.
Quality path: preflight -> SOUTH proxy -> explicit approval -> final four directions.
Public sidewalk/curb/road and large vegetation are deliberately excluded.
"""
from __future__ import annotations

import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import build_residential_suburban_cottage_guarded as base  # noqa: E402

ASSET_ID = "residential_popular_house_3x3_01"
DEFAULT_RECIPE = "tools/tycoon_photo_studio/assets/residential_popular_house_3x3_01.house.json"

_original_build_house = base.build_house


def _add_garage_and_reference_details(root, mats, r):
    """Add the characteristic one-car garage and modest starter-home detail."""
    g = r["garage"]
    m = r["mass"]
    front = -float(m["bodyDepth"]) / 2.0
    gx = float(g["centerX"])
    door_w = float(g["doorWidth"])
    door_h = float(g["doorHeight"])
    z0 = float(m["wallBaseZ"])

    # Garage door: cream segmented panel, readable at gameplay scale.
    base.box("GarageDoorFrame", (gx, front - 0.082, z0 + door_h / 2.0),
             (door_w + 0.20, 0.16, door_h + 0.18), mats["trim"], root, 0.028)
    base.box("GarageDoor", (gx, front - 0.174, z0 + door_h / 2.0),
             (door_w, 0.045, door_h), mats["trim"], root, 0.012)
    for i in range(1, 4):
        z = z0 + door_h * i / 4.0
        base.box(f"GaragePanelH{i}", (gx, front - 0.202, z),
                 (door_w - 0.10, 0.025, 0.035), mats["frame"], root, 0.004)
    for xoff in (-door_w * 0.25, door_w * 0.25):
        base.box("GaragePanelV" + ("L" if xoff < 0 else "R"),
                 (gx + xoff, front - 0.204, z0 + door_h * 0.57),
                 (0.035, 0.024, door_h * 0.72), mats["frame"], root, 0.004)
    # Warm clerestory panes at the top of the garage door.
    for idx, xoff in enumerate((-0.58, -0.20, 0.20, 0.58)):
        base.box(f"GarageWarmPane{idx}", (gx + xoff, front - 0.218, z0 + door_h * 0.83),
                 (0.30, 0.025, 0.25), mats["glass"], root, 0.006)

    # Front-facing garage gable gives the silhouette a second strong peak.
    base.gable_y("GarageFrontGableRoof", gx, front + 0.38,
                 float(g["roofWidth"]), float(g["roofDepth"]),
                 float(g["roofEaveZ"]), float(g["roofRidgeZ"]), mats["roof"], root)
    base.box("GarageFrontFascia", (gx, front - 0.03, float(g["roofEaveZ"]) - 0.02),
             (float(g["roofWidth"]) + 0.06, 0.10, 0.13), mats["roofEdge"], root, 0.015)

    # Private driveway stub only; public sidewalk and curb remain runtime-owned.
    base.box("PrivateGarageDriveway", (gx, front - float(g["drivewayDepth"]) * 0.55, 0.035),
             (float(g["drivewayWidth"]), float(g["drivewayDepth"]), 0.07), mats["path"], root, 0.018)

    # Stone/brick lower facade accent, matching the reference without over-detailing.
    for x in (-2.72, -2.12, -1.52, 0.34, 0.92, 1.50, 2.08, 2.66, 3.18):
        base.box(f"StoneBase_{x:+.2f}", (x, front - 0.094, 0.47),
                 (0.52, 0.12, 0.48), mats["foundation"], root, 0.018)

    # Shutters around the main front window improve the sage/cream suburban read.
    win = r["windows"]
    if win["frontCentersX"]:
        wx = float(win["frontCentersX"][0])
        ww = float(win["frontWidth"])
        wz = float(win["frontCenterZ"])
        wh = float(win["frontHeight"])
        for side, sx in (("L", wx - ww / 2.0 - 0.16), ("R", wx + ww / 2.0 + 0.16)):
            base.box(f"FrontShutter{side}", (sx, front - 0.16, wz),
                     (0.22, 0.055, wh + 0.05), mats["frame"], root, 0.012)
            for k in (-0.28, 0.0, 0.28):
                base.box(f"FrontShutter{side}Slat{k:+.2f}", (sx, front - 0.194, wz + k),
                         (0.16, 0.025, 0.028), mats["trim"], root, 0.003)

    # Small warm porch/garage sconces; geometry rather than baked environment.
    for idx, lx in enumerate((-0.02, 3.30)):
        base.box(f"SconceBack{idx}", (lx, front - 0.18, 1.55),
                 (0.14, 0.05, 0.28), mats["frame"], root, 0.012)
        base.sphere(f"SconceGlow{idx}", (lx, front - 0.225, 1.55), 0.085,
                    mats["glass"], root, (0.8, 0.45, 1.15), 12, 6)


def build_house(root, mats, r):
    _original_build_house(root, mats, r)
    _add_garage_and_reference_details(root, mats, r)


def main():
    base.ASSET_ID = ASSET_ID
    base.DEFAULT_RECIPE = DEFAULT_RECIPE
    base.build_house = build_house
    base.main()


if __name__ == "__main__":
    main()
