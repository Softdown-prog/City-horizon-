"""
Authoritative MapModel holding intact raw scenario JSON dictionary.
Exposes read-only views over scenario layers while preserving 100% of raw JSON keys.
"""

from typing import Dict, Any, List, Optional
import copy


class MapModel:
    def __init__(self, raw_data: Dict[str, Any]):
        # Keep raw JSON dictionary completely intact
        self._raw_data: Dict[str, Any] = copy.deepcopy(raw_data)
        
    @property
    def raw_data(self) -> Dict[str, Any]:
        """Returns intact raw dictionary."""
        return self._raw_data

    @property
    def save_version(self) -> int:
        return self._raw_data.get("saveVersion", 7)

    @property
    def city_funds(self) -> int:
        return self._raw_data.get("cityFunds", 0)

    @property
    def current_population(self) -> int:
        return self._raw_data.get("currentPopulation", 0)

    @property
    def owned_parcel_ids(self) -> List[int]:
        return self._raw_data.get("ownedParcelIds", [])

    @property
    def terrain_tiles(self) -> List[Dict[str, Any]]:
        """Read-only view of terrain list."""
        return self._raw_data.get("terrain", [])

    @property
    def buildings(self) -> List[Dict[str, Any]]:
        """Read-only view of buildings list."""
        return self._raw_data.get("buildings", [])

    @property
    def roads(self) -> List[Dict[str, Any]]:
        """Read-only view of roads list."""
        return self._raw_data.get("roads", [])

    @property
    def sidewalks(self) -> List[Dict[str, Any]]:
        """Read-only view of sidewalks list."""
        return self._raw_data.get("sidewalks", [])

    @property
    def farming_tiles(self) -> List[Dict[str, Any]]:
        """Read-only view of farming tiles list."""
        return self._raw_data.get("farmingTiles", [])

    @property
    def agricultural_inventory(self) -> List[Dict[str, Any]]:
        return self._raw_data.get("agriculturalInventory", [])

    @property
    def service_vehicles(self) -> List[Dict[str, Any]]:
        return self._raw_data.get("serviceVehicles", [])

    def get_terrain_at(self, tile_x: int, tile_y: int) -> Optional[Dict[str, Any]]:
        """Finds custom terrain entry at (tile_x, tile_y)."""
        for t in self.terrain_tiles:
            if t.get("tileX") == tile_x and t.get("tileY") == tile_y:
                return t
        return None

    def get_building_at(self, tile_x: int, tile_y: int) -> Optional[Dict[str, Any]]:
        """Finds building starting at (tile_x, tile_y)."""
        for b in self.buildings:
            if b.get("tileX") == tile_x and b.get("tileY") == tile_y:
                return b
    def is_road_at(self, tile_x: int, tile_y: int) -> bool:
        for r in self.roads:
            if r.get("tileX") == tile_x and r.get("tileY") == tile_y:
                return True
        return False

    @property
    def raw_json(self) -> str:
        """Returns JSON string of raw data."""
        import json
        return json.dumps(self._raw_data, indent=2, ensure_ascii=False)

    def set_terrain(self, tile_x: int, tile_y: int, texture_path: str) -> None:
        """Sets or updates custom terrain entry at (tile_x, tile_y)."""
        terrain_list = self._raw_data.setdefault("terrain", [])
        for entry in terrain_list:
            if entry.get("tileX") == tile_x and entry.get("tileY") == tile_y:
                entry["texture"] = texture_path
                return
        terrain_list.append({"tileX": tile_x, "tileY": tile_y, "texture": texture_path})

    def add_building(self, definition_id: str, tile_x: int, tile_y: int, rotation: int = 0, instance_id: Optional[int] = None) -> int:
        """Allocates next instance ID or uses provided instance_id and adds building instance."""
        buildings_list = self._raw_data.setdefault("buildings", [])
        if instance_id is None:
            instance_id = self._raw_data.get("nextBuildingInstanceId", 1)
            self._raw_data["nextBuildingInstanceId"] = instance_id + 1

        building_entry = {
            "instanceId": instance_id,
            "definitionId": definition_id,
            "tileX": tile_x,
            "tileY": tile_y,
            "rotation": rotation
        }
        buildings_list.append(building_entry)
        return instance_id

    def remove_building_at(self, tile_x: int, tile_y: int) -> Optional[Dict[str, Any]]:
        """Removes building at (tile_x, tile_y). Returns removed building dict or None."""
        buildings_list = self._raw_data.get("buildings", [])
        for i, b in enumerate(buildings_list):
            if b.get("tileX") == tile_x and b.get("tileY") == tile_y:
                return buildings_list.pop(i)
        return None

    def set_road(self, tile_x: int, tile_y: int, present: bool = True) -> None:
        """Adds or removes road tile at (tile_x, tile_y)."""
        roads_list = self._raw_data.setdefault("roads", [])
        for i, r in enumerate(roads_list):
            if r.get("tileX") == tile_x and r.get("tileY") == tile_y:
                if not present:
                    roads_list.pop(i)
                return
        if present:
            roads_list.append({"tileX": tile_x, "tileY": tile_y})
