#!/usr/bin/env python3
"""Expand CH_CROP_OVERLAY_RECIPE_V1 recipes into TYCOON_ASSET_SOURCE_V1.

This generator creates transparent crop-only geometry recipes for wheat,
sugar cane and coffee. It intentionally emits no soil, no tile border and no
shadow plate so the final Blender bake can sit over CH_FARM_GROUND_V2.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

BLENDER_UNITS_PER_TILE = 3.0


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def hex_rgba(value: str, alpha: float = 1.0) -> list[float]:
    value = value.lstrip("#")
    return [int(value[i:i+2], 16) / 255.0 for i in (0, 2, 4)] + [alpha]


def mat(name: str, color: str, roughness: float = 0.78) -> dict:
    return {"id": name, "rgba": hex_rgba(color), "roughness": roughness, "metallic": 0.0}


def box(name: str, location, scale, material: str, rotation=None) -> dict:
    part = {
        "id": name,
        "type": "box",
        "location": list(location),
        "scale": list(scale),
        "material": material,
    }
    if rotation is not None:
        part["rotationDegrees"] = list(rotation)
    return part


def cylinder(name: str, location, radius: float, depth: float, material: str, sides=8) -> dict:
    return {
        "id": name,
        "type": "cylinder",
        "location": list(location),
        "radius": radius,
        "depth": depth,
        "vertices": sides,
        "material": material,
    }


def sphere(name: str, location, radius: float, material: str) -> dict:
    return {
        "id": name,
        "type": "uv_sphere",
        "location": list(location),
        "radius": radius,
        "segments": 10,
        "ringCount": 6,
        "material": material,
    }


def add_leaf(parts, prefix, x, y, z, length, width, material, yaw, pitch=18.0):
    parts.append(box(
        prefix,
        (x, y, z),
        (length * 0.5, width * 0.5, 0.018),
        material,
        (pitch, 0.0, yaw),
    ))


def build_wheat(recipe: dict, stage: dict) -> tuple[list[dict], list[dict]]:
    rng = random.Random(stage["seed"])
    colors = recipe["proceduralGrammar"]["palette"]
    materials = [
        mat("leaf", colors[0]),
        mat("stem", colors[1]),
        mat("head", colors[3] if stage.get("feature") == "golden_heads" else colors[2]),
    ]
    parts: list[dict] = []
    height = 0.35 + stage["height"] * 1.35
    clusters = recipe["proceduralGrammar"]["clusterCount"]
    lo, hi = recipe["proceduralGrammar"]["stemsPerCluster"]
    spacing = 2.45 / max(1, clusters - 1)
    for c in range(clusters):
        base_y = -1.2 + c * spacing
        stems = max(2, round((lo + hi) * 0.5 * stage["density"]))
        for i in range(stems):
            x = rng.uniform(-1.22, 1.22)
            y = base_y + rng.uniform(-0.07, 0.07)
            h = height * rng.uniform(0.88, 1.08)
            parts.append(cylinder(f"wheat_stem_{c}_{i}", (x, y, h * 0.5), 0.022, h, "stem", 6))
            add_leaf(parts, f"wheat_leaf_{c}_{i}", x + rng.uniform(-0.03, 0.03), y, h * 0.48,
                     0.25, 0.045, "leaf", rng.choice((-36, -22, 22, 36)), rng.uniform(12, 24))
            if stage["height"] >= 0.62:
                parts.append(box(f"wheat_head_{c}_{i}", (x, y, h + 0.07), (0.035, 0.025, 0.09), "head",
                                 (rng.uniform(-8, 8), rng.uniform(-5, 5), rng.uniform(-15, 15))))
    return materials, parts


def build_sugar_cane(recipe: dict, stage: dict) -> tuple[list[dict], list[dict]]:
    rng = random.Random(stage["seed"])
    colors = recipe["proceduralGrammar"]["palette"]
    materials = [mat("stalk", colors[1]), mat("stalk_light", colors[2]), mat("leaf", colors[0])]
    parts: list[dict] = []
    height = 0.45 + stage["height"] * 2.0
    rows = recipe["proceduralGrammar"]["rowCount"]
    lo, hi = recipe["proceduralGrammar"]["stalksPerRow"]
    for row in range(rows):
        y = -1.05 + row * (2.10 / max(1, rows - 1))
        count = max(2, round(((lo + hi) * 0.5) * stage["density"]))
        for i in range(count):
            x = -1.18 + (2.36 * (i + 0.5) / count) + rng.uniform(-0.05, 0.05)
            yy = y + rng.uniform(-0.05, 0.05)
            h = height * rng.uniform(0.9, 1.05)
            stalk_mat = "stalk_light" if ((i + row) & 1) else "stalk"
            parts.append(cylinder(f"cane_stalk_{row}_{i}", (x, yy, h * 0.5), 0.055, h, stalk_mat, 8))
            segments = 4 if stage.get("feature") == "thicker_segmented_stalks" else 3
            for s in range(1, segments):
                parts.append(cylinder(f"cane_node_{row}_{i}_{s}", (x, yy, h * s / segments), 0.066, 0.025, "stalk_light", 8))
            for side in (-1, 1):
                add_leaf(parts, f"cane_leaf_{row}_{i}_{side}", x + side * 0.10, yy, h * rng.uniform(0.55, 0.88),
                         0.42, 0.055, "leaf", side * rng.uniform(28, 48), rng.uniform(18, 32))
    return materials, parts


def build_coffee(recipe: dict, stage: dict) -> tuple[list[dict], list[dict]]:
    rng = random.Random(stage["seed"])
    colors = recipe["proceduralGrammar"]["palette"]
    materials = [mat("stem", "#5a4934"), mat("leaf_dark", colors[0]), mat("leaf", colors[1]), mat("leaf_light", colors[2]), mat("fruit", colors[3])]
    parts: list[dict] = []
    rows = recipe["proceduralGrammar"]["rowCount"]
    lo, hi = recipe["proceduralGrammar"]["bushesPerRow"]
    bush_h = 0.35 + stage["height"] * 1.2
    for row in range(rows):
        y = -0.95 + row * (1.90 / max(1, rows - 1))
        count = max(2, round(((lo + hi) * 0.5) * max(0.55, stage["density"])))
        for i in range(count):
            x = -1.15 + (2.30 * (i + 0.5) / count) + rng.uniform(-0.05, 0.05)
            yy = y + rng.uniform(-0.06, 0.06)
            parts.append(cylinder(f"coffee_stem_{row}_{i}", (x, yy, bush_h * 0.42), 0.035, bush_h * 0.84, "stem", 7))
            leaf_count = max(4, round(7 * stage["density"]))
            for l in range(leaf_count):
                angle = (360.0 / leaf_count) * l + rng.uniform(-12, 12)
                rad = math.radians(angle)
                reach = rng.uniform(0.16, 0.30)
                lx = x + math.cos(rad) * reach
                ly = yy + math.sin(rad) * reach
                lz = bush_h * rng.uniform(0.45, 0.95)
                material = rng.choice(("leaf_dark", "leaf", "leaf_light"))
                add_leaf(parts, f"coffee_leaf_{row}_{i}_{l}", lx, ly, lz,
                         rng.uniform(0.20, 0.30), rng.uniform(0.075, 0.11), material, angle, rng.uniform(6, 18))
            if stage.get("feature") == "red_cherries":
                for f in range(3):
                    angle = rng.uniform(0, math.tau)
                    parts.append(sphere(f"coffee_fruit_{row}_{i}_{f}",
                                        (x + math.cos(angle) * 0.11, yy + math.sin(angle) * 0.11,
                                         bush_h * rng.uniform(0.46, 0.72)), 0.038, "fruit"))
    return materials, parts


def expand(recipe: dict, stage_id: str) -> dict:
    stage = next((s for s in recipe["stages"] if s["id"] == stage_id), None)
    if stage is None:
        raise SystemExit(f"Unknown stage: {stage_id}")

    crop_id = recipe["cropId"]
    if crop_id == "wheat":
        materials, parts = build_wheat(recipe, stage)
    elif crop_id == "sugar_cane":
        materials, parts = build_sugar_cane(recipe, stage)
    elif crop_id == "coffee":
        materials, parts = build_coffee(recipe, stage)
    else:
        raise SystemExit(f"Unsupported crop: {crop_id}")

    return {
        "contract": "TYCOON_ASSET_SOURCE_V1",
        "id": f"{recipe['id']}.{stage_id}",
        "category": "crop_overlay",
        "displayName": f"{recipe['displayName']} - {stage_id}",
        "studioPreset": recipe["handoff"]["studio"],
        "cameraContract": recipe["handoff"]["camera"],
        "footprint": {"widthTiles": 1, "depthTiles": 1},
        "groundEmbedded": False,
        "transparentBackground": True,
        "canvas": recipe["canvas"],
        "anchor": recipe["anchor"],
        "overlayScale": recipe["overlayScale"],
        "materials": materials,
        "parts": parts,
        "metadata": {
            "sourceRecipeContract": recipe["contract"],
            "cropId": crop_id,
            "stage": stage_id,
            "cameraContract": recipe["handoff"]["camera"],
            "studioContract": recipe["handoff"]["studio"],
            "notes": "Crop geometry only; no soil, no tile border, no shadow plate."
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipe", required=True, type=Path)
    parser.add_argument("--stage", default="ripe")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    recipe = load_json(args.recipe)
    if recipe.get("contract") != "CH_CROP_OVERLAY_RECIPE_V1":
        raise SystemExit("Unsupported recipe contract")
    asset = expand(recipe, args.stage)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(asset, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
