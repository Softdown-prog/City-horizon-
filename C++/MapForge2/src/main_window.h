#pragma once

#include "editor_canvas.h"

#include <QMainWindow>
#include <QString>

class QAction;
class QComboBox;
class QDockWidget;
class QLabel;

namespace ch::editor {

class MainWindow final : public QMainWindow {
public:
    explicit MainWindow(QWidget* parent = nullptr);

    bool loadScenario(const QString& path);

private:
    void buildMenus();
    void buildToolbar();
    void buildDocks();
    void refreshHistoryActions();
    void refreshMapStatus();
    void resizeMapInteractive();
    void setTool(EditorTool tool);
    void setAuthoringEnabled(bool enabled);
    void showStudioPanels(bool visible);

    EditorCanvas* canvas_ = nullptr;
    QDockWidget* studio_dock_ = nullptr;
    QAction* studio_panels_action_ = nullptr;
    QAction* undo_action_ = nullptr;
    QAction* redo_action_ = nullptr;
    QAction* inspect_action_ = nullptr;
    QAction* terrain_action_ = nullptr;
    QAction* road_action_ = nullptr;
    QAction* erase_action_ = nullptr;
    QLabel* tile_status_ = nullptr;
    QLabel* map_status_ = nullptr;
    QComboBox* terrain_combo_ = nullptr;
    QComboBox* brush_combo_ = nullptr;
};

} // namespace ch::editor
