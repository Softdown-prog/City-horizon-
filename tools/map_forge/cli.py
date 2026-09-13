"""
Read-Only Command Line Interface for AI Agents (mapforge-cli).
Provides structured JSON responses for agent inspection and validation.
"""

import sys
import json
import argparse
from typing import Dict, Any

from tools.map_forge.importers.map_importer import load_scenario, load_building_catalog
from tools.map_forge.exporters.game_exporter import verify_round_trip
from tools.map_forge.core.command_executor import ReadOnlyCommandExecutor


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
    else:
        result = {"success": False, "error": f"Unknown action '{args.action}' or action not permitted in Phase 1 Read-Only mode."}

    print(json.dumps(result, indent=2, ensure_ascii=False))


def action_requires_map(action: str) -> bool:
    return action in ["validate", "inspect-tile", "inspect-building", "list-assets", "get-bounds"]


def main_cli():
    parser = argparse.ArgumentParser(description="City Horizon Map Forge — Read-Only Agent CLI")
    parser.add_argument("action", choices=["validate", "inspect-tile", "inspect-building", "list-assets", "get-bounds", "roundtrip"], help="Action to execute")
    parser.add_argument("--x", type=int, default=0, help="Tile X coordinate")
    parser.add_argument("--y", type=int, default=0, help="Tile Y coordinate")
    parser.add_argument("--id", type=str, default="", help="Building ID or Instance ID")
    parser.add_argument("--asset-root", type=str, default=r"C:\Users\User\Documents\Codex\2026-09-05\ve\build", help="Asset root path")
    parser.add_argument("--scenario", type=str, default=r"C:\Users\User\Documents\Codex\2026-09-05\ve\build\assets\scenarios\initial_city.json", help="Scenario JSON path")

    args = parser.parse_args()
    run_cli(args, args.asset_root, args.scenario)


if __name__ == "__main__":
    main_cli()
