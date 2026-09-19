"""
Lossless Game Exporter, Manifest Generator, and Round-Trip Verifier for Map Forge.
Saves initial_city.json and custom scenarios without losing any raw fields,
exports game scenario packages, and renders high-res preview images.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Tuple, Dict, Any
from tools.map_forge.core.map_model import MapModel
from tools.map_forge.core.validator import validate_map


def save_scenario(map_model: MapModel, target_path: str) -> None:
    """Saves raw scenario data losslessly to target JSON file."""
    os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(map_model.raw_data, f, indent=2, ensure_ascii=False)


def export_game_scenario(map_model: MapModel, target_path: str, asset_root: str = "", building_catalog: Dict[str, Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Exports scenario JSON for game executable consumption.
    Performs validation audit, saves to target path, and mirrors to build/Debug/assets/scenarios/ if applicable.
    """
    # 1. Perform validation audit
    validation = {}
    if asset_root and building_catalog:
        validation = validate_map(map_model, asset_root, building_catalog)

    # 2. Save target scenario file
    save_scenario(map_model, target_path)

    # 3. Mirror into the selected runtime root, never a machine-specific path.
    # This lets the human UI, a CI worker, and the game consume one package.
    mirrored_paths = []
    runtime_dir = Path(asset_root) / "assets" / "scenarios" if asset_root else None
    if runtime_dir and runtime_dir.is_dir():
        target_resolved = Path(target_path).resolve()
        runtime_target = (runtime_dir / os.path.basename(target_path)).resolve()
        if target_resolved != runtime_target:
            mirror_file = str(runtime_target)
            save_scenario(map_model, mirror_file)
            mirrored_paths.append(mirror_file)

    return {
        "success": True,
        "target_path": target_path,
        "mirrored_paths": mirrored_paths,
        "validation": validation,
        "buildings_count": len(map_model.buildings),
        "terrain_tiles_count": len(map_model.terrain_tiles),
        "roads_count": len(map_model.roads)
    }


def export_scenario_manifest(map_model: MapModel, target_path: str, asset_root: str = "", building_catalog: Dict[str, Dict[str, Any]] = None) -> str:
    """Exports a scenario manifest JSON describing scenario metadata, asset breakdown, and validation summary."""
    validation = {}
    if asset_root and building_catalog:
        validation = validate_map(map_model, asset_root, building_catalog)

    manifest_data = {
        "manifestVersion": "1.0.0",
        "scenarioVersion": map_model.save_version,
        "cityFunds": map_model.city_funds,
        "currentPopulation": map_model.current_population,
        "counts": {
            "terrainTiles": len(map_model.terrain_tiles),
            "buildings": len(map_model.buildings),
            "roads": len(map_model.roads),
            "sidewalks": len(map_model.sidewalks)
        },
        "buildingDefinitionsUsed": sorted(list(set(b.get("definitionId") for b in map_model.buildings if b.get("definitionId")))),
        "validationSummary": {
            "valid": validation.get("valid", True),
            "errorsCount": len(validation.get("errors", [])),
            "warningsCount": len(validation.get("warnings", []))
        }
    }

    os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False)

    return target_path


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
