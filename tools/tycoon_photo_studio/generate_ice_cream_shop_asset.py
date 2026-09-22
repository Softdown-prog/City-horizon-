#!/usr/bin/env python3
"""Procedural specialization for the animated City Horizon ice cream shop.

The common small-commercial generator remains the architectural base. This
module adds ice-cream-specific, gameplay-scale geometry and animation metadata
without teaching the generic shop contract about one business subtype.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import generate_small_commercial_asset as base


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
    if recipe.get("subtype") != "ice_cream_shop":
        raise ValueError("generate_ice_cream_shop_asset expects subtype=ice_cream_shop")

    asset = base.expand(recipe)
    parts = asset["parts"]
    mass = recipe["mass"]
    facade = recipe["facade"]
    details = recipe.get("iceCream", {})

    width = float(mass["width"])
    depth = float(mass["depth"])
    wall_h = float(mass["wallHeight"])
    base_h = float(mass.get("baseHeight", 0.12))
    front_y = -depth / 2.0
    back_y = depth / 2.0
    east_x = width / 2.0
    roof_z = base_h + wall_h + 0.07
    sill = float(facade["windowSill"])

    # V2 architectural read: a broad projecting crown and corner blades make the
    # storefront feel designed rather than like a decorated box. These are large
    # enough to survive the gameplay render and deliberately avoid microdetail.
    if details.get("facadeCrown", False):
        crown_y = front_y - 0.105
        parts.append(_box(
            "IceCreamFacadeCrown",
            [-0.30, crown_y, 2.17],
            [width - 0.34, 0.20, 0.30],
            "trim",
            0.045,
        ))
        parts.append(_box(
            "IceCreamFacadeCrownAccent",
            [-0.30, crown_y - 0.115, 2.17],
            [width - 0.72, 0.055, 0.14],
            "awning",
            0.024,
        ))

    if details.get("colorPillars", False):
        pillar_y = front_y - 0.072
        pillar_z = 1.17
        pillar_h = 1.78
        for name, x, mat in (
            ("West", -2.18, "strawberry"),
            ("MidWest", -0.92, "pistachio"),
            ("MidEast", 0.78, "blueberry"),
            ("East", 2.10, "strawberry"),
        ):
            parts.append(_box(
                f"IceCreamColorPillar{name}",
                [x, pillar_y, pillar_z],
                [0.16, 0.11, pillar_h],
                mat,
                0.028,
            ))

    # Broad refrigerated display visible through the storefront. The large tubs
    # are deliberately exaggerated so flavor colors survive the final sprite.
    if details.get("freezerCase", False):
        display_y = front_y - 0.120
        parts.append(_box(
            "IceCreamFreezerCase",
            [-0.58, display_y, sill + 0.15],
            [3.46, 0.13, 0.30],
            "trim",
            0.020,
        ))
        parts.append(_box(
            "IceCreamFreezerCaseBaseAccent",
            [-0.58, display_y - 0.035, sill + 0.03],
            [3.28, 0.060, 0.13],
            "awning",
            0.018,
        ))
        parts.append(_box(
            "IceCreamFreezerGlass",
            [-0.58, display_y - 0.060, sill + 0.40],
            [3.26, 0.048, 0.29],
            "glass",
            0.010,
        ))

    if details.get("windowDisplay", False):
        display_y = front_y - 0.162
        flavor_x = (-1.58, -0.92, -0.26, 0.40)
        flavor_mats = ("strawberry", "vanilla", "pistachio", "blueberry")
        for index, (x, mat) in enumerate(zip(flavor_x, flavor_mats)):
            parts.append(_box(
                f"IceCreamFlavorTub_{index}",
                [x, display_y, sill + 0.23],
                [0.50, 0.105, 0.19],
                mat,
                0.048,
            ))
            parts.append(_sphere(
                f"IceCreamFlavorScoop_{index}",
                [x, display_y - 0.056, sill + 0.45],
                0.155,
                mat,
            ))

    # Larger geometric sundae mark. It is intentionally oversized so the shop
    # remains identifiable without readable text after downsampling.
    if details.get("sundaeSign", False):
        sign = facade.get("sign", {})
        sign_z = float(sign.get("z", 2.48))
        sign_d = float(sign.get("depth", 0.14))
        mark_y = front_y - sign_d - 0.090
        cup_x = -0.28
        parts.append(_box(
            "IceCreamSundaeCup",
            [cup_x, mark_y, sign_z - 0.15],
            [0.92, 0.058, 0.29],
            "cone",
            0.070,
        ))
        for index, (dx, dz, mat) in enumerate((
            (-0.31, 0.16, "strawberry"),
            (0.00, 0.23, "vanilla"),
            (0.31, 0.16, "pistachio"),
        )):
            parts.append(_sphere(
                f"IceCreamSundaeScoop_{index}",
                [cup_x + dx, mark_y - 0.014, sign_z + dz],
                0.205,
                mat,
            ))

    # Small side accent band breaks up the large wall plane without becoming
    # texture noise. It also visually ties the side elevation back to the shop.
    if details.get("sideAccentBand", False):
        parts.append(_box(
            "IceCreamEastAccentBand",
            [east_x + 0.042, 0.12, 1.98],
            [0.070, depth - 0.46, 0.18],
            "awning",
            0.018,
        ))

    # Rear cold-storage/service cue, still sparse enough for gameplay scale.
    parts.append(_box(
        "IceCreamRearColdBox",
        [-1.40, back_y + 0.20, 0.36],
        [0.72, 0.36, 0.70],
        "trim",
        0.040,
    ))
    parts.append(_box(
        "IceCreamRearColdBoxLatch",
        [-1.40, back_y + 0.405, 0.40],
        [0.12, 0.04, 0.22],
        "dark",
        0.012,
    ))

    # Localized building animation moved off the roof mass and into a dedicated
    # corner totem. The rotating object is now one rounded popsicle board, so the
    # motion reads cleanly instead of visually separating a fixed scoop cap.
    if details.get("rotatingPopsicleSign", False):
        spinner_x = east_x - 0.18
        spinner_y = front_y - 0.28
        totem_base_z = 1.54
        spinner_z = 2.58
        parts.append(_box(
            "IceCreamSpinnerBracket",
            [spinner_x - 0.10, front_y - 0.095, 1.62],
            [0.42, 0.22, 0.18],
            "dark",
            0.030,
        ))
        parts.append(_box(
            "IceCreamSpinnerMast",
            [spinner_x, spinner_y, totem_base_z],
            [0.11, 0.11, 1.30],
            "dark",
            0.020,
        ))
        parts.append(_box(
            "IceCreamSpinnerStick",
            [spinner_x, spinner_y, spinner_z - 0.57],
            [0.14, 0.12, 0.36],
            "cone",
            0.028,
        ))
        parts.append(_box(
            "IceCreamSpinner",
            [spinner_x, spinner_y, spinner_z],
            [0.64, 0.17, 0.96],
            "spinner",
            0.22,
        ))
        parts.append(_box(
            "IceCreamSpinnerStripe",
            [spinner_x, spinner_y - 0.100, spinner_z + 0.05],
            [0.42, 0.040, 0.15],
            "strawberry",
            0.050,
        ))

    anim = dict(recipe.get("animation", {}))
    if anim.get("enabled", False):
        if anim.get("bladeObjectName") != "IceCreamSpinner":
            raise ValueError("ice cream animation must rotate IceCreamSpinner")
        asset["animation"] = anim
        asset["assetType"] = "animated_building"

    generation = dict(asset.get("generation", {}))
    generation.update({
        "specialization": "CITY_HORIZON_ICE_CREAM_SHOP_V2",
        "animationReady": bool(anim.get("enabled", False)),
        "animatedObject": anim.get("bladeObjectName"),
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
    print(f"[ice_cream_shop] wrote {output} ({len(asset['parts'])} parts)")


if __name__ == "__main__":
    main()
