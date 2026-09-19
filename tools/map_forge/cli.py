"""
Controlled Command Line Interface for AI Agents (mapforge-cli).
Inspection is read-only. Generation is restricted to named recipes that write
to an explicit new output path after validation.
"""

import sys
import json
import argparse
import os
from typing import Dict, Any

from tools.map_forge.importers.map_importer import load_scenario, load_building_catalog
from tools.map_forge.exporters.game_exporter import verify_round_trip, save_scenario
from tools.map_forge.core.command_executor import ReadOnlyCommandExecutor
from tools.map_forge.recipes.coastal_forest_hydroelectric import build_coastal_forest_hydroelectric


def _default_runtime_root() -> str:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    debug_root = os.path.join(repo_root, "build", "Debug")
    return debug_root if os.path.isdir(os.path.join(debug_root, "assets")) else os.path.join(repo_root, "build")


def _default_scenario(root: str) -> str:
    scenarios = os.path.join(root, "assets", "scenarios")
    marker = os.path.join(scenarios, "active_scenario.txt")
    if os.path.isfile(marker):
        with open(marker, "r", encoding="utf-8") as f:
            selected = os.path.basename(f.readline().strip())
        candidate = os.path.join(scenarios, selected)
        if selected.endswith(".json") and os.path.isfile(candidate):
            return candidate
    return os.path.join(scenarios, "initial_city.json")


def run_cli(args: argparse.Namespace, asset_root: str, scenario_path: str):
    executor = None
    if action_requires_map(args.action):
        map_model = load_scenario(scenario_path)
        building_catalog = load_building_catalog(asset_root)
        executor = ReadOnlyCommandExecutor(map_model, asset_root, building_catalog)

    result: Dict[str, Any] = {}

    if args.action == "validate":
        result = executor.execute({"action": "validate"})
    elif args.action == "inspect-tile":
        result = executor.execute({"action": "inspect_tile", "x": args.x, "y": args.y})
    elif args.action == "inspect-building":
        result = executor.execute({"action": "inspect_building", "id": args.id})
    elif args.action == "list-assets":
        result = executor.execute({"action": "list_assets"})
    elif args.action == "get-bounds":
        result = executor.execute({"action": "get_bounds"})
    elif args.action == "roundtrip":
        map_model = load_scenario(scenario_path)
        success, message = verify_round_trip(map_model)
        result = {"success": success, "message": message}
    elif args.action == "generate-coastal-district":
        if not args.output:
            result = {"success": False, "error": "--output is required; source scenarios are never overwritten."}
        else:
            map_model = load_scenario(scenario_path)
            catalog = load_building_catalog(asset_root)
            generated = build_coastal_forest_hydroelectric(map_model.raw_data, catalog)
            generated_model = type(map_model)(generated)
            validation = ReadOnlyCommandExecutor(generated_model, asset_root, catalog).execute({"action": "validate"})
            if not validation["valid"]:
                result = {"success": False, "error": "Generated scenario failed validation", "validation": validation}
            else:
                output = args.output
                save_scenario(generated_model, output)
                result = {"success": True, "output": output, "validation": validation,
                          "message": "Generated coastal beach, forest and hydroelectric scenario."}
    else:
        result = {"success": False, "error": f"Unknown action '{args.action}' or action not permitted in Phase 1 Read-Only mode."}

    print(json.dumps(result, indent=2, ensure_ascii=False))


def action_requires_map(action: str) -> bool:
    return action in ["validate", "inspect-tile", "inspect-building", "list-assets", "get-bounds"]


def main_cli():
    parser = argparse.ArgumentParser(description="City Horizon Map Forge — Read-Only Agent CLI")
    parser.add_argument("action", choices=["validate", "inspect-tile", "inspect-building", "list-assets", "get-bounds", "roundtrip", "generate-coastal-district"], help="Action to execute")
    parser.add_argument("--x", type=int, default=0, help="Tile X coordinate")
    parser.add_argument("--y", type=int, default=0, help="Tile Y coordinate")
    parser.add_argument("--id", type=str, default="", help="Building ID or Instance ID")
    default_root = _default_runtime_root()
    parser.add_argument("--asset-root", type=str, default=default_root, help="Runtime asset root path")
    parser.add_argument("--scenario", type=str, default=None, help="Scenario JSON path; defaults to active runtime scenario")
    parser.add_argument("--output", type=str, default="", help="required output path for generation actions")

    args = parser.parse_args()
    scenario_path = args.scenario or _default_scenario(args.asset_root)
    run_cli(args, args.asset_root, scenario_path)


if __name__ == "__main__":
    main_cli()
