#!/usr/bin/env python3
"""Expand CITY_HORIZON_SHAPE_GRAMMAR_V1 into TYCOON_ASSET_SOURCE_V1.

This stage deliberately runs before Blender.  It keeps build_scene.py generic:
procedural architecture is resolved into the same small declarative primitives
already consumed by the canonical Tycoon baker.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

TILE_WORLD = 3.0


def _positive(value, name):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{name} must be a finite positive number")
    return number


def _nonnegative_integer(value, name):
    number = int(value)
    if isinstance(value, bool) or number != float(value) or number < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return number


def _box(name, loc, dims, material, bevel=0.025):
    return {
        "type": "box",
        "name": name,
        "location": [round(v, 4) for v in loc],
        "dimensions": [round(v, 4) for v in dims],
        "material": material,
        "bevel": bevel,
    }


def _choose(rng, value):
    if isinstance(value, list):
        if not value:
            raise ValueError("grammar choice list cannot be empty")
        return rng.choice(value)
    return value


def _poisson_roof_props(rng, width, depth, count, radius, z):
    """Small deterministic blue-noise sampler for roof props."""
    pts = []
    margin = 0.42
    xmin, xmax = -width / 2 + margin, width / 2 - margin
    ymin, ymax = -depth / 2 + margin, depth / 2 - margin
    attempts = max(80, count * 40)
    for _ in range(attempts):
        if len(pts) >= count:
            break
        p = (rng.uniform(xmin, xmax), rng.uniform(ymin, ymax))
        if all(math.dist(p, q) >= radius for q in pts):
            pts.append(p)
    return [(x, y, z) for x, y in pts]


def expand(grammar):
    if grammar.get("contract") != "CITY_HORIZON_SHAPE_GRAMMAR_V1":
        raise ValueError("Expected CITY_HORIZON_SHAPE_GRAMMAR_V1")

    seed = int(grammar.get("seed", 0))
    rng = random.Random(seed)
    footprint = grammar["footprint"]
    w_tiles = _nonnegative_integer(footprint["widthTiles"], "footprint.widthTiles")
    d_tiles = _nonnegative_integer(footprint["depthTiles"], "footprint.depthTiles")
    if w_tiles < 1 or d_tiles < 1:
        raise ValueError("footprint dimensions must be >= 1")

    mass = grammar["mass"]
    width = _positive(mass.get("width", w_tiles * TILE_WORLD * 0.82), "mass.width")
    depth = _positive(mass.get("depth", d_tiles * TILE_WORLD * 0.82), "mass.depth")
    max_w = w_tiles * TILE_WORLD
    max_d = d_tiles * TILE_WORLD
    if width > max_w or depth > max_d:
        raise ValueError("building mass exceeds declared footprint")
    if width <= 0.72 or depth <= 0.72:
        raise ValueError("building mass is too small for the facade opening margins")

    floor_h = _positive(mass["floorHeight"], "mass.floorHeight")
    floor_spec = mass["floorCount"]
    floor_min = _nonnegative_integer(floor_spec["min"], "mass.floorCount.min")
    floor_max = _nonnegative_integer(floor_spec["max"], "mass.floorCount.max")
    if floor_min < 2 or floor_max < floor_min:
        raise ValueError("mixed-use grammar requires at least 2 floors")
    floors = rng.randint(floor_min, floor_max)

    materials = grammar["materials"]
    wall_key = _choose(rng, materials["wallPalette"])
    material_defs = grammar["materialDefinitions"]
    required_materials = {wall_key, materials["trim"], materials["glass"], materials["roof"], materials["door"]}
    missing = required_materials - set(material_defs)
    if missing:
        raise ValueError(f"Missing material definitions: {sorted(missing)}")

    parts = []
    vertical = grammar["grammar"]["vertical"]
    if not vertical:
        raise ValueError("grammar.vertical must contain at least one level")
    ground_h = _positive(vertical[0].get("height", floor_h * 1.15), "grammar.vertical[0].height")
    upper_count = floors - 1
    body_h = ground_h + upper_count * floor_h

    # Main wall volume.
    parts.append(_box("Grammar_MainMass", [0, 0, body_h / 2], [width, depth, body_h], wall_key, 0.045))

    trim = materials["trim"]
    glass = materials["glass"]
    door_mat = materials["door"]

    # Ground-floor commercial facade on south and east faces.
    shop_h = ground_h * 0.58
    sill_z = ground_h * 0.52
    inset = 0.032
    door_w = 0.62
    opening_margin = 0.36
    usable_w = width - 2 * opening_margin
    bay_count = max(2, int(usable_w / 1.05))
    bay_w = usable_w / bay_count

    for i in range(bay_count):
        x = -usable_w / 2 + bay_w * (i + 0.5)
        is_door = i == bay_count - 1
        mat = door_mat if is_door else glass
        opening_w = door_w if is_door else bay_w * 0.72
        opening_h = ground_h * (0.68 if is_door else 0.52)
        opening_z = opening_h / 2 + 0.08 if is_door else sill_z
        parts.append(_box(f"South_Ground_{i}", [x, -depth / 2 - inset, opening_z], [opening_w, 0.055, opening_h], mat, 0.012))

    east_bays = max(2, int((depth - 2 * opening_margin) / 1.05))
    east_usable = depth - 2 * opening_margin
    east_bay_w = east_usable / east_bays
    for i in range(east_bays):
        y = -east_usable / 2 + east_bay_w * (i + 0.5)
        parts.append(_box(f"East_Ground_{i}", [width / 2 + inset, y, sill_z], [0.055, east_bay_w * 0.72, shop_h], glass, 0.012))

    # Deterministic upper-floor facade grammar.
    facade = grammar["grammar"]["facades"]["residential"]
    patterns = facade["patternChoices"]
    if not patterns or any(not pattern or any(token not in {"wall", "window", "balcony"} for token in pattern) for pattern in patterns):
        raise ValueError("residential.patternChoices must contain non-empty wall/window/balcony patterns")
    module_w = _positive(facade["moduleWidth"], "residential.moduleWidth")
    max_balconies = _nonnegative_integer(grammar["constraints"].get("balconyMaxPerFacade", 2), "constraints.balconyMaxPerFacade")

    def add_residential_face(face, level, pattern):
        z = ground_h + floor_h * (level + 0.52)
        horizontal = width if face in ("south", "north") else depth
        modules = max(2, int((horizontal - 0.48) / module_w))
        span = horizontal - 0.48
        step = span / modules
        balconies = 0
        for idx in range(modules):
            token = pattern[idx % len(pattern)]
            if token == "wall":
                continue
            pos = -span / 2 + step * (idx + 0.5)
            ww = min(step * 0.58, 0.54)
            wh = floor_h * 0.48
            if face == "south":
                loc, dims = [pos, -depth / 2 - inset, z], [ww, 0.05, wh]
            elif face == "north":
                loc, dims = [-pos, depth / 2 + inset, z], [ww, 0.05, wh]
            elif face == "east":
                loc, dims = [width / 2 + inset, pos, z], [0.05, ww, wh]
            else:
                loc, dims = [-width / 2 - inset, -pos, z], [0.05, ww, wh]
            parts.append(_box(f"{face.title()}_{level}_{idx}_Window", loc, dims, glass, 0.01))

            if token == "balcony" and balconies < max_balconies:
                balconies += 1
                if face in ("south", "north"):
                    by = loc[1] + (-0.16 if face == "south" else 0.16)
                    bloc, bdims = [loc[0], by, z - wh * 0.47], [ww * 1.35, 0.32, 0.08]
                else:
                    bx = loc[0] + (0.16 if face == "east" else -0.16)
                    bloc, bdims = [bx, loc[1], z - wh * 0.47], [0.32, ww * 1.35, 0.08]
                parts.append(_box(f"{face.title()}_{level}_{idx}_Balcony", bloc, bdims, trim, 0.018))

    for level in range(upper_count):
        for face in ("south", "east", "north", "west"):
            add_residential_face(face, level, rng.choice(patterns))

    # Crown / parapet.
    crown_h = _positive(vertical[-1].get("height", 0.24), "grammar.vertical[-1].height")
    crown_z = body_h + crown_h / 2
    parts.append(_box("Crown_South", [0, -depth / 2 + 0.08, crown_z], [width, 0.16, crown_h], trim, 0.02))
    parts.append(_box("Crown_North", [0, depth / 2 - 0.08, crown_z], [width, 0.16, crown_h], trim, 0.02))
    parts.append(_box("Crown_East", [width / 2 - 0.08, 0, crown_z], [0.16, depth, crown_h], trim, 0.02))
    parts.append(_box("Crown_West", [-width / 2 + 0.08, 0, crown_z], [0.16, depth, crown_h], trim, 0.02))

    # Roof props with deterministic Poisson-disk spacing.
    roof_spec = grammar.get("roofProps", {})
    prop_max = _nonnegative_integer(roof_spec.get("maxCount", 3), "roofProps.maxCount") if roof_spec else 0
    prop_count = rng.randint(1, prop_max) if prop_max else 0
    prop_mat = materials["roof"]
    radius = _positive(roof_spec.get("radius", 0.55), "roofProps.radius") if prop_count else 0.55
    if prop_count and (width <= 0.84 or depth <= 0.84):
        raise ValueError("roof props need mass.width and mass.depth greater than 0.84")
    choices = roof_spec.get("choices", ["vent_stack"])
    if prop_count and (not choices or any(choice not in {"vent_stack", "water_tank_small", "ac_unit_small"} for choice in choices)):
        raise ValueError("roofProps.choices contains an unsupported or empty roof prop list")
    for i, (x, y, z) in enumerate(_poisson_roof_props(rng, width, depth, prop_count, radius, body_h + 0.18)):
        kind = rng.choice(choices)
        if kind == "water_tank_small":
            dims = [0.48, 0.48, 0.42]
        elif kind == "ac_unit_small":
            dims = [0.62, 0.42, 0.30]
        else:
            dims = [0.24, 0.24, 0.48]
        parts.append(_box(f"RoofProp_{i}_{kind}", [x, y, z + dims[2] / 2], dims, prop_mat, 0.025))

    out_materials = {key: material_defs[key] for key in required_materials}
    return {
        "contract": "TYCOON_ASSET_SOURCE_V1",
        "assetId": grammar["assetId"],
        "assetType": "static_building",
        "studioPreset": "CH_TYCOON_STUDIO_V1",
        "floors": floors,
        "footprint": {
            "widthTiles": w_tiles,
            "depthTiles": d_tiles,
            "occupiedCells": [[x, y] for y in range(d_tiles) for x in range(w_tiles)],
        },
        "materials": out_materials,
        "parts": parts,
        "generation": {
            "sourceContract": grammar["contract"],
            "seed": seed,
            "floorCount": floors,
            "wallMaterial": wall_key,
            "partCount": len(parts),
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grammar", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    grammar = json.loads(Path(args.grammar).read_text(encoding="utf-8"))
    asset = expand(grammar)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(asset, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(asset["generation"], sort_keys=True))


if __name__ == "__main__":
    main()
