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


def _add_cross_gable(root, mats, r, front):
    """Give the living-room side the broad front gable visible in the reference read."""
    win = r["windows"]
    wx = float(win["frontCentersX"][0]) if win["frontCentersX"] else -2.20
    base.box("LivingFrontProjection", (wx, front - 0.22, 1.42),
             (2.34, 0.48, 2.34), mats["wall"], root, 0.035)
    base.gable_y("LivingFrontGableRoof", wx, front - 0.02,
                 2.82, 1.54, 2.63, 3.56, mats["roof"], root)
    base.box("LivingGableFascia", (wx, front - 0.82, 2.60),
             (2.92, 0.11, 0.14), mats["trim"], root, 0.012)

    # Cream triangular-edge suggestion: thick enough to survive the proxy scale.
    for dx in (-1.18, 1.18):
        edge = base.box("LivingGableTrimL" if dx < 0 else "LivingGableTrimR",
                        (wx + dx * 0.56, front - 0.835, 3.02),
                        (1.38, 0.075, 0.10), mats["trim"], root, 0.006)
        edge.rotation_euler[1] = (-0.64 if dx < 0 else 0.64)


def _add_fine_architectural_details(root, mats, r, front, garage_front, garage_w, gx, z0):
    """Third-pass game-readable detail without changing the approved house massing."""
    win = r["windows"]

    # Main front window: stronger cream surround, sill, lintel and simple mullions.
    if win["frontCentersX"]:
        wx = float(win["frontCentersX"][0])
        ww = float(win["frontWidth"])
        wh = float(win["frontHeight"])
        wz = float(win["frontCenterZ"])
        y = front - 0.385
        base.box("FrontWindowLintelV3", (wx, y, wz + wh / 2.0 + 0.09),
                 (ww + 0.28, 0.075, 0.13), mats["trim"], root, 0.01)
        base.box("FrontWindowSillV3", (wx, y - 0.01, wz - wh / 2.0 - 0.075),
                 (ww + 0.34, 0.11, 0.12), mats["trim"], root, 0.012)
        for mx in (-ww * 0.18, ww * 0.18):
            base.box(f"FrontWindowMullionV3_{mx:+.2f}", (wx + mx, y - 0.03, wz),
                     (0.045, 0.028, wh - 0.08), mats["trim"], root, 0.003)
        base.box("FrontWindowMullionHV3", (wx, y - 0.032, wz + 0.10),
                 (ww - 0.10, 0.028, 0.045), mats["trim"], root, 0.003)

    # East wall window gains a proper frame/sill read at the isometric camera.
    sy = float(win["sideCenterY"])
    sw = float(win["sideWidth"])
    sh = float(win["sideHeight"])
    sz = float(win["sideCenterZ"])
    side_x = float(r["mass"]["bodyWidth"]) / 2.0 + 0.09
    base.box("EastWindowSillV3", (side_x + 0.035, sy, sz - sh / 2.0 - 0.07),
             (0.10, sw + 0.26, 0.11), mats["trim"], root, 0.01)
    base.box("EastWindowMullionV3", (side_x + 0.045, sy, sz),
             (0.04, 0.045, sh - 0.08), mats["trim"], root, 0.003)
    base.box("EastWindowMullionHV3", (side_x + 0.047, sy, sz + 0.08),
             (0.04, sw - 0.10, 0.045), mats["trim"], root, 0.003)

    # Porch columns get base/cap blocks so they stop reading as simple extruded sticks.
    entry = r["entry"]
    ex = float(entry["centerX"])
    spacing = float(entry["columnSpacing"])
    for side, cx in (("L", ex - spacing / 2.0), ("R", ex + spacing / 2.0)):
        base.box(f"PorchColumnBaseV3{side}", (cx, front - 0.76, 0.49),
                 (0.38, 0.38, 0.34), mats["foundation"], root, 0.018)
        base.box(f"PorchColumnCapV3{side}", (cx, front - 0.76, 2.06),
                 (0.34, 0.34, 0.15), mats["trim"], root, 0.01)

    # Front door gains recessed panels and a warm glazed top section.
    dy = front - 0.43
    dz = z0 + float(entry["doorHeight"]) / 2.0
    for idx, pz in enumerate((dz - 0.44, dz + 0.05)):
        base.box(f"DoorPanelV3_{idx}", (ex, dy - 0.035, pz),
                 (0.58, 0.032, 0.34), mats["frame"], root, 0.006)
    base.box("DoorTopGlassV3", (ex, dy - 0.04, dz + 0.50),
             (0.58, 0.03, 0.30), mats["glass"], root, 0.006)
    for mx in (-0.19, 0.0, 0.19):
        base.box(f"DoorTopMullionV3_{mx:+.2f}", (ex + mx, dy - 0.06, dz + 0.50),
                 (0.025, 0.018, 0.27), mats["trim"], root, 0.002)
    base.sphere("DoorHandleV3", (ex + 0.30, dy - 0.075, dz - 0.03), 0.045,
                mats["trim"], root, (1.0, 0.65, 0.75), 10, 6)

    # Garage: finer recessed panel grid, bottom rail and a small handle.
    door_w = float(r["garage"]["doorWidth"])
    door_h = float(r["garage"]["doorHeight"])
    door_y = garage_front - 0.225
    for row in range(3):
        pz = z0 + 0.34 + row * 0.43
        for col in (-0.52, 0.0, 0.52):
            base.box(f"GarageInsetV3_{row}_{col:+.2f}", (gx + col, door_y, pz),
                     (0.46, 0.022, 0.26), mats["frame"], root, 0.004)
    base.box("GarageBottomRailV3", (gx, door_y - 0.01, z0 + 0.11),
             (door_w - 0.10, 0.026, 0.08), mats["frame"], root, 0.004)
    base.sphere("GarageHandleV3", (gx, door_y - 0.035, z0 + 0.58), 0.04,
                mats["trim"], root, (1.0, 0.55, 0.75), 10, 6)

    # Stonework gains horizontal course joints and a few vertical breaks.
    stone_y = front - 0.176
    for row_z in (0.31, 0.47, 0.63):
        base.box(f"FrontStoneCourseV3_{row_z:.2f}", (-2.16, stone_y, row_z),
                 (2.35, 0.022, 0.022), mats["frame"], root, 0.002)
    for sx in (-2.82, -2.28, -1.74, -1.20):
        base.box(f"FrontStoneJointV3_{sx:+.2f}", (sx, stone_y - 0.006, 0.46),
                 (0.022, 0.018, 0.40), mats["frame"], root, 0.002)
    for px in (gx - 1.02, gx + 1.02):
        for row_z in (0.29, 0.45, 0.61):
            base.box(f"GaragePierCourseV3_{px:+.2f}_{row_z:.2f}",
                     (px, garage_front - 0.225, row_z),
                     (0.30, 0.022, 0.022), mats["frame"], root, 0.002)

    # Roof/chimney finishing that survives at 256px: chimney banding and cap shadow.
    ch = r["chimney"]
    cx = float(ch["x"])
    cy = float(ch["y"])
    for z in (3.30, 3.55, 3.80, 4.05):
        base.box(f"ChimneyCourseV3_{z:.2f}", (cx, cy - 0.285, z),
                 (float(ch["width"]) + 0.04, 0.035, 0.035), mats["foundation"], root, 0.004)
    base.box("ChimneyTopBandV3", (cx, cy, 4.36),
             (0.67, 0.67, 0.12), mats["trim"], root, 0.01)

    # Small private planting accents near the porch/garage. No public vegetation.
    for idx, (px, py, scale) in enumerate(((-1.15, front - 0.72, 0.16),
                                            (0.45, front - 0.66, 0.15),
                                            (gx + garage_w / 2.0 + 0.18, garage_front + 0.45, 0.14))):
        base.sphere(f"DetailShrubV3_{idx}", (px, py, 0.24), scale,
                    mats["greenLight"], root, (1.25, 0.88, 0.95), 12, 7)


