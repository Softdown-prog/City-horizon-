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
    roof_z = base_h + wall_h + 0.07
    sill = float(facade["windowSill"])

    # Broad refrigerated display visible through the storefront. The large tubs
    # are deliberately exaggerated so flavor colors survive the 256 px sprite.
    if details.get("freezerCase", False):
        display_y = front_y - 0.112
        parts.append(_box(
            "IceCreamFreezerCase",
            [-0.58, display_y, sill + 0.15],
            [3.35, 0.12, 0.28],
            "trim",
            0.018,
        ))
        parts.append(_box(
            "IceCreamFreezerGlass",
            [-0.58, display_y - 0.055, sill + 0.38],
            [3.18, 0.045, 0.26],
            "glass",
            0.010,
        ))

    if details.get("windowDisplay", False):
        display_y = front_y - 0.150
        flavor_x = (-1.55, -0.91, -0.27, 0.37)
        flavor_mats = ("strawberry", "vanilla", "pistachio", "blueberry")
        for index, (x, mat) in enumerate(zip(flavor_x, flavor_mats)):
            parts.append(_box(
                f"IceCreamFlavorTub_{index}",
                [x, display_y, sill + 0.22],
                [0.48, 0.10, 0.18],
                mat,
                0.045,
            ))
            parts.append(_sphere(
                f"IceCreamFlavorScoop_{index}",
                [x, display_y - 0.052, sill + 0.42],
                0.145,
                mat,
            ))

    # Geometric sundae mark: three oversized scoops over a wafer-colored cup.
    # No text is required to identify the business.
    if details.get("sundaeSign", False):
        sign = facade.get("sign", {})
        sign_z = float(sign.get("z", 2.48))
        sign_d = float(sign.get("depth", 0.14))
        mark_y = front_y - sign_d - 0.078
        cup_x = -0.28
        parts.append(_box(
            "IceCreamSundaeCup",
            [cup_x, mark_y, sign_z - 0.13],
            [0.72, 0.052, 0.24],
            "cone",
            0.060,
        ))
        for index, (dx, dz, mat) in enumerate((
            (-0.25, 0.13, "strawberry"),
            (0.00, 0.18, "vanilla"),
            (0.25, 0.13, "pistachio"),
        )):
            parts.append(_sphere(
                f"IceCreamSundaeScoop_{index}",
                [cup_x + dx, mark_y - 0.012, sign_z + dz],
                0.16,
                mat,
            ))

    # Pastel facade pillars strengthen the storefront rhythm without adding
    # microdetail. These are product colors, intentionally outside recolor mask.
    if details.get("colorPillars", False):
        pillar_y = front_y - 0.060
        parts.append(_box(
            "IceCreamColorPillarWest",
            [-2.18, pillar_y, 1.16],
            [0.18, 0.10, 1.66],
            "strawberry",
            0.025,
        ))
        parts.append(_box(
            "IceCreamColorPillarEast",
            [1.18, pillar_y, 1.16],
            [0.18, 0.10, 1.66],
            "blueberry",
            0.025,
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

    # Localized building animation: a rounded popsicle-shaped board rotates on
    # a fixed mast. The generic animation baker already supports one rotating
    # named object, so this remains compatible with the canonical 4-dir baker.
    if details.get("rotatingPopsicleSign", False):
        spinner_x = 1.42
        spinner_y = -0.72
        mast_top = roof_z + 1.12
        parts.append(_box(
            "IceCreamSpinnerMast",
            [spinner_x, spinner_y, roof_z + 0.52],
            [0.10, 0.10, 0.96],
            "dark",
            0.018,
        ))
        parts.append(_box(
            "IceCreamSpinnerStick",
            [spinner_x, spinner_y, mast_top - 0.19],
            [0.16, 0.12, 0.38],
            "cone",
            0.030,
        ))
        parts.append(_box(
            "IceCreamSpinner",
            [spinner_x, spinner_y, mast_top + 0.32],
            [0.72, 0.16, 0.92],
            "spinner",
            0.16,
        ))
        parts.append(_sphere(
            "IceCreamSpinnerTopScoop",
            [spinner_x, spinner_y, mast_top + 0.77],
            0.28,
            "strawberry",
        ))

    anim = dict(recipe.get("animation", {}))
    if anim.get("enabled", False):
        if anim.get("bladeObjectName") != "IceCreamSpinner":
            raise ValueError("ice cream animation must rotate IceCreamSpinner")
        asset["animation"] = anim
        asset["assetType"] = "animated_building"

    generation = dict(asset.get("generation", {}))
    generation.update({
        "specialization": "CITY_HORIZON_ICE_CREAM_SHOP_V1",
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
