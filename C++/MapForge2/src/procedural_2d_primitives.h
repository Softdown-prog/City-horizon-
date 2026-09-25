#pragma once

#include <QColor>
#include <QPainter>
#include <QPainterPath>
#include <QPointF>
#include <QPolygonF>
#include <QRectF>
#include <QVector>

namespace ch::studio::procedural2d {

struct Stroke {
    QColor color = Qt::transparent;
    qreal width = 0.0;
    Qt::PenCapStyle cap = Qt::RoundCap;
    Qt::PenJoinStyle join = Qt::RoundJoin;
};

struct FillStroke {
    QColor fill = Qt::transparent;
    Stroke stroke{};
};

struct BevelStyle {
    QColor fill = Qt::transparent;
    QColor light = Qt::transparent;
    QColor shadow = Qt::transparent;
    QColor outline = Qt::transparent;
    qreal bevel_px = 1.5;
    qreal outline_px = 0.75;
};

struct ShadowStyle {
    QColor color = QColor(20, 24, 28, 52);
    QPointF offset = QPointF(2.0, 3.0);
    qreal spread_px = 2.0;
    int layers = 3;
};

QPointF lerp(const QPointF& a, const QPointF& b, qreal t);
QPointF quadraticPoint(const QPointF& a, const QPointF& control,
                       const QPointF& b, qreal t);
QPolygonF insetQuad(const QPolygonF& quad, qreal amount);
QPolygonF offsetQuad(const QPolygonF& quad, const QPointF& offset);
QPolygonF extrudedSide(const QPointF& a, const QPointF& b, const QPointF& offset);

void polygon(QPainter& painter, const QPolygonF& shape, const FillStroke& style);
void polyline(QPainter& painter, const QPolygonF& points, const Stroke& stroke,
              bool closed = false);
void roundedRect(QPainter& painter, const QRectF& rect, qreal radius,
                 const FillStroke& style);
void ellipse(QPainter& painter, const QRectF& rect, const FillStroke& style);
void circle(QPainter& painter, const QPointF& center, qreal radius,
            const FillStroke& style);
void capsule(QPainter& painter, const QPointF& a, const QPointF& b, qreal radius,
             const FillStroke& style);
void star(QPainter& painter, const QPointF& center, qreal outer_radius,
          qreal inner_radius, int points, qreal rotation_radians,
          const FillStroke& style);

void beveledQuad(QPainter& painter, const QPolygonF& quad, const BevelStyle& style);
void insetPanel(QPainter& painter, const QPolygonF& quad, qreal inset_px,
                const BevelStyle& frame, const FillStroke& center);
void extrudedQuad(QPainter& painter, const QPolygonF& front, const QPointF& depth,
                  const FillStroke& front_style, const FillStroke& side_style,
                  const FillStroke& top_style);
void stripedQuad(QPainter& painter, const QPolygonF& quad, int stripe_count,
                 const QColor& first, const QColor& second,
                 const Stroke& outline = {});

void quadraticRibbon(QPainter& painter, const QPointF& a0, const QPointF& a1,
                     const QPointF& b0, const QPointF& b1,
                     const QPointF& control_offset,
                     const FillStroke& style);
void scallopedEdge(QPainter& painter, const QPointF& a, const QPointF& b,
                   int scallops, qreal depth_px, const Stroke& stroke);
void contactShadow(QPainter& painter, const QPolygonF& footprint,
                   const ShadowStyle& style);

} // namespace ch::studio::procedural2d
