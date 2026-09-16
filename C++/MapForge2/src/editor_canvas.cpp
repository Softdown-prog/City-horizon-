#include "editor_canvas.h"
#include "canonical_viewport.h"

#include "src/ch_core/contracts.h"
#include "src/ch_core/map_document.h"

#include <QCoreApplication>
#include <QEvent>
#include <QKeyEvent>
#include <QMouseEvent>
#include <QPainter>
#include <QPaintEvent>
#include <QPolygonF>
#include <QResizeEvent>
#include <QTimer>
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

QPolygonF tilePolygon(const int x, const int y, const ch::CameraState& camera,
                      const float viewportW, const float viewportH) {
    const auto a = ch::world_to_screen_point(static_cast<float>(x), static_cast<float>(y), camera, viewportW, viewportH);
    const auto b = ch::world_to_screen_point(static_cast<float>(x + 1), static_cast<float>(y), camera, viewportW, viewportH);
    const auto c = ch::world_to_screen_point(static_cast<float>(x + 1), static_cast<float>(y + 1), camera, viewportW, viewportH);
    const auto d = ch::world_to_screen_point(static_cast<float>(x), static_cast<float>(y + 1), camera, viewportW, viewportH);
    return QPolygonF{QPointF(a.x, a.y), QPointF(b.x, b.y), QPointF(c.x, c.y), QPointF(d.x, d.y)};
}

} // namespace

EditorCanvas::EditorCanvas(QWidget* parent)
    : QWidget(parent), canonical_viewport_(std::make_unique<CanonicalViewport>()) {
    setMouseTracking(true);
    setFocusPolicy(Qt::StrongFocus);
    setAttribute(Qt::WA_NativeWindow, true);
    setAttribute(Qt::WA_OpaquePaintEvent, true);
    setAutoFillBackground(false);
    camera_.zoom = 1.0F;

    render_timer_ = new QTimer(this);
    render_timer_->setInterval(16);
    render_timer_->setTimerType(Qt::PreciseTimer);
    connect(render_timer_, &QTimer::timeout, this, [this]() {
        if (canonical_mode_ && isVisible()) update();
    });
}

EditorCanvas::~EditorCanvas() = default;

std::uint64_t EditorCanvas::tileKey(const int x, const int y) {
    return (static_cast<std::uint64_t>(static_cast<std::uint32_t>(x)) << 32U)
        | static_cast<std::uint32_t>(y);
}

float EditorCanvas::coordinateScale() const {
    return canonical_mode_ ? static_cast<float>(devicePixelRatioF()) : 1.0F;
}

float EditorCanvas::viewportWidth() const {
    return static_cast<float>(std::max(1, width())) * coordinateScale();
}

float EditorCanvas::viewportHeight() const {
    return static_cast<float>(std::max(1, height())) * coordinateScale();
}

bool EditorCanvas::ensureCanonicalViewport(std::string* error) {
    if (canonical_viewport_->isInitialized()) return true;

    const int physicalWidth = std::max(1, static_cast<int>(std::lround(width() * devicePixelRatioF())));
    const int physicalHeight = std::max(1, static_cast<int>(std::lround(height() * devicePixelRatioF())));
    const QByteArray appPath = QCoreApplication::applicationDirPath().toUtf8();
    return canonical_viewport_->initialize(
        reinterpret_cast<void*>(winId()), physicalWidth, physicalHeight,
        std::filesystem::path(appPath.constData()), error);
}

bool EditorCanvas::loadCanonicalScenario(const std::string& path, std::string* error) {
    const auto parsed = ch::MapDocument::load_from_file(path);
    if (!parsed) {
        if (error != nullptr) *error = "Unable to open canonical scenario: " + path;
        return false;
    }

    if (!document_.loadScenario(path, error)) return false;
    if (!ensureCanonicalViewport(error)) return false;

    canonical_viewport_->loadDocument(*parsed);
    canonical_mode_ = true;
    tool_ = EditorTool::Inspect;
    history_.clear();
    hover_tile_.reset();
    camera_.zoom = 1.0F;
    centerCamera();
    render_timer_->start();
    if (onDocumentBoundsChanged) onDocumentBoundsChanged();
    update();
    return true;
}

