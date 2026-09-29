"""Fourth-pass detailing for the City Horizon Casa Popular.

Keeps the approved Casa Popular massing and adds only game-readable details that
reinforce this house's own identity.  No public sidewalk, curb, street furniture
or large vegetation is authored here.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import build_residential_popular_house_guarded as popular  # noqa: E402

ASSET_ID = popular.ASSET_ID
DEFAULT_RECIPE = popular.DEFAULT_RECIPE
_original_build_house = popular.build_house
base = popular.base


def _add_v4_details(root, mats, r):
    m = r["mass"]
    ent = r["entry"]
    win = r["windows"]
    g = r["garage"]
    front = -float(m["bodyDepth"]) / 2.0
    z0 = float(m["wallBaseZ"])
    gx = float(g["centerX"])
    garage_w = 2.58
    garage_front = front - 0.68

    # Stronger porch carpentry: a proper header and shallow inner soffit edge.
    ex = float(ent["centerX"])
    spacing = float(ent["columnSpacing"])
    py = front - float(ent["porticoDepth"]) * 0.47
    base.box("PorchHeaderV4", (ex, py - 0.30, 2.04),
             (spacing + 0.36, 0.20, 0.22), mats["trim"], root, 0.018)
    base.box("PorchSoffitEdgeV4", (ex, py - 0.47, 2.18),
             (float(ent["porticoWidth"]) - 0.12, 0.10, 0.10), mats["roofEdge"], root, 0.010)

    # Entry threshold and two narrow side casings improve the warm-door read.
    door_w = float(ent["doorWidth"])
    for side, x in (("L", ex - door_w / 2.0 - 0.09), ("R", ex + door_w / 2.0 + 0.09)):
        base.box(f"DoorCasingV4{side}", (x, front - 0.445, z0 + 0.98),
                 (0.12, 0.08, 2.02), mats["trim"], root, 0.010)
    base.box("DoorThresholdV4", (ex, front - 0.46, z0 + 0.055),
             (door_w + 0.30, 0.24, 0.11), mats["foundation"], root, 0.012)

    # Living-room front gable gets its own simple vent/slat signature.
    wx = float(win["frontCentersX"][0]) if win["frontCentersX"] else -2.35
    gy = front - 0.846
    base.box("LivingGableVentFrameV4", (wx, gy, 2.92),
             (0.64, 0.07, 0.42), mats["trim"], root, 0.010)
    base.box("LivingGableVentInsetV4", (wx, gy - 0.040, 2.92),
             (0.50, 0.025, 0.29), mats["frame"], root, 0.006)
    for i, z in enumerate((2.84, 2.92, 3.00)):
        base.box(f"LivingGableVentSlatV4_{i}", (wx, gy - 0.060, z),
                 (0.42, 0.018, 0.022), mats["trim"], root, 0.002)

    # Window crown and flower box separate this facade from the older cottage.
    ww = float(win["frontWidth"])
    wz = float(win["frontCenterZ"])
    wh = float(win["frontHeight"])
    fy = front - 0.405
    base.box("FrontWindowCrownV4", (wx, fy, wz + wh / 2.0 + 0.18),
             (ww + 0.46, 0.12, 0.11), mats["trim"], root, 0.014)
    box_z = wz - wh / 2.0 - 0.20
    base.box("FrontFlowerBoxV4", (wx, fy - 0.03, box_z),
             (ww + 0.18, 0.30, 0.24), mats["foundation"], root, 0.018)
    for i, dx in enumerate((-0.50, -0.25, 0.0, 0.25, 0.50)):
        base.sphere(f"FrontFlowerBoxLeafV4_{i}", (wx + dx, fy - 0.16, box_z + 0.20),
                    0.13, mats["green"], root, (1.0, 0.82, 0.78), 12, 7)
        if i % 2 == 0:
            base.sphere(f"FrontFlowerBoxBloomV4_{i}", (wx + dx, fy - 0.19, box_z + 0.27),
                        0.055, mats["flower"], root, (1.0, 0.78, 0.92), 10, 6)

    # Garage casing and carriage-style corner blocks add depth without changing massing.
    garage_door_w = float(g["doorWidth"])
    garage_door_h = float(g["doorHeight"])
    door_y = garage_front - 0.235
    base.box("GarageTopCasingV4", (gx, door_y, z0 + garage_door_h + 0.13),
             (garage_door_w + 0.34, 0.11, 0.16), mats["trim"], root, 0.012)
    for side, x in (("L", gx - garage_door_w / 2.0 - 0.13),
                    ("R", gx + garage_door_w / 2.0 + 0.13)):
        base.box(f"GarageSideCasingV4{side}", (x, door_y, z0 + garage_door_h / 2.0),
                 (0.16, 0.11, garage_door_h + 0.18), mats["trim"], root, 0.012)
        base.box(f"GarageBracketV4{side}", (x, door_y - 0.035, z0 + garage_door_h + 0.02),
                 (0.22, 0.08, 0.22), mats["foundation"], root, 0.018)

    # Main visible east wall: corner boards and base trim sharpen the silhouette.
    east_x = float(m["bodyWidth"]) / 2.0 + 0.085
    base.box("EastCornerBoardFrontV4", (east_x, front + 0.16, 1.42),
             (0.12, 0.18, 2.30), mats["trim"], root, 0.010)
    base.box("EastFoundationTrimV4", (east_x + 0.01, 0.20, 0.29),
             (0.12, float(m["bodyDepth"]) - 0.30, 0.14), mats["foundation"], root, 0.010)

    # Gutters/downspout: small but important silhouette detail at the tycoon camera.
    roof = r["roof"]
    rd = float(roof["depth"])
    rw = float(roof["width"])
    eave = float(roof["eaveZ"])
    south_y = -rd / 2.0 - 0.075
    base.box("SouthGutterV4", (0.0, south_y, eave - 0.10),
             (rw - 0.20, 0.11, 0.10), mats["roofEdge"], root, 0.016)
    down_x = float(m["bodyWidth"]) / 2.0 - 0.10
    base.box("FrontDownspoutV4", (down_x, south_y + 0.03, 1.18),
             (0.10, 0.10, 2.16), mats["roofEdge"], root, 0.012)
    base.box("DownspoutKickV4", (down_x - 0.10, south_y - 0.02, 0.16),
             (0.30, 0.10, 0.10), mats["roofEdge"], root, 0.010)

    # A few compact hydrangea-like clusters echo the supplied art direction while
    # remaining private landscaping inside the footprint.
    for i, (px, py) in enumerate(((-3.05, front - 0.48), (-2.72, front - 0.56),
                                  (-1.45, front - 0.68), (0.36, front - 0.62))):
        base.sphere(f"HydrangeaLeafV4_{i}", (px, py, 0.28), 0.22,
                    mats["green" if i % 2 == 0 else "greenLight"], root,
                    (1.18, 0.92, 0.86), 14, 8)
        for j, (dx, dz) in enumerate(((-0.08, 0.08), (0.04, 0.12), (0.10, 0.03))):
            base.sphere(f"HydrangeaBloomV4_{i}_{j}", (px + dx, py - 0.12, 0.34 + dz),
                        0.065, mats["flower"], root, (1.0, 0.88, 0.92), 10, 6)


def build_house(root, mats, r):
    _original_build_house(root, mats, r)
    _add_v4_details(root, mats, r)


def main():
    popular.build_house = build_house
    popular.main()


if __name__ == "__main__":
    main()
