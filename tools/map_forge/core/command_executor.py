"""
Command Executor for Map Forge (Supporting Read-Only, Active Manual Editing, and Transaction Engine CH_TRANSACTION_V1).
Executes query, mutation, and transaction undo/redo commands over the scenario model.
"""

from typing import Dict, Any, Optional
from tools.map_forge.core.map_model import MapModel
from tools.map_forge.core.validator import validate_map
from tools.map_forge.core.projection import MAP_MIN, MAP_MAX
from tools.map_forge.core.transaction_manager import MapTransactionManager
from tools.map_forge.exporters.game_exporter import save_scenario


class CommandExecutor:
    def __init__(self, map_model: MapModel, asset_root: str, building_catalog: Dict[str, Dict[str, Any]], read_only: bool = False):
        self.map_model = map_model
        self.asset_root = asset_root
        self.building_catalog = building_catalog
        self.read_only = read_only
        self.transaction_manager = MapTransactionManager(map_model)

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

        elif action in ["undo"]:
            cmd = self.transaction_manager.undo()
            if cmd:
                return {"success": True, "action": "undo", "description": cmd["description"]}
            return {"success": False, "error": "Nothing to undo"}

        elif action in ["redo"]:
            cmd = self.transaction_manager.redo()
            if cmd:
                return {"success": True, "action": "redo", "description": cmd["description"]}
            return {"success": False, "error": "Nothing to redo"}

        elif action in ["can_undo"]:
            return {"can_undo": self.transaction_manager.can_undo(), "undo_stack_size": len(self.transaction_manager.undo_stack)}

        elif action in ["can_redo"]:
            return {"can_redo": self.transaction_manager.can_redo(), "redo_stack_size": len(self.transaction_manager.redo_stack)}

        elif action in ["begin_transaction"]:
            desc = command.get("description", "Batch Operation")
            self.transaction_manager.begin_transaction(desc)
            return {"success": True, "action": "begin_transaction", "description": desc}

        elif action in ["commit_transaction"]:
            self.transaction_manager.commit_transaction()
            return {"success": True, "action": "commit_transaction"}

        elif action in ["cancel_transaction"]:
            self.transaction_manager.cancel_transaction()
            return {"success": True, "action": "cancel_transaction"}

        # Mutation Actions
        if self.read_only:
            return {
                "success": False,
                "error": f"Action '{action}' is not supported in Phase 1 Read-Only Mode."
            }

        if action in ["paint_terrain", "set_terrain"]:
            x = command.get("x", 0)
            y = command.get("y", 0)
            texture = command.get("texture", "assets/terrain/grass_isometric_01.png")

            prev_entry = self.map_model.get_terrain_at(x, y)
            prev_texture = prev_entry.get("texture", "assets/terrain/grass_isometric_01.png") if prev_entry else "assets/terrain/grass_isometric_01.png"

            if prev_texture == texture:
                return {"success": True, "action": "paint_terrain", "x": x, "y": y, "texture": texture, "no_op": True}

            inv = [{"type": "terrain", "x": x, "y": y, "texture": prev_texture}]
            fwd = [{"type": "terrain", "x": x, "y": y, "texture": texture}]

            self.map_model.set_terrain(x, y, texture)
            self.transaction_manager.record_mutation("paint_terrain", f"Paint terrain at ({x},{y})", inv, fwd)
            return {"success": True, "action": "paint_terrain", "x": x, "y": y, "texture": texture}

        elif action in ["place_building", "place_object", "add_building"]:
            def_id = command.get("definitionId") or command.get("definition_id") or command.get("id")
            x = command.get("x", 0)
            y = command.get("y", 0)
            rotation = command.get("rotation", 0)
            if not def_id or def_id not in self.building_catalog:
                return {"success": False, "error": f"Invalid or unknown asset definition: '{def_id}'"}

            instance_id = self.map_model.add_building(def_id, x, y, rotation)

            inv = [{"type": "remove_building", "x": x, "y": y}]
            fwd = [{"type": "add_building", "definition_id": def_id, "x": x, "y": y, "rotation": rotation, "instance_id": instance_id}]

            self.transaction_manager.record_mutation("place_building", f"Place {def_id} at ({x},{y})", inv, fwd)
            return {"success": True, "action": "place_building", "instanceId": instance_id, "definitionId": def_id, "x": x, "y": y, "rotation": rotation}

        elif action in ["remove_building", "demolish_building", "delete_building"]:
            x = command.get("x", 0)
            y = command.get("y", 0)
            removed = self.map_model.remove_building_at(x, y)
            if removed:
                inv = [{
                    "type": "add_building",
                    "definition_id": removed.get("definitionId"),
                    "x": removed.get("tileX"),
                    "y": removed.get("tileY"),
                    "rotation": removed.get("rotation", 0),
                    "instance_id": removed.get("instanceId")
                }]
                fwd = [{"type": "remove_building", "x": x, "y": y}]

                self.transaction_manager.record_mutation("remove_building", f"Demolish building at ({x},{y})", inv, fwd)
                return {"success": True, "action": "remove_building", "removed": removed}
            return {"success": False, "error": f"No building instance found at ({x}, {y})"}

        elif action in ["set_road", "place_road", "remove_road"]:
            x = command.get("x", 0)
            y = command.get("y", 0)
            present = command.get("present", True) if action != "remove_road" else False
            was_road = self.map_model.is_road_at(x, y)

            if was_road == present:
                return {"success": True, "action": "set_road", "x": x, "y": y, "present": present, "no_op": True}

            inv = [{"type": "set_road", "x": x, "y": y, "present": was_road}]
            fwd = [{"type": "set_road", "x": x, "y": y, "present": present}]

            self.map_model.set_road(x, y, present)
            self.transaction_manager.record_mutation("set_road", f"{'Build' if present else 'Remove'} road at ({x},{y})", inv, fwd)
            return {"success": True, "action": "set_road", "x": x, "y": y, "present": present}

        elif action in ["save_map", "export_map"]:
            target_path = command.get("target_path") or command.get("path")
            if not target_path:
                return {"success": False, "error": "Target save path not specified."}
            save_scenario(self.map_model, target_path)
            return {"success": True, "action": "save_map", "path": target_path}

        else:
            return {"success": False, "error": f"Unknown action: '{action}'"}


class ReadOnlyCommandExecutor(CommandExecutor):
    def __init__(self, map_model: MapModel, asset_root: str, building_catalog: Dict[str, Dict[str, Any]]):
        super().__init__(map_model, asset_root, building_catalog, read_only=True)
