#!/usr/bin/env python3
"""Expand CITY_HORIZON_PARK_KIOSK_V1 into TYCOON_ASSET_SOURCE_V1.

The kiosk identity is authored as real geometry so the frozen AssetRoot rotation
produces consistent SOUTH/EAST/WEST/NORTH views. No 2D generative repaint is
required for category identity.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def box(name, location, dimensions, material, bevel=0.025):
    return {
        "type": "box",
        "name": name,
        "location": [round(float(v), 4) for v in location],
        "dimensions": [round(float(v), 4) for v in dimensions],
        "material": material,
        "bevel": bevel,
    }


def sphere(name, location, radius, material, segments=20, rings=10):
    return {
        "type": "uv_sphere",
        "name": name,
        "location": [round(float(v), 4) for v in location],
        "radius": round(float(radius), 4),
        "segments": int(segments),
        "rings": int(rings),
        "material": material,
    }


def expand(recipe: dict) -> dict:
    if recipe.get("contract") != "CITY_HORIZON_PARK_KIOSK_V1":
        raise ValueError("Expected CITY_HORIZON_PARK_KIOSK_V1")

    fp = recipe["footprint"]
    if int(fp["widthTiles"]) != 1 or int(fp["depthTiles"]) != 1:
        raise ValueError("park kiosk pilot is intentionally a 1x1 asset")

    m = recipe["mass"]
    op = recipe["openings"]
    awning = recipe["awning"]
    roof_identity = recipe["roofIdentity"]
    menu = recipe["menuBoard"]
    mats = recipe["materials"]

    bw = float(m["bodyWidth"])
    bd = float(m["bodyDepth"])
    bh = float(m["bodyHeight"])
    base_h = float(m["baseHeight"])
    cw = float(m["canopyWidth"])
    cd = float(m["canopyDepth"])
    ct = float(m["canopyThickness"])
    cz = float(m["canopyZ"])

    if max(bw, cw) > 3.0 or max(bd, cd) > 3.0:
        raise ValueError("kiosk geometry exceeds 1x1 world footprint")
    if cw <= bw or cd <= bd:
        raise ValueError("canopy must visibly overhang the kiosk body")

    parts = []
    parts.append(box("Kiosk_Base", [0, 0, base_h / 2], [bw + 0.12, bd + 0.12, base_h], "base", 0.05))
    parts.append(box("Kiosk_Body", [0, 0, base_h + bh / 2], [bw, bd, bh], "body", 0.07))

    # Flat graphic canopy, intentionally non-residential.
    parts.append(box("Kiosk_Canopy", [0, 0, cz], [cw, cd, ct], "canopy", 0.08))
    fascia_h = 0.16
    parts.append(box("Kiosk_Fascia_South", [0, -cd / 2 + 0.035, cz - 0.01], [cw - 0.10, 0.07, fascia_h], "accent", 0.025))
    parts.append(box("Kiosk_Fascia_East", [cw / 2 - 0.035, 0, cz - 0.01], [0.07, cd - 0.10, fascia_h], "accent", 0.025))

    sill = float(op["sillZ"])
    sw = float(op["southWindowWidth"])
    sh = float(op["southWindowHeight"])
    ew = float(op["eastWindowWidth"])
    eh = float(op["eastWindowHeight"])
    inset = 0.035

    # Deep, dark serving openings: read as food-service windows rather than glass office windows.
    parts.append(box("Kiosk_South_Window", [0, -bd / 2 - inset, sill + sh / 2], [sw, 0.06, sh], "glass", 0.018))
    parts.append(box("Kiosk_East_Window", [bw / 2 + inset, -0.08, sill + eh / 2], [0.06, ew, eh], "glass", 0.018))

    counter_d = float(op["counterDepth"])
    counter_t = float(op["counterThickness"])
    counter_z = sill - 0.03
    parts.append(box("Kiosk_South_Counter", [0, -bd / 2 - counter_d / 2, counter_z], [sw + 0.24, counter_d, counter_t], "counter", 0.035))
    parts.append(box("Kiosk_East_Counter", [bw / 2 + counter_d / 2, -0.08, counter_z], [counter_d, ew + 0.16, counter_t], "counter", 0.035))

    # Red/cream striped awning in front of the main service window.
    if bool(awning.get("enabled", True)):
        stripe_count = max(3, int(awning.get("stripeCount", 7)))
        awning_depth = float(awning.get("depth", 0.42))
        drop = float(awning.get("drop", 0.16))
        stripe_w = (sw + 0.52) / stripe_count
        start_x = -(sw + 0.52) / 2 + stripe_w / 2
        y = -bd / 2 - awning_depth / 2 - 0.02
        z = cz - ct / 2 - drop / 2 + 0.02
        for i in range(stripe_count):
            material = "accent" if i % 2 == 0 else "canopy"
            parts.append(box(f"Awning_Stripe_{i}", [start_x + i * stripe_w, y, z], [stripe_w * 0.94, awning_depth, drop], material, 0.045))

    # Menu board on the east face: strong dark rectangle with warm frame.
    menu_w = float(menu["width"])
    menu_h = float(menu["height"])
    menu_y = float(menu.get("offsetY", 0.34))
    menu_x = bw / 2 + 0.045
    menu_z = base_h + 0.72
    parts.append(box("Menu_Frame", [menu_x, menu_y, menu_z], [0.075, menu_w + 0.12, menu_h + 0.12], "counter", 0.028))
    parts.append(box("Menu_Board", [menu_x + 0.006, menu_y, menu_z], [0.085, menu_w, menu_h], "dark", 0.02))
    # Three chunky menu lines visible at gameplay scale.
    for i, scale in enumerate((0.72, 0.60, 0.48)):
        parts.append(box(f"Menu_Line_{i}", [menu_x + 0.055, menu_y - 0.08 + i * 0.16, menu_z + 0.14 - i * 0.16], [0.035, menu_w * scale, 0.045], "canopy", 0.012))

    # Condiment bottles as tiny iconic blocks on the counter.
    condiment_y = -bd / 2 - counter_d - 0.035
    parts.append(box("Ketchup_Bottle", [-0.28, condiment_y, counter_z + 0.17], [0.11, 0.11, 0.27], "accent", 0.045))
    parts.append(box("Mustard_Bottle", [-0.10, condiment_y, counter_z + 0.17], [0.11, 0.11, 0.27], "mustard", 0.045))

    # Oversized roof hot-dog identity. Rounded bars are built from beveled boxes plus
    # small spherical end-caps so the icon remains original, simple and rotation-safe.
    hot_len = float(roof_identity["length"])
    bun_w = float(roof_identity["bunWidth"])
    sausage_w = float(roof_identity["sausageWidth"])
    hot_h = float(roof_identity["height"])
    hot_z = float(roof_identity["z"])
    support_h = float(roof_identity.get("supportHeight", 0.20))

    # Two discreet supports make the roof prop feel physically attached.
    for x in (-hot_len * 0.28, hot_len * 0.28):
        parts.append(box("HotDog_Support_L" if x < 0 else "HotDog_Support_R", [x, 0.03, hot_z - hot_h / 2 - support_h / 2], [0.10, 0.10, support_h], "dark", 0.025))

    # Bun halves, sausage and rounded end caps.
    parts.append(box("HotDog_Bun_Back", [0, 0.11, hot_z], [hot_len, bun_w, hot_h], "bun", hot_h * 0.42))
    parts.append(box("HotDog_Sausage", [0, -0.01, hot_z + 0.01], [hot_len * 0.88, sausage_w, hot_h * 0.74], "sausage", hot_h * 0.34))
    parts.append(box("HotDog_Bun_Front", [0, -0.17, hot_z - 0.015], [hot_len, bun_w * 0.78, hot_h * 0.72], "bun", hot_h * 0.34))
    cap_r = hot_h * 0.25
    for x in (-hot_len * 0.44, hot_len * 0.44):
        parts.append(sphere(f"HotDog_SausageCap_{'L' if x < 0 else 'R'}", [x, -0.01, hot_z + 0.01], cap_r, "sausage"))

    # Mustard squiggle: five bright beads across the sausage. It reads as a graphic
    # line after downsampling without requiring textures or image-space painting.
    mustard_points = [(-0.48, -0.045), (-0.24, 0.015), (0.0, -0.035), (0.24, 0.018), (0.48, -0.04)]
    for i, (x, yoff) in enumerate(mustard_points):
        parts.append(sphere(f"HotDog_Mustard_{i}", [x * hot_len * 0.78, -0.13 + yoff, hot_z + hot_h * 0.23], 0.055, "mustard", 16, 8))

    # Rear service door keeps the back view authored rather than blank.
    door_h = 1.02
    door_w = 0.58
    parts.append(box("Kiosk_Rear_Service_Door", [-0.34, bd / 2 + inset, base_h + door_h / 2], [door_w, 0.06, door_h], "dark", 0.02))

    return {
        "contract": "TYCOON_ASSET_SOURCE_V1",
        "assetId": recipe["assetId"],
        "assetType": "static_building",
        "styleContract": recipe.get("styleContract", "CH_TYCOON_MINIATURE_V1"),
        "studioPreset": recipe.get("studioPreset", "CH_TYCOON_STUDIO_V1"),
        "footprint": {
            "widthTiles": 1,
            "depthTiles": 1,
            "occupiedCells": [[0, 0]],
        },
        "materials": {key: value for key, value in mats.items()},
        "parts": parts,
        "buildingPostProcess": recipe.get("buildingPostProcess", {}),
        "generation": {
            "sourceContract": recipe["contract"],
            "designGrammar": "hotdog_kiosk_geometry_identity_v2",
            "partCount": len(parts),
            "retiredHouseGeometryReused": False,
            "identityAuthoredIn3D": True,
            "rotationConsistency": "AssetRoot_four_direction_bake",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipe", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    recipe = json.loads(Path(args.recipe).read_text(encoding="utf-8"))
    asset = expand(recipe)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(asset, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(asset["generation"], sort_keys=True))


if __name__ == "__main__":
    main()
