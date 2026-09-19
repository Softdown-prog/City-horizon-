#include "carousel_part_library.h"

#include <QBrush>
#include <QColor>
#include <QJsonArray>
#include <QLinearGradient>
#include <QPainter>
#include <QPainterPath>
#include <QPen>
#include <QRadialGradient>

#include <algorithm>

namespace ch::studio {
namespace {

constexpr const char* kBaseId = "carousel.base.classic.v1";
constexpr const char* kPlatformId = "carousel.platform.classic.v1";
constexpr const char* kCanopyId = "carousel.canopy.classic.v1";
constexpr const char* kPoleId = "carousel.center_pole.classic.v1";
constexpr const char* kHorseId = "carousel.horse.classic.v1";
constexpr const char* kFinialId = "carousel.ornament.finial.v1";
constexpr const char* kRosetteId = "carousel.ornament.rosette.v1";

QColor mix(const QColor& a, const QColor& b, const qreal t) {
    const qreal clamped = std::clamp(t, 0.0, 1.0);
    return QColor::fromRgbF(
        a.redF() + (b.redF() - a.redF()) * clamped,
        a.greenF() + (b.greenF() - a.greenF()) * clamped,
        a.blueF() + (b.blueF() - a.blueF()) * clamped,
        a.alphaF() + (b.alphaF() - a.alphaF()) * clamped);
}

QColor lightened(const QColor& c, const qreal amount) {
    return mix(c, QColor("#fff4df"), amount);
}

QColor darkened(const QColor& c, const qreal amount) {
    return mix(c, QColor("#2c3135"), amount);
}

void setupPainter(QPainter& painter) {
    painter.setRenderHint(QPainter::Antialiasing, true);
    painter.setRenderHint(QPainter::SmoothPixmapTransform, true);
}

void drawBase(QPainter& p, const QRectF& r, const QColor& primary, const QColor& outline) {
    const QRectF lower(r.left() + r.width() * 0.05, r.top() + r.height() * 0.43,
                       r.width() * 0.90, r.height() * 0.42);
    const QRectF upper(r.left() + r.width() * 0.10, r.top() + r.height() * 0.26,
                       r.width() * 0.80, r.height() * 0.38);

    QLinearGradient body(lower.topLeft(), lower.bottomLeft());
    body.setColorAt(0.0, lightened(primary, 0.22));
    body.setColorAt(0.52, primary);
    body.setColorAt(1.0, darkened(primary, 0.28));
    p.setPen(QPen(outline, 1.4));
    p.setBrush(body);
    p.drawEllipse(lower);

    QLinearGradient cap(upper.topLeft(), upper.bottomLeft());
    cap.setColorAt(0.0, lightened(primary, 0.34));
    cap.setColorAt(1.0, darkened(primary, 0.10));
    p.setBrush(cap);
    p.drawEllipse(upper);

    p.setPen(QPen(lightened(primary, 0.55), 1.2));
    p.drawArc(upper.adjusted(5, 4, -5, -6), 20 * 16, 140 * 16);
}

void drawPlatform(QPainter& p, const QRectF& r, const QColor& primary, const QColor& outline) {
    const QRectF deck(r.left() + r.width() * 0.04, r.top() + r.height() * 0.22,
                      r.width() * 0.92, r.height() * 0.56);
    QLinearGradient gradient(deck.topLeft(), deck.bottomLeft());
    gradient.setColorAt(0.0, lightened(primary, 0.30));
    gradient.setColorAt(0.45, primary);
    gradient.setColorAt(1.0, darkened(primary, 0.32));
    p.setPen(QPen(outline, 1.3));
    p.setBrush(gradient);
    p.drawEllipse(deck);

    const QRectF trim = deck.adjusted(r.width() * 0.05, r.height() * 0.12,
                                      -r.width() * 0.05, -r.height() * 0.10);
    p.setPen(QPen(QColor("#f1d69b"), 2.0));
    p.setBrush(Qt::NoBrush);
    p.drawArc(trim, 190 * 16, 160 * 16);

    const int bulbs = 9;
    p.setPen(Qt::NoPen);
    p.setBrush(QColor("#ffe7a6"));
    for (int i = 0; i < bulbs; ++i) {
        const qreal t = static_cast<qreal>(i) / (bulbs - 1);
        const qreal x = deck.left() + deck.width() * (0.10 + t * 0.80);
        const qreal y = deck.center().y() + deck.height() * 0.23;
        p.drawEllipse(QPointF(x, y), 1.8, 1.8);
    }
}

void drawCanopy(QPainter& p, const QRectF& r, const QColor& primary, const QColor& outline) {
    const QPointF top(r.center().x(), r.top() + r.height() * 0.07);
    const qreal y = r.top() + r.height() * 0.73;
    const qreal left = r.left() + r.width() * 0.05;
    const qreal right = r.right() - r.width() * 0.05;

    QPainterPath canopy;
    canopy.moveTo(left, y);
    canopy.quadTo(r.center().x() - r.width() * 0.27, r.top() + r.height() * 0.24, top.x(), top.y());
    canopy.quadTo(r.center().x() + r.width() * 0.27, r.top() + r.height() * 0.24, right, y);
    canopy.quadTo(r.center().x(), r.top() + r.height() * 0.93, left, y);
    canopy.closeSubpath();

    QLinearGradient g(r.topLeft(), r.bottomRight());
    g.setColorAt(0.0, lightened(primary, 0.26));
    g.setColorAt(0.55, primary);
    g.setColorAt(1.0, darkened(primary, 0.22));
    p.setPen(QPen(outline, 1.4));
    p.setBrush(g);
    p.drawPath(canopy);

    const QColor cream("#f4e1b9");
    p.setPen(QPen(cream, 1.3));
    for (int i = 1; i < 6; ++i) {
        const qreal x = left + (right - left) * static_cast<qreal>(i) / 6.0;
        p.drawLine(top, QPointF(x, y - 1.0));
    }
    p.setPen(QPen(outline, 1.0));
    p.setBrush(cream);
    for (int i = 0; i < 9; ++i) {
        const qreal x = left + (right - left) * static_cast<qreal>(i) / 8.0;
        p.drawEllipse(QPointF(x, y + 2.0), 2.1, 2.1);
    }
}

void drawPole(QPainter& p, const QRectF& r, const QColor& primary, const QColor& outline) {
    QRectF pole(r.center().x() - r.width() * 0.18, r.top() + r.height() * 0.03,
                r.width() * 0.36, r.height() * 0.94);
    QLinearGradient g(pole.topLeft(), pole.topRight());
    g.setColorAt(0.0, darkened(primary, 0.28));
    g.setColorAt(0.40, lightened(primary, 0.45));
    g.setColorAt(0.72, primary);
    g.setColorAt(1.0, darkened(primary, 0.30));
    p.setPen(QPen(outline, 1.0));
    p.setBrush(g);
    p.drawRoundedRect(pole, pole.width() * 0.45, pole.width() * 0.45);

    p.setPen(QPen(QColor("#f4d88f"), 1.0));
    p.drawLine(QPointF(pole.center().x(), pole.top() + 3), QPointF(pole.center().x(), pole.bottom() - 3));
}

void drawHorse(QPainter& p, const QRectF& r, const QColor& primary, const QColor& outline) {
    const QColor body = primary;
    const QColor shade = darkened(primary, 0.24);
    const QColor highlight = lightened(primary, 0.34);
    const QColor saddle("#7a4a37");
    const QColor gold("#e0b05c");

    const QRectF torso(r.left() + r.width() * 0.18, r.top() + r.height() * 0.38,
                       r.width() * 0.54, r.height() * 0.28);
    p.setPen(QPen(outline, 1.15, Qt::SolidLine, Qt::RoundCap, Qt::RoundJoin));
    p.setBrush(body);
    p.drawEllipse(torso);

    QPainterPath neck;
    neck.moveTo(r.left() + r.width() * 0.60, r.top() + r.height() * 0.44);
    neck.cubicTo(r.left() + r.width() * 0.65, r.top() + r.height() * 0.28,
                 r.left() + r.width() * 0.72, r.top() + r.height() * 0.20,
                 r.left() + r.width() * 0.79, r.top() + r.height() * 0.25);
    neck.lineTo(r.left() + r.width() * 0.72, r.top() + r.height() * 0.53);
    neck.closeSubpath();
    p.setBrush(body);
    p.drawPath(neck);

    const QRectF head(r.left() + r.width() * 0.70, r.top() + r.height() * 0.18,
                      r.width() * 0.22, r.height() * 0.17);
    p.drawEllipse(head);

    p.setBrush(shade);
    p.drawPolygon(QPolygonF{
        QPointF(head.left() + 2, head.top() + 2),
        QPointF(head.left() - 1, head.top() - r.height() * 0.07),
        QPointF(head.center().x(), head.top() + 1)});

    p.setBrush(QColor("#f3e7cf"));
    p.drawEllipse(QPointF(head.right() - 4.0, head.center().y()), 2.2, 1.6);
    p.setBrush(outline);
    p.drawEllipse(QPointF(head.left() + head.width() * 0.58, head.top() + head.height() * 0.35), 1.2, 1.2);

    p.setBrush(saddle);
    QRectF saddleRect(torso.left() + torso.width() * 0.30, torso.top() - r.height() * 0.04,
                      torso.width() * 0.34, torso.height() * 0.36);
    p.drawRoundedRect(saddleRect, 3, 3);
    p.setPen(QPen(gold, 1.4));
    p.drawLine(saddleRect.bottomLeft(), saddleRect.bottomRight());

    p.setPen(QPen(outline, 2.0, Qt::SolidLine, Qt::RoundCap));
    const qreal legTop = torso.bottom() - 2.0;
    const qreal legBottom = r.bottom() - r.height() * 0.08;
    p.drawLine(QPointF(torso.left() + torso.width() * 0.23, legTop),
               QPointF(torso.left() + torso.width() * 0.18, legBottom));
    p.drawLine(QPointF(torso.left() + torso.width() * 0.43, legTop),
               QPointF(torso.left() + torso.width() * 0.46, legBottom - 2));
    p.drawLine(QPointF(torso.left() + torso.width() * 0.70, legTop),
               QPointF(torso.left() + torso.width() * 0.75, legBottom));
    p.drawLine(QPointF(torso.left() + torso.width() * 0.84, legTop),
               QPointF(torso.left() + torso.width() * 0.88, legBottom - 3));

    p.setPen(QPen(shade, 2.2, Qt::SolidLine, Qt::RoundCap));
    QPainterPath tail;
    tail.moveTo(torso.left() + 1, torso.center().y());
    tail.cubicTo(r.left() + r.width() * 0.05, r.top() + r.height() * 0.46,
                 r.left() + r.width() * 0.08, r.top() + r.height() * 0.72,
                 r.left() + r.width() * 0.02, r.top() + r.height() * 0.69);
    p.drawPath(tail);

    p.setPen(QPen(highlight, 1.2, Qt::SolidLine, Qt::RoundCap));
    p.drawArc(torso.adjusted(3, 3, -3, -4), 35 * 16, 105 * 16);
}

void drawFinial(QPainter& p, const QRectF& r, const QColor& primary, const QColor& outline) {
    QRadialGradient g(r.center(), r.width() * 0.42, r.center() - QPointF(r.width() * 0.15, r.height() * 0.18));
    g.setColorAt(0.0, QColor("#fff0b6"));
    g.setColorAt(0.45, lightened(primary, 0.28));
    g.setColorAt(1.0, darkened(primary, 0.22));
    p.setPen(QPen(outline, 1.0));
    p.setBrush(g);
    p.drawEllipse(r.adjusted(r.width() * 0.20, r.height() * 0.24,
                             -r.width() * 0.20, -r.height() * 0.18));
    p.setBrush(primary);
    QPainterPath tip;
    tip.moveTo(r.center().x(), r.top());
    tip.lineTo(r.center().x() - r.width() * 0.12, r.top() + r.height() * 0.34);
    tip.lineTo(r.center().x() + r.width() * 0.12, r.top() + r.height() * 0.34);
    tip.closeSubpath();
    p.drawPath(tip);
}

void drawRosette(QPainter& p, const QRectF& r, const QColor& primary, const QColor& outline) {
    const QPointF c = r.center();
    const qreal rx = r.width() * 0.20;
    const qreal ry = r.height() * 0.20;
    p.setPen(QPen(outline, 0.9));
    p.setBrush(primary);
    for (int i = 0; i < 8; ++i) {
        const qreal angle = i * 45.0;
        p.save();
        p.translate(c);
        p.rotate(angle);
        p.drawEllipse(QRectF(-rx * 0.45, -r.height() * 0.38, rx * 0.90, ry * 1.55));
        p.restore();
    }
    p.setBrush(QColor("#f6d58b"));
    p.drawEllipse(c, r.width() * 0.13, r.height() * 0.13);
}

} // namespace

QStringList CarouselPartLibrary::partIds() {
    return {
        QString::fromLatin1(kBaseId),
        QString::fromLatin1(kPlatformId),
        QString::fromLatin1(kCanopyId),
        QString::fromLatin1(kPoleId),
        QString::fromLatin1(kHorseId),
        QString::fromLatin1(kFinialId),
        QString::fromLatin1(kRosetteId),
    };
}

bool CarouselPartLibrary::contains(const QString& part_id) {
    return partIds().contains(part_id);
}

QString CarouselPartLibrary::displayName(const QString& part_id) {
    if (part_id == QLatin1String(kBaseId)) return QStringLiteral("Classic carousel base");
    if (part_id == QLatin1String(kPlatformId)) return QStringLiteral("Classic carousel platform");
    if (part_id == QLatin1String(kCanopyId)) return QStringLiteral("Classic striped canopy");
    if (part_id == QLatin1String(kPoleId)) return QStringLiteral("Classic center pole");
    if (part_id == QLatin1String(kHorseId)) return QStringLiteral("Classic carousel horse");
    if (part_id == QLatin1String(kFinialId)) return QStringLiteral("Classic canopy finial");
    if (part_id == QLatin1String(kRosetteId)) return QStringLiteral("Classic decorative rosette");
    return {};
}

QSizeF CarouselPartLibrary::defaultSize(const QString& part_id) {
    if (part_id == QLatin1String(kBaseId)) return QSizeF(250.0, 78.0);
    if (part_id == QLatin1String(kPlatformId)) return QSizeF(224.0, 72.0);
    if (part_id == QLatin1String(kCanopyId)) return QSizeF(250.0, 118.0);
    if (part_id == QLatin1String(kPoleId)) return QSizeF(24.0, 170.0);
    if (part_id == QLatin1String(kHorseId)) return QSizeF(62.0, 70.0);
    if (part_id == QLatin1String(kFinialId)) return QSizeF(34.0, 46.0);
    if (part_id == QLatin1String(kRosetteId)) return QSizeF(30.0, 30.0);
    return QSizeF(24.0, 24.0);
}

QPointF CarouselPartLibrary::defaultPivot(const QString& part_id) {
    if (part_id == QLatin1String(kHorseId)) return QPointF(0.50, 0.78);
    if (part_id == QLatin1String(kCanopyId)) return QPointF(0.50, 0.86);
    if (part_id == QLatin1String(kFinialId)) return QPointF(0.50, 0.90);
    return QPointF(0.50, 0.50);
}

AnimationNodeSpec CarouselPartLibrary::makeNode(const QString& part_id,
                                                const QString& node_id,
                                                const QString& parent_id,
                                                const QPointF& position_px,
                                                const int draw_order,
                                                const QColor& primary,
                                                const QColor& outline) {
    AnimationNodeSpec node;
    node.id = node_id;
    node.parent_id = parent_id;
    node.position_px = position_px;
    node.draw_order = draw_order;
    node.visual_kind = AnimationNodeVisualKind::LibraryPart;
    node.visual_library_id = part_id;
    node.visual_size_px = defaultSize(part_id);
    node.pivot_normalized = defaultPivot(part_id);
    node.fill_color = primary;
    node.outline_color = outline;
    node.visual_trim_transparent = true;
    node.visual_preserve_aspect = true;
    node.visual_smooth_scaling = true;
    return node;
}

QImage CarouselPartLibrary::renderPart(const QString& part_id,
                                       const QSize& target_size,
                                       const QColor& primary,
                                       const QColor& outline,
                                       QString* reason) {
    if (!contains(part_id)) {
        if (reason) *reason = QStringLiteral("unknown carousel library part: %1").arg(part_id);
        return {};
    }
    if (target_size.width() <= 0 || target_size.height() <= 0) {
        if (reason) *reason = QStringLiteral("carousel part target size must be positive");
        return {};
    }

    QImage image(target_size, QImage::Format_ARGB32_Premultiplied);
    image.fill(Qt::transparent);
    QPainter painter(&image);
    setupPainter(painter);
    const QRectF bounds(1.5, 1.5, target_size.width() - 3.0, target_size.height() - 3.0);

    if (part_id == QLatin1String(kBaseId)) drawBase(painter, bounds, primary, outline);
    else if (part_id == QLatin1String(kPlatformId)) drawPlatform(painter, bounds, primary, outline);
    else if (part_id == QLatin1String(kCanopyId)) drawCanopy(painter, bounds, primary, outline);
    else if (part_id == QLatin1String(kPoleId)) drawPole(painter, bounds, primary, outline);
    else if (part_id == QLatin1String(kHorseId)) drawHorse(painter, bounds, primary, outline);
    else if (part_id == QLatin1String(kFinialId)) drawFinial(painter, bounds, primary, outline);
    else if (part_id == QLatin1String(kRosetteId)) drawRosette(painter, bounds, primary, outline);

    painter.end();
    if (reason) reason->clear();
    return image;
}

QJsonObject CarouselPartLibrary::manifest() {
    QJsonArray parts;
    for (const QString& id : partIds()) {
        const QSizeF size = defaultSize(id);
        const QPointF pivot = defaultPivot(id);
        parts.append(QJsonObject{
            {"id", id},
            {"name", displayName(id)},
            {"defaultSizePx", QJsonObject{{"width", size.width()}, {"height", size.height()}}},
            {"defaultPivot", QJsonObject{{"x", pivot.x()}, {"y", pivot.y()}}},
            {"deterministic", true},
            {"transparentRgba", true},
        });
    }
    return QJsonObject{
        {"version", QString::fromLatin1(kVersion)},
        {"namespace", QStringLiteral("carousel.*")},
        {"style", QStringLiteral("city_horizon_classic_tycoon")},
        {"partCount", parts.size()},
        {"parts", parts},
        {"productionReadySourceType", QStringLiteral("library_part")},
    };
}

} // namespace ch::studio
