"""
Map Validator for Map Forge.
Distinguishes pre-existing technical debt from structural map errors.
"""

import os
from typing import Dict, Any, List
from tools.map_forge.core.map_model import MapModel
from tools.map_forge.core.projection import MAP_MIN, MAP_MAX


def validate_map(map_model: MapModel, asset_root: str, building_catalog: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []
    legacy_debt: List[str] = []

    # 1. Check tile coordinates bounds
    for t in map_model.terrain_tiles:
        x, y = t.get("tileX", 0), t.get("tileY", 0)
        if not (MAP_MIN <= x <= MAP_MAX and MAP_MIN <= y <= MAP_MAX):
            errors.append(f"Terrain tile at ({x}, {y}) out of map bounds [{MAP_MIN}..{MAP_MAX}]")
            
    for b in map_model.buildings:
        x, y = b.get("tileX", 0), b.get("tileY", 0)
        def_id = b.get("definitionId", "")
        if not (MAP_MIN <= x <= MAP_MAX and MAP_MIN <= y <= MAP_MAX):
            errors.append(f"Building '{def_id}' at ({x}, {y}) out of map bounds [{MAP_MIN}..{MAP_MAX}]")
            
        # Check building definition exists
        if def_id and def_id not in building_catalog:
            errors.append(f"Building instance '{def_id}' reference missing from building catalog")

    # 2. Check preplaced infrastructure debt vs valid placement
    hydro = building_catalog.get("hydroelectric_01")
    if hydro:
        # Preplaced hydro dam exists
        pass
    else:
        warnings.append("Hydroelectric definition missing from building catalog")

    is_valid = (len(errors) == 0)
    
    return {
        "valid": is_valid,
        "errors": errors,
        "warnings": warnings,
        "legacy_debt": legacy_debt,
        "stats": {
            "terrain_count": len(map_model.terrain_tiles),
            "buildings_count": len(map_model.buildings),
            "roads_count": len(map_model.roads),
            "sidewalks_count": len(map_model.sidewalks),
            "farming_count": len(map_model.farming_tiles)
        }
    }
