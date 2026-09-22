#!/usr/bin/env python3
"""Expand CITY_HORIZON_SMALL_COMMERCIAL_V1 into TYCOON_ASSET_SOURCE_V1.

This is the reusable procedural authoring layer for compact City Horizon shops.
The recipe carries design intent; this expander resolves it into deterministic
canonical primitives consumed by CH Blender's frozen baker.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

TILE_WORLD = 3.0


def _box(name, loc, dims, material, bevel=0.03):
    return {
        "type": "box",
        "name": name,
        "location": [round(float(v), 4) for v in loc],
        "dimensions": [round(float(v), 4) for v in dims],
        "material": material,
        "bevel": float(bevel),
    }


def _sphere(name, loc, radius, material):
    return {
        "type": "uv_sphere",
        "name": name,
        "location": [round(float(v), 4) for v in loc],
        "radius": float(radius),
        "segments": 20,
        "rings": 10,
        "material": material,
    }


def _validate(recipe):
    if recipe.get("contract") != "CITY_HORIZON_SMALL_COMMERCIAL_V1":
        raise ValueError("Expected CITY_HORIZON_SMALL_COMMERCIAL_V1")
    footprint = recipe.get("footprint", {})
    w = int(footprint.get("widthTiles", 0))
    d = int(footprint.get("depthTiles", 0))
    if w < 1 or d < 1:
        raise ValueError("commercial footprint must be at least 1x1")
    mass = recipe.get("mass", {})
    width = float(mass["width"])
    depth = float(mass["depth"])
    if width > w * TILE_WORLD or depth > d * TILE_WORLD:
        raise ValueError("commercial mass exceeds declared footprint")
    if recipe.get("facade", {}).get("front", "south") != "south":
        raise ValueError("V1 small commercial recipe uses SOUTH as authored front")


def expand(recipe):
    _validate(recipe)
    fp = recipe["footprint"]
    mass = recipe["mass"]
    facade = recipe["facade"]
    materials = recipe["materials"]

    width = float(mass["width"])
    depth = float(mass["depth"])
    wall_h = float(mass["wallHeight"])
    base_h = float(mass.get("baseHeight", 0.12))
    parapet_h = float(mass.get("parapetHeight", 0.30))
    front_y = -depth / 2.0
    back_y = depth / 2.0
    east_x = width / 2.0
    west_x = -width / 2.0
    face_eps = 0.035

    parts = []

    # Ground-contact base and compact main mass.
    parts.append(_box("CommercialBase", [0, 0, base_h / 2], [width, depth, base_h], "sidewalk", 0.025))
    parts.append(_box("CommercialMainMass", [0, 0, base_h + wall_h / 2], [width, depth, wall_h], "wall", 0.045))

    # Flat roof + four raised parapets. Roof/parapet uses the second recolor role.
    roof_z = base_h + wall_h + 0.07
    parts.append(_box("RoofSlab", [0, 0, roof_z], [width + 0.12, depth + 0.12, 0.14], "roof", 0.025))
    parapet_z = roof_z + 0.07 + parapet_h / 2
    parts.extend([
        _box("ParapetSouth", [0, front_y + 0.08, parapet_z], [width, 0.16, parapet_h], "roof", 0.018),
        _box("ParapetNorth", [0, back_y - 0.08, parapet_z], [width, 0.16, parapet_h], "roof", 0.018),
        _box("ParapetEast", [east_x - 0.08, 0, parapet_z], [0.16, depth, parapet_h], "roof", 0.018),
        _box("ParapetWest", [west_x + 0.08, 0, parapet_z], [0.16, depth, parapet_h], "roof", 0.018),
    ])

    # Integrated front apron. It remains inside the declared 2x2 footprint and
    # visually eliminates the unexplained grass strip in road-facing placement.
    apron_depth = max(0.42, min(0.62, 3.0 - depth / 2.0 - 0.04))
    apron_y = front_y - apron_depth / 2.0
    parts.append(_box("FrontSidewalkApron", [0, apron_y, 0.055], [width + 0.24, apron_depth, 0.11], "sidewalk", 0.018))

    # Front storefront: two broad display windows with centered/right entrance.
    win_w = float(facade["windowWidth"])
    win_h = float(facade["windowHeight"])
    sill = float(facade["windowSill"])
    door_w = float(facade["doorWidth"])
    door_h = float(facade["doorHeight"])
    glass_y = front_y - face_eps
    parts.append(_box("FrontWindowLeft_Frame", [-1.46, glass_y - 0.012, sill + win_h / 2], [win_w + 0.16, 0.095, win_h + 0.16], "trim", 0.018))
    parts.append(_box("FrontWindowLeft_Glass", [-1.46, glass_y - 0.065, sill + win_h / 2], [win_w, 0.045, win_h], "glass", 0.010))
    parts.append(_box("FrontWindowRight_Frame", [0.36, glass_y - 0.012, sill + win_h / 2], [win_w + 0.16, 0.095, win_h + 0.16], "trim", 0.018))
    parts.append(_box("FrontWindowRight_Glass", [0.36, glass_y - 0.065, sill + win_h / 2], [win_w, 0.045, win_h], "glass", 0.010))
    door_x = width / 2.0 - door_w / 2.0 - 0.34
    parts.append(_box("FrontDoor_Frame", [door_x, glass_y - 0.012, base_h + door_h / 2], [door_w + 0.17, 0.10, door_h + 0.12], "trim", 0.018))
    parts.append(_box("FrontDoor", [door_x, glass_y - 0.068, base_h + door_h / 2], [door_w, 0.05, door_h], "door", 0.012))
    parts.append(_box("FrontDoorGlass", [door_x, glass_y - 0.100, base_h + door_h * 0.69], [door_w * 0.63, 0.026, door_h * 0.42], "glass", 0.008))

    # Awning and simple broad stripes, all in trim mask group.
    awning = facade.get("awning", {})
    if awning.get("enabled", False):
        aw_w = float(awning["width"])
        aw_d = float(awning["depth"])
        aw_h = float(awning["height"])
        aw_z = float(awning["z"])
        parts.append(_box("BakeryAwning", [-0.34, front_y - aw_d / 2 - 0.06, aw_z], [aw_w, aw_d, aw_h], "awning", 0.025))
        stripe_count = 7
        stripe_w = aw_w / stripe_count
        for i in range(0, stripe_count, 2):
            x = -0.34 - aw_w / 2 + stripe_w * (i + 0.5)
            parts.append(_box(f"AwningStripe_{i}", [x, front_y - aw_d - 0.075, aw_z - 0.01], [stripe_w * 0.72, 0.055, aw_h * 0.74], "trim", 0.010))

    # Sign is intentionally geometry-based; bakery identity does not depend on text.
    sign = facade.get("sign", {})
    if sign.get("enabled", False):
        sign_w = float(sign["width"])
        sign_h = float(sign["height"])
        sign_d = float(sign["depth"])
        sign_z = float(sign["z"])
        parts.append(_box("BakerySignBoard", [-0.28, front_y - sign_d / 2 - 0.04, sign_z], [sign_w, sign_d, sign_h], "trim", 0.035))
        if sign.get("breadMark", False):
            # Three warm circular marks read as rolls/loaves at gameplay scale.
            for i, x in enumerate((-0.55, -0.28, -0.01)):
                parts.append(_sphere(f"BreadMark_{i}", [x, front_y - sign_d - 0.07, sign_z], 0.105, "bread"))

    # Side windows make EAST/WEST/NORTH useful rotations rather than blank backs.
    def side_windows(face, count):
        if count <= 0:
            return
        span = depth - 1.10
        step = span / count
        for i in range(count):
            y = -span / 2 + step * (i + 0.5)
            if face == "east":
                frame_loc = [east_x + 0.025, y, 1.18]
                frame_dims = [0.095, 1.02, 0.92]
                glass_loc = [east_x + 0.078, y, 1.18]
                glass_dims = [0.045, 0.86, 0.76]
            else:
                frame_loc = [west_x - 0.025, -y, 1.18]
                frame_dims = [0.095, 1.02, 0.92]
                glass_loc = [west_x - 0.078, -y, 1.18]
                glass_dims = [0.045, 0.86, 0.76]
            parts.append(_box(f"{face.title()}Window_{i}_Frame", frame_loc, frame_dims, "trim", 0.016))
            parts.append(_box(f"{face.title()}Window_{i}_Glass", glass_loc, glass_dims, "glass", 0.009))

    side_windows("east", int(recipe.get("sideWindows", {}).get("east", 0)))
    side_windows("west", int(recipe.get("sideWindows", {}).get("west", 0)))

    # Rear service language for NORTH rotation.
    rear = recipe.get("rear", {})
    if rear.get("serviceDoor", False):
        parts.append(_box("RearServiceDoorFrame", [-1.16, back_y + 0.025, 0.98], [0.92, 0.10, 1.82], "trim", 0.016))
        parts.append(_box("RearServiceDoor", [-1.16, back_y + 0.078, 0.98], [0.76, 0.045, 1.66], "door", 0.010))
    if rear.get("smallWindow", False):
        parts.append(_box("RearWindowFrame", [0.78, back_y + 0.025, 1.26], [1.20, 0.10, 0.82], "trim", 0.016))
        parts.append(_box("RearWindowGlass", [0.78, back_y + 0.078, 1.26], [1.04, 0.045, 0.66], "glass", 0.008))

    roof_props = recipe.get("roofProps", {})
    if roof_props.get("chimney", False):
        parts.append(_box("BakeryChimney", [-1.46, 0.74, roof_z + 0.48], [0.42, 0.42, 0.86], "roof", 0.025))
        parts.append(_box("BakeryChimneyCap", [-1.46, 0.74, roof_z + 0.94], [0.55, 0.55, 0.10], "dark", 0.018))
    if roof_props.get("acUnit", False):
        parts.append(_box("BakeryACUnit", [1.25, 0.72, roof_z + 0.24], [0.78, 0.56, 0.34], "dark", 0.028))

    occupied = [[x, y] for y in range(int(fp["depthTiles"])) for x in range(int(fp["widthTiles"]))]
    return {
        "contract": "TYCOON_ASSET_SOURCE_V1",
        "assetId": recipe["assetId"],
        "assetType": "static_building",
        "studioPreset": recipe.get("studioPreset", "CH_TYCOON_STUDIO_V1"),
        "styleContract": recipe.get("styleContract", "CH_STYLIZED_PRERENDER_V1"),
        "floors": 1,
        "footprint": {
            "widthTiles": int(fp["widthTiles"]),
            "depthTiles": int(fp["depthTiles"]),
            "occupiedCells": occupied,
        },
        "materials": materials,
        "parts": parts,
        "colorMask": recipe.get("colorMask"),
        "generation": {
            "sourceContract": recipe["contract"],
            "subtype": recipe.get("subtype"),
            "seed": int(recipe.get("seed", 0)),
            "partCount": len(parts),
            "front": "south",
        },
        "designIntent": recipe.get("designIntent", {}),
    }


def main():
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
