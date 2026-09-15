#pragma once

#include "editor_canvas.h"

#include <QMainWindow>
#include <QString>

class QAction;
class QComboBox;
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
    void setTool(EditorTool tool);
    void setAuthoringEnabled(bool enabled);

    EditorCanvas* canvas_ = nullptr;
    QAction* undo_action_ = nullptr;
    QAction* redo_action_ = nullptr;
    QAction* inspect_action_ = nullptr;
    QAction* terrain_action_ = nullptr;
    QAction* road_action_ = nullptr;
    QAction* erase_action_ = nullptr;
    QLabel* tile_status_ = nullptr;
    QComboBox* terrain_combo_ = nullptr;
    QComboBox* brush_combo_ = nullptr;
};

} // namespace ch::editor
