"""Second guarded detail pass for the City Horizon mini market.

Keeps the already validated 3x2 massing/camera/studio contract and improves the
parts that matter most at gameplay scale: storefront depth, sign readability,
awning supports, parapet finish and rooftop equipment.  The supplied grocery
image remains art direction only; geometry here is original City Horizon work.
"""
from __future__ import annotations

import copy
import math

import build_commercial_mini_market_guarded as base


_original_build_market = base.build_market


def _front_y(recipe: dict) -> float:
    return -float(recipe["mass"]["bodyDepth"]) / 2.0 - 0.065


def _add_storefront_depth(root, mats, recipe):
    """Add readable merchandising and framing without requiring transparent glass."""
    front_y = _front_y(recipe)
    windows = recipe["windows"]
    z = float(windows["frontCenterZ"])
    w = float(windows["frontWidth"])
    h = float(windows["frontHeight"])

    # Strong vertical facade rhythm like a real small grocery storefront.
    for idx, x in enumerate((-2.93, -1.12, 1.12, 2.93)):
        base.box(f"StorefrontPilasterV2_{idx}", (x, front_y - 0.105, 1.46),
                 (0.18, 0.12, 2.42), mats["trim"], root, 0.018)
        base.box(f"StorefrontPilasterCapV2_{idx}", (x, front_y - 0.112, 2.64),
                 (0.28, 0.15, 0.14), mats["wall"], root, 0.018)

    # Window transoms and merchandising silhouettes. These sit fractionally in
    # front of the warm glass so they survive the gameplay downsample.
    for side, x in (("L", float(windows["frontCentersX"][0])),
                    ("R", float(windows["frontCentersX"][1]))):
        glass_y = front_y - 0.132
        base.box(f"StorefrontTransom_{side}", (x, glass_y, z + h * 0.30),
                 (w * 0.92, 0.035, 0.055), mats["frame"], root, 0.006)
        for shelf, dz in enumerate((-0.43, -0.08, 0.27)):
            base.box(f"DisplayShelf_{side}_{shelf}", (x, glass_y - 0.015, z + dz),
                     (w * 0.78, 0.025, 0.055), mats["wood"], root, 0.005)
        # Chunky produce shapes read as stocked windows without microscopic noise.
        produce = mats["greenLight"] if side == "L" else mats["orange"]
        for n, dx in enumerate((-0.46, -0.20, 0.08, 0.36)):
            base.sphere(f"WindowProduce_{side}_{n}",
                        (x + dx, glass_y - 0.022, z - 0.24 + (n % 2) * 0.10),
                        0.10, produce if n % 3 else mats["red"], root,
                        (1.0, 0.42, 0.82), 12, 6)

    # The entrance gets a more convincing commercial aluminum frame.
    entry = recipe["entry"]
    ew = float(entry["doorWidth"])
    ez = float(entry["doorCenterZ"])
    base.box("EntranceHeaderV2", (0.0, front_y - 0.145, ez + float(entry["doorHeight"]) * 0.50),
             (ew + 0.30, 0.055, 0.11), mats["frame"], root, 0.010)
    for x in (-ew * 0.26, ew * 0.26):
        base.box("EntranceLowerRailL" if x < 0 else "EntranceLowerRailR",
                 (x, front_y - 0.145, ez - 0.56),
                 (ew * 0.42, 0.045, 0.075), mats["darkMetal"], root, 0.006)


