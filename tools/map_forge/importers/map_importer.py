"""
Map and Asset Catalog Importer for Map Forge.
Loads initial_city.json and catalog definitions directly from canonical build/assets/.
"""

import json
import os
import glob
from typing import Dict, Any, List
from tools.map_forge.core.map_model import MapModel


def load_scenario(scenario_path: str) -> MapModel:
    """Loads scenario JSON into MapModel."""
    if not os.path.exists(scenario_path):
        raise FileNotFoundError(f"Scenario JSON file not found: {scenario_path}")
        
    with open(scenario_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
        
    return MapModel(raw_data)


def load_building_catalog(asset_root: str) -> Dict[str, Dict[str, Any]]:
    """Loads all building definitions from build/assets/definitions/*.json."""
    candidate_dirs = [
        os.path.join(asset_root, "assets", "definitions"),
        os.path.join(asset_root, "definitions"),
        os.path.join(r"C:\Users\User\Documents\Codex\2026-09-05\ve", "assets", "definitions"),
    ]
    defs_dir = next((d for d in candidate_dirs if os.path.exists(d)), candidate_dirs[0])
    catalog = {}
    
    if not os.path.exists(defs_dir):
        return catalog
        
    for json_file in glob.glob(os.path.join(defs_dir, "*.json")):
        if os.path.basename(json_file) == "road_visual_catalog.json":
            continue
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                building_id = data.get("id")
                if building_id:
                    catalog[building_id] = data
        except Exception as e:
            print(f"Warning: Could not load definition {json_file}: {e}")
            
    return catalog


def load_coast_catalog(asset_root: str) -> Dict[str, Any]:
    """Loads coast tiles catalog from build/assets/terrain/coast/coast_tiles.json."""
    coast_json = os.path.join(asset_root, "assets", "terrain", "coast", "coast_tiles.json")
    if not os.path.exists(coast_json):
        return {}
        
    with open(coast_json, "r", encoding="utf-8") as f:
        return json.load(f)
