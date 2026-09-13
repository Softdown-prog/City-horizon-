"""
PySide6 Main Window for City Horizon Map Forge (Phase 1 Read-Only Engine).
"""

import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QStatusBar, QDockWidget, QMessageBox, QFileDialog, QPushButton
)
from PySide6.QtCore import Qt

from tools.map_forge.importers.map_importer import load_scenario, load_building_catalog
from tools.map_forge.exporters.game_exporter import verify_round_trip
from tools.map_forge.core.validator import validate_map
from tools.map_forge.ui.map_view import MapViewCanvas


class MapForgeMainWindow(QMainWindow):
    def __init__(self, asset_root: str, scenario_path: str):
        super().__init__()
        self.asset_root = asset_root
        self.scenario_path = scenario_path
        self.building_catalog = load_building_catalog(asset_root)

        self.setWindowTitle("City Horizon Map Forge — Phase 1 Core [READ-ONLY MODE]")
        self.resize(1360, 820)

        # Central canvas widget
        self.canvas = MapViewCanvas(asset_root, self.building_catalog, self)
        self.setCentralWidget(self.canvas)

        # Status Bar
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)

        self.lbl_mode = QLabel(" MODE: READ-ONLY | CH_GRID_V1 LOCKED (128x64) ", self)
        self.lbl_mode.setStyleSheet("background-color: #1a2530; color: #40e0d0; font-weight: bold; padding: 4px;")
        self.status_bar.addWidget(self.lbl_mode)

        self.lbl_tile = QLabel(" TILE: (-,-) ", self)
        self.status_bar.addWidget(self.lbl_tile)

        self.lbl_zoom = QLabel(" ZOOM: 100% ", self)
        self.status_bar.addPermanentWidget(self.lbl_zoom)

        self.canvas.hovered_tile_changed.connect(self._on_tile_hovered)

        # Side Dock Inspector
        self._create_inspector_dock()

        # Load initial scenario
        self._load_current_scenario()

    def _create_inspector_dock(self):
        dock = QDockWidget("Map Inspector & Governance", self)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        panel = QWidget()
        layout = QVBoxLayout(panel)

        layout.addWidget(QLabel("<b>CANONICAL DATA SOURCE:</b>"))
        lbl_path = QLabel(f"build/assets/scenarios/initial_city.json")
        lbl_path.setWordWrap(True)
        lbl_path.setStyleSheet("color: #60a0e0;")
        layout.addWidget(lbl_path)

        layout.addSpacing(15)
        btn_roundtrip = QPushButton("Run Lossless Round-Trip Verification")
        btn_roundtrip.clicked.connect(self._run_roundtrip_test)
        layout.addWidget(btn_roundtrip)

        btn_validate = QPushButton("Run Map Validation Engine")
        btn_validate.clicked.connect(self._run_map_validation)
        layout.addWidget(btn_validate)

        layout.addSpacing(15)
        self.txt_info = QLabel("Loading map info...")
        self.txt_info.setWordWrap(True)
        layout.addWidget(self.txt_info)

        layout.addStretch()
        dock.setWidget(panel)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)

    def _load_current_scenario(self):
        if os.path.exists(self.scenario_path):
            try:
                self.map_model = load_scenario(self.scenario_path)
                self.canvas.set_map_model(self.map_model)

                info_text = (
                    f"<b>Scenario Version:</b> {self.map_model.save_version}<br>"
                    f"<b>Terrain Tiles:</b> {len(self.map_model.terrain_tiles)}<br>"
                    f"<b>Buildings:</b> {len(self.map_model.buildings)}<br>"
                    f"<b>Roads:</b> {len(self.map_model.roads)}<br>"
                    f"<b>Population:</b> {self.map_model.current_population}<br>"
                    f"<b>City Funds:</b> ${self.map_model.city_funds:,}"
                )
                self.txt_info.setText(info_text)
                self.status_bar.showMessage("Scenario loaded successfully in READ-ONLY mode.", 4000)
            except Exception as e:
                QMessageBox.critical(self, "Load Error", f"Could not load scenario: {e}")

    def _on_tile_hovered(self, x: int, y: int):
        self.lbl_tile.setText(f" TILE: ({x}, {y}) ")
        if self.canvas and self.canvas.camera:
            zoom_pct = int(self.canvas.camera.zoom * 100)
            self.lbl_zoom.setText(f" ZOOM: {zoom_pct}% ")

    def _run_roundtrip_test(self):
        if not self.map_model:
            return
        success, message = verify_round_trip(self.map_model)
        if success:
            QMessageBox.information(self, "Round-Trip Verification PASS", message)
        else:
            QMessageBox.warning(self, "Round-Trip Verification FAIL", message)

    def _run_map_validation(self):
        if not self.map_model:
            return
        result = validate_map(self.map_model, self.asset_root, self.building_catalog)
        msg = f"Map Valid: {result['valid']}\n"
        msg += f"Errors: {len(result['errors'])}\n"
        msg += f"Warnings: {len(result['warnings'])}\n"
        if result['errors']:
            msg += "\nErrors:\n" + "\n".join(result['errors'][:5])
        QMessageBox.information(self, "Map Validation Results", msg)
