"""
Transaction & Undo/Redo Engine for Map Forge (CH_TRANSACTION_V1).
Manages reversible mutation commands and atomic batch transactions over MapModel.
"""

from typing import Dict, Any, List, Optional
from tools.map_forge.core.map_model import MapModel


class MapTransactionManager:
    def __init__(self, map_model: MapModel, max_depth: int = 100):
        self.map_model = map_model
        self.max_depth = max_depth
        self.undo_stack: List[Dict[str, Any]] = []
        self.redo_stack: List[Dict[str, Any]] = []
        self.active_batch: Optional[Dict[str, Any]] = None

    def record_mutation(self, action_type: str, description: str, inverse_changes: List[Dict[str, Any]], forward_changes: List[Dict[str, Any]]):
        if not inverse_changes or not forward_changes:
            return

        cmd = {
            "action_type": action_type,
            "description": description,
            "inverse_changes": inverse_changes,
            "forward_changes": forward_changes
        }

        if self.active_batch is not None:
            self.active_batch["inverse_changes"] = inverse_changes + self.active_batch["inverse_changes"]
            self.active_batch["forward_changes"] = self.active_batch["forward_changes"] + forward_changes
            return

        self.undo_stack.append(cmd)
        self.redo_stack.clear()

        if len(self.undo_stack) > self.max_depth:
            self.undo_stack.pop(0)

    def begin_transaction(self, description: str = "Batch Operation"):
        if self.active_batch is not None:
            self.commit_transaction()

        self.active_batch = {
            "action_type": "batch_transaction",
            "description": description,
            "inverse_changes": [],
            "forward_changes": []
        }

    def commit_transaction(self):
        if self.active_batch is None:
            return

        batch = self.active_batch
        self.active_batch = None

        if batch["forward_changes"]:
            self.undo_stack.append(batch)
            self.redo_stack.clear()

            if len(self.undo_stack) > self.max_depth:
                self.undo_stack.pop(0)

    def cancel_transaction(self):
        if self.active_batch is None:
            return
        
        # Rollback transient batch changes applied so far
        for change in self.active_batch["inverse_changes"]:
            self._apply_change(change)
        
        self.active_batch = None

    def can_undo(self) -> bool:
        return len(self.undo_stack) > 0 and self.active_batch is None

    def can_redo(self) -> bool:
        return len(self.redo_stack) > 0 and self.active_batch is None

    def undo(self) -> Optional[Dict[str, Any]]:
        if not self.can_undo():
            return None

        cmd = self.undo_stack.pop()
        for change in cmd["inverse_changes"]:
            self._apply_change(change)

        self.redo_stack.append(cmd)
        return cmd

    def redo(self) -> Optional[Dict[str, Any]]:
        if not self.can_redo():
            return None

        cmd = self.redo_stack.pop()
        for change in cmd["forward_changes"]:
            self._apply_change(change)

        self.undo_stack.append(cmd)
        return cmd

    def clear_history(self):
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.active_batch = None

    def _apply_change(self, change: Dict[str, Any]):
        type_ = change.get("type")
        if type_ == "terrain":
            self.map_model.set_terrain(change["x"], change["y"], change["texture"],
                                       change.get("terrain_definition"), change.get("apply_semantics", False))
        elif type_ == "add_building":
            self.map_model.add_building(
                change["definition_id"],
                change["x"],
                change["y"],
                change.get("rotation", 0),
                instance_id=change.get("instance_id")
            )
        elif type_ == "remove_building":
            self.map_model.remove_building_at(change["x"], change["y"])
        elif type_ == "set_road":
            self.map_model.set_road(change["x"], change["y"], change["present"])
