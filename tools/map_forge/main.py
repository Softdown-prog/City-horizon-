"""
Main entry point for City Horizon Map Forge.
Launches PySide6 GUI editor or dispatches to CLI mode.
"""

import sys
import os

# Add ve root directory to sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from PySide6.QtWidgets import QApplication
from tools.map_forge.ui.main_window import MapForgeMainWindow
from tools.map_forge.cli import main_cli


def _active_runtime_scenario(asset_root: str) -> str:
    scenarios = os.path.join(asset_root, "assets", "scenarios")
    marker = os.path.join(scenarios, "active_scenario.txt")
    if os.path.isfile(marker):
        with open(marker, "r", encoding="utf-8") as f:
            selected = os.path.basename(f.readline().strip())
        candidate = os.path.join(scenarios, selected)
        if selected.endswith(".json") and os.path.isfile(candidate):
            return candidate
    return os.path.join(scenarios, "initial_city.json")


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ["validate", "inspect-tile", "inspect-building", "list-assets", "get-bounds", "roundtrip", "--cli"]:
        if sys.argv[1] == "--cli":
            sys.argv.pop(1)
        main_cli()
        return

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    requested_scenario = ""
    if len(sys.argv) == 3 and sys.argv[1] == "--scenario":
        requested_scenario = os.path.abspath(sys.argv[2])
    elif "--scenario" in sys.argv:
        raise RuntimeError("MAP FORGE USAGE: --scenario <canonical scenario json>")
    build_debug_root = os.path.join(repo_root, "build", "Debug")
    build_root = os.path.join(repo_root, "build")
    build_debug_scenario = _active_runtime_scenario(build_debug_root)
    build_scenario = _active_runtime_scenario(build_root)

    repo_scenario = _active_runtime_scenario(repo_root)

    if requested_scenario:
        if not os.path.isfile(requested_scenario):
            raise RuntimeError(f"MAP FORGE CANONICAL ASSET ERROR: Scenario not found at '{requested_scenario}'.")
        debug_prefix = os.path.abspath(os.path.join(repo_root, "build", "Debug", "assets")) + os.sep
        build_prefix = os.path.abspath(os.path.join(repo_root, "build", "assets")) + os.sep
        repo_prefix = os.path.abspath(os.path.join(repo_root, "assets")) + os.sep
        if requested_scenario.startswith(debug_prefix):
            scenario_path = requested_scenario
            asset_root = os.path.abspath(os.path.join(repo_root, "build", "Debug"))
            selection_source = "CLI Argument (--scenario in build/Debug)"
        elif requested_scenario.startswith(build_prefix):
            scenario_path = requested_scenario
            asset_root = os.path.abspath(os.path.join(repo_root, "build"))
            selection_source = "CLI Argument (--scenario in build)"
        elif requested_scenario.startswith(repo_prefix):
            scenario_path = requested_scenario
            asset_root = repo_root
            selection_source = "CLI Argument (--scenario in repo_root)"
        else:
            raise RuntimeError("MAP FORGE CANONICAL ASSET ERROR: --scenario must live under assets/.")
    elif os.path.exists(build_debug_scenario):
        scenario_path = os.path.abspath(build_debug_scenario)
        asset_root = build_debug_root
        selection_source = "Active Build Debug (build/Debug)"
    elif os.path.exists(build_scenario):
        scenario_path = os.path.abspath(build_scenario)
        asset_root = build_root
        selection_source = "Active Build (build)"
    elif os.path.exists(repo_scenario):
        scenario_path = os.path.abspath(repo_scenario)
        asset_root = repo_root
        selection_source = "Repository Root Fallback (repo_root)"
    else:
        raise RuntimeError(
            f"MAP FORGE CANONICAL ASSET ERROR: Canonical scenario not found at '{build_debug_scenario}', '{build_scenario}', or '{repo_scenario}'."
        )

    print(f"[MAP FORGE ASSET RESOLUTION] Selection Source: {selection_source}")
    print(f"[MAP FORGE ASSET RESOLUTION] Selected Asset Root: {asset_root}")
    print(f"[MAP FORGE ASSET RESOLUTION] Selected Scenario Path: {scenario_path}")

    app = QApplication(sys.argv)
    app.setApplicationName("City Horizon Map Forge")

    window = MapForgeMainWindow(asset_root, scenario_path)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
