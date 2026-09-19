"""
MapForge Recipe: Recreate Beach with Water V2 Semantics (CH_SHORELINE_V1).

Converts legacy static coast PNG rows into dynamic Water V2 semantics:
  LAND:  grass, sand_dry, sand_wet
  WATER: coast_water_shallow, coast_water_deep

Fail-closed: Unmapped legacy coast textures raise ValueError.
Preserves all non-coast scenario data (buildings, roads, parcels, vegetation).
Does NOT mutate initial_city.json; outputs assets/scenarios/recreated_beach_water_v2.json.
"""

from __future__ import annotations

import copy
import json
import os
from typing import Any, Dict, List, Tuple

# Fail-closed legacy PNG mapping table
LEGACY_COAST_MAP: Dict[str, Tuple[str, str]] = {
    "assets/terrain/coast_adjusted/coast_grass_sand_transition.png": ("LAND", "assets/terrain/coast_adjusted/coast_sand_center_01.png"),
    "assets/terrain/coast_adjusted/coast_sand_center_01.png": ("LAND", "assets/terrain/coast_adjusted/coast_sand_center_01.png"),
    "assets/terrain/coast_adjusted/coast_sand_wet_01.png": ("LAND", "assets/terrain/coast_adjusted/coast_sand_wet_01.png"),
    "assets/terrain/coast_adjusted/coast_shallow_transition.png": ("WATER", "assets/terrain/coast_adjusted/coast_water_shallow.png"),
    "assets/terrain/coast_adjusted/coast_water_shallow.png": ("WATER", "assets/terrain/coast_adjusted/coast_water_shallow.png"),
    "assets/terrain/coast_adjusted/coast_water_deep.png": ("WATER", "assets/terrain/coast_adjusted/coast_water_deep.png"),
    "assets/terrain/coast_adjusted/ocean_shallow_01.png": ("WATER", "assets/terrain/coast_adjusted/coast_water_shallow.png"),
    "assets/terrain/coast_adjusted/ocean_shallow_02.png": ("WATER", "assets/terrain/coast_adjusted/coast_water_shallow.png"),
    "assets/terrain/coast_adjusted/ocean_shallow_04.png": ("WATER", "assets/terrain/coast_adjusted/coast_water_shallow.png"),
    "assets/terrain/coast_adjusted/ocean_shallow_05.png": ("WATER", "assets/terrain/coast_adjusted/coast_water_shallow.png"),
    "assets/terrain/coast_adjusted/ocean_shallow_06.png": ("WATER", "assets/terrain/coast_adjusted/coast_water_shallow.png"),
    "assets/terrain/coast_adjusted/ocean_deep_01.png": ("WATER", "assets/terrain/coast_adjusted/coast_water_deep.png"),
    "assets/terrain/coast_adjusted/ocean_deep_02.png": ("WATER", "assets/terrain/coast_adjusted/coast_water_deep.png"),
    "assets/terrain/coast_adjusted/ocean_deep_03.png": ("WATER", "assets/terrain/coast_adjusted/coast_water_deep.png"),
    "assets/terrain/coast_adjusted/ocean_deep_04.png": ("WATER", "assets/terrain/coast_adjusted/coast_water_deep.png"),
    "assets/terrain/coast_adjusted/ocean_deep_05.png": ("WATER", "assets/terrain/coast_adjusted/coast_water_deep.png"),
    "assets/terrain/coast_adjusted/ocean_deep_06.png": ("WATER", "assets/terrain/coast_adjusted/coast_water_deep.png"),
}


# Explicit compatibility policies for objects on/near the coast
OBJECT_COMPATIBILITY_POLICIES: Dict[str, str] = {
    "beach_lighthouse": "requires_land",
    "beach_lifeguard_tower": "requires_land",
    "beach_umbrella_blue": "requires_land",
    "beach_umbrella_red": "requires_land",
    "beach_surfboards": "requires_land",
    "beach_volleyball": "requires_land",
    "beach_sandcastle": "requires_land",
    "gazebo_01": "requires_land",
    "plaza_01": "requires_land",
    "small_barn_01": "requires_land",
    "small_silo_01": "requires_land",
    "beach_yacht_large": "requires_water",
    "beach_pier_large": "shoreline_mixed",
    "beach_rocks": "water_or_shoreline",
}


