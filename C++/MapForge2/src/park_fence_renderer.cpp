#include "park_fence_renderer.h"

#include "procedural_2d_primitives.h"

#include <QFont>
#include <QPainter>
#include <QPolygonF>

#include <algorithm>
#include <array>
#include <cmath>
#include <vector>

namespace ch::studio {
namespace {

struct LocalPoint {
    qreal x = 0.0;
    qreal y = 0.0;
};

LocalPoint rotateLocal(LocalPoint point, const ParkFenceRotation rotation) {
    switch (rotation) {
        case ParkFenceRotation::South: return point;
        case ParkFenceRotation::East: return {-point.y, point.x};
        case ParkFenceRotation::North: return {-point.x, -point.y};
        case ParkFenceRotation::West: return {point.y, -point.x};
    }
    return point;
}

QPointF projectLocal(const LocalPoint point, const qreal z_px, const QPointF& origin) {
    return {
        origin.x() + (point.x - point.y) * (ParkFenceRenderer::kTileWidthPx * 0.5),
        origin.y() + (point.x + point.y) * (ParkFenceRenderer::kTileHeightPx * 0.5) - z_px,
    };
}

qreal screenLength(const LocalPoint a, const LocalPoint b,
                   const ParkFenceRotation rotation, const QPointF& origin) {
    const QPointF pa = projectLocal(rotateLocal(a, rotation), 0.0, origin);
    const QPointF pb = projectLocal(rotateLocal(b, rotation), 0.0, origin);
    return std::hypot(pb.x() - pa.x(), pb.y() - pa.y());
}

LocalPoint lerpLocal(const LocalPoint a, const LocalPoint b, const qreal t) {
    return {a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t};
}

void drawPost(QPainter& painter, const ParkFenceSpec& spec, LocalPoint point,
              const ParkFenceRotation rotation, const QPointF& origin) {
    point = rotateLocal(point, rotation);
    const QPointF ground = projectLocal(point, 0.0, origin);
    const QPointF top = projectLocal(point, spec.post_height_px, origin);

    using namespace procedural2d;
    const qreal width = spec.post_width_px;
    roundedRect(painter,
                QRectF(top.x() - width * 0.5, top.y(), width, spec.post_height_px),
                1.2,
                {spec.metal_shadow, {QColor(5, 18, 14, 210), 0.8}});

    roundedRect(painter,
                QRectF(top.x() - width * 0.27, top.y() + 2.0,
                       width * 0.28, spec.post_height_px - 4.0),
                0.6,
                {spec.metal_light, {}});

    roundedRect(painter,
                QRectF(ground.x() - width * 0.72, ground.y() - 3.0,
                       width * 1.44, 4.0),
                1.0,
                {spec.metal_shadow, {QColor(4, 15, 12, 190), 0.7}});

    circle(painter, QPointF(top.x(), top.y() - 1.5), width * 0.56,
           {spec.finial, {QColor(5, 18, 14, 220), 0.8}});
    circle(painter, QPointF(top.x() - width * 0.16, top.y() - 2.7), width * 0.15,
           {QColor(88, 135, 113, 180), {}});
}

void drawSpear(QPainter& painter, const ParkFenceSpec& spec, const LocalPoint point,
               const ParkFenceRotation rotation, const QPointF& origin,
               const qreal height_px) {
    const LocalPoint rotated = rotateLocal(point, rotation);
    const QPointF top = projectLocal(rotated, height_px, origin);
    const QPointF tip = projectLocal(rotated, height_px + spec.spear_height_px, origin);
    const qreal half = std::max<qreal>(1.4, spec.picket_width_px * 1.15);

    procedural2d::polygon(
        painter,
        QPolygonF{QPointF(top.x() - half, top.y()), tip, QPointF(top.x() + half, top.y())},
        {spec.metal_light, {QColor(5, 18, 14, 205), 0.55}});
}

void drawSpan(QPainter& painter, const ParkFenceSpec& spec, const LocalPoint a,
              const LocalPoint b, const ParkFenceRotation rotation,
              const QPointF& origin, const qreal height_scale = 1.0) {
    using namespace procedural2d;

    const LocalPoint ar = rotateLocal(a, rotation);
    const LocalPoint br = rotateLocal(b, rotation);
    const qreal fence_h = spec.fence_height_px * height_scale;

    const QPointF ground_a = projectLocal(ar, 0.0, origin);
    const QPointF ground_b = projectLocal(br, 0.0, origin);
    polyline(painter,
             QPolygonF{ground_a + QPointF(3.0, 4.0), ground_b + QPointF(3.0, 4.0)},
             {spec.shadow, 5.0, Qt::RoundCap, Qt::RoundJoin});

    for (const qreal rail_z : {fence_h * 0.34, fence_h * 0.78}) {
        polyline(painter,
                 QPolygonF{projectLocal(ar, rail_z, origin), projectLocal(br, rail_z, origin)},
                 {spec.metal_shadow, spec.rail_width_px + 1.25, Qt::RoundCap, Qt::RoundJoin});
        polyline(painter,
                 QPolygonF{projectLocal(ar, rail_z + 0.8, origin),
                           projectLocal(br, rail_z + 0.8, origin)},
                 {spec.metal_light, spec.rail_width_px * 0.55, Qt::RoundCap, Qt::RoundJoin});
    }

    const qreal length = std::max<qreal>(1.0, screenLength(a, b, rotation, origin));
    const int count = std::max(2, static_cast<int>(std::floor(length / spec.picket_spacing_px)));
    for (int index = 1; index < count; ++index) {
        const qreal t = static_cast<qreal>(index) / static_cast<qreal>(count);
        const LocalPoint p = rotateLocal(lerpLocal(a, b, t), rotation);
        const QPointF bottom = projectLocal(p, 3.5, origin);
        const QPointF top = projectLocal(p, fence_h, origin);
        capsule(painter, bottom, top, spec.picket_width_px * 0.5,
                {spec.metal, {QColor(5, 18, 14, 210), 0.5}});
        drawSpear(painter, spec, lerpLocal(a, b, t), rotation, origin, fence_h);
    }
}

void drawGate(QPainter& painter, const ParkFenceSpec& spec,
              const ParkFenceRotation rotation, const QPointF& origin) {
    const qreal half_gap = spec.gate_gap_world * 0.5;
    const LocalPoint outer_a{-0.50, 0.0};
    const LocalPoint gate_a{-half_gap, 0.0};
    const LocalPoint gate_b{half_gap, 0.0};
    const LocalPoint outer_b{0.50, 0.0};

    drawSpan(painter, spec, outer_a, gate_a, rotation, origin);
    drawSpan(painter, spec, gate_b, outer_b, rotation, origin);
    drawSpan(painter, spec, gate_a, gate_b, rotation, origin, 0.83);

    drawPost(painter, spec, outer_a, rotation, origin);
    drawPost(painter, spec, gate_a, rotation, origin);
    drawPost(painter, spec, gate_b, rotation, origin);
    drawPost(painter, spec, outer_b, rotation, origin);

    const LocalPoint center = rotateLocal({0.0, 0.0}, rotation);
    const QPointF latch = projectLocal(center, spec.fence_height_px * 0.43, origin);
    procedural2d::circle(painter, latch, 2.2,
                         {QColor("#b39a58"), {QColor(70, 55, 27, 210), 0.6}});
}

const char* pieceLabel(const ParkFencePiece piece) {
    switch (piece) {
        case ParkFencePiece::Straight: return "STRAIGHT";
        case ParkFencePiece::Corner: return "CORNER";
        case ParkFencePiece::End: return "END";
        case ParkFencePiece::Gate: return "GATE";
    }
    return "FENCE";
}

const char* rotationLabel(const ParkFenceRotation rotation) {
    switch (rotation) {
        case ParkFenceRotation::South: return "S";
        case ParkFenceRotation::East: return "E";
        case ParkFenceRotation::North: return "N";
        case ParkFenceRotation::West: return "W";
    }
    return "?";
}

} // namespace

QImage ParkFenceRenderer::renderPiece(const ParkFenceSpec& spec,
                                      const ParkFencePiece piece,
                                      const ParkFenceRotation rotation,
                                      const QSize& canvas) {
    QImage image(canvas, QImage::Format_RGBA8888);
    image.fill(Qt::transparent);

    QPainter painter(&image);
    painter.setRenderHint(QPainter::Antialiasing, true);
    const QPointF origin(canvas.width() * 0.5, canvas.height() * 0.70);

    switch (piece) {
        case ParkFencePiece::Straight: {
            const LocalPoint a{-0.50, 0.0};
            const LocalPoint b{0.50, 0.0};
            drawSpan(painter, spec, a, b, rotation, origin);
            drawPost(painter, spec, a, rotation, origin);
            drawPost(painter, spec, b, rotation, origin);
            break;
        }
        case ParkFencePiece::Corner: {
            const LocalPoint a{-0.50, 0.0};
            const LocalPoint c{0.0, 0.0};
            const LocalPoint b{0.0, 0.50};
            drawSpan(painter, spec, a, c, rotation, origin);
            drawSpan(painter, spec, c, b, rotation, origin);
            drawPost(painter, spec, a, rotation, origin);
            drawPost(painter, spec, c, rotation, origin);
            drawPost(painter, spec, b, rotation, origin);
            break;
        }
        case ParkFencePiece::End: {
            const LocalPoint a{0.0, 0.0};
            const LocalPoint b{0.50, 0.0};
            drawSpan(painter, spec, a, b, rotation, origin);
            drawPost(painter, spec, a, rotation, origin);
            drawPost(painter, spec, b, rotation, origin);
            break;
        }
        case ParkFencePiece::Gate:
            drawGate(painter, spec, rotation, origin);
            break;
    }

    painter.end();
    return image;
}

QImage ParkFenceRenderer::renderReviewSheet(const ParkFenceSpec& spec, const QSize& cell) {
    constexpr std::array<ParkFencePiece, 4> pieces = {
        ParkFencePiece::Straight,
        ParkFencePiece::Corner,
        ParkFencePiece::End,
        ParkFencePiece::Gate,
    };
    constexpr std::array<ParkFenceRotation, 4> rotations = {
        ParkFenceRotation::South,
        ParkFenceRotation::East,
        ParkFenceRotation::West,
        ParkFenceRotation::North,
    };

    QImage sheet(cell.width() * static_cast<int>(pieces.size()),
                 cell.height() * static_cast<int>(rotations.size()),
                 QImage::Format_RGBA8888);
    sheet.fill(QColor("#6f915f"));

    QPainter painter(&sheet);
    painter.setRenderHint(QPainter::Antialiasing, true);
    QFont font = painter.font();
    font.setBold(true);
    font.setPointSize(9);
    painter.setFont(font);

    for (int row = 0; row < static_cast<int>(rotations.size()); ++row) {
        for (int column = 0; column < static_cast<int>(pieces.size()); ++column) {
            const QRect cell_rect(column * cell.width(), row * cell.height(),
                                  cell.width(), cell.height());
            painter.fillRect(cell_rect.adjusted(1, 1, -1, -1),
                             ((row + column) & 1) ? QColor("#789c65") : QColor("#739660"));

            const QPointF center(cell_rect.center().x(), cell_rect.center().y() + 18.0);
            const QPolygonF diamond{
                center + QPointF(0.0, -32.0),
                center + QPointF(64.0, 0.0),
                center + QPointF(0.0, 32.0),
                center + QPointF(-64.0, 0.0),
            };
            procedural2d::polygon(painter, diamond,
                                  {QColor(126, 159, 101, 210),
                                   {QColor(73, 105, 63, 120), 1.0}});

            const QImage piece = renderPiece(spec, pieces[column], rotations[row],
                                             QSize(cell.width(), cell.height() - 24));
            painter.drawImage(cell_rect.topLeft() + QPoint(0, 16), piece);

            painter.setPen(QColor("#edf2df"));
            painter.drawText(cell_rect.adjusted(8, 5, -8, -5),
                             Qt::AlignTop | Qt::AlignHCenter,
                             QString::fromLatin1("%1 / %2")
                                 .arg(QString::fromLatin1(pieceLabel(pieces[column])))
                                 .arg(QString::fromLatin1(rotationLabel(rotations[row]))));
        }
    }

    painter.end();
    return sheet;
}

} // namespace ch::studio