def _add_sign_readability(root, mats, recipe):
    """Place a crisp basket outline over the first-pass sign geometry."""
    facade = recipe["facade"]
    front_y = _front_y(recipe)
    z = float(facade["signCenterZ"]) + 0.05
    face_y = front_y - 0.315
    width = float(facade["signWidth"])

    # Layered crown and border make the sign panel read independently from the
    # green fascia behind it.
    base.box("SignTopCapV2", (0.0, front_y - 0.20, z + 0.53),
             (width + 0.34, 0.18, 0.13), mats["green"], root, 0.028)
    base.box("SignBottomCapV2", (0.0, front_y - 0.205, z - 0.48),
             (width + 0.16, 0.17, 0.11), mats["green"], root, 0.022)
    for x in (-width / 2 + 0.10, width / 2 - 0.10):
        base.box("SignBorderL" if x < 0 else "SignBorderR", (x, face_y, z),
                 (0.075, 0.028, 0.78), mats["green"], root, 0.008)

    # Open-frame generic basket; much clearer at 256 px than a filled rectangle.
    basket_w = 0.88
    base.box("BasketRimV2", (0.0, face_y - 0.012, z + 0.10),
             (basket_w, 0.026, 0.075), mats["green"], root, 0.006)
    base.box("BasketBottomV2", (0.0, face_y - 0.012, z - 0.23),
             (0.66, 0.026, 0.075), mats["green"], root, 0.006)
    for x, tilt in ((-0.37, -8.0), (0.37, 8.0)):
        rail = base.box("BasketSideLV2" if x < 0 else "BasketSideRV2",
                        (x, face_y - 0.012, z - 0.07),
                        (0.07, 0.026, 0.34), mats["green"], root, 0.006)
        rail.rotation_euler[1] = math.radians(tilt)
    for x in (-0.22, 0.0, 0.22):
        base.box(f"BasketRailV2_{x:+.2f}", (x, face_y - 0.016, z - 0.07),
                 (0.055, 0.024, 0.30), mats["green"], root, 0.005)
    for x, tilt in ((-0.20, -28.0), (0.20, 28.0)):
        handle = base.box("BasketHandleLV2" if x < 0 else "BasketHandleRV2",
                          (x, face_y - 0.012, z + 0.35),
                          (0.07, 0.026, 0.48), mats["green"], root, 0.006)
        handle.rotation_euler[1] = math.radians(tilt)


def _add_awning_supports(root, mats, recipe):
    front_y = _front_y(recipe)
    windows = recipe["windows"]
    awnings = recipe["awnings"]

    # Visible underside bars keep the awnings from looking like floating slabs.
    awning_specs = [
        ("L", float(windows["frontCentersX"][0]), float(awnings["sideDepth"]), float(awnings["sideCenterZ"])),
        ("C", 0.0, float(awnings["centerDepth"]), float(awnings["centerCenterZ"])),
        ("R", float(windows["frontCentersX"][1]), float(awnings["sideDepth"]), float(awnings["sideCenterZ"])),
    ]
    for label, cx, depth, z in awning_specs:
        for dx in (-0.42, 0.42):
            if label == "C":
                x = cx + dx * 1.35
            else:
                x = cx + dx
            arm = base.box(f"AwningArm_{label}_{'L' if dx < 0 else 'R'}",
                           (x, front_y - depth * 0.52, z - 0.23),
                           (0.055, depth * 0.70, 0.055), mats["darkMetal"], root, 0.005)
            arm.rotation_euler[0] = math.radians(-14.0)

    # A thin continuous green fascia ties the three front awnings together.
    base.box("AwningHeaderRailV2", (0.0, front_y - 0.16, 2.31),
             (5.55, 0.08, 0.12), mats["green"], root, 0.010)


