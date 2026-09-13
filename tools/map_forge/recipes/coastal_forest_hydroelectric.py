"""Build the first expanded City Horizon showcase scenario.

The recipe is intentionally narrow: it only uses already-approved coast tiles,
existing vegetation definitions and the canonical hydroelectric definition.
It never mutates its source document; callers must provide an output path.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

from tools.map_forge.core.projection import MAP_MAX, MAP_MIN


COAST_ROWS = (
    "assets/terrain/coast_adjusted/coast_grass_sand_transition.png",
    "assets/terrain/coast_adjusted/coast_sand_center_01.png",
    "assets/terrain/coast_adjusted/coast_sand_wet_01.png",
    "assets/terrain/coast_adjusted/coast_shallow_transition.png",
)
OCEAN_ROWS = (
    "assets/terrain/coast_adjusted/ocean_shallow_01.png",
    "assets/terrain/coast_adjusted/ocean_shallow_02.png",
    "assets/terrain/coast_adjusted/ocean_deep_04.png",
    "assets/terrain/coast_adjusted/ocean_deep_05.png",
    "assets/terrain/coast_adjusted/ocean_deep_06.png",
)

# A sparse, irregular stand leaves negative space around the civic district;
# these are anchors, not a blanket of trees over buildable land.
FOREST_PLAN = (
    ("tree_pine_large", -23, -22),
    ("tree_oak_large", -20, -20),
    ("tree_pine_medium", -17, -22),
    ("tree_oak_medium", -14, -20),
    ("tree_pine_large", -22, -17),
    ("tree_pine_small", -19, -16),
    ("tree_oak_large", -16, -17),
    ("tree_pine_medium", -13, -16),
    ("tree_pine_small", -11, -19),
)
HYDROELECTRIC = ("hydroelectric_01", -18, 12)


def _footprint(definition: Dict[str, Any]) -> Tuple[int, int]:
    footprint = definition.get("footprint", {})
    return int(footprint.get("width", 1)), int(footprint.get("height", 1))


def _occupied_tiles(definition: Dict[str, Any], x: int, y: int) -> Iterable[Tuple[int, int]]:
    width, height = _footprint(definition)
    for tile_y in range(y, y + height):
        for tile_x in range(x, x + width):
            yield tile_x, tile_y


def _add_building(raw: Dict[str, Any], catalog: Dict[str, Dict[str, Any]], definition_id: str, x: int, y: int,
                  occupied: set[Tuple[int, int]]) -> bool:
    if definition_id not in catalog:
        raise ValueError(f"Recipe requires missing definition '{definition_id}'")
    definition = catalog[definition_id]
    footprint = tuple(_occupied_tiles(definition, x, y))
    if any(tile_x < MAP_MIN or tile_x > MAP_MAX or tile_y < MAP_MIN or tile_y > MAP_MAX for tile_x, tile_y in footprint):
        raise ValueError(f"'{definition_id}' at ({x}, {y}) exceeds map bounds")
    if any(tile in occupied for tile in footprint):
        return False
    next_id = int(raw.get("nextBuildingInstanceId", 1))
    raw.setdefault("buildings", []).append({
        "instanceId": next_id,
        "definitionId": definition_id,
        "tileX": x,
        "tileY": y,
        "rotation": 0,
    })
    raw["nextBuildingInstanceId"] = next_id + 1
    occupied.update(footprint)
    return True


def build_coastal_forest_hydroelectric(source: Dict[str, Any], catalog: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Return an expanded, independent scenario based on *source*.

    Coast tiles are inserted only when absent, so the function is idempotent
    with respect to the current authored beach.  Buildings are footprint-tested
    before being placed; duplicate recipe runs never stack scenery.
    """
    raw = copy.deepcopy(source)
    terrain_by_tile = {(int(item["tileX"]), int(item["tileY"])): item
                       for item in raw.get("terrain", []) if "tileX" in item and "tileY" in item}
    for index, texture in enumerate(COAST_ROWS + OCEAN_ROWS):
        tile_y = 15 + index
        for tile_x in range(MAP_MIN, MAP_MAX + 1):
            terrain_by_tile.setdefault((tile_x, tile_y), {"tileX": tile_x, "tileY": tile_y, "texture": texture})
    raw["terrain"] = [terrain_by_tile[key] for key in sorted(terrain_by_tile, key=lambda tile: (tile[1], tile[0]))]

    occupied: set[Tuple[int, int]] = set()
    existing_ids = set()
    for building in raw.get("buildings", []):
        definition_id = building.get("definitionId", "")
        definition = catalog.get(definition_id)
        if definition is None:
            continue
        existing_ids.add(definition_id)
        occupied.update(_occupied_tiles(definition, int(building.get("tileX", 0)), int(building.get("tileY", 0))))

    hydro_id, hydro_x, hydro_y = HYDROELECTRIC
    if hydro_id not in existing_ids:
        if not _add_building(raw, catalog, hydro_id, hydro_x, hydro_y, occupied):
            raise ValueError("Hydroelectric placement collides with the source scenario")

    for definition_id, tile_x, tile_y in FOREST_PLAN:
        # A repeated tree type is fine; a duplicate position is not.  Skip a
        # conflicting point rather than ever overwriting player/city content.
        _add_building(raw, catalog, definition_id, tile_x, tile_y, occupied)
    return raw
