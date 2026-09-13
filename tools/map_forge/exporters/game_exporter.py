"""
Lossless Game Exporter and Round-Trip Verifier for Map Forge.
Saves initial_city.json without losing any raw fields, and provides temp-file round-trip verification.
"""

import json
import os
import tempfile
from typing import Tuple
from tools.map_forge.core.map_model import MapModel


def save_scenario(map_model: MapModel, target_path: str) -> None:
    """Saves raw scenario data losslessly to target JSON file."""
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(map_model.raw_data, f, indent=2, ensure_ascii=False)


def verify_round_trip(map_model: MapModel) -> Tuple[bool, str]:
    """
    Saves MapModel raw data to a temporary file, loads it back, and compares raw JSON data equivalence.
    Deletes temporary file immediately afterwards.
    """
    temp_file = tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".json")
    temp_path = temp_file.name
    temp_file.close()
    
    try:
        save_scenario(map_model, temp_path)
        
        with open(temp_path, "r", encoding="utf-8") as f:
            reloaded_data = json.load(f)
            
        is_equal = (map_model.raw_data == reloaded_data)
        if is_equal:
            return True, "Round-trip successful: zero loss of fields or structural differences."
        else:
            return False, "Round-trip mismatch: reloaded raw data differs from original raw data."
    except Exception as e:
        return False, f"Round-trip failed with exception: {e}"
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
