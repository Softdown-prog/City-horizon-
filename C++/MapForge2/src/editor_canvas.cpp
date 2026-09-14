#include "editor_canvas.h"

#include <QEvent>
#include <QMouseEvent>
#include <QPainter>
#include <QPaintEvent>
#include <QPolygonF>
#include <QResizeEvent>
#include <QWheelEvent>

#include <algorithm>
#include <cmath>
#include <vector>

namespace ch::editor {
namespace {

QColor terrainColor(const std::string& id) {
    const QString value = QString::fromStdString(id).toLower();
    if (value.contains("deep") && value.contains("water")) return QColor(32, 92, 145);
    if (value.contains("water") || value.contains("ocean") || value.contains("shallow")) return QColor(56, 145, 190);
    if (value.contains("sand_wet") || value.contains("wet_sand")) return QColor(190, 164, 105);
    if (value.contains("sand")) return QColor(222, 198, 132);
    if (value.contains("concrete") || value.contains("cement") || value.contains("sidewalk")) return QColor(170, 174, 174);
    if (value.contains("stone") || value.contains("rock")) return QColor(128, 132, 132);
    if (value.contains("dirt") || value.contains("soil")) return QColor(137, 101, 67);
    return QColor(92, 151, 72);
}

QPolygonF tilePolygon(const int x, const int y, const ch::CameraState& camera, const float viewportW, const float viewportH) {
    const auto a = ch::world_to_screen_point(static_cast<float>(x), static_cast<float>(y), camera, viewportW, viewportH);
    const auto b = ch::world_to_screen_point(static_cast<float>(x + 1), static_cast<float>(y), camera, viewportW, viewportH);
    const auto c = ch::world_to_screen_point(static_cast<float>(x + 1), static_cast<float>(y + 1), camera, viewportW, viewportH);
    const auto d = ch::world_to_screen_point(static_cast<float>(x), static_cast<float>(y + 1), camera, viewportW, viewportH);
    return QPolygonF{QPointF(a.x, a.y), QPointF(b.x, b.y), QPointF(c.x, c.y), QPointF(d.x, d.y)};
}

} // namespace

EditorCanvas::EditorCanvas(QWidget* parent)
    : QWidget(parent) {
    setMouseTracking(true);
    setFocusPolicy(Qt::StrongFocus);
    setAttribute(Qt::WA_OpaquePaintEvent, true);
    camera_.zoom = 1.0F;
}

std::uint64_t EditorCanvas::tileKey(const int x, const int y) {
    return (static_cast<std::uint64_t>(static_cast<std::uint32_t>(x)) << 32U)
        | static_cast<std::uint32_t>(y);
}

void EditorCanvas::setTool(const EditorTool tool) {
    if (stroke_active_) {
        endStroke();
    }
    tool_ = tool;
    update();
}

void EditorCanvas::setTerrainId(std::string terrainId) {
    terrain_id_ = std::move(terrainId);
}

void EditorCanvas::setBrushSize(const int size) {
    brush_size_ = (size <= 1) ? 1 : (size <= 3 ? 3 : 5);
    update();
}

void EditorCanvas::centerCamera() {
    ch::CameraState probe = camera_;
    probe.pan_x = 0.0F;
    probe.pan_y = 0.0F;
    const float cx = static_cast<float>(document_.width()) * 0.5F;
    const float cy = static_cast<float>(document_.height()) * 0.5F;
    const auto screen = ch::world_to_screen_point(cx, cy, probe, static_cast<float>(width()), static_cast<float>(height()));
    camera_.pan_x = static_cast<float>(width()) * 0.5F - screen.x;
    camera_.pan_y = static_cast<float>(height()) * 0.5F - screen.y;
    update();
}

void EditorCanvas::undo() {
    if (stroke_active_) endStroke();
    if (history_.undo(document_)) {
        update();
        if (onHistoryChanged) onHistoryChanged();
    }
}

void EditorCanvas::redo() {
    if (stroke_active_) endStroke();
    if (history_.redo(document_)) {
        update();
        if (onHistoryChanged) onHistoryChanged();
    }
}

QPoint EditorCanvas::screenToTile(const QPointF& screen) const {
    const auto tile = ch::screen_to_tile_coord(
        static_cast<float>(screen.x()), static_cast<float>(screen.y()), camera_,
        static_cast<float>(width()), static_cast<float>(height()));
    return {tile.x, tile.y};
}

void EditorCanvas::updateHover(const QPointF& screen) {
    const QPoint tile = screenToTile(screen);
    if (document_.inBounds(tile.x(), tile.y())) {
        if (!hover_tile_ || *hover_tile_ != tile) {
            hover_tile_ = tile;
            if (onHoverTileChanged) onHoverTileChanged(tile.x(), tile.y());
            update();
        }
    } else if (hover_tile_) {
        hover_tile_.reset();
        update();
    }
}

std::vector<QPoint> EditorCanvas::bresenham(const QPoint& from, const QPoint& to) {
    std::vector<QPoint> result;
    int x0 = from.x();
    int y0 = from.y();
    const int x1 = to.x();
    const int y1 = to.y();
    const int dx = std::abs(x1 - x0);
    const int sx = x0 < x1 ? 1 : -1;
    const int dy = -std::abs(y1 - y0);
    const int sy = y0 < y1 ? 1 : -1;
    int error = dx + dy;

    while (true) {
        result.emplace_back(x0, y0);
        if (x0 == x1 && y0 == y1) break;
        const int e2 = error * 2;
        if (e2 >= dy) {
            error += dy;
            x0 += sx;
        }
        if (e2 <= dx) {
            error += dx;
            y0 += sy;
        }
    }
    return result;
}

void EditorCanvas::beginStroke(const QPoint& tile) {
    if (tool_ == EditorTool::Inspect || !document_.inBounds(tile.x(), tile.y())) return;
    stroke_active_ = true;
    active_changes_.clear();
    last_stroke_tile_ = tile;
    paintBrushAt(tile);
}

void EditorCanvas::updateStroke(const QPoint& tile) {
    if (!stroke_active_ || !last_stroke_tile_) return;
    for (const QPoint& point : bresenham(*last_stroke_tile_, tile)) {
        paintBrushAt(point);
    }
    last_stroke_tile_ = tile;
}

void EditorCanvas::endStroke() {
    if (!stroke_active_) return;

    std::vector<TileChange> committed;
    committed.reserve(active_changes_.size());
    for (auto& [_, change] : active_changes_) {
        change.after = document_.tile(change.x, change.y);
        committed.push_back(std::move(change));
    }
    history_.commit(std::move(committed));

    active_changes_.clear();
    last_stroke_tile_.reset();
    stroke_active_ = false;
    if (onHistoryChanged) onHistoryChanged();
}

void EditorCanvas::paintBrushAt(const QPoint& tile) {
    const int radius = (brush_size_ - 1) / 2;
    for (int y = tile.y() - radius; y <= tile.y() + radius; ++y) {
        for (int x = tile.x() - radius; x <= tile.x() + radius; ++x) {
            mutateTile(x, y);
        }
    }
    update();
}

void EditorCanvas::mutateTile(const int x, const int y) {
    if (!document_.inBounds(x, y)) return;

    const auto k = tileKey(x, y);
    if (!active_changes_.contains(k)) {
        active_changes_.emplace(k, TileChange{x, y, document_.tile(x, y), document_.tile(x, y)});
    }

    switch (tool_) {
        case EditorTool::Terrain:
            document_.setTerrain(x, y, terrain_id_);
            break;
        case EditorTool::Road:
            document_.setRoad(x, y, true);
            break;
        case EditorTool::Erase:
            document_.setTile(x, y, TileState{});
            break;
        case EditorTool::Inspect:
            break;
    }
}

void EditorCanvas::paintEvent(QPaintEvent*) {
    QPainter painter(this);
    painter.setRenderHint(QPainter::Antialiasing, false);
    painter.fillRect(rect(), QColor(44, 52, 55));

    const float viewportW = static_cast<float>(width());
    const float viewportH = static_cast<float>(height());
    QPen gridPen(QColor(45, 70, 55, 110));
    gridPen.setWidthF(1.0);

    const int maxSum = document_.width() + document_.height() - 2;
    for (int sum = 0; sum <= maxSum; ++sum) {
        const int startX = std::max(0, sum - (document_.height() - 1));
        const int endX = std::min(document_.width() - 1, sum);
        for (int x = startX; x <= endX; ++x) {
            const int y = sum - x;
            const auto state = document_.tile(x, y);
            const QPolygonF polygon = tilePolygon(x, y, camera_, viewportW, viewportH);
            painter.setPen(gridPen);
            painter.setBrush(state.road ? QColor(69, 73, 77) : terrainColor(state.terrain_id));
            painter.drawPolygon(polygon);
        }
    }

    if (hover_tile_) {
        const int radius = tool_ == EditorTool::Inspect ? 0 : (brush_size_ - 1) / 2;
        QPen hoverPen(QColor(255, 210, 72));
        hoverPen.setWidthF(2.0);
        painter.setPen(hoverPen);
        painter.setBrush(QColor(255, 210, 72, 45));
        for (int y = hover_tile_->y() - radius; y <= hover_tile_->y() + radius; ++y) {
            for (int x = hover_tile_->x() - radius; x <= hover_tile_->x() + radius; ++x) {
                if (document_.inBounds(x, y)) {
                    painter.drawPolygon(tilePolygon(x, y, camera_, viewportW, viewportH));
                }
            }
        }
    }
}

void EditorCanvas::mousePressEvent(QMouseEvent* event) {
    setFocus();
    updateHover(event->position());

    if (event->button() == Qt::MiddleButton || event->button() == Qt::RightButton) {
        pan_active_ = true;
        last_pan_position_ = event->position();
        setCursor(Qt::ClosedHandCursor);
        return;
    }

    if (event->button() == Qt::LeftButton && hover_tile_) {
        beginStroke(*hover_tile_);
    }
}

void EditorCanvas::mouseMoveEvent(QMouseEvent* event) {
    if (pan_active_) {
        const QPointF delta = event->position() - last_pan_position_;
        camera_.pan_x += static_cast<float>(delta.x());
        camera_.pan_y += static_cast<float>(delta.y());
        last_pan_position_ = event->position();
        update();
        return;
    }

    updateHover(event->position());
    if (stroke_active_ && (event->buttons() & Qt::LeftButton) && hover_tile_) {
        updateStroke(*hover_tile_);
    }
}

void EditorCanvas::mouseReleaseEvent(QMouseEvent* event) {
    if (event->button() == Qt::LeftButton) {
        endStroke();
    }
    if (event->button() == Qt::MiddleButton || event->button() == Qt::RightButton) {
        pan_active_ = false;
        unsetCursor();
    }
}

void EditorCanvas::wheelEvent(QWheelEvent* event) {
    const float factor = event->angleDelta().y() > 0 ? 1.15F : (1.0F / 1.15F);
    camera_.zoom = std::clamp(camera_.zoom * factor, 0.35F, 3.0F);
    updateHover(event->position());
    update();
}

void EditorCanvas::leaveEvent(QEvent*) {
    hover_tile_.reset();
    if (stroke_active_) endStroke();
    update();
}

void EditorCanvas::resizeEvent(QResizeEvent* event) {
    QWidget::resizeEvent(event);
}

} // namespace ch::editor
