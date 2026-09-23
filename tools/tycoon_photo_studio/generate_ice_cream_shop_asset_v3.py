#!/usr/bin/env python3
"""Light V3 polish layer for the City Horizon procedural ice cream shop.

V2 already established the approved architecture. This layer deliberately keeps
that structure intact and adds only gameplay-scale finishing geometry: a stronger
sign surround, a thin storefront fascia, a side identity badge and a clearer
corner-totem cap. It does not change camera, lighting, footprint or animation
contract.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import generate_ice_cream_shop_asset as v2


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


def expand(recipe):
    asset = v2.expand(recipe)
    details = recipe.get("iceCream", {})
    if not details.get("polishV3", False):
        return asset

    parts = asset["parts"]
    mass = recipe["mass"]
    facade = recipe["facade"]
    width = float(mass["width"])
    depth = float(mass["depth"])
    front_y = -depth / 2.0
    east_x = width / 2.0

    # Raise the complete corner totem as one visual unit. The V2 proportions are
    # preserved; only its height changes so the animated sign clears the awning
    # and remains readable in all four runtime rotations.
    totem_raise = 0.18
    for part in parts:
        if part.get("name") in {
            "IceCreamSpinnerBracket",
            "IceCreamSpinnerMast",
            "IceCreamSpinnerStick",
            "IceCreamSpinner",
            "IceCreamSpinnerStripe",
        }:
            location = list(part.get("location", []))
            if len(location) == 3:
                location[2] = round(float(location[2]) + totem_raise, 4)
                part["location"] = location

    sign = facade.get("sign", {})
    sign_w = float(sign.get("width", 3.2))
    sign_h = float(sign.get("height", 0.72))
    sign_d = float(sign.get("depth", 0.15))
    sign_z = float(sign.get("z", 2.45))
    sign_y = front_y - sign_d - 0.022

    # Cream outer surround + thin berry inset: the main identity mark now reads
    # as a designed storefront sign rather than loose geometry on a blank panel.
    parts.append(_box(
        "IceCreamV3SignSurround",
        [-0.28, sign_y + 0.030, sign_z],
        [sign_w + 0.28, 0.075, sign_h + 0.20],
        "trim",
        0.050,
    ))
    parts.append(_box(
        "IceCreamV3SignInset",
        [-0.28, sign_y - 0.018, sign_z],
        [sign_w + 0.04, 0.040, sign_h + 0.02],
        "awning",
        0.035,
    ))

    # A thin fascia under the crown visually compresses the wall mass and makes
    # the storefront feel shallower without changing the actual footprint.
    parts.append(_box(
        "IceCreamV3StorefrontFascia",
        [-0.30, front_y - 0.092, 2.055],
        [width - 0.48, 0.090, 0.11],
        "trim",
        0.020,
    ))

    # Side badge carries the ice-cream identity around the building so EAST/WEST
    # views are not just a colored wall with windows.
    badge_x = east_x + 0.055
    badge_y = 0.22
    parts.append(_sphere(
        "IceCreamV3SideBadge",
        [badge_x, badge_y, 1.56],
        0.30,
        "vanilla",
    ))
    parts.append(_sphere(
        "IceCreamV3SideBadgeCenter",
        [badge_x + 0.035, badge_y, 1.56],
        0.17,
        "strawberry",
    ))

    # Fixed vanilla cap above the animated board gives the corner totem a more
    # obvious frozen-treat silhouette even when the rotating board is edge-on.
    spinner_x = east_x - 0.18
    spinner_y = front_y - 0.28
    parts.append(_sphere(
        "IceCreamV3TotemCap",
        [spinner_x, spinner_y, 3.10 + totem_raise],
        0.25,
        "vanilla",
    ))

    generation = dict(asset.get("generation", {}))
    generation.update({
        "specialization": "CITY_HORIZON_ICE_CREAM_SHOP_V3",
        "v3Polish": True,
        "totemRaise": totem_raise,
        "partCount": len(parts),
    })
    asset["generation"] = generation
    return asset


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipe", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    recipe = json.loads(Path(args.recipe).read_text(encoding="utf-8"))
    asset = expand(recipe)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(asset, indent=2) + "\n", encoding="utf-8")
    print(f"[ice_cream_shop_v3] wrote {output} ({len(asset['parts'])} parts)")


if __name__ == "__main__":
    main()
