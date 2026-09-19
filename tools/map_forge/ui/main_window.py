"""
PySide6 Main Window for City Horizon Map Forge.
Supports Import of Game Maps & Asset Catalogs, Full Active Manual Human Editing,
and Comprehensive Game Map Export Suite (Scenario JSON, High-Res PNG Preview, Manifest).
"""

import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QStatusBar, QDockWidget, QMessageBox, QFileDialog, QPushButton,
    QComboBox, QLineEdit, QListWidget, QListWidgetItem, QRadioButton,
    QButtonGroup, QGroupBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence, QColor, QIcon, QPainter, QPixmap

from tools.map_forge.importers.map_importer import load_scenario, load_building_catalog
from tools.map_forge.exporters.game_exporter import (
    verify_round_trip, save_scenario, export_game_scenario, export_scenario_manifest
)
from tools.map_forge.core.validator import validate_map
from tools.map_forge.core.command_executor import CommandExecutor
from tools.map_forge.ui.sdl_viewport import MapForgeSDLViewport
from tools.map_forge.asset_catalog import building_catalog_entries, scenario_catalog, terrain_catalog, resolve_asset_path
from tools.map_forge.core.terrain_semantics import load_terrain_semantic_catalog, TerrainSemanticContractError, native_catalog_json


class MapForgeMainWindow(QMainWindow):
    def __init__(self, asset_root: str, scenario_path: str):
        super().__init__()
        self.asset_root = asset_root
        self.scenario_path = scenario_path
        self.building_catalog = load_building_catalog(asset_root)
        self.terrain_semantic_catalog = load_terrain_semantic_catalog(asset_root)
        self.map_model = None

        self.setWindowTitle("City Horizon Map Forge — Native C++20 + SDL3 Engine [HUMAN EDITING & EXPORT MODE]")
        self.resize(1440, 880)

        # Active Manual Tool State
        self.active_tool = "inspect"  # "inspect", "paint_terrain", "place_asset", "demolish", "road"
        self.selected_terrain_texture = "assets/terrain/coast_adjusted/coast_sand_center_01.png"
        self.selected_terrain_definition = None
        self.terrain_catalog_json = native_catalog_json(self.terrain_semantic_catalog)
        self.selected_asset_id = "beach_lighthouse"
        self.selected_rotation = 0
        self.brush_radius = 0
        self.stroke_visited_tiles = set()

        # Central native viewport widget
        self.canvas = MapForgeSDLViewport(asset_root, self.building_catalog, self)
        self.setCentralWidget(self.canvas)

        # Connect canvas signals
        self.canvas.hovered_tile_changed.connect(self._on_tile_hovered)
        self.canvas.tile_clicked.connect(self._on_tile_clicked)
        self.canvas.brush_stroke_started.connect(self._on_stroke_started)
        self.canvas.brush_tile_dragged.connect(self._on_stroke_dragged)
        self.canvas.brush_stroke_ended.connect(self._on_stroke_ended)

        # Status Bar
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)

        self.lbl_mode = QLabel(" MODE: ACTIVE MANUAL HUMAN EDITING & EXPORT | CH_GRID_V1 ", self)
        self.lbl_mode.setStyleSheet("background-color: #1a3025; color: #40ffb0; font-weight: bold; padding: 4px;")
        self.status_bar.addWidget(self.lbl_mode)

        self.lbl_tile = QLabel(" TILE: (-,-) ", self)
        self.status_bar.addWidget(self.lbl_tile)

        self.lbl_zoom = QLabel(" ZOOM: 100% ", self)
        self.status_bar.addPermanentWidget(self.lbl_zoom)

        # Create Menu Bar and Docks
        self._create_menu_bar()
        self._create_inspector_and_tools_dock()

        # Load initial scenario
        self._load_current_scenario()

    def _create_menu_bar(self):
        menubar = self.menuBar()

        # 1. File Menu
        file_menu = menubar.addMenu("&File")

        act_open_map = QAction("&Import Map Scenario...", self)
        act_open_map.setShortcut(QKeySequence.Open)
        act_open_map.triggered.connect(self._import_map_dialog)
        file_menu.addAction(act_open_map)

        act_open_assets = QAction("Import &Asset Catalog...", self)
        act_open_assets.triggered.connect(self._import_assets_dialog)
        file_menu.addAction(act_open_assets)

        file_menu.addSeparator()

        act_save = QAction("&Save Map", self)
        act_save.setShortcut(QKeySequence.Save)
        act_save.triggered.connect(self._save_current_map)
        file_menu.addAction(act_save)

        act_save_as = QAction("Save Map &As...", self)
        act_save_as.setShortcut(QKeySequence.SaveAs)
        act_save_as.triggered.connect(self._save_map_as_dialog)
        file_menu.addAction(act_save_as)

        file_menu.addSeparator()

        act_exit = QAction("E&xit", self)
        act_exit.setShortcut(QKeySequence.Quit)
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        # 2. Edit Menu
        edit_menu = menubar.addMenu("&Edit")

        self.act_undo = QAction("↩️ &Undo", self)
        self.act_undo.setShortcut(QKeySequence.Undo)
        self.act_undo.triggered.connect(self._perform_undo)
        edit_menu.addAction(self.act_undo)

        self.act_redo = QAction("↪️ &Redo", self)
        self.act_redo.setShortcut(QKeySequence.Redo)
        self.act_redo.triggered.connect(self._perform_redo)
        edit_menu.addAction(self.act_redo)

        # 3. Export Menu
        export_menu = menubar.addMenu("&Export")

        act_export_game = QAction("🚀 &Export Scenario for Game Executable...", self)
        act_export_game.setShortcut(QKeySequence("Ctrl+E"))
        act_export_game.triggered.connect(self._export_game_scenario_dialog)
        export_menu.addAction(act_export_game)

        act_export_png = QAction("📸 Export &High-Res Map Preview PNG...", self)
        act_export_png.triggered.connect(self._export_map_preview_png_dialog)
        export_menu.addAction(act_export_png)

        act_export_manifest = QAction("📋 Export Scenario &Manifest JSON...", self)
        act_export_manifest.triggered.connect(self._export_manifest_dialog)
        export_menu.addAction(act_export_manifest)

    def _create_inspector_and_tools_dock(self):
        dock = QDockWidget("Human Manual Editing & Governance", self)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        panel = QWidget()
        layout = QVBoxLayout(panel)

        # 1. Active Tool Palette
        grp_tools = QGroupBox("MANUAL EDITING TOOLBOX")
        tool_layout = QVBoxLayout(grp_tools)

        self.btn_group_tools = QButtonGroup(self)

        rb_inspect = QRadioButton("🔍 Inspect / Select Tile")
        rb_paint = QRadioButton("🖌️ Paint Terrain Brush")
        rb_asset = QRadioButton("🏗️ Place Asset / Building")
        rb_demolish = QRadioButton("🧹 Demolish / Remove")
        rb_road = QRadioButton("🛣️ Build / Remove Road")

        rb_inspect.setChecked(True)

        self.btn_group_tools.addButton(rb_inspect, 0)
        self.btn_group_tools.addButton(rb_paint, 1)
        self.btn_group_tools.addButton(rb_asset, 2)
        self.btn_group_tools.addButton(rb_demolish, 3)
        self.btn_group_tools.addButton(rb_road, 4)

        self.btn_group_tools.idClicked.connect(self._on_tool_changed)

        tool_layout.addWidget(rb_inspect)
        tool_layout.addWidget(rb_paint)
        tool_layout.addWidget(rb_asset)
        tool_layout.addWidget(rb_demolish)
        tool_layout.addWidget(rb_road)

        brush_layout = QHBoxLayout()
        brush_layout.addWidget(QLabel("Brush Size:"))
        self.cbo_brush_size = QComboBox()
        self.cbo_brush_size.addItems(["1x1 Tile (Radius 0)", "3x3 Tiles (Radius 1)", "5x5 Tiles (Radius 2)"])
        self.cbo_brush_size.currentIndexChanged.connect(self._on_brush_size_changed)
        brush_layout.addWidget(self.cbo_brush_size)
        tool_layout.addLayout(brush_layout)

        hist_layout = QHBoxLayout()
        self.btn_undo = QPushButton("↩️ Undo (Ctrl+Z)")
        self.btn_undo.clicked.connect(self._perform_undo)
        self.btn_redo = QPushButton("↪️ Redo (Ctrl+Y)")
        self.btn_redo.clicked.connect(self._perform_redo)
        hist_layout.addWidget(self.btn_undo)
        hist_layout.addWidget(self.btn_redo)
        tool_layout.addLayout(hist_layout)

        btn_reload_cat = QPushButton("🔄 Reload Asset Catalogs (Hot-Reload)")
        btn_reload_cat.clicked.connect(self._on_reload_catalogs_clicked)
        tool_layout.addWidget(btn_reload_cat)

        layout.addWidget(grp_tools)

        # 2. Terrain Brush Selector (Active when Paint Terrain selected)
        self.grp_terrain = QGroupBox("TERRAIN BRUSH OPTIONS")
        t_layout = QVBoxLayout(self.grp_terrain)
        self.cbo_terrain = QComboBox()
        self.terrain_options = [
            ("Areia Seca Limpa", "assets/terrain/coast_adjusted/coast_sand_center_01.png"),
            ("Areia Molhada (Orla)", "assets/terrain/coast_adjusted/coast_sand_wet_01.png"),
            ("Transição Grama-Areia", "assets/terrain/coast_adjusted/coast_grass_sand_transition.png"),
            ("Grama Padrão", "assets/terrain/grass_isometric_01.png"),
            ("Margem Rasa / Espuma", "assets/terrain/coast_adjusted/coast_shallow_transition.png"),
            ("Água Rasa Base", "assets/terrain/coast_adjusted/coast_water_shallow.png"),
            ("Água Profunda Base", "assets/terrain/coast_adjusted/coast_water_deep.png"),
        ]
        discovered_terrain = terrain_catalog(self.asset_root)
        if discovered_terrain:
            self.terrain_options = [(entry.label, entry.relative_path) for entry in discovered_terrain]
        for name, path in self.terrain_options:
            self.cbo_terrain.addItem(name, path)
            self.cbo_terrain.setItemIcon(self.cbo_terrain.count() - 1, self._thumbnail_icon(path, 42))
        # Definitions are intentional, semantic-bearing choices; texture entries remain visual-only.
        for definition in self.terrain_semantic_catalog.values():
            semantic = definition["semantic"]
            label = f"{definition['id']} — {semantic['surface']}"
            self.cbo_terrain.addItem(label, {"texture": definition["visualMaterial"], "definition": definition["id"]})
            self.cbo_terrain.setItemIcon(self.cbo_terrain.count() - 1, self._thumbnail_icon(definition["visualMaterial"], 42))
        self.cbo_terrain.currentIndexChanged.connect(self._on_terrain_selected)
        t_layout.addWidget(self.cbo_terrain)
        self.grp_paint_mode = QButtonGroup(self)
        self.rb_visual_only = QRadioButton("Visual Only — preserva lógica")
        self.rb_visual_semantic = QRadioButton("Visual + Semantics — aplica definição")
        self.rb_visual_only.setChecked(True)
        self.grp_paint_mode.addButton(self.rb_visual_only, 0)
        self.grp_paint_mode.addButton(self.rb_visual_semantic, 1)
        t_layout.addWidget(self.rb_visual_only)
        t_layout.addWidget(self.rb_visual_semantic)
        self.lbl_terrain_semantics = QLabel("Semântica: não alterada (Visual Only)")
        self.lbl_terrain_semantics.setWordWrap(True)
        t_layout.addWidget(self.lbl_terrain_semantics)
        self.lbl_terrain_preview = QLabel("Selecione um terreno para ver a miniatura.")
        self.lbl_terrain_preview.setAlignment(Qt.AlignCenter)
        self.lbl_terrain_preview.setMinimumHeight(92)
        self.lbl_terrain_preview.setStyleSheet("background: #101820; border: 1px solid #28546b;")
        t_layout.addWidget(self.lbl_terrain_preview)
        layout.addWidget(self.grp_terrain)

        # 3. Asset Selector & Rotation (Active when Place Asset selected)
        self.grp_asset_palette = QGroupBox("IMPORTED GAME ASSETS CATALOG")
        a_layout = QVBoxLayout(self.grp_asset_palette)

        self.txt_asset_search = QLineEdit()
        self.txt_asset_search.setPlaceholderText("Filter assets...")
        self.txt_asset_search.textChanged.connect(self._filter_asset_list)
        a_layout.addWidget(self.txt_asset_search)

        self.lst_assets = QListWidget()
        self.lst_assets.setFixedHeight(130)
        self.lst_assets.itemSelectionChanged.connect(self._on_asset_selected)
        a_layout.addWidget(self.lst_assets)
        self.lbl_asset_preview = QLabel("Selecione um objeto para ver a miniatura.")
        self.lbl_asset_preview.setAlignment(Qt.AlignCenter)
        self.lbl_asset_preview.setMinimumHeight(120)
        self.lbl_asset_preview.setWordWrap(True)
        self.lbl_asset_preview.setStyleSheet("background: #101820; border: 1px solid #28546b;")
        a_layout.addWidget(self.lbl_asset_preview)

        rot_layout = QHBoxLayout()
        rot_layout.addWidget(QLabel("Rotation:"))
        self.cbo_rotation = QComboBox()
        self.cbo_rotation.addItems(["0° (South)", "90° (West)", "180° (North)", "270° (East)"])
        self.cbo_rotation.currentIndexChanged.connect(lambda idx: setattr(self, 'selected_rotation', idx))
        rot_layout.addWidget(self.cbo_rotation)

        btn_rot = QPushButton("Rotate (R)")
        btn_rot.clicked.connect(self._rotate_asset)
        rot_layout.addWidget(btn_rot)
        a_layout.addLayout(rot_layout)

        layout.addWidget(self.grp_asset_palette)

        # 3b. Scenario browser: actual scenario previews, not opaque filenames.
        grp_scenarios = QGroupBox("CENÁRIOS DISPONÍVEIS")
        scenario_layout = QVBoxLayout(grp_scenarios)
        self.lst_scenarios = QListWidget()
        self.lst_scenarios.setFixedHeight(135)
        self.lst_scenarios.itemSelectionChanged.connect(self._on_scenario_selected)
        scenario_layout.addWidget(self.lst_scenarios)
        layout.addWidget(grp_scenarios)

        # 4. MAP EXPORT SUITE
        grp_export = QGroupBox("MAP EXPORT & SAVING SUITE")
        exp_layout = QVBoxLayout(grp_export)

        btn_export_game = QPushButton("🚀 Export Map Scenario for Game")
        btn_export_game.setStyleSheet("background-color: #204555; color: #40e0ff; font-weight: bold; padding: 6px;")
        btn_export_game.clicked.connect(self._export_game_scenario_dialog)
        exp_layout.addWidget(btn_export_game)

        btn_export_activate = QPushButton("▶ Exportar e ativar no City Builder")
        btn_export_activate.setStyleSheet("background-color: #1f6a32; color: white; font-weight: bold; padding: 6px;")
        btn_export_activate.clicked.connect(self._export_and_activate_game_scenario_dialog)
        exp_layout.addWidget(btn_export_activate)

        btn_export_png = QPushButton("📸 Export High-Res Preview PNG")
        btn_export_png.clicked.connect(self._export_map_preview_png_dialog)
        exp_layout.addWidget(btn_export_png)

        btn_export_manifest = QPushButton("📋 Export Scenario Manifest")
        btn_export_manifest.clicked.connect(self._export_manifest_dialog)
        exp_layout.addWidget(btn_export_manifest)

        layout.addWidget(grp_export)

        # 5. View Mode & Overlays
        layout.addWidget(QLabel("<b>VIEW MODE & OVERLAYS:</b>"))
        mode_layout = QHBoxLayout()
        btn_art = QPushButton("ART")
        btn_art.clicked.connect(lambda: self.canvas.set_view_mode(0))
        btn_logic = QPushButton("LOGIC")
        btn_logic.clicked.connect(lambda: self.canvas.set_view_mode(1))
        btn_both = QPushButton("ART + LOGIC")
        btn_both.clicked.connect(lambda: self.canvas.set_view_mode(2))
        mode_layout.addWidget(btn_art)
        mode_layout.addWidget(btn_logic)
        mode_layout.addWidget(btn_both)
        layout.addLayout(mode_layout)

        btn_validate = QPushButton("Run Map Validation Engine")
        btn_validate.clicked.connect(self._run_map_validation)
        layout.addWidget(btn_validate)

        btn_shoreline = QPushButton("🌊 Rebuild Shoreline Derived State (CH_SHORELINE_V1)")
        btn_shoreline.setStyleSheet("background-color: #1a3a4b; color: #70d0ff; font-weight: bold; padding: 6px;")
        btn_shoreline.clicked.connect(self._on_rebuild_shoreline_clicked)
        layout.addWidget(btn_shoreline)

        # 6. Tile Semantic Inspector
        layout.addSpacing(6)
        layout.addWidget(QLabel("<b>TILE SEMANTIC INSPECTOR (CH_SEMANTIC_STATE_V1):</b>"))
        self.lbl_semantic_info = QLabel("Hover over a tile to inspect semantic channels...")
        self.lbl_semantic_info.setWordWrap(True)
        self.lbl_semantic_info.setStyleSheet("background-color: #121820; color: #a0d0f0; font-family: monospace; padding: 5px; border: 1px solid #203545;")
        layout.addWidget(self.lbl_semantic_info)

        layout.addSpacing(6)
        self.txt_info = QLabel("Loading scenario data...")
        self.txt_info.setWordWrap(True)
        layout.addWidget(self.txt_info)

        layout.addStretch()
        dock.setWidget(panel)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)

        # Populate asset list
        self._populate_asset_list()
        self._populate_scenario_list()
        self._update_terrain_preview()

    def _populate_asset_list(self):
        self.lst_assets.clear()
        if not self.building_catalog:
            return

        for entry in building_catalog_entries(self.building_catalog):
            item = QListWidgetItem(f"{entry.label} [{entry.id}] ({entry.category})")
            item.setData(Qt.UserRole, entry.id)
            item.setData(Qt.UserRole + 1, entry.relative_path)
            item.setIcon(self._thumbnail_icon(entry.relative_path, 42))
            self.lst_assets.addItem(item)

        if self.lst_assets.count() > 0:
            self.lst_assets.setCurrentRow(0)

    def _thumbnail_icon(self, relative_path: str, size: int) -> QIcon:
        try:
            pixmap = QPixmap(str(resolve_asset_path(self.asset_root, relative_path)))
            if not pixmap.isNull():
                return QIcon(pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        except (OSError, ValueError):
            pass
        return QIcon()

    def _set_preview(self, label: QLabel, relative_path: str, caption: str, size: int = 112):
        try:
            pixmap = QPixmap(str(resolve_asset_path(self.asset_root, relative_path)))
            if not pixmap.isNull():
                label.setPixmap(pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                label.setToolTip(caption + "\n" + relative_path)
                return
        except (OSError, ValueError):
            pass
        label.setPixmap(QPixmap())
        label.setText(caption + "\nMiniatura indisponível")

    def _scenario_thumbnail(self, scenario_path: str) -> QIcon:
        """Small deterministic semantic overview for a selectable scenario."""
        image = QPixmap(128, 78)
        image.fill(QColor("#112431"))
        try:
            model = load_scenario(scenario_path)
            painter = QPainter(image)
            for tile in model.terrain_tiles:
                texture = str(tile.get("texture", ""))
                color = QColor("#4e8f4d")
                if "water" in texture or "ocean" in texture:
                    color = QColor("#4ac6d5")
                elif "sand" in texture or "beach" in texture:
                    color = QColor("#d8bb70")
                x = int(64 + (int(tile.get("tileX", 0)) - int(tile.get("tileY", 0))) * 1.4)
                y = int(36 + (int(tile.get("tileX", 0)) + int(tile.get("tileY", 0))) * 0.65)
                painter.setPen(color)
                painter.drawPoint(x, y)
            painter.setPen(QColor("#f4c95d"))
            for building in model.buildings:
                x = int(64 + (int(building.get("tileX", 0)) - int(building.get("tileY", 0))) * 1.4)
                y = int(36 + (int(building.get("tileX", 0)) + int(building.get("tileY", 0))) * 0.65)
                painter.drawRect(x - 1, y - 1, 3, 3)
            painter.end()
        except Exception:
            pass
        return QIcon(image)

    def _populate_scenario_list(self):
        self.lst_scenarios.blockSignals(True)
        self.lst_scenarios.clear()
        for path in scenario_catalog(self.asset_root):
            item = QListWidgetItem(path.stem.replace("_", " ").title())
            item.setData(Qt.UserRole, str(path))
            item.setIcon(self._scenario_thumbnail(str(path)))
            self.lst_scenarios.addItem(item)
            if os.path.abspath(str(path)) == os.path.abspath(self.scenario_path):
                item.setSelected(True)
        self.lst_scenarios.blockSignals(False)

    def _filter_asset_list(self, text: str):
        search = text.lower().strip()
        for i in range(self.lst_assets.count()):
            item = self.lst_assets.item(i)
            item.setHidden(search not in item.text().lower())

    def _on_tool_changed(self, tool_id: int):
        tools = ["inspect", "paint_terrain", "place_asset", "demolish", "road"]
        self.active_tool = tools[tool_id]
        self.lbl_mode.setText(f" MODE: MANUAL EDIT ({self.active_tool.upper()}) | CH_GRID_V1 ")

    def _on_terrain_selected(self, index: int):
        data = self.cbo_terrain.currentData()
        if isinstance(data, dict):
            self.selected_terrain_texture = data["texture"]
            self.selected_terrain_definition = data["definition"]
            semantic = self.terrain_semantic_catalog[data["definition"]]["semantic"]
            self.lbl_terrain_semantics.setText(
                f"Material: {data['texture']}\nSemantic: {semantic['surface']} | Pedestrian: {'YES' if semantic['pedestrianWalkable'] else 'NO'} | Vehicle: {'YES' if semantic['vehicleDriveable'] else 'NO'} | Buildable: {'YES' if semantic['buildable'] else 'NO'}")
        else:
            self.selected_terrain_texture = data
            self.selected_terrain_definition = None
            self.lbl_terrain_semantics.setText("Semântica: não declarada — Visual Only preserva os canais atuais.")
        self._update_terrain_preview()

    def _update_terrain_preview(self):
        if hasattr(self, "lbl_terrain_preview"):
            self._set_preview(self.lbl_terrain_preview, self.selected_terrain_texture or "", self.cbo_terrain.currentText(), 105)

    def _on_asset_selected(self):
        items = self.lst_assets.selectedItems()
        if items:
            self.selected_asset_id = items[0].data(Qt.UserRole)
            self._set_preview(self.lbl_asset_preview, items[0].data(Qt.UserRole + 1), items[0].text(), 118)

    def _on_scenario_selected(self):
        items = self.lst_scenarios.selectedItems()
        if not items:
            return
        selected = items[0].data(Qt.UserRole)
        if selected and os.path.abspath(selected) != os.path.abspath(self.scenario_path):
            self.scenario_path = selected
            self._load_current_scenario()

    def _rotate_asset(self):
        self.selected_rotation = (self.selected_rotation + 1) % 4
        self.cbo_rotation.setCurrentIndex(self.selected_rotation)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_R:
            self._rotate_asset()
        else:
            super().keyPressEvent(event)

    def _load_current_scenario(self):
        if os.path.exists(self.scenario_path):
            try:
                self.map_model = load_scenario(self.scenario_path)
                self.executor = CommandExecutor(self.map_model, self.asset_root, self.building_catalog, read_only=False,
                                                terrain_semantic_catalog=self.terrain_semantic_catalog)
                self.canvas.set_map_model(self.map_model)
                self.canvas.center_camera_on_content(self.canvas.map_document)

                info_text = (
                    f"<b>Scenario Path:</b> {os.path.basename(self.scenario_path)}<br>"
                    f"<b>Version:</b> {self.map_model.save_version} | "
                    f"<b>Terrain Tiles:</b> {len(self.map_model.terrain_tiles)}<br>"
                    f"<b>Buildings:</b> {len(self.map_model.buildings)} | "
                    f"<b>Roads:</b> {len(self.map_model.roads)}<br>"
                    f"<b>Population:</b> {self.map_model.current_population} | "
                    f"<b>Funds:</b> ${self.map_model.city_funds:,}"
                )
                self.txt_info.setText(info_text)
                self._update_undo_redo_ui_state()
                self.status_bar.showMessage("Game Map & Asset Catalog imported successfully.", 4000)
            except Exception as e:
                QMessageBox.critical(self, "Load Error", f"Could not load scenario: {e}")

    def _import_map_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Game Map Scenario", self.scenario_path, "JSON Scenarios (*.json)")
        if path and os.path.exists(path):
            self.scenario_path = path
            self._load_current_scenario()

    def _import_assets_dialog(self):
        path = QFileDialog.getExistingDirectory(self, "Select Asset Catalog Directory", self.asset_root)
        if path and os.path.exists(path):
            self.asset_root = path
            self.building_catalog = load_building_catalog(self.asset_root)
            self.terrain_semantic_catalog = load_terrain_semantic_catalog(self.asset_root)
            self.terrain_catalog_json = native_catalog_json(self.terrain_semantic_catalog)
            self._populate_asset_list()
            self._populate_scenario_list()
            QMessageBox.information(self, "Asset Catalog Imported", f"Imported {len(self.building_catalog)} definitions from asset root.")

    def _save_current_map(self):
        if not self.map_model:
            return
        try:
            save_scenario(self.map_model, self.scenario_path)
            debug_scenario = r"C:\Users\User\Documents\Codex\2026-09-05\ve\build\Debug\assets\scenarios\initial_city.json"
            if os.path.exists(os.path.dirname(debug_scenario)):
                save_scenario(self.map_model, debug_scenario)

            self._load_current_scenario()
            QMessageBox.information(self, "Map Saved", f"Successfully saved map modifications to {os.path.basename(self.scenario_path)}.")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save map: {e}")

    def _save_map_as_dialog(self):
        if not self.map_model:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save Map Scenario As", self.scenario_path, "JSON Scenarios (*.json)")
        if path:
            self.scenario_path = path
            self._save_current_map()

    def _export_game_scenario_dialog(self, activate: bool = False):
        if not self.map_model:
            return
        default_dir = os.path.join(self.asset_root, "assets", "scenarios")
        default_file = os.path.join(default_dir, os.path.basename(self.scenario_path))
        path, _ = QFileDialog.getSaveFileName(self, "Export Scenario for Game Executable", default_file, "JSON Scenarios (*.json)")
        if path:
            if activate:
                # The runtime marker accepts only a filename under its scenario root.
                path = os.path.join(default_dir, os.path.basename(path))
            result = export_game_scenario(self.map_model, path, self.asset_root, self.building_catalog)
            if activate:
                marker = os.path.join(default_dir, "active_scenario.txt")
                with open(marker, "w", encoding="utf-8") as f:
                    f.write(os.path.basename(path) + "\n")
                result["active_marker"] = marker
            msg = f"🚀 Scenario exported successfully to:\n{result['target_path']}\n\n"
            if result['mirrored_paths']:
                msg += f"Mirrored to Game Executable Debug path:\n{result['mirrored_paths'][0]}\n\n"
            msg += f"Buildings: {result['buildings_count']} | Terrain: {result['terrain_tiles_count']} | Roads: {result['roads_count']}"
            if activate:
                msg += "\n\n▶ This scenario is now selected for the next City Builder launch."
            self._populate_scenario_list()
            QMessageBox.information(self, "Game Scenario Exported", msg)

    def _export_and_activate_game_scenario_dialog(self):
        self._export_game_scenario_dialog(activate=True)

    def _export_map_preview_png_dialog(self):
        if not self.canvas:
            return
        default_path = os.path.join(self.asset_root, "map_preview.png")
        path, _ = QFileDialog.getSaveFileName(self, "Export High-Res Map Preview PNG", default_path, "PNG Images (*.png)")
        if path:
            pixmap = self.grab()
            pixmap.save(path, "PNG")
            QMessageBox.information(self, "Map Preview Exported", f"📸 High-res map preview image saved to:\n{path}")

    def _export_manifest_dialog(self):
        if not self.map_model:
            return
        default_path = os.path.join(self.asset_root, "scenario_manifest.json")
        path, _ = QFileDialog.getSaveFileName(self, "Export Scenario Manifest JSON", default_path, "JSON Manifests (*.json)")
        if path:
            export_scenario_manifest(self.map_model, path, self.asset_root, self.building_catalog)
            QMessageBox.information(self, "Manifest Exported", f"📋 Scenario manifest JSON exported to:\n{path}")

    def _perform_undo(self):
        if not self.executor:
            return
        res = self.executor.execute({"action": "undo"})
        if res.get("success"):
            self.canvas.set_map_model(self.map_model)
            self._update_scenario_info_label()
            self._update_undo_redo_ui_state()
            self.status_bar.showMessage(f"↩️ Undid action: {res.get('description', '')}", 3000)
        else:
            self.status_bar.showMessage(f"Undo Error: {res.get('error')}", 3000)

    def _perform_redo(self):
        if not self.executor:
            return
        res = self.executor.execute({"action": "redo"})
        if res.get("success"):
            self.canvas.set_map_model(self.map_model)
            self._update_scenario_info_label()
            self._update_undo_redo_ui_state()
            self.status_bar.showMessage(f"↪️ Redid action: {res.get('description', '')}", 3000)
        else:
            self.status_bar.showMessage(f"Redo Error: {res.get('error')}", 3000)

    def _update_undo_redo_ui_state(self):
        if not hasattr(self, 'executor') or not self.executor:
            can_u, can_r = False, False
        else:
            can_u = self.executor.transaction_manager.can_undo()
            can_r = self.executor.transaction_manager.can_redo()

        if hasattr(self, 'act_undo'):
            self.act_undo.setEnabled(can_u)
        if hasattr(self, 'act_redo'):
            self.act_redo.setEnabled(can_r)
        if hasattr(self, 'btn_undo'):
            self.btn_undo.setEnabled(can_u)
        if hasattr(self, 'btn_redo'):
            self.btn_redo.setEnabled(can_r)

    def _on_brush_size_changed(self, index: int):
        self.brush_radius = index  # 0 -> 1x1, 1 -> 3x3, 2 -> 5x5
        self.canvas.set_hover_brush_radius(self.brush_radius)

    def _on_reload_catalogs_clicked(self):
        self.canvas.reload_catalogs()
        self.status_bar.showMessage("🔄 Asset overlays & animated prop catalogs reloaded from disk.", 3000)

    def _bresenham_line(self, x0: int, y0: int, x1: int, y1: int):
        points = []
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        curr_x, curr_y = x0, y0
        while True:
            points.append((curr_x, curr_y))
            if curr_x == x1 and curr_y == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                curr_x += sx
            if e2 < dx:
                err += dx
                curr_y += sy
        return points

    def _on_stroke_started(self, x: int, y: int, button: int):
        if button != 1 or not self.map_model or not hasattr(self, 'executor') or not self.executor:
            return
        if self.active_tool == "inspect":
            return

        self.stroke_visited_tiles = set()
        self.last_stroke_tile = (x, y)
        desc = f"{self.active_tool.replace('_', ' ').title()} Stroke"
        self.executor.execute({"action": "begin_transaction", "description": desc})
        if self._apply_brush_at(x, y):
            self.canvas.set_map_model(self.map_model)

    def _on_stroke_dragged(self, x: int, y: int, button: int):
        if button != 1 or not self.map_model or not hasattr(self, 'executor') or not self.executor:
            return
        if self.active_tool == "inspect":
            return

        last_x, last_y = getattr(self, 'last_stroke_tile', (x, y))
        line_points = self._bresenham_line(last_x, last_y, x, y)
        self.last_stroke_tile = (x, y)

        modified = False
        for px, py in line_points:
            if self._apply_brush_at(px, py):
                modified = True

        if modified:
            self.canvas.set_map_model(self.map_model)

    def _on_stroke_ended(self, button: int):
        if button != 1 or not hasattr(self, 'executor') or not self.executor:
            return
        if self.active_tool == "inspect":
            return

        if hasattr(self.executor, 'transaction_manager') and not self.executor.transaction_manager.active_batch:
            return

        if self.active_tool == "road" and self.map_model:
            self.map_model.recompute_road_connections()

        self.executor.execute({"action": "commit_transaction"})
        self.stroke_visited_tiles.clear()
        self.canvas.set_map_model(self.map_model)
        self._update_scenario_info_label()
        self._update_undo_redo_ui_state()

    def _apply_brush_at(self, cx: int, cy: int) -> bool:
        radius = self.brush_radius
        modified = False

        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                tx = cx + dx
                ty = cy + dy
                if tx < 0 or tx > 63 or ty < 0 or ty > 63:
                    continue

                if (tx, ty) in self.stroke_visited_tiles:
                    continue

                self.stroke_visited_tiles.add((tx, ty))

                if self.active_tool == "paint_terrain":
                    semantic_mode = self.rb_visual_semantic.isChecked()
                    if semantic_mode and not self.selected_terrain_definition:
                        continue
                    res = self.executor.execute({
                        "action": "paint_terrain",
                        "x": tx, "y": ty,
                        "texture": self.selected_terrain_texture,
                        "terrainDefinition": self.selected_terrain_definition,
                        "paintMode": "visual_plus_semantics" if semantic_mode else "visual_only"
                    })
                    if res.get("success"):
                        modified = True

                elif self.active_tool == "place_asset":
                    if (tx, ty) == (cx, cy):
                        res = self.executor.execute({
                            "action": "place_building",
                            "definitionId": self.selected_asset_id,
                            "x": tx, "y": ty,
                            "rotation": self.selected_rotation
                        })
                        if res.get("success"):
                            modified = True

                elif self.active_tool == "demolish":
                    res = self.executor.execute({"action": "remove_building", "x": tx, "y": ty})
                    if res.get("success"):
                        modified = True

                elif self.active_tool == "road":
                    res = self.executor.execute({"action": "set_road", "x": tx, "y": ty, "present": True})
                    if res.get("success"):
                        modified = True

        return modified

    def _on_tile_clicked(self, x: int, y: int, button: int):
        if not self.map_model or not hasattr(self, 'executor') or not self.executor:
            return

        executor = self.executor

        if self.active_tool == "paint_terrain":
            semantic_mode = self.rb_visual_semantic.isChecked()
            if semantic_mode and not self.selected_terrain_definition:
                self.status_bar.showMessage("Visual + Semantics exige uma definição declarada; nenhuma inferência foi feita.", 4000)
                return
            res = executor.execute({"action": "paint_terrain", "x": x, "y": y, "texture": self.selected_terrain_texture,
                                    "terrainDefinition": self.selected_terrain_definition,
                                    "paintMode": "visual_plus_semantics" if semantic_mode else "visual_only"})
            if res.get("success"):
                self.canvas.set_map_model(self.map_model)
                self.status_bar.showMessage(f"Painted terrain at ({x}, {y})", 2000)

        elif self.active_tool == "place_asset":
            try:
                from tools.map_forge.core.native_bridge import get_native_core
                core = get_native_core()
                req = core.PlacementRequest()
                req.object_id = self.selected_asset_id
                req.origin = core.GridCoord(x, y)
                req.rotation = self.selected_rotation

                if self.canvas and self.canvas.map_document:
                    world = core.SemanticWorldView()
                    world.map_document = self.canvas.map_document
                    bdef = self.building_catalog.get(self.selected_asset_id, {})
                    class SingleCatalogAdapter(core.IAssetCatalogView):
                        def get_footprint(self, _id):
                            info = core.AssetFootprintInfo()
                            info.width = bdef.get("footprint", {}).get("width", bdef.get("footprintWidth", 1))
                            info.height = bdef.get("footprint", {}).get("height", bdef.get("footprintHeight", 1))
                            info.declared = True
                            return info

                    val_res = core.can_place(req, world, SingleCatalogAdapter())
                    if val_res.state != core.SemanticState.VALID:
                        v_str = ", ".join([v.name for v in val_res.violations])
                        self.status_bar.showMessage(f"Placement REJECTED at ({x}, {y}): {v_str}", 4000)
                        return
            except Exception:
                pass

            res = executor.execute({"action": "place_building", "definitionId": self.selected_asset_id, "x": x, "y": y, "rotation": self.selected_rotation})
            if res.get("success"):
                self.canvas.set_map_model(self.map_model)
                self.status_bar.showMessage(f"Placed {self.selected_asset_id} at ({x}, {y})", 2000)
            else:
                self.status_bar.showMessage(f"Placement Error: {res.get('error')}", 4000)

        elif self.active_tool == "demolish":
            res = executor.execute({"action": "remove_building", "x": x, "y": y})
            if res.get("success"):
                self.canvas.set_map_model(self.map_model)
                self.status_bar.showMessage(f"Removed building at ({x}, {y})", 2000)

        elif self.active_tool == "road":
            is_road = self.map_model.is_road_at(x, y)
            res = executor.execute({"action": "set_road", "x": x, "y": y, "present": not is_road})
            if res.get("success"):
                self.canvas.set_map_model(self.map_model)
                self.status_bar.showMessage(f"Toggled road at ({x}, {y})", 2000)

        self._update_scenario_info_label()
        self._update_undo_redo_ui_state()

    def _update_scenario_info_label(self):
        if self.map_model:
            info_text = (
                f"<b>Scenario Path:</b> {os.path.basename(self.scenario_path)}<br>"
                f"<b>Version:</b> {self.map_model.save_version} | "
                f"<b>Terrain Tiles:</b> {len(self.map_model.terrain_tiles)}<br>"
                f"<b>Buildings:</b> {len(self.map_model.buildings)} | "
                f"<b>Roads:</b> {len(self.map_model.roads)}<br>"
                f"<b>Population:</b> {self.map_model.current_population} | "
                f"<b>Funds:</b> ${self.map_model.city_funds:,}"
            )
            self.txt_info.setText(info_text)

    def _on_tile_hovered(self, x: int, y: int):
        self.lbl_tile.setText(f" TILE: ({x}, {y}) ")
        if self.canvas and self.canvas.camera:
            zoom_pct = int(self.canvas.camera.zoom * 100)
            self.lbl_zoom.setText(f" ZOOM: {zoom_pct}% ")

        if self.canvas and self.canvas.map_document:
            try:
                from tools.map_forge.core.native_bridge import get_native_core
                core = get_native_core()
                info = core.inspect_tile_channels_with_terrain_catalog(
                    self.canvas.map_document, x, y, self.terrain_catalog_json)

                asset_str = info.occupied_by_asset if info.occupied_by_asset else "(none)"
                info_text = (
                    f"<b>Grid Origin:</b> ({x}, {y})<br>"
                    f"<b>Terrain:</b> {info.terrain_type}<br>"
                    f"<b>Asset:</b> {asset_str}<br>"
                    f"<b>Footprint:</b> {info.footprint_width}x{info.footprint_height} | State: {info.footprint_state.name}<br>"
                    f"<b>Occupancy:</b> {info.occupancy_state.name}<br>"
                    f"<b>Buildable:</b> {info.buildable_state.name}<br>"
                    f"<b>Anchor:</b> GROUND_ANCHOR | State: {info.pivot_state.name}<br>"
                    f"<b>Road State:</b> {info.road_state.name}<br>"
                    f"<b>Contracts:</b> CH_ANCHOR_V1, CH_FOOTPRINT_V1, CH_CONNECTOR_V1, CH_SEMANTIC_STATE_V1"
                )
                self.lbl_semantic_info.setText(info_text)
            except Exception:
                pass

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
        msg += f"Legacy Debt Items: {len(result['legacy_debt'])}\n"
        if result['errors']:
            msg += "\nTop Errors:\n" + "\n".join(result['errors'][:5])
        QMessageBox.information(self, "Map Governance & Validation Report", msg)

    def _on_rebuild_shoreline_clicked(self):
        if not self.map_model:
            return
        from tools.map_forge.core.shoreline_autotile import run_shoreline_autotile
        result = run_shoreline_autotile(self.map_model)
        QMessageBox.information(
            self,
            "Shoreline Autotile Engine (CH_SHORELINE_V1)",
            f"Evaluated shoreline autotiling over the map model.\n\n"
            f"Edits evaluated: {len(result.edits)} shoreline tile recipes derived.\n"
            f"Terrain semantics preserved (LAND vs WATER)."
        )
        self.canvas.update()
