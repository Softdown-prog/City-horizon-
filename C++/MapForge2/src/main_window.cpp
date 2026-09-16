#include "main_window.h"
#include "building_composer_widget.h"
#include "production_studio_panel.h"
#include "studio_panel.h"

#include <QAction>
#include <QActionGroup>
#include <QComboBox>
#include <QDockWidget>
#include <QFileDialog>
#include <QFileInfo>
#include <QInputDialog>
#include <QKeySequence>
#include <QLabel>
#include <QMenu>
#include <QMenuBar>
#include <QMessageBox>
#include <QStatusBar>
#include <QTabWidget>
#include <QTimer>
#include <QToolBar>
#include <QVBoxLayout>
#include <QWidget>

#include <algorithm>

namespace ch::editor {

MainWindow::MainWindow(QWidget* parent)
    : QMainWindow(parent), canvas_(new EditorCanvas(this)) {
    setWindowTitle("City Horizon Studio / Map Forge 2 — C++ / Qt6");
    resize(1600, 960);
    setDockNestingEnabled(true);
    setCentralWidget(canvas_);

    buildMenus();
    buildDocks();
    buildToolbar();

    map_status_ = new QLabel("Map: —", this);
    tile_status_ = new QLabel("Tile: —", this);
    statusBar()->addPermanentWidget(map_status_);
    statusBar()->addPermanentWidget(tile_status_);
    statusBar()->showMessage(
        "Viewport ready. Drag with Inspect (or RMB/MMB) to move the map; WASD/arrows pan; wheel zooms.");

    canvas_->onHistoryChanged = [this]() { refreshHistoryActions(); };
    canvas_->onDocumentBoundsChanged = [this]() { refreshMapStatus(); };
    canvas_->onHoverTileChanged = [this](const int x, const int y) {
        tile_status_->setText(QString("Tile: %1, %2").arg(x).arg(y));
    };

    setStyleSheet(R"(
        QMainWindow { background: #20282b; }
        QToolBar { background: #263238; border: 0; spacing: 4px; padding: 4px; }
        QToolBar QToolButton { color: #e5edf0; padding: 6px 10px; border-radius: 4px; }
        QToolBar QToolButton:checked { background: #1f8ea8; color: white; }
        QDockWidget { color: #dfe8eb; }
        QDockWidget::title { background: #263238; padding: 7px; }
        QTabWidget::pane { border: 1px solid #3a474c; background: #242d31; }
        QTabBar::tab { background: #303b40; color: #dfe8eb; padding: 8px 12px; }
        QTabBar::tab:selected { background: #1f8ea8; color: white; }
        QLabel { color: #dfe8eb; }
        QComboBox { min-height: 26px; background: #313d42; color: #e8eef0; border: 1px solid #4b5a60; padding: 2px 6px; }
        QLineEdit { min-height: 26px; background: #192125; color: #e8eef0; border: 1px solid #4b5a60; padding: 2px 6px; }
        QListWidget { background: #192125; color: #dfe8eb; border: 1px solid #3a474c; }
        QListWidget::item:selected { background: #1f8ea8; color: white; }
        QPushButton { background: #313d42; color: #e8eef0; border: 1px solid #4b5a60; padding: 6px 10px; border-radius: 4px; }
        QPushButton:hover { background: #3b4a50; }
        QPlainTextEdit { background: #192125; color: #dfe8eb; border: 1px solid #3a474c; }
        QMenuBar, QMenu { background: #263238; color: #e8eef0; }
        QMenu::item:selected { background: #1f8ea8; }
        QStatusBar { background: #263238; color: #dfe8eb; }
    )");

    refreshHistoryActions();
    refreshMapStatus();
    QTimer::singleShot(0, canvas_, [this]() { canvas_->centerCamera(); });
}

void MainWindow::buildMenus() {
    auto* fileMenu = menuBar()->addMenu("&File");

    auto* newAction = fileMenu->addAction("&New 64x64 Scratch Map");
    connect(newAction, &QAction::triggered, this, [this]() {
        canvas_->newScratchMap(64, 64);
        setAuthoringEnabled(true);
        refreshHistoryActions();
        refreshMapStatus();
        statusBar()->showMessage("Created diagnostic 64x64 scratch map. Authoring and map resize are enabled.", 5000);
        setWindowTitle("City Horizon Studio / Map Forge 2 — Scratch Map");
    });

    auto* openAction = fileMenu->addAction("&Open Scenario…");
    openAction->setShortcut(QKeySequence::Open);
    connect(openAction, &QAction::triggered, this, [this]() {
        const QString path = QFileDialog::getOpenFileName(this, "Open City Horizon scenario", {}, "Scenario JSON (*.json);;All files (*.*)");
        if (!path.isEmpty()) loadScenario(path);
    });

    fileMenu->addSeparator();
    auto* saveNotice = fileMenu->addAction("Save (lossless authoring gate not yet enabled)");
    saveNotice->setEnabled(false);
    fileMenu->addSeparator();
    auto* exitAction = fileMenu->addAction("E&xit");
    connect(exitAction, &QAction::triggered, this, &QWidget::close);

    auto* editMenu = menuBar()->addMenu("&Edit");
    undo_action_ = editMenu->addAction("&Undo");
    undo_action_->setShortcut(QKeySequence::Undo);
    connect(undo_action_, &QAction::triggered, this, [this]() { canvas_->undo(); });

    redo_action_ = editMenu->addAction("&Redo");
    redo_action_->setShortcut(QKeySequence::Redo);
    connect(redo_action_, &QAction::triggered, this, [this]() { canvas_->redo(); });

    auto* mapMenu = menuBar()->addMenu("&Map");
    auto* resizeAction = mapMenu->addAction("Resize Map Bounds…");
    resizeAction->setShortcut(QKeySequence("Ctrl+Shift+R"));
    connect(resizeAction, &QAction::triggered, this, [this]() { resizeMapInteractive(); });

    auto* centerMapAction = mapMenu->addAction("Center Map");
    centerMapAction->setShortcut(QKeySequence("Ctrl+0"));
    connect(centerMapAction, &QAction::triggered, this, [this]() { canvas_->centerCamera(); });

    auto* viewMenu = menuBar()->addMenu("&View");
    auto* centerAction = viewMenu->addAction("Center Map");
    connect(centerAction, &QAction::triggered, this, [this]() { canvas_->centerCamera(); });

    studio_panels_action_ = viewMenu->addAction("Studio Panels");
    studio_panels_action_->setCheckable(true);
    studio_panels_action_->setChecked(false);
    studio_panels_action_->setShortcut(QKeySequence("Tab"));
    connect(studio_panels_action_, &QAction::toggled, this, [this](const bool visible) {
        showStudioPanels(visible);
    });
}

void MainWindow::buildToolbar() {
    auto* toolbar = addToolBar("Map Tools");
    toolbar->setObjectName("MapToolsToolbar");
    toolbar->setMovable(false);
    toolbar->setToolButtonStyle(Qt::ToolButtonTextOnly);

    auto* toolGroup = new QActionGroup(this);
    toolGroup->setExclusive(true);

    auto addTool = [&](const QString& label, const QKeySequence& shortcut, const EditorTool tool, const bool checked = false) {
        auto* action = toolbar->addAction(label);
        action->setCheckable(true);
        action->setChecked(checked);
        action->setShortcut(shortcut);
        toolGroup->addAction(action);
        connect(action, &QAction::triggered, this, [this, tool]() { setTool(tool); });
        return action;
    };

    inspect_action_ = addTool("Inspect / Pan", QKeySequence("1"), EditorTool::Inspect, true);
    terrain_action_ = addTool("Terrain", QKeySequence("2"), EditorTool::Terrain);
    road_action_ = addTool("Road", QKeySequence("3"), EditorTool::Road);
    erase_action_ = addTool("Erase", QKeySequence("4"), EditorTool::Erase);

    toolbar->addSeparator();
    toolbar->addWidget(new QLabel("Terrain:", toolbar));
    terrain_combo_ = new QComboBox(toolbar);
    terrain_combo_->addItems({"grass", "dirt", "concrete", "sand_dry", "sand_wet", "stone", "water_shallow", "water_deep"});
    toolbar->addWidget(terrain_combo_);
    connect(terrain_combo_, &QComboBox::currentTextChanged, this, [this](const QString& value) {
        canvas_->setTerrainId(value.toStdString());
    });

    toolbar->addSeparator();
    toolbar->addWidget(new QLabel("Brush:", toolbar));
    brush_combo_ = new QComboBox(toolbar);
    brush_combo_->addItems({"1x1", "3x3", "5x5"});
    toolbar->addWidget(brush_combo_);
    connect(brush_combo_, &QComboBox::currentIndexChanged, this, [this](const int index) {
        const int sizes[] = {1, 3, 5};
        canvas_->setBrushSize(sizes[std::clamp(index, 0, 2)]);
    });

    toolbar->addSeparator();
    auto* centerAction = toolbar->addAction("Center");
    centerAction->setShortcut(QKeySequence("Ctrl+0"));
    connect(centerAction, &QAction::triggered, this, [this]() { canvas_->centerCamera(); });

    auto* resizeAction = toolbar->addAction("Map Size");
    resizeAction->setToolTip("Resize editable scratch-map bounds while preserving in-bounds content");
    connect(resizeAction, &QAction::triggered, this, [this]() { resizeMapInteractive(); });

    toolbar->addSeparator();
    if (studio_panels_action_ != nullptr) {
        toolbar->addAction(studio_panels_action_);
    }
}

void MainWindow::buildDocks() {
    studio_dock_ = new QDockWidget("Studio Panels", this);
    studio_dock_->setObjectName("StudioPanelsDock");
    studio_dock_->setAllowedAreas(Qt::LeftDockWidgetArea | Qt::RightDockWidgetArea | Qt::BottomDockWidgetArea);
    studio_dock_->setFeatures(QDockWidget::DockWidgetClosable | QDockWidget::DockWidgetMovable | QDockWidget::DockWidgetFloatable);
    studio_dock_->setMinimumWidth(300);
    studio_dock_->setMaximumWidth(560);

    auto* tabs = new QTabWidget(studio_dock_);
    tabs->setDocumentMode(true);
    tabs->addTab(new ch::studio::ProductionStudioPanel(tabs), "Production");
    tabs->addTab(new ch::studio::BuildingComposerWidget(tabs), "Building Composer");
    tabs->addTab(new ch::studio::StudioPanel(tabs), "Studio");

    auto* terrainPage = new QWidget(tabs);
    auto* terrainLayout = new QVBoxLayout(terrainPage);
    terrainLayout->addWidget(new QLabel(
        "Semantic terrain palette\n\n"
        "Scratch-map authoring remains available for interaction testing. Scratch bounds can now grow/shrink while preserving in-bounds tiles. Canonical scenarios remain lossless-read-only until the mutable document gate is complete.",
        terrainPage));
    terrainLayout->addStretch(1);
    tabs->addTab(terrainPage, "Terrain");

    auto* objectsPage = new QWidget(tabs);
    auto* objectsLayout = new QVBoxLayout(objectsPage);
    objectsLayout->addWidget(new QLabel(
        "Object catalog migration target\n\n"
        "Canonical scenario inspection now renders terrain, connectivity-aware roads and building definitions through ch_render. Placement/rotation editing comes after lossless mutation.",
        objectsPage));
    objectsLayout->addStretch(1);
    tabs->addTab(objectsPage, "Objects");

    auto* diagnosticsPage = new QWidget(tabs);
    auto* diagnosticsLayout = new QVBoxLayout(diagnosticsPage);
    diagnosticsLayout->addWidget(new QLabel(
        "Diagnostics\n\n"
        "• Qt6 owns desktop UI, input and the event loop\n"
        "• SDL3 wraps the Qt-owned native viewport HWND\n"
        "• ch_render owns canonical world drawing\n"
        "• physical-pixel DPR conversion is explicit\n"
        "• canonical viewport redraw work is dirty-gated\n"
        "• Inspect + left drag, RMB/MMB and WASD/arrows pan the map\n"
        "• scratch map bounds can be resized without moving their minimum coordinate\n"
        "• Building Composer V0 generates four bitmap views from one parametric definition\n"
        "• canonical scenario mode is still read-only until lossless serialization\n"
        "• production Save remains disabled until lossless serialization\n"
        "• Production Workbench V1 never overwrites source assets\n"
        "• CH_CONTENT_PACK_V1 remains the data-driven content boundary",
        diagnosticsPage));
    diagnosticsLayout->addStretch(1);
    tabs->addTab(diagnosticsPage, "Diagnostics");

    studio_dock_->setWidget(tabs);
    addDockWidget(Qt::RightDockWidgetArea, studio_dock_);
    studio_dock_->hide();

    connect(studio_dock_, &QDockWidget::visibilityChanged, this, [this](const bool visible) {
        if (studio_panels_action_ != nullptr && studio_panels_action_->isChecked() != visible) {
            studio_panels_action_->blockSignals(true);
            studio_panels_action_->setChecked(visible);
            studio_panels_action_->blockSignals(false);
        }
    });
}

void MainWindow::showStudioPanels(const bool visible) {
    if (studio_dock_ == nullptr) return;
    studio_dock_->setVisible(visible);
    if (visible) {
        studio_dock_->raise();
        studio_dock_->setFocus();
    } else if (canvas_ != nullptr) {
        canvas_->setFocus();
    }
}

void MainWindow::setTool(const EditorTool tool) {
    if (canvas_->canonicalMode() && tool != EditorTool::Inspect) {
        if (inspect_action_ != nullptr) inspect_action_->setChecked(true);
        canvas_->setTool(EditorTool::Inspect);
        statusBar()->showMessage("Canonical viewport is inspection-only until the lossless mutation gate is implemented.", 4500);
        return;
    }
    canvas_->setTool(tool);
}

void MainWindow::setAuthoringEnabled(const bool enabled) {
    if (terrain_action_ != nullptr) terrain_action_->setEnabled(enabled);
    if (road_action_ != nullptr) road_action_->setEnabled(enabled);
    if (erase_action_ != nullptr) erase_action_->setEnabled(enabled);
    if (terrain_combo_ != nullptr) terrain_combo_->setEnabled(enabled);
    if (brush_combo_ != nullptr) brush_combo_->setEnabled(enabled);

    if (!enabled && inspect_action_ != nullptr) {
        inspect_action_->setChecked(true);
        canvas_->setTool(EditorTool::Inspect);
    }
}

void MainWindow::refreshHistoryActions() {
    const bool authoring = !canvas_->canonicalMode();
    if (undo_action_ != nullptr) undo_action_->setEnabled(authoring && canvas_->history().canUndo());
    if (redo_action_ != nullptr) redo_action_->setEnabled(authoring && canvas_->history().canRedo());
}

void MainWindow::refreshMapStatus() {
    if (map_status_ == nullptr || canvas_ == nullptr) return;
    const auto& document = canvas_->document();
    map_status_->setText(QString("Map: %1×%2  [%3,%4 → %5,%6]")
        .arg(document.width()).arg(document.height())
        .arg(document.minX()).arg(document.minY())
        .arg(document.maxX()).arg(document.maxY()));
}

void MainWindow::resizeMapInteractive() {
    if (canvas_->canonicalMode()) {
        QMessageBox::information(
            this,
            "Resize Map",
            "Imported canonical scenarios can now be moved freely in the viewport, but their logical bounds are still protected by the lossless-authoring gate.\n\n"
            "Resize is enabled for editable scratch maps now. Canonical resize will be enabled together with real scenario mutation/save so the Studio never pretends to grow a map that it cannot serialize safely.");
        return;
    }

    bool accepted = false;
    const int width = QInputDialog::getInt(
        this, "Resize Map", "Width in tiles:", canvas_->document().width(), 1, 256, 1, &accepted);
    if (!accepted) return;

    const int height = QInputDialog::getInt(
        this, "Resize Map", "Height in tiles:", canvas_->document().height(), 1, 256, 1, &accepted);
    if (!accepted) return;

    if (canvas_->resizeScratchMap(width, height)) {
        refreshHistoryActions();
        refreshMapStatus();
        statusBar()->showMessage(
            QString("Map resized to %1×%2 tiles. Existing in-bounds terrain/roads were preserved; cropped cells were discarded.")
                .arg(width).arg(height),
            7000);
    } else {
        statusBar()->showMessage("Map size unchanged.", 2500);
    }
}

bool MainWindow::loadScenario(const QString& path) {
    std::string error;
    if (!canvas_->loadCanonicalScenario(path.toStdString(), &error)) {
        QMessageBox::critical(this, "City Horizon Studio", QString::fromStdString(error));
        return false;
    }

    setAuthoringEnabled(false);
    refreshHistoryActions();
    refreshMapStatus();
    showStudioPanels(false);
    statusBar()->showMessage(
        QString("Canonical renderer active: %1 — drag with Inspect/RMB/MMB or use WASD/arrows to move the map; editing remains gated until lossless authoring is implemented.").arg(path),
        9000);
    setWindowTitle(QString("City Horizon Studio / Map Forge 2 — %1 [Canonical]").arg(QFileInfo(path).fileName()));
    canvas_->setFocus();
    canvas_->update();
    return true;
}

} // namespace ch::editor
