#include "pine_tree_renderer.h"

#include "procedural_2d_primitives.h"

#include <QFont>
#include <QPainter>
#include <QPolygonF>

#include <algorithm>
#include <cmath>
#include <random>
#include <vector>

namespace ch::studio {
namespace {

using procedural2d::FillStroke;
using procedural2d::Stroke;

QPolygonF scaledAround(const QPolygonF& shape, const QPointF& center,
                       const qreal sx, const qreal sy, const QPointF& offset = {}) {
    QPolygonF result;
    result.reserve(shape.size());
    for (const QPointF& p : shape) {
        const QPointF d = p - center;
        result << QPointF(center.x() + d.x() * sx + offset.x(),
                          center.y() + d.y() * sy + offset.y());
    }
    return result;
}

QPolygonF translated(const QPolygonF& shape, const QPointF& offset) {
    QPolygonF result;
    result.reserve(shape.size());
    for (const QPointF& p : shape) result << p + offset;
    return result;
}

QPolygonF makeTier(const QPointF& center, const qreal half_width, const qreal height,
                   std::mt19937& rng) {
    std::uniform_real_distribution<qreal> jitter(-1.0, 1.0);
    const qreal j0 = jitter(rng) * 3.2;
    const qreal j1 = jitter(rng) * 3.8;
    const qreal j2 = jitter(rng) * 3.0;
    const qreal j3 = jitter(rng) * 2.6;

    const qreal x = center.x();
    const qreal y = center.y();
    const qreal w = half_width;
    const qreal h = height;

    return QPolygonF{
        QPointF(x + j0,             y - h * 0.58),
        QPointF(x - w * 0.25 + j1, y - h * 0.28),
        QPointF(x - w * 0.17,      y - h * 0.08),
        QPointF(x - w * 0.52 + j2, y + h * 0.08),
        QPointF(x - w * 0.39,      y + h * 0.22),
        QPointF(x - w + j3,        y + h * 0.39),
        QPointF(x - w * 0.70,      y + h * 0.48),
        QPointF(x - w * 0.28,      y + h * 0.60),
        QPointF(x,                 y + h * 0.47),
        QPointF(x + w * 0.30,      y + h * 0.60),
        QPointF(x + w * 0.72,      y + h * 0.48),
        QPointF(x + w + j2,        y + h * 0.39),
        QPointF(x + w * 0.40,      y + h * 0.22),
        QPointF(x + w * 0.55 + j1, y + h * 0.08),
        QPointF(x + w * 0.18,      y - h * 0.08),
        QPointF(x + w * 0.26 + j0, y - h * 0.28),
    };
}

void drawTrunk(QPainter& painter, const PineTreeSpec& spec, const QPointF& ground,
               const qreal crown_bottom_y) {
    const qreal half = spec.trunk_half_width_px;
    const qreal top_y = std::min(crown_bottom_y + 8.0,
                                 ground.y() - spec.trunk_height_px);

    const QPolygonF trunk{
        QPointF(ground.x() - half * 1.10, ground.y()),
        QPointF(ground.x() + half * 1.10, ground.y()),
        QPointF(ground.x() + half * 0.72, top_y),
        QPointF(ground.x() - half * 0.70, top_y),
    };

    procedural2d::polygon(
        painter, trunk,
        {spec.trunk, {QColor(47, 31, 22, 170), 1.0, Qt::RoundCap, Qt::RoundJoin}});

    procedural2d::polygon(
        painter,
        QPolygonF{
            QPointF(ground.x() - half * 0.75, ground.y() - 2.0),
            QPointF(ground.x() - half * 0.22, ground.y() - 2.0),
            QPointF(ground.x() - half * 0.10, top_y + 4.0),
            QPointF(ground.x() - half * 0.46, top_y + 5.0),
        },
        {spec.trunk_light, {Qt::transparent, 0.0}});

    procedural2d::polygon(
        painter,
        QPolygonF{
            QPointF(ground.x() + half * 0.20, ground.y() - 1.0),
            QPointF(ground.x() + half * 0.92, ground.y() - 1.0),
            QPointF(ground.x() + half * 0.63, top_y + 5.0),
            QPointF(ground.x() + half * 0.18, top_y + 4.0),
        },
        {spec.trunk_shadow, {Qt::transparent, 0.0}});
}

void drawNeedleAccents(QPainter& painter, const QPolygonF& tier, const QPointF& center,
                       const QColor& light, const QColor& shadow, const int index) {
    if (tier.size() < 16) return;

    const qreal light_width = std::max<qreal>(1.2, 2.1 - index * 0.08);
    procedural2d::polyline(
        painter,
        QPolygonF{tier[1], tier[3], tier[5]},
        {QColor(light.red(), light.green(), light.blue(), 135), light_width,
         Qt::RoundCap, Qt::RoundJoin});

    procedural2d::polyline(
        painter,
        QPolygonF{tier[11], tier[13], tier[15]},
        {QColor(shadow.red(), shadow.green(), shadow.blue(), 130), 1.4,
         Qt::RoundCap, Qt::RoundJoin});

    const QPointF branch_a(center.x() - 7.0, center.y() + 7.0);
    const QPointF branch_b(center.x() - 27.0 - index * 2.0, center.y() + 19.0);
    const QPointF branch_c(center.x() + 6.0, center.y() + 13.0);
    const QPointF branch_d(center.x() + 29.0 + index * 2.0, center.y() + 24.0);

    procedural2d::polyline(
        painter, QPolygonF{branch_a, branch_b},
        {QColor(shadow.red(), shadow.green(), shadow.blue(), 92), 1.25,
         Qt::RoundCap, Qt::RoundJoin});
    procedural2d::polyline(
        painter, QPolygonF{branch_c, branch_d},
        {QColor(shadow.red(), shadow.green(), shadow.blue(), 80), 1.1,
         Qt::RoundCap, Qt::RoundJoin});
}

void drawTreeBody(QPainter& painter, const PineTreeSpec& spec, const QRectF& bounds,
                  const bool draw_shadow) {
    const QPointF ground(bounds.center().x(), bounds.bottom() - 11.0);
    const qreal crown_top = bounds.top() + 14.0;
    const qreal crown_bottom = ground.y() - 37.0;

    if (draw_shadow) {
        procedural2d::ellipse(
            painter,
            QRectF(ground.x() - 58.0, ground.y() - 10.0, 116.0, 24.0),
            {spec.contact_shadow, {Qt::transparent, 0.0}});
    }

    drawTrunk(painter, spec, ground, crown_bottom);

    const int tiers = std::max(4, spec.tier_count);
    std::mt19937 rng(spec.seed);

    std::vector<QPolygonF> shapes;
    std::vector<QPointF> centers;
    shapes.reserve(tiers);
    centers.reserve(tiers);

    const qreal usable_h = crown_bottom - crown_top;
    for (int i = 0; i < tiers; ++i) {
        const qreal t = tiers == 1 ? 0.0
                                   : static_cast<qreal>(i) / static_cast<qreal>(tiers - 1);
        const qreal center_y = crown_top + usable_h * (0.08 + t * 0.86);
        const qreal half_w = 24.0 + t * (spec.crown_half_width_px - 24.0);
        const qreal tier_h = 66.0 + t * 23.0;
        const QPointF center(bounds.center().x() + std::sin(i * 1.63) * 2.4, center_y);
        centers.push_back(center);
        shapes.push_back(makeTier(center, half_w, tier_h, rng));
    }

    for (int i = tiers - 1; i >= 0; --i) {
        const QPolygonF& shape = shapes[i];
        const QPointF center = centers[i];

        procedural2d::polygon(
            painter, translated(shape, QPointF(0.0, 7.0)),
            {spec.foliage_deep, {Qt::transparent, 0.0}});

        const QColor main_color = (i % 2 == 0) ? spec.foliage : spec.foliage_mid;
        procedural2d::polygon(
            painter, shape,
            {main_color, {spec.foliage_shadow, 1.35, Qt::RoundCap, Qt::RoundJoin}});

        const QPolygonF light_patch = scaledAround(shape, center, 0.74, 0.62,
                                                   QPointF(-9.0, -8.0));
        painter.save();
        painter.setOpacity(0.68);
        procedural2d::polygon(
            painter, light_patch,
            {spec.foliage_light, {Qt::transparent, 0.0}});
        painter.restore();

        const QPolygonF lower_shadow = scaledAround(shape, center, 0.80, 0.44,
                                                     QPointF(7.0, 19.0));
        painter.save();
        painter.setOpacity(0.38);
        procedural2d::polygon(
            painter, lower_shadow,
            {spec.foliage_shadow, {Qt::transparent, 0.0}});
        painter.restore();

        drawNeedleAccents(painter, shape, center,
                          spec.foliage_light, spec.foliage_deep, i);
    }

    const QPointF top(bounds.center().x(), crown_top - 2.0);
    procedural2d::polygon(
        painter,
        QPolygonF{
            QPointF(top.x(), top.y() - 19.0),
            QPointF(top.x() - 15.0, top.y() + 19.0),
            QPointF(top.x() - 5.0, top.y() + 14.0),
            QPointF(top.x(), top.y() + 28.0),
            QPointF(top.x() + 6.0, top.y() + 14.0),
            QPointF(top.x() + 15.0, top.y() + 19.0),
        },
        {spec.foliage_light, {spec.foliage_shadow, 1.0, Qt::RoundCap, Qt::RoundJoin}});
}

QPolygonF canonicalTile(const QPointF& center) {
    return QPolygonF{
        center + QPointF(0.0, -32.0),
        center + QPointF(64.0, 0.0),
        center + QPointF(0.0, 32.0),
        center + QPointF(-64.0, 0.0),
    };
}

} // namespace

QImage PineTreeRenderer::renderTree(const PineTreeSpec& spec, const QSize& canvas) {
    QImage image(canvas, QImage::Format_RGBA8888);
    image.fill(Qt::transparent);

    QPainter painter(&image);
    painter.setRenderHint(QPainter::Antialiasing, true);
    painter.setRenderHint(QPainter::SmoothPixmapTransform, true);

    drawTreeBody(painter, spec,
                 QRectF(10.0, 8.0, canvas.width() - 20.0, canvas.height() - 18.0),
                 true);
    painter.end();
    return image;
}

QImage PineTreeRenderer::renderReviewSheet(const PineTreeSpec& spec, const QSize& canvas) {
    QImage image(canvas, QImage::Format_RGBA8888);
    image.fill(QColor("#71945f"));

    QPainter painter(&image);
    painter.setRenderHint(QPainter::Antialiasing, true);
    painter.setRenderHint(QPainter::SmoothPixmapTransform, true);

    painter.fillRect(QRectF(0, 0, canvas.width(), 110), QColor("#243c36"));
    painter.fillRect(QRectF(0, canvas.height() - 70, canvas.width(), 70), QColor("#5d7e50"));

    const QPointF tile_center(canvas.width() * 0.5, canvas.height() - 115.0);
    procedural2d::polygon(
        painter, canonicalTile(tile_center),
        {QColor("#82a86a"), {QColor(72, 103, 61, 150), 1.2,
                              Qt::RoundCap, Qt::RoundJoin}});

    const QImage tree = renderTree(spec, QSize(320, 448));
    const QPoint draw_at(static_cast<int>(canvas.width() * 0.5 - tree.width() * 0.5),
                         static_cast<int>(tile_center.y() - tree.height() + 23.0));
    painter.drawImage(draw_at, tree);

    QFont title = painter.font();
    title.setBold(true);
    title.setPointSize(18);
    painter.setFont(title);
    painter.setPen(QColor("#f2f0dc"));
    painter.drawText(QRectF(26, 19, canvas.width() - 52, 36),
                     Qt::AlignLeft | Qt::AlignVCenter,
                     QStringLiteral("PROCEDURAL 2D PINE TREE — V1"));

    QFont subtitle = painter.font();
    subtitle.setBold(false);
    subtitle.setPointSize(10);
    painter.setFont(subtitle);
    painter.setPen(QColor("#c8d8c6"));
    painter.drawText(QRectF(27, 59, canvas.width() - 54, 28),
                     Qt::AlignLeft | Qt::AlignVCenter,
                     QStringLiteral("transparent RGBA • deterministic seed • gameplay-scale silhouette"));

    painter.setPen(QColor("#dce6d5"));
    painter.drawText(QRectF(22, canvas.height() - 55, canvas.width() - 44, 30),
                     Qt::AlignCenter,
                     QStringLiteral("CH stylized evergreen / fixed 2D procedural renderer"));

    painter.end();
    return image;
}

} // namespace ch::studio
