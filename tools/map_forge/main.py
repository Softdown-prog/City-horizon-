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

    asset_root = r"C:\Users\User\Documents\Codex\2026-09-05\ve\build"
    scenario_path = r"C:\Users\User\Documents\Codex\2026-09-05\ve\build\assets\scenarios\initial_city.json"

    app = QApplication(sys.argv)
    app.setApplicationName("City Horizon Map Forge")

    window = MapForgeMainWindow(asset_root, scenario_path)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
