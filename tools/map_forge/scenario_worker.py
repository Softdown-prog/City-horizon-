"""One-command, deterministic scenario worker for people and automation.

The worker only invokes reviewed recipes, validates through the native core, and
writes a scenario package to the configured runtime asset tree.  It never
mutates its source and refuses overwrite unless explicitly requested.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable, Dict, Any

from tools.map_forge.exporters.game_exporter import export_game_scenario, export_scenario_manifest
from tools.map_forge.importers.map_importer import load_building_catalog, load_scenario
from tools.map_forge.core.map_model import MapModel
from tools.map_forge.core.validator import validate_map
from tools.map_forge.recipes.coastal_forest_hydroelectric import build_coastal_forest_hydroelectric
from tools.map_forge.recipes.recreate_beach_water_v2 import recreate_beach_water_v2


def _coastal(source: Dict[str, Any], catalog: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    return build_coastal_forest_hydroelectric(source, catalog)


def _water_v2(source: Dict[str, Any], _catalog: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    return recreate_beach_water_v2(source)


RECIPES: dict[str, Callable[[Dict[str, Any], Dict[str, Dict[str, Any]]], Dict[str, Any]]] = {
    "coastal_forest_hydroelectric": _coastal,
    "beach_water_v2": _water_v2,
}


def run_worker(asset_root: Path, source_path: Path, recipe_id: str, scenario_id: str,
               activate: bool = False, overwrite: bool = False) -> dict[str, Any]:
    if recipe_id not in RECIPES:
        raise ValueError(f"Unknown deterministic recipe '{recipe_id}'. Available: {', '.join(sorted(RECIPES))}")
    if not scenario_id or Path(scenario_id).name != scenario_id or not scenario_id.endswith(".json"):
        raise ValueError("scenario_id must be a plain filename ending in .json")
    if not source_path.is_file():
        raise FileNotFoundError(f"Source scenario not found: {source_path}")

    target = asset_root / "assets" / "scenarios" / scenario_id
    if target.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing scenario: {target}")

    source = load_scenario(str(source_path))
    catalog = load_building_catalog(str(asset_root))
    generated = MapModel(RECIPES[recipe_id](source.raw_data, catalog))
    validation = validate_map(generated, str(asset_root), catalog)
    if not validation["valid"]:
        raise RuntimeError("Recipe output rejected by native validation: " + "; ".join(validation["errors"][:5]))

    export = export_game_scenario(generated, str(target), str(asset_root), catalog)
    manifest_path = target.with_suffix(".manifest.json")
    export_scenario_manifest(generated, str(manifest_path), str(asset_root), catalog)
    active_marker = None
    if activate:
        active_marker = asset_root / "assets" / "scenarios" / "active_scenario.txt"
        active_marker.write_text(scenario_id + "\n", encoding="utf-8")
    return {
        "success": True,
        "contract": "CH_MAP_FORGE_WORKER_V1",
        "recipe": recipe_id,
        "source": str(source_path),
        "scenario": str(target),
        "manifest": str(manifest_path),
        "active_marker": str(active_marker) if active_marker else None,
        "validation": validation,
        "export": export,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="City Horizon deterministic scenario worker")
    parser.add_argument("--asset-root", type=Path, required=True, help="Runtime root, e.g. build/Debug")
    parser.add_argument("--source", type=Path, default=None, help="Source scenario; defaults to initial_city.json")
    parser.add_argument("--recipe", choices=sorted(RECIPES), required=True)
    parser.add_argument("--scenario-id", required=True, help="Output filename under assets/scenarios")
    parser.add_argument("--activate", action="store_true", help="Select the generated scenario for city_builder startup")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    root = args.asset_root.resolve()
    source = args.source.resolve() if args.source else root / "assets" / "scenarios" / "initial_city.json"
    print(json.dumps(run_worker(root, source, args.recipe, args.scenario_id, args.activate, args.overwrite), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
