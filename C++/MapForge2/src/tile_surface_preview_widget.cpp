#include "tile_surface_preview_widget.h"

#include <QPainter>
#include <QPaintEvent>
#include <QPen>

#include <algorithm>

namespace ch::studio {
namespace {

constexpr qreal kTileWidth = 128.0;
constexpr qreal kTileHeight = 64.0;

} // namespace

TileSurfacePreviewWidget::TileSurfacePreviewWidget(QWidget* parent)
    : QWidget(parent) {
    setMinimumSize(480, 360);
}

void TileSurfacePreviewWidget::setTile(const QPixmap& tile) {
    tile_ = tile;
    update();
}

void TileSurfacePreviewWidget::setAutotileTiles(const QHash<int, QPixmap>& tiles) {
    autotile_tiles_ = tiles;
    update();
}

void TileSurfacePreviewWidget::clearTile() {
    tile_ = QPixmap();
    update();
}

void TileSurfacePreviewWidget::clearAutotileTiles() {
    autotile_tiles_.clear();
    update();
}

void TileSurfacePreviewWidget::setRepeatCount(const int repeat_x, const int repeat_y) {
    repeat_x_ = std::clamp(repeat_x, 1, 12);
    repeat_y_ = std::clamp(repeat_y, 1, 12);
    update();
}

void TileSurfacePreviewWidget::setShowGrid(const bool show_grid) {
    show_grid_ = show_grid;
    update();
}

void TileSurfacePreviewWidget::setAutotileMask(const int mask) {
    autotile_mask_ = std::clamp(mask, 0, 15);
    update();
}

const QPixmap* TileSurfacePreviewWidget::tileForMask(const int mask) const {
    const auto it = autotile_tiles_.constFind(mask);
    if (it != autotile_tiles_.cend() && !it.value().isNull()) return &it.value();
    if (!tile_.isNull()) return &tile_;
    return nullptr;
}

QPointF TileSurfacePreviewWidget::projectTile(const qreal tile_x, const qreal tile_y) const {
    const qreal span = std::max(repeat_x_, repeat_y_);
    const QPointF origin(width() * 0.5,
                         std::max(72.0, height() * 0.22 - span * 2.0));
    return {
        origin.x() + (tile_x - tile_y) * (kTileWidth * 0.5),
        origin.y() + (tile_x + tile_y) * (kTileHeight * 0.5),
    };
}

void TileSurfacePreviewWidget::paintEvent(QPaintEvent* event) {
    Q_UNUSED(event);

    QPainter painter(this);
    painter.setRenderHint(QPainter::Antialiasing, true);
    painter.setRenderHint(QPainter::SmoothPixmapTransform, false);
    painter.fillRect(rect(), QColor(31, 31, 31));

    const QPixmap* selected = tileForMask(autotile_mask_);

    for (int y = 0; y < repeat_y_; ++y) {
        for (int x = 0; x < repeat_x_; ++x) {
            const QPointF north = projectTile(x, y);
            const QPointF east = projectTile(x + 1, y);
            const QPointF west = projectTile(x, y + 1);
            const QPointF top_left(north.x() - kTileWidth * 0.5, north.y());

            if (selected != nullptr) {
                painter.drawPixmap(QRectF(top_left, QSizeF(kTileWidth, kTileHeight)), *selected, selected->rect());
            }

            if (show_grid_) {
                QPolygonF diamond;
                diamond << north << east << projectTile(x + 1, y + 1) << west;
                painter.setPen(QPen(QColor(255, 255, 255, 72), 1.0));
                painter.setBrush(Qt::NoBrush);
                painter.drawPolygon(diamond);
            }
        }
    }

    painter.setPen(QColor(220, 220, 220));
    painter.drawText(QRectF(12, 10, width() - 24, 22), Qt::AlignLeft | Qt::AlignVCenter,
                     QStringLiteral("Tile/Surface continuity preview — 128×64 — repeat %1×%2 — mask %3")
                         .arg(repeat_x_)
                         .arg(repeat_y_)
                         .arg(autotile_mask_, 2, 10, QLatin1Char('0')));

    if (selected == nullptr) {
        painter.setPen(QColor(185, 185, 185));
        painter.drawText(rect().adjusted(20, 40, -20, -20), Qt::AlignCenter,
                         QStringLiteral("No tile assigned for this mask\n\nLoad a base tile or one of the 16 autotile PNGs."));
    }
}

} // namespace ch::studio