void EditorCanvas::newScratchMap(const int width, const int height) {
    render_timer_->stop();
    canonical_mode_ = false;
    canonical_viewport_->shutdown();
    document_.newEmpty(width, height);
    history_.clear();
    hover_tile_.reset();
    tool_ = EditorTool::Inspect;
    camera_ = ch::CameraState{};
    camera_.zoom = 1.0F;
    centerCamera();
    if (onDocumentBoundsChanged) onDocumentBoundsChanged();
    update();
}

bool EditorCanvas::resizeScratchMap(const int width, const int height) {
    if (canonical_mode_) return false;
    if (stroke_active_) endStroke();

    if (!document_.resize(width, height)) return false;

    history_.clear();
    if (hover_tile_ && !document_.inBounds(hover_tile_->x(), hover_tile_->y())) {
        hover_tile_.reset();
    }
    centerCamera();
    if (onHistoryChanged) onHistoryChanged();
    if (onDocumentBoundsChanged) onDocumentBoundsChanged();
    update();
    return true;
}

void EditorCanvas::setTool(const EditorTool tool) {
    if (stroke_active_) endStroke();
    tool_ = canonical_mode_ ? EditorTool::Inspect : tool;
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

    const float centerX = (static_cast<float>(document_.minX()) + static_cast<float>(document_.maxX()) + 1.0F) * 0.5F;
    const float centerY = (static_cast<float>(document_.minY()) + static_cast<float>(document_.maxY()) + 1.0F) * 0.5F;
    const float viewportW = viewportWidth();
    const float viewportH = viewportHeight();
    const auto screen = ch::world_to_screen_point(centerX, centerY, probe, viewportW, viewportH);
    camera_.pan_x = viewportW * 0.5F - screen.x;
    camera_.pan_y = viewportH * 0.5F - screen.y;
    update();
}

void EditorCanvas::panBy(const float dx, const float dy) {
    camera_.pan_x += dx * coordinateScale();
    camera_.pan_y += dy * coordinateScale();
    update();
}

void EditorCanvas::undo() {
    if (canonical_mode_) return;
    if (stroke_active_) endStroke();
    if (history_.undo(document_)) {
        update();
        if (onHistoryChanged) onHistoryChanged();
    }
}

void EditorCanvas::redo() {
    if (canonical_mode_) return;
    if (stroke_active_) endStroke();
    if (history_.redo(document_)) {
        update();
        if (onHistoryChanged) onHistoryChanged();
    }
}

QPoint EditorCanvas::screenToTile(const QPointF& screen) const {
    const float scale = coordinateScale();
    const auto tile = ch::screen_to_tile_coord(
        static_cast<float>(screen.x()) * scale, static_cast<float>(screen.y()) * scale,
        camera_, viewportWidth(), viewportHeight());
    return {tile.x, tile.y};
}