def recreate_beach_water_v2(source_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transforms source_data (initial_city) into a Water V2 beach scenario.
    Enforces infrastructure protection and item compatibility policies while preserving
    topological variations (straight, bay/cove, peninsula, diagonal step).
    """
    raw = copy.deepcopy(source_data)
    terrain_by_tile = {(int(item["tileX"]), int(item["tileY"])): item
                       for item in raw.get("terrain", []) if "tileX" in item and "tileY" in item}

    # 1. Convert legacy coast tiles fail-closed
    for (x, y), tile in list(terrain_by_tile.items()):
        texture = tile.get("texture", "")
        if "coast" in texture or "ocean" in texture:
            if texture not in LEGACY_COAST_MAP:
                raise ValueError(f"Fail-closed conversion error: Unmapped legacy coast texture '{texture}' at ({x}, {y})")
            cat, new_texture = LEGACY_COAST_MAP[texture]
            tile["texture"] = new_texture
            if "water_shallow" in new_texture or "ocean_shallow" in new_texture:
                tile["terrainDefinition"] = "ocean_shallow"
            elif "water_deep" in new_texture or "ocean_deep" in new_texture:
                tile["terrainDefinition"] = "ocean_deep"
            elif "sand_wet" in new_texture:
                tile["terrainDefinition"] = "sand_wet"
            elif "sand" in new_texture:
                tile["terrainDefinition"] = "sand_center"

    # 2. Build Infrastructure & Object Protection Mask
    land_protected_tiles: Set[Tuple[int, int]] = set()

    for r in raw.get("roads", []):
        land_protected_tiles.add((int(r["tileX"]), int(r["tileY"])))
    for s in raw.get("sidewalks", []):
        land_protected_tiles.add((int(s["tileX"]), int(s["tileY"])))
    for f in raw.get("farmingTiles", []):
        land_protected_tiles.add((int(f["tileX"]), int(f["tileY"])))

    for b in raw.get("buildings", []):
        def_id = b.get("definitionId", "")
        policy = OBJECT_COMPATIBILITY_POLICIES.get(def_id, "requires_land")
        if policy == "requires_land":
            bx = int(b["tileX"])
            by = int(b["tileY"])
            bw = int(b.get("footprintWidth", 1))
            bh = int(b.get("footprintDepth", 1))
            for dx in range(bw):
                for dy in range(bh):
                    land_protected_tiles.add((bx + dx, by + dy))

    # 3. Solve Topological Coastline with Infrastructure Protection
    # Desired topologic profile:
    #   Region A: Straight Coast (x: -24 to -12) -> target_coast_y = 20
    #   Region B: Cove / Bay (x: -11 to -3) -> target_coast_y = 17 (water cuts inward towards land)
    #   Region C: Peninsula (x: -2 to 6) -> target_coast_y = 21 (land extends into water)
    #   Region D: Diagonal Step (x: 7 to 23) -> target_coast_y = 19 + (x - 7)//4
    for x in range(-24, 24):
        if -11 <= x <= -3:
            target_coast_y = 17
        elif -2 <= x <= 6:
            target_coast_y = 21
        elif 7 <= x <= 23:
            target_coast_y = min(22, 19 + ((x - 7) // 4))
        else:
            target_coast_y = 20

        # Protect land infrastructure: find highest y occupied by land_protected_tiles at column x
        max_land_y = max([y for (px, y) in land_protected_tiles if px == x], default=-999)

        # Coast water cannot start above max_land_y + 2 (providing 1 sand_center + 1 sand_wet buffer)
        effective_coast_y = max(target_coast_y, max_land_y + 2)

        # Lay out sand_center (effective_coast_y - 2), sand_wet (effective_coast_y - 1), ocean_shallow (effective_coast_y..effective_coast_y+1), ocean_deep (effective_coast_y+2..23)
        if 10 <= effective_coast_y - 2 <= 23:
            terrain_by_tile[(x, effective_coast_y - 2)] = {
                "tileX": x, "tileY": effective_coast_y - 2,
                "texture": "assets/terrain/coast_adjusted/coast_sand_center_01.png",
                "terrainDefinition": "sand_center"
            }
        if 10 <= effective_coast_y - 1 <= 23:
            terrain_by_tile[(x, effective_coast_y - 1)] = {
                "tileX": x, "tileY": effective_coast_y - 1,
                "texture": "assets/terrain/coast_adjusted/coast_sand_wet_01.png",
                "terrainDefinition": "sand_wet"
            }

        for y_w in range(effective_coast_y, min(effective_coast_y + 2, 24)):
            if 10 <= y_w <= 23:
                terrain_by_tile[(x, y_w)] = {
                    "tileX": x, "tileY": y_w,
                    "texture": "assets/terrain/coast_adjusted/coast_water_shallow.png",
                    "terrainDefinition": "ocean_shallow"
                }

        for y_d in range(effective_coast_y + 2, 24):
            if 10 <= y_d <= 23:
                terrain_by_tile[(x, y_d)] = {
                    "tileX": x, "tileY": y_d,
                    "texture": "assets/terrain/coast_adjusted/coast_water_deep.png",
                    "terrainDefinition": "ocean_deep"
                }

    raw["terrain"] = [terrain_by_tile[k] for k in sorted(terrain_by_tile, key=lambda t: (t[1], t[0]))]
    return raw


def generate_recreated_beach_scenario(repo_root: str) -> str:
    """Reads initial_city.json and writes assets/scenarios/recreated_beach_water_v2.json."""
    src_path = os.path.join(repo_root, "assets", "scenarios", "initial_city.json")
    out_path = os.path.join(repo_root, "assets", "scenarios", "recreated_beach_water_v2.json")

    with open(src_path, "r", encoding="utf-8") as f:
        src_data = json.load(f)

    recreated = recreate_beach_water_v2(src_data)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(recreated, f, indent=2)

    return out_path
