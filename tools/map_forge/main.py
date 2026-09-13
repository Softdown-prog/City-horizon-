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
    build_debug_scenario = os.path.join(repo_root, "build", "Debug", "assets", "scenarios", "initial_city.json")
    build_scenario = os.path.join(repo_root, "build", "assets", "scenarios", "initial_city.json")

    if requested_scenario:
        if not os.path.isfile(requested_scenario):
            raise RuntimeError(f"MAP FORGE CANONICAL ASSET ERROR: Scenario not found at '{requested_scenario}'.")
        debug_prefix = os.path.abspath(os.path.join(repo_root, "build", "Debug", "assets")) + os.sep
        build_prefix = os.path.abspath(os.path.join(repo_root, "build", "assets")) + os.sep
        if requested_scenario.startswith(debug_prefix):
            scenario_path = requested_scenario
            asset_root = os.path.abspath(os.path.join(repo_root, "build", "Debug"))
        elif requested_scenario.startswith(build_prefix):
            scenario_path = requested_scenario
            asset_root = os.path.abspath(os.path.join(repo_root, "build"))
        else:
            raise RuntimeError("MAP FORGE CANONICAL ASSET ERROR: --scenario must live under build/*/assets/.")
    elif os.path.exists(build_debug_scenario):
        scenario_path = os.path.abspath(build_debug_scenario)
        asset_root = os.path.abspath(os.path.join(repo_root, "build", "Debug"))
    elif os.path.exists(build_scenario):
        scenario_path = os.path.abspath(build_scenario)
        asset_root = os.path.abspath(os.path.join(repo_root, "build"))
    else:
        raise RuntimeError(
            f"MAP FORGE CANONICAL ASSET ERROR: Canonical scenario not found at '{build_debug_scenario}' or '{build_scenario}'. "
            "Please build the project first so assets are synced to build directory."
        )

    print(f"[MAP FORGE CANONICAL SOURCE] Asset Root: {asset_root}")
    print(f"[MAP FORGE CANONICAL SOURCE] Scenario Path: {scenario_path}")

    app = QApplication(sys.argv)
    app.setApplicationName("City Horizon Map Forge")

    window = MapForgeMainWindow(asset_root, scenario_path)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
