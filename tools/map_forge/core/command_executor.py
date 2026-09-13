"""
Read-Only Command Executor for AI Agents (Phase 1 Core).
Executes query commands over the scenario model without modifying map data.
"""

from typing import Dict, Any
from tools.map_forge.core.map_model import MapModel
from tools.map_forge.core.validator import validate_map
from tools.map_forge.core.projection import MAP_MIN, MAP_MAX


class ReadOnlyCommandExecutor:
    def __init__(self, map_model: MapModel, asset_root: str, building_catalog: Dict[str, Dict[str, Any]]):
        self.map_model = map_model
        self.asset_root = asset_root
        self.building_catalog = building_catalog

    def execute(self, command: Dict[str, Any]) -> Dict[str, Any]:
        action = command.get("action") or command.get("command")
        
        if action == "validate":
            return validate_map(self.map_model, self.asset_root, self.building_catalog)
            
        elif action in ["inspect_tile", "inspect-tile"]:
            x = command.get("x", 0)
            y = command.get("y", 0)
            terrain = self.map_model.get_terrain_at(x, y)
            building = self.map_model.get_building_at(x, y)
            is_road = self.map_model.is_road_at(x, y)
            
            return {
                "tileX": x,
                "tileY": y,
                "terrain": terrain,
                "building": building,
                "isRoad": is_road
            }
            
        elif action in ["inspect_building", "inspect-building", "get_building"]:
            b_id = command.get("id") or command.get("instanceId")
            for b in self.map_model.buildings:
                if b.get("instanceId") == b_id or b.get("definitionId") == b_id:
                    return {"building": b}
            return {"building": None, "error": "Building instance not found"}
            
        elif action in ["get_bounds"]:
            return {"min": MAP_MIN, "max": MAP_MAX, "width": MAP_MAX - MAP_MIN + 1, "height": MAP_MAX - MAP_MIN + 1}
            
        elif action in ["list_assets", "list-assets"]:
            return {
                "building_definitions_count": len(self.building_catalog),
                "building_ids": sorted(list(self.building_catalog.keys()))
            }
            
        else:
            return {
                "success": False,
                "error": f"Action '{action}' is not supported in Phase 1 Read-Only Mode. Editing actions are deferred to Phase 2."
            }
