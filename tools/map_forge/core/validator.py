"""
Map Validator for Map Forge.
Delegates bounds and map validation to C++ city_horizon_native.
Distinguishes pre-existing technical debt from structural map errors.
"""

import json
from typing import Dict, Any, List
from tools.map_forge.core.map_model import MapModel
from tools.map_forge.core.native_bridge import get_native_core


def validate_map(map_model: MapModel, asset_root: str, building_catalog: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    ch = get_native_core()
    
    # Run C++ core validation on raw scenario JSON
    raw_json_str = json.dumps(map_model.raw_data) if isinstance(map_model.raw_data, dict) else "{}"
    doc = ch.MapDocument(raw_json_str)
    report = ch.validate_map_document(doc)

    errors: List[str] = list(report.errors)
    warnings: List[str] = list(report.warnings)
    legacy_debt: List[str] = list(report.legacy_debt)

    # Catalog reference check
    for b in map_model.buildings:
        def_id = b.get("definitionId", "")
        if def_id and def_id not in building_catalog:
            errors.append(f"Building instance '{def_id}' reference missing from building catalog")

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
