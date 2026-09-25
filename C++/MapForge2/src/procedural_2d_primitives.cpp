#include "procedural_2d_primitives.h"

#include <QPainterPath>
#include <QtMath>

#include <algorithm>
#include <cmath>

namespace ch::studio::procedural2d {
namespace {

QPen makePen(const Stroke& stroke) {
    if (stroke.width <= 0.0 || stroke.color.alpha() == 0) return QPen(Qt::NoPen);
    QPen pen(stroke.color, stroke.width, Qt::SolidLine, stroke.cap, stroke.join);
    pen.setMiterLimit(3.0);
    return pen;
}

QPointF normalized(const QPointF& p) {
    const qreal length = std::hypot(p.x(), p.y());
    if (length <= 1.0e-6) return QPointF();
    return QPointF(p.x() / length, p.y() / length);
}

QPointF normalFor(const QPointF& a, const QPointF& b) {
    const QPointF tangent = normalized(b - a);
    return QPointF(-tangent.y(), tangent.x());
}

QPolygonF starShape(const QPointF& center, const qreal outer_radius,
                    const qreal inner_radius, const int points,
                    const qreal rotation_radians) {
    QPolygonF shape;
    const int count = std::max(2, points);
    shape.reserve(count * 2);
    for (int i = 0; i < count * 2; ++i) {
        const qreal radius = (i % 2 == 0) ? outer_radius : inner_radius;
        const qreal angle = rotation_radians
            + static_cast<qreal>(i) * M_PI / static_cast<qreal>(count);
        shape << QPointF(center.x() + std::cos(angle) * radius,
                         center.y() + std::sin(angle) * radius);
    }
    return shape;
}

} // namespace

QPointF lerp(const QPointF& a, const QPointF& b, const qreal t) {
    const qreal u = std::clamp(t, 0.0, 1.0);
    return QPointF(a.x() + (b.x() - a.x()) * u,
                   a.y() + (b.y() - a.y()) * u);
}

QPointF quadraticPoint(const QPointF& a, const QPointF& control,
                       const QPointF& b, const qreal t) {
    const qreal u = std::clamp(t, 0.0, 1.0);
    const qreal inv = 1.0 - u;
    return a * (inv * inv) + control * (2.0 * inv * u) + b * (u * u);
}

QPolygonF insetQuad(const QPolygonF& quad, const qreal amount) {
    if (quad.size() != 4 || amount <= 0.0) return quad;
    QPointF center;
    for (const QPointF& point : quad) center += point;
    center /= 4.0;

    QPolygonF result;
    result.reserve(4);
    for (const QPointF& point : quad) {
        const QPointF direction = center - point;
        const qreal distance = std::hypot(direction.x(), direction.y());
        if (distance <= 1.0e-6) {
            result << point;
        } else {
            const qreal t = std::min<qreal>(1.0, amount / distance);
            result << lerp(point, center, t);
        }
    }
    return result;
}

QPolygonF offsetQuad(const QPolygonF& quad, const QPointF& offset) {
    QPolygonF result;
    result.reserve(quad.size());
    for (const QPointF& point : quad) result << point + offset;
    return result;
}

QPolygonF extrudedSide(const QPointF& a, const QPointF& b, const QPointF& offset) {
    return QPolygonF{a, b, b + offset, a + offset};
}

void polygon(QPainter& painter, const QPolygonF& shape, const FillStroke& style) {
    painter.save();
    painter.setPen(makePen(style.stroke));
    painter.setBrush(style.fill.alpha() == 0 ? Qt::NoBrush : QBrush(style.fill));
    painter.drawPolygon(shape);
    painter.restore();
}

void polyline(QPainter& painter, const QPolygonF& points, const Stroke& stroke,
              const bool closed) {
    if (points.size() < 2) return;
    painter.save();
    painter.setBrush(Qt::NoBrush);
    painter.setPen(makePen(stroke));
    if (closed) painter.drawPolygon(points);
    else painter.drawPolyline(points);
    painter.restore();
}

void roundedRect(QPainter& painter, const QRectF& rect, const qreal radius,
                 const FillStroke& style) {
    painter.save();
    painter.setPen(makePen(style.stroke));
    painter.setBrush(style.fill.alpha() == 0 ? Qt::NoBrush : QBrush(style.fill));
    painter.drawRoundedRect(rect, radius, radius);
    painter.restore();
}

void ellipse(QPainter& painter, const QRectF& rect, const FillStroke& style) {
    painter.save();
    painter.setPen(makePen(style.stroke));
    painter.setBrush(style.fill.alpha() == 0 ? Qt::NoBrush : QBrush(style.fill));
    painter.drawEllipse(rect);
    painter.restore();
}

void circle(QPainter& painter, const QPointF& center, const qreal radius,
            const FillStroke& style) {
    ellipse(painter, QRectF(center.x() - radius, center.y() - radius,
                           radius * 2.0, radius * 2.0), style);
}

void capsule(QPainter& painter, const QPointF& a, const QPointF& b, const qreal radius,
             const FillStroke& style) {
    if (radius <= 0.0) return;
    const QPointF n = normalFor(a, b) * radius;
    QPainterPath path;
    path.moveTo(a + n);
    path.lineTo(b + n);
    path.arcTo(QRectF(b.x() - radius, b.y() - radius,
                      radius * 2.0, radius * 2.0),
               std::atan2(n.y(), n.x()) * 180.0 / M_PI, -180.0);
    path.lineTo(a - n);
    path.arcTo(QRectF(a.x() - radius, a.y() - radius,
                      radius * 2.0, radius * 2.0),
               std::atan2(-n.y(), -n.x()) * 180.0 / M_PI, -180.0);
    path.closeSubpath();

    painter.save();
    painter.setPen(makePen(style.stroke));
    painter.setBrush(style.fill.alpha() == 0 ? Qt::NoBrush : QBrush(style.fill));
    painter.drawPath(path);
    painter.restore();
}

void star(QPainter& painter, const QPointF& center, const qreal outer_radius,
          const qreal inner_radius, const int points, const qreal rotation_radians,
          const FillStroke& style) {
    polygon(painter, starShape(center, outer_radius, inner_radius, points,
                               rotation_radians), style);
}

void beveledQuad(QPainter& painter, const QPolygonF& quad, const BevelStyle& style) {
    if (quad.size() != 4) return;
    polygon(painter, quad, {style.fill, {style.outline, style.outline_px,
                                         Qt::SquareCap, Qt::MiterJoin}});
    const qreal bevel = std::max<qreal>(0.0, style.bevel_px);
    if (bevel <= 0.0) return;

    const QPolygonF inner = insetQuad(quad, bevel);
    if (inner.size() != 4) return;
    polygon(painter, QPolygonF{quad[0], quad[1], inner[1], inner[0]},
            {style.light, {Qt::transparent, 0.0}});
    polygon(painter, QPolygonF{quad[3], quad[0], inner[0], inner[3]},
            {style.light, {Qt::transparent, 0.0}});
    polygon(painter, QPolygonF{quad[1], quad[2], inner[2], inner[1]},
            {style.shadow, {Qt::transparent, 0.0}});
    polygon(painter, QPolygonF{quad[2], quad[3], inner[3], inner[2]},
            {style.shadow, {Qt::transparent, 0.0}});
}

void insetPanel(QPainter& painter, const QPolygonF& quad, const qreal inset_px,
                const BevelStyle& frame, const FillStroke& center) {
    if (quad.size() != 4) return;
    beveledQuad(painter, quad, frame);
    polygon(painter, insetQuad(quad, std::max<qreal>(0.0, inset_px)), center);
}

void extrudedQuad(QPainter& painter, const QPolygonF& front, const QPointF& depth,
                  const FillStroke& front_style, const FillStroke& side_style,
                  const FillStroke& top_style) {
    if (front.size() != 4) return;
    const QPolygonF back = offsetQuad(front, depth);
    polygon(painter, QPolygonF{front[0], front[1], back[1], back[0]}, top_style);
    polygon(painter, QPolygonF{front[1], front[2], back[2], back[1]}, side_style);
    polygon(painter, front, front_style);
}

void stripedQuad(QPainter& painter, const QPolygonF& quad, const int stripe_count,
                 const QColor& first, const QColor& second, const Stroke& outline) {
    if (quad.size() != 4 || stripe_count <= 0) return;
    for (int stripe = 0; stripe < stripe_count; ++stripe) {
        const qreal t0 = static_cast<qreal>(stripe) / stripe_count;
        const qreal t1 = static_cast<qreal>(stripe + 1) / stripe_count;
        QPolygonF cell{
            lerp(quad[0], quad[1], t0),
            lerp(quad[0], quad[1], t1),
            lerp(quad[3], quad[2], t1),
            lerp(quad[3], quad[2], t0),
        };
        polygon(painter, cell, {stripe % 2 == 0 ? first : second, {Qt::transparent, 0.0}});
    }
    if (outline.width > 0.0 && outline.color.alpha() > 0)
        polyline(painter, quad, outline, true);
}

void quadraticRibbon(QPainter& painter, const QPointF& a0, const QPointF& a1,
                     const QPointF& b0, const QPointF& b1,
                     const QPointF& control_offset,
                     const FillStroke& style) {
    const QPointF ac = (a0 + a1) * 0.5 + control_offset;
    const QPointF bc = (b0 + b1) * 0.5 + control_offset;
    QPainterPath path;
    path.moveTo(a0);
    path.quadTo(ac, a1);
    path.lineTo(b1);
    path.quadTo(bc, b0);
    path.closeSubpath();

    painter.save();
    painter.setPen(makePen(style.stroke));
    painter.setBrush(style.fill.alpha() == 0 ? Qt::NoBrush : QBrush(style.fill));
    painter.drawPath(path);
    painter.restore();
}

void scallopedEdge(QPainter& painter, const QPointF& a, const QPointF& b,
                   const int scallops, const qreal depth_px, const Stroke& stroke) {
    if (scallops <= 0 || stroke.width <= 0.0) return;
    const QPointF n = normalFor(a, b) * depth_px;
    QPainterPath path;
    path.moveTo(a);
    for (int i = 0; i < scallops; ++i) {
        const qreal t0 = static_cast<qreal>(i) / scallops;
        const qreal t1 = static_cast<qreal>(i + 1) / scallops;
        const QPointF p0 = lerp(a, b, t0);
        const QPointF p1 = lerp(a, b, t1);
        const QPointF c = (p0 + p1) * 0.5 + n;
        path.quadTo(c, p1);
    }
    painter.save();
    painter.setBrush(Qt::NoBrush);
    painter.setPen(makePen(stroke));
    painter.drawPath(path);
    painter.restore();
}

void contactShadow(QPainter& painter, const QPolygonF& footprint,
                   const ShadowStyle& style) {
    if (footprint.isEmpty() || style.layers <= 0) return;
    painter.save();
    painter.setPen(Qt::NoPen);
    for (int layer = style.layers; layer >= 1; --layer) {
        const qreal t = static_cast<qreal>(layer) / style.layers;
        QColor color = style.color;
        color.setAlphaF(style.color.alphaF() * (0.35 + 0.65 * (1.0 - t)));
        const QPointF offset = style.offset + QPointF(0.0, style.spread_px * t * 0.35);
        painter.setBrush(color);
        painter.drawPolygon(offsetQuad(footprint, offset));
    }
    painter.restore();
}

} // namespace ch::studio::procedural2d
