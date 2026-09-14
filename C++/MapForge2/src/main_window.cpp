#include "main_window.h"

#include <QAction>
#include <QActionGroup>
#include <QComboBox>
#include <QDockWidget>
#include <QFileDialog>
#include <QFileInfo>
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
    setWindowTitle("City Horizon Map Forge 2 — C++ / Qt6");
    resize(1440, 900);
    setCentralWidget(canvas_);

    buildMenus();
    buildToolbar();
    buildDocks();

    tile_status_ = new QLabel("Tile: —", this);
    statusBar()->addPermanentWidget(tile_status_);
    statusBar()->showMessage("Native editor core ready. Production saving is intentionally disabled in this migration milestone.");

    canvas_->onHistoryChanged = [this]() { refreshHistoryActions(); };
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
        QMenuBar, QMenu { background: #263238; color: #e8eef0; }
        QMenu::item:selected { background: #1f8ea8; }
        QStatusBar { background: #263238; color: #dfe8eb; }
    )");

    refreshHistoryActions();
    QTimer::singleShot(0, canvas_, [this]() { canvas_->centerCamera(); });
}

void MainWindow::buildMenus() {
    auto* fileMenu = menuBar()->addMenu("&File");

    auto* newAction = fileMenu->addAction("&New 64x64");
    connect(newAction, &QAction::triggered, this, [this]() {
        canvas_->document().newEmpty(64, 64);
        canvas_->history().clear();
        canvas_->centerCamera();
        refreshHistoryActions();
        statusBar()->showMessage("Created native 64x64 scratch map.", 4000);
    });

    auto* openAction = fileMenu->addAction("&Open Scenario…");
    openAction->setShortcut(QKeySequence::Open);
    connect(openAction, &QAction::triggered, this, [this]() {
        const QString path = QFileDialog::getOpenFileName(this, "Open City Horizon scenario", {}, "Scenario JSON (*.json);;All files (*.*)");
        if (!path.isEmpty()) loadScenario(path);
    });

    fileMenu->addSeparator();
    auto* saveNotice = fileMenu->addAction("Save (migration gate not yet enabled)");
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

    auto* viewMenu = menuBar()->addMenu("&View");
    auto* centerAction = viewMenu->addAction("Center Map");
    centerAction->setShortcut(QKeySequence("Ctrl+0"));
    connect(centerAction, &QAction::triggered, this, [this]() { canvas_->centerCamera(); });
}

void MainWindow::buildToolbar() {
    auto* toolbar = addToolBar("Editor");
    toolbar->setMovable(false);

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

    addTool("Inspect", QKeySequence("1"), EditorTool::Inspect, true);
    addTool("Terrain", QKeySequence("2"), EditorTool::Terrain);
    addTool("Road", QKeySequence("3"), EditorTool::Road);
    addTool("Erase", QKeySequence("4"), EditorTool::Erase);

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
}

void MainWindow::buildDocks() {
    auto* dock = new QDockWidget("Map Forge 2", this);
    dock->setAllowedAreas(Qt::LeftDockWidgetArea | Qt::RightDockWidgetArea);
    dock->setMinimumWidth(300);

    auto* tabs = new QTabWidget(dock);

    auto* terrainPage = new QWidget(tabs);
    auto* terrainLayout = new QVBoxLayout(terrainPage);
    terrainLayout->addWidget(new QLabel(
        "Semantic terrain palette\n\n"
        "Paint intent here. Technical edge/corner/shoreline sprites will never be exposed as user terrain choices.",
        terrainPage));
    terrainLayout->addStretch(1);
    tabs->addTab(terrainPage, "Terrain");

    auto* objectsPage = new QWidget(tabs);
    auto* objectsLayout = new QVBoxLayout(objectsPage);
    objectsLayout->addWidget(new QLabel(
        "Object catalog migration target\n\n"
        "Buildings, decorations, rotation, footprints and access points will be connected to the canonical C++ catalogs in the next milestones.",
        objectsPage));
    objectsLayout->addStretch(1);
    tabs->addTab(objectsPage, "Objects");

    auto* diagnosticsPage = new QWidget(tabs);
    auto* diagnosticsLayout = new QVBoxLayout(diagnosticsPage);
    diagnosticsLayout->addWidget(new QLabel(
        "Diagnostics\n\n"
        "• C++ event loop\n"
        "• canonical 2:1 projection\n"
        "• stroke transaction = one undo entry\n"
        "• Bresenham continuous drag\n"
        "• production save disabled until lossless serializer gate\n"
        "• Python asset tools remain external/offline",
        diagnosticsPage));
    diagnosticsLayout->addStretch(1);
    tabs->addTab(diagnosticsPage, "Diagnostics");

    dock->setWidget(tabs);
    addDockWidget(Qt::RightDockWidgetArea, dock);
}

void MainWindow::setTool(const EditorTool tool) {
    canvas_->setTool(tool);
}

void MainWindow::refreshHistoryActions() {
    if (undo_action_ != nullptr) undo_action_->setEnabled(canvas_->history().canUndo());
    if (redo_action_ != nullptr) redo_action_->setEnabled(canvas_->history().canRedo());
}

bool MainWindow::loadScenario(const QString& path) {
    std::string error;
    if (!canvas_->document().loadScenario(path.toStdString(), &error)) {
        QMessageBox::critical(this, "Map Forge 2", QString::fromStdString(error));
        return false;
    }

    canvas_->history().clear();
    refreshHistoryActions();
    canvas_->centerCamera();
    statusBar()->showMessage(QString("Loaded canonical scenario: %1").arg(path), 6000);
    setWindowTitle(QString("City Horizon Map Forge 2 — %1").arg(QFileInfo(path).fileName()));
    canvas_->update();
    return true;
}

} // namespace ch::editor