def _add_roof_finish(root, mats, recipe):
    roof = recipe["roof"]
    rw = float(roof["slabWidth"])
    rd = float(roof["slabDepth"])
    slab_z = float(roof["slabZ"])
    slab_h = float(roof["slabHeight"])
    parapet_h = float(roof["parapetHeight"])
    parapet_t = float(roof["parapetThickness"])
    cap_h = float(roof["parapetCapHeight"])
    parapet_z = slab_z + slab_h / 2 + parapet_h / 2
    cap_z = parapet_z + parapet_h / 2

    # Complete the cap on all four sides (base pass intentionally had only N/S).
    base.box("ParapetCapEastV2", (rw / 2 - parapet_t / 2, 0, cap_z),
             (parapet_t + 0.06, rd + 0.08, cap_h), mats["wall"], root, 0.015)
    base.box("ParapetCapWestV2", (-rw / 2 + parapet_t / 2, 0, cap_z),
             (parapet_t + 0.06, rd + 0.08, cap_h), mats["wall"], root, 0.015)

    # Sparse roof seams give scale without turning the roof into noisy texture.
    roof_surface = slab_z + slab_h / 2 + 0.025
    for i, x in enumerate((-2.0, -0.65, 0.70, 2.05)):
        base.box(f"RoofJointV2_{i}", (x, 0.0, roof_surface),
                 (0.025, rd - 0.48, 0.018), mats["darkMetal"], root, 0.003)
    for i, y in enumerate((-0.70, 0.70)):
        base.box(f"RoofCrossJointV2_{i}", (0.0, y, roof_surface),
                 (rw - 0.52, 0.025, 0.018), mats["darkMetal"], root, 0.003)

    # Add a fan disk/cross to both HVACs and a raised equipment curb beneath each.
    roof_top = slab_z + slab_h / 2
    for index, spec in enumerate(recipe["roofEquipment"]["hvacUnits"]):
        x, y = float(spec["x"]), float(spec["y"])
        width, depth, height = float(spec["width"]), float(spec["depth"]), float(spec["height"])
        base.box(f"HVACCurbV2_{index}", (x, y, roof_top + 0.06),
                 (width + 0.18, depth + 0.18, 0.12), mats["darkMetal"], root, 0.020)
        fan_z = roof_top + 0.08 + height + 0.15
        base.cylinder(f"HVACFanDiskV2_{index}", (x, y, fan_z),
                      min(width, depth) * 0.27, 0.035, mats["darkMetal"], root,
                      vertices=28, scale=(1.0, 1.0, 0.40), bevel=0.005)
        for angle in (0.0, 90.0):
            blade = base.box(f"HVACFanBladeV2_{index}_{int(angle)}", (x, y, fan_z + 0.022),
                             (min(width, depth) * 0.50, 0.055, 0.028), mats["metal"], root, 0.004)
            blade.rotation_euler[2] = math.radians(angle)


def _add_side_detail(root, mats, recipe):
    mass = recipe["mass"]
    windows = recipe["windows"]
    bw = float(mass["bodyWidth"])
    east_x = bw / 2 + 0.13
    y = float(windows["sideCenterY"])

    # A small planter directly below the side window gives the rotation more
    # visual story while staying fully inside the 3x2 asset footprint.
    base.box("EastWindowPlanterV2", (east_x, y, 0.46),
             (0.34, 1.24, 0.36), mats["trim"], root, 0.024)
    for i, dy in enumerate((-0.40, -0.14, 0.16, 0.42)):
        base.sphere(f"EastPlanterLeafV2_{i}", (east_x + 0.08, y + dy, 0.73),
                    0.14, mats["greenLight" if i % 3 == 0 else "leaf"], root,
                    (0.72, 1.0, 1.20), 12, 7)


def build_market_v2(root, mats, recipe):
    tuned = copy.deepcopy(recipe)
    # Keep footprint/camera invariant; tune only proportions that improve the
    # south proxy at gameplay scale.
    tuned["facade"]["signWidth"] = 2.72
    tuned["facade"]["signHeight"] = 1.08
    tuned["facade"]["signCenterZ"] = 3.08
    tuned["windows"]["frontWidth"] = 1.68
    tuned["windows"]["frontHeight"] = 1.78
    tuned["awnings"]["centerDepth"] = 0.98
    tuned["awnings"]["sideDepth"] = 0.84
    tuned["roofEquipment"]["hvacUnits"][0]["width"] = 1.04
    tuned["roofEquipment"]["hvacUnits"][0]["depth"] = 0.86
    tuned["roofEquipment"]["hvacUnits"][0]["height"] = 0.62
    tuned["roofEquipment"]["hvacUnits"][1]["width"] = 0.76
    tuned["roofEquipment"]["hvacUnits"][1]["depth"] = 0.68
    tuned["roofEquipment"]["hvacUnits"][1]["height"] = 0.66

    _original_build_market(root, mats, tuned)
    _add_storefront_depth(root, mats, tuned)
    _add_sign_readability(root, mats, tuned)
    _add_awning_supports(root, mats, tuned)
    _add_roof_finish(root, mats, tuned)
    _add_side_detail(root, mats, tuned)
    root["detailPass"] = "commercial_mini_market_v2"


base.build_market = build_market_v2


if __name__ == "__main__":
    base.main()