def _add_garage_and_reference_details(root, mats, r):
    """Add a readable protruding garage and starter-home facade details."""
    g = r["garage"]
    m = r["mass"]
    front = -float(m["bodyDepth"]) / 2.0
    gx = float(g["centerX"])
    door_w = float(g["doorWidth"])
    door_h = float(g["doorHeight"])
    z0 = float(m["wallBaseZ"])

    # The first proxy only suggested a garage on the facade.  This version gives
    # it a real south-projecting mass so it reads immediately at gameplay scale.
    garage_w = 2.58
    garage_d = 4.35
    garage_front = front - 0.68
    garage_center_y = garage_front + garage_d / 2.0
    garage_wall_h = 2.36
    base.box("GarageWing", (gx, garage_center_y, z0 + garage_wall_h / 2.0),
             (garage_w, garage_d, garage_wall_h), mats["wall"], root, 0.045)

    # Horizontal siding on the visible garage front and east wall.
    for i in range(1, 7):
        z = z0 + garage_wall_h * i / 7.0
        base.box(f"GarageSidingSouth{i}", (gx, garage_front - 0.025, z),
                 (garage_w - 0.10, 0.035, 0.032), mats["trim"], root, 0.004)
        base.box(f"GarageSidingEast{i}", (gx + garage_w / 2.0 + 0.024, garage_center_y, z),
                 (0.035, garage_d - 0.12, 0.032), mats["trim"], root, 0.004)

    # Strong front-facing gable over the garage.  The eave/ridge are deliberately
    # lower than the main roof so the house keeps the broad suburban hierarchy.
    garage_roof_w = 2.96
    garage_roof_d = garage_d + 0.48
    garage_eave = 2.60
    garage_ridge = 3.52
    base.gable_y("GarageFrontGableRoof", gx, garage_center_y - 0.04,
                 garage_roof_w, garage_roof_d, garage_eave, garage_ridge,
                 mats["roof"], root)
    base.box("GarageFrontFascia", (gx, garage_front - 0.21, garage_eave - 0.02),
             (garage_roof_w + 0.06, 0.11, 0.14), mats["trim"], root, 0.015)

    # Cream segmented one-car door with warm upper panes.
    door_y = garage_front - 0.095
    base.box("GarageDoorFrame", (gx, door_y, z0 + door_h / 2.0),
             (door_w + 0.22, 0.16, door_h + 0.20), mats["trim"], root, 0.028)
    base.box("GarageDoor", (gx, door_y - 0.092, z0 + door_h / 2.0),
             (door_w, 0.045, door_h), mats["trim"], root, 0.012)
    for i in range(1, 4):
        z = z0 + door_h * i / 4.0
        base.box(f"GaragePanelH{i}", (gx, door_y - 0.120, z),
                 (door_w - 0.10, 0.025, 0.035), mats["frame"], root, 0.004)
    for xoff in (-door_w * 0.25, door_w * 0.25):
        base.box("GaragePanelV" + ("L" if xoff < 0 else "R"),
                 (gx + xoff, door_y - 0.122, z0 + door_h * 0.57),
                 (0.035, 0.024, door_h * 0.72), mats["frame"], root, 0.004)
    for idx, xoff in enumerate((-0.58, -0.20, 0.20, 0.58)):
        base.box(f"GarageWarmPane{idx}", (gx + xoff, door_y - 0.136, z0 + door_h * 0.83),
                 (0.30, 0.025, 0.25), mats["glass"], root, 0.006)

    # Short private driveway only; the map owns sidewalk, curb and public road.
    drive_d = 0.90
    base.box("PrivateGarageDriveway", (gx, garage_front - drive_d / 2.0, 0.035),
             (float(g["drivewayWidth"]), drive_d, 0.07), mats["path"], root, 0.018)

    _add_cross_gable(root, mats, r, front)

    # Stone/brick lower facade, kept chunky enough for the tycoon camera.
    for x in (-3.05, -2.48, -1.90, -1.30, 0.18, 0.76):
        base.box(f"StoneBase_{x:+.2f}", (x, front - 0.10, 0.46),
                 (0.50, 0.13, 0.46), mats["foundation"], root, 0.018)
    for x in (gx - 1.02, gx + 1.02):
        base.box(f"GarageStonePier_{x:+.2f}", (x, garage_front - 0.13, 0.45),
                 (0.34, 0.18, 0.58), mats["foundation"], root, 0.018)

    # Shutters around the main front window.
    win = r["windows"]
    if win["frontCentersX"]:
        wx = float(win["frontCentersX"][0])
        ww = float(win["frontWidth"])
        wz = float(win["frontCenterZ"])
        wh = float(win["frontHeight"])
        for side, sx in (("L", wx - ww / 2.0 - 0.16), ("R", wx + ww / 2.0 + 0.16)):
            base.box(f"FrontShutter{side}", (sx, front - 0.35, wz),
                     (0.23, 0.055, wh + 0.07), mats["frame"], root, 0.012)
            for k in (-0.28, 0.0, 0.28):
                base.box(f"FrontShutter{side}Slat{k:+.2f}", (sx, front - 0.384, wz + k),
                         (0.17, 0.025, 0.028), mats["trim"], root, 0.003)

    # Warm porch and garage sconces.
    for idx, (lx, ly) in enumerate(((-0.02, front - 0.20),
                                    (gx + garage_w / 2.0 - 0.15, garage_front - 0.14))):
        base.box(f"SconceBack{idx}", (lx, ly, 1.55),
                 (0.14, 0.05, 0.28), mats["frame"], root, 0.012)
        base.sphere(f"SconceGlow{idx}", (lx, ly - 0.045, 1.55), 0.085,
                    mats["glass"], root, (0.8, 0.45, 1.15), 12, 6)

    _add_fine_architectural_details(root, mats, r, front, garage_front, garage_w, gx, z0)


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