void EditorCanvas::updateHover(const QPointF& screen) {
    const QPoint tile = screenToTile(screen);
    const bool inside = canonical_mode_
        ? (tile.x() >= ch::contracts::kMapMin && tile.x() <= ch::contracts::kMapMax
           && tile.y() >= ch::contracts::kMapMin && tile.y() <= ch::contracts::kMapMax)
        : document_.inBounds(tile.x(), tile.y());

    if (inside) {
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
    if (canonical_mode_ || tool_ == EditorTool::Inspect || !document_.inBounds(tile.x(), tile.y())) return;
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
    if (canonical_mode_ || !document_.inBounds(x, y)) return;

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
    if (canonical_mode_ && canonical_viewport_->isInitialized()) {
        canonical_viewport_->setCamera(camera_);
        if (hover_tile_) {
            canonical_viewport_->setHover(hover_tile_->x(), hover_tile_->y(), 1, true);
        } else {
            canonical_viewport_->setHover(0, 0, 1, false);
        }
        canonical_viewport_->renderFrame();
        return;
    }

    QPainter painter(this);
    painter.setRenderHint(QPainter::Antialiasing, false);
    painter.fillRect(rect(), QColor(44, 52, 55));

    const float viewportW = static_cast<float>(width());
    const float viewportH = static_cast<float>(height());
    QPen gridPen(QColor(45, 70, 55, 110));
    gridPen.setWidthF(1.0);

    const int minSum = document_.minX() + document_.minY();
    const int maxSum = document_.maxX() + document_.maxY();
    for (int sum = minSum; sum <= maxSum; ++sum) {
        const int startX = std::max(document_.minX(), sum - document_.maxY());
        const int endX = std::min(document_.maxX(), sum - document_.minY());
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

    const bool inspectGrab = event->button() == Qt::LeftButton && tool_ == EditorTool::Inspect;
    if (event->button() == Qt::MiddleButton || event->button() == Qt::RightButton || inspectGrab) {
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
        panBy(static_cast<float>(delta.x()), static_cast<float>(delta.y()));
        last_pan_position_ = event->position();
        return;
    }

    updateHover(event->position());
    if (stroke_active_ && (event->buttons() & Qt::LeftButton) && hover_tile_) {
        updateStroke(*hover_tile_);
    }
}

void EditorCanvas::mouseReleaseEvent(QMouseEvent* event) {
    if (event->button() == Qt::LeftButton && tool_ != EditorTool::Inspect) endStroke();

    if (event->button() == Qt::MiddleButton || event->button() == Qt::RightButton
        || (event->button() == Qt::LeftButton && tool_ == EditorTool::Inspect)) {
        pan_active_ = false;
        unsetCursor();
        updateHover(event->position());
    }
}

void EditorCanvas::wheelEvent(QWheelEvent* event) {
    const float factor = event->angleDelta().y() > 0 ? 1.15F : (1.0F / 1.15F);
    camera_.zoom = std::clamp(camera_.zoom * factor, 0.35F, 3.0F);
    updateHover(event->position());
    update();
}

void EditorCanvas::keyPressEvent(QKeyEvent* event) {
    const float step = (event->modifiers() & Qt::ShiftModifier) ? 96.0F : 48.0F;
    switch (event->key()) {
        case Qt::Key_Left:
        case Qt::Key_A:
            panBy(-step, 0.0F);
            event->accept();
            return;
        case Qt::Key_Right:
        case Qt::Key_D:
            panBy(step, 0.0F);
            event->accept();
            return;
        case Qt::Key_Up:
        case Qt::Key_W:
            panBy(0.0F, -step);
            event->accept();
            return;
        case Qt::Key_Down:
        case Qt::Key_S:
            panBy(0.0F, step);
            event->accept();
            return;
        case Qt::Key_Plus:
        case Qt::Key_Equal:
            camera_.zoom = std::clamp(camera_.zoom * 1.15F, 0.35F, 3.0F);
            update();
            event->accept();
            return;
        case Qt::Key_Minus:
            camera_.zoom = std::clamp(camera_.zoom / 1.15F, 0.35F, 3.0F);
            update();
            event->accept();
            return;
        default:
            break;
    }
    QWidget::keyPressEvent(event);
}

void EditorCanvas::leaveEvent(QEvent*) {
    hover_tile_.reset();
    if (stroke_active_) endStroke();
    if (pan_active_) {
        pan_active_ = false;
        unsetCursor();
    }
    update();
}

void EditorCanvas::resizeEvent(QResizeEvent* event) {
    QWidget::resizeEvent(event);
    if (canonical_mode_ && canonical_viewport_->isInitialized()) {
        const int physicalWidth = std::max(1, static_cast<int>(std::lround(width() * devicePixelRatioF())));
        const int physicalHeight = std::max(1, static_cast<int>(std::lround(height() * devicePixelRatioF())));
        canonical_viewport_->resize(physicalWidth, physicalHeight);
    }
}

} // namespace ch::editor
