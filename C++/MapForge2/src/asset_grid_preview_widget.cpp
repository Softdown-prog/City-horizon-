#include "asset_grid_preview_widget.h"

#include <QPainter>
#include <QPaintEvent>
#include <QPen>

#include <algorithm>

namespace ch::studio {
namespace {

constexpr qreal kTileWidth = 128.0;
constexpr qreal kTileHeight = 64.0;

} // namespace

AssetGridPreviewWidget::AssetGridPreviewWidget(QWidget* parent)
    : QWidget(parent) {
    setMinimumSize(480, 480);
}

void AssetGridPreviewWidget::setSprite(const QPixmap& sprite) {
    sprite_ = sprite;
    update();
}

void AssetGridPreviewWidget::clearSprite() {
    sprite_ = QPixmap();
    update();
}

void AssetGridPreviewWidget::setFootprint(const QSize& footprint_tiles) {
    footprint_tiles_.setWidth(std::max(1, footprint_tiles.width()));
    footprint_tiles_.setHeight(std::max(1, footprint_tiles.height()));
    update();
}

void AssetGridPreviewWidget::setAnchorNormalized(const QPointF& anchor_normalized) {
    anchor_normalized_ = anchor_normalized;
    update();
}

void AssetGridPreviewWidget::setDirectionLabel(const QString& direction_label) {
    direction_label_ = direction_label;
    update();
}

QPointF AssetGridPreviewWidget::projectTile(const qreal tile_x, const qreal tile_y) const {
    const QPointF origin(width() * 0.5, height() * 0.58);
    return {
        origin.x() + (tile_x - tile_y) * (kTileWidth * 0.5),
        origin.y() + (tile_x + tile_y) * (kTileHeight * 0.5),
    };
}

void AssetGridPreviewWidget::paintEvent(QPaintEvent* event) {
    Q_UNUSED(event);

    QPainter painter(this);
    painter.setRenderHint(QPainter::Antialiasing, true);
    painter.fillRect(rect(), QColor(36, 36, 36));

    const int margin = 2;
    const int grid_w = footprint_tiles_.width() + margin * 2;
    const int grid_h = footprint_tiles_.height() + margin * 2;

    QPen grid_pen(QColor(86, 86, 86));
    grid_pen.setWidthF(1.0);
    painter.setPen(grid_pen);

    for (int y = -margin; y < grid_h - margin; ++y) {
        for (int x = -margin; x < grid_w - margin; ++x) {
            const QPointF north = projectTile(x, y);
            const QPointF east = projectTile(x + 1, y);
            const QPointF south = projectTile(x + 1, y + 1);
            const QPointF west = projectTile(x, y + 1);
            QPolygonF diamond;
            diamond << north << east << south << west;
            painter.drawPolygon(diamond);
        }
    }

    QPen footprint_pen(QColor(230, 190, 74));
    footprint_pen.setWidthF(2.5);
    painter.setPen(footprint_pen);
    for (int y = 0; y < footprint_tiles_.height(); ++y) {
        for (int x = 0; x < footprint_tiles_.width(); ++x) {
            const QPointF north = projectTile(x, y);
            const QPointF east = projectTile(x + 1, y);
            const QPointF south = projectTile(x + 1, y + 1);
            const QPointF west = projectTile(x, y + 1);
            QPolygonF diamond;
            diamond << north << east << south << west;
            painter.drawPolygon(diamond);
        }
    }

    if (!sprite_.isNull()) {
        const QPointF footprint_anchor = projectTile(
            footprint_tiles_.width() * anchor_normalized_.x(),
            footprint_tiles_.height() * anchor_normalized_.y());
        const QPointF sprite_anchor(sprite_.width() * anchor_normalized_.x(),
                                    sprite_.height() * anchor_normalized_.y());
        const QPointF top_left = footprint_anchor - sprite_anchor;
        painter.drawPixmap(top_left, sprite_);
    } else {
        painter.setPen(QColor(190, 190, 190));
        painter.drawText(rect().adjusted(20, 20, -20, -20), Qt::AlignCenter,
                         QStringLiteral("No sprite assigned\n\nAssign a direction PNG to see it\non the CH_CAMERA_V1 gameplay grid."));
    }

    painter.setPen(QColor(210, 210, 210));
    painter.drawText(QRectF(12, 10, width() - 24, 24), Qt::AlignLeft | Qt::AlignVCenter,
                     QStringLiteral("Gameplay grid preview — %1 — footprint %2×%3")
                         .arg(direction_label_)
                         .arg(footprint_tiles_.width())
                         .arg(footprint_tiles_.height()));
}

} // namespace ch::studio
