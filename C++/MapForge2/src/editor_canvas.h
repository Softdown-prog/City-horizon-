#pragma once

#include "editor_document.h"
#include "editor_history.h"
#include "src/ch_core/projection.h"

#include <QPoint>
#include <QWidget>

#include <cstdint>
#include <functional>
#include <memory>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>

class QMouseEvent;
class QPaintEvent;
class QWheelEvent;
class QResizeEvent;
class QTimer;

namespace ch::editor {

class CanonicalViewport;

enum class EditorTool {
    Inspect,
    Terrain,
    Road,
    Erase,
};

class EditorCanvas final : public QWidget {
public:
    explicit EditorCanvas(QWidget* parent = nullptr);
    ~EditorCanvas() override;

    EditorDocument& document() { return document_; }
    const EditorDocument& document() const { return document_; }
    EditorHistory& history() { return history_; }

    bool loadCanonicalScenario(const std::string& path, std::string* error = nullptr);
    void newScratchMap(int width = 64, int height = 64);
    [[nodiscard]] bool canonicalMode() const { return canonical_mode_; }

    void setTool(EditorTool tool);
    void setTerrainId(std::string terrainId);
    void setBrushSize(int size);
    void centerCamera();
    void undo();
    void redo();

    std::function<void()> onHistoryChanged;
    std::function<void(int, int)> onHoverTileChanged;

protected:
    void paintEvent(QPaintEvent* event) override;
    void mousePressEvent(QMouseEvent* event) override;
    void mouseMoveEvent(QMouseEvent* event) override;
    void mouseReleaseEvent(QMouseEvent* event) override;
    void wheelEvent(QWheelEvent* event) override;
    void leaveEvent(QEvent* event) override;
    void resizeEvent(QResizeEvent* event) override;

private:
    static std::uint64_t tileKey(int x, int y);
    static std::vector<QPoint> bresenham(const QPoint& from, const QPoint& to);

    [[nodiscard]] float coordinateScale() const;
    [[nodiscard]] float viewportWidth() const;
    [[nodiscard]] float viewportHeight() const;
    [[nodiscard]] QPoint screenToTile(const QPointF& screen) const;
    bool ensureCanonicalViewport(std::string* error = nullptr);
    void updateHover(const QPointF& screen);
    void beginStroke(const QPoint& tile);
    void updateStroke(const QPoint& tile);
    void endStroke();
    void paintBrushAt(const QPoint& tile);
    void mutateTile(int x, int y);

    EditorDocument document_;
    EditorHistory history_;
    ch::CameraState camera_;
    EditorTool tool_ = EditorTool::Inspect;
    std::string terrain_id_ = "grass";
    int brush_size_ = 1;

    std::unique_ptr<CanonicalViewport> canonical_viewport_;
    QTimer* render_timer_ = nullptr;
    bool canonical_mode_ = false;

    std::optional<QPoint> hover_tile_;
    std::optional<QPoint> last_stroke_tile_;
    std::unordered_map<std::uint64_t, TileChange> active_changes_;
    bool stroke_active_ = false;
    bool pan_active_ = false;
    QPointF last_pan_position_;
};

} // namespace ch::editor
