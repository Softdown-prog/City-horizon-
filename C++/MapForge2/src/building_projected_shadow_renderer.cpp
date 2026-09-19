#include "building_projected_shadow_renderer.h"

#include "src/ch_core/contracts.h"

#include <QPainter>
#include <QPolygonF>

#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
#include <vector>

namespace ch::studio {
namespace {

struct Point3 {
    float x = 0.0F;
    float y = 0.0F;
    float z = 0.0F;
};

constexpr float kShadowWorldX = 1.0F;
constexpr float kShadowWorldY = 0.35F;
constexpr float kShadowLengthScale = 0.27F;
constexpr float kShadowMinLengthPx = 14.0F;
constexpr float kShadowMaxLengthPx = 34.0F;
constexpr float kPenumbraExtension = 1.08F;
constexpr float kFrameSafetyMarginPx = 4.0F;
constexpr int kPenumbraAlpha = 18;
constexpr int kCoreAlpha = 46;
constexpr int kNearFieldAlpha = 12;

Point3 rotatePoint(const Point3 point, const BuildingView view) {
    switch (view) {
        case BuildingView::East: return {-point.y, point.x, point.z};
        case BuildingView::North: return {-point.x, -point.y, point.z};
        case BuildingView::West: return {point.y, -point.x, point.z};
        case BuildingView::South: return point;
    }
    return point;
}

QPointF projectGroundPoint(const Point3 point, const BuildingView view, const QSize canvas) {
    const Point3 rotated = rotatePoint(point, view);
    const float half_tile_w = static_cast<float>(ch::contracts::kTileWidth) * 0.5F;
    const float half_tile_h = static_cast<float>(ch::contracts::kTileHeight) * 0.5F;
    const float center_x = static_cast<float>(canvas.width()) * 0.5F;
    const float ground_y = static_cast<float>(canvas.height()) - 42.0F;
    return {
        center_x + (rotated.x - rotated.y) * half_tile_w,
        ground_y + (rotated.x + rotated.y) * half_tile_h,
    };
}

QPointF projectedShadowDirection(const BuildingView view) {
    const Point3 world_direction{kShadowWorldX, kShadowWorldY, 0.0F};
    const Point3 rotated = rotatePoint(world_direction, view);
    const float dx = (rotated.x - rotated.y) * static_cast<float>(ch::contracts::kTileWidth) * 0.5F;
    const float dy = (rotated.x + rotated.y) * static_cast<float>(ch::contracts::kTileHeight) * 0.5F;
    const float length = std::hypot(dx, dy);
    if (length <= 0.001F) return {1.0, 0.0};
    return {dx / length, dy / length};
}

float cross(const QPointF& origin, const QPointF& a, const QPointF& b) {
    return static_cast<float>((a.x() - origin.x()) * (b.y() - origin.y())
                            - (a.y() - origin.y()) * (b.x() - origin.x()));
}

QPolygonF polygonFromPoints(const std::vector<QPointF>& points) {
    QPolygonF polygon;
    polygon.reserve(static_cast<int>(points.size()));
    for (const QPointF& point : points) polygon << point;
    return polygon;
}

QPolygonF convexHull(std::vector<QPointF> points) {
    if (points.size() <= 2) return polygonFromPoints(points);

    std::sort(points.begin(), points.end(), [](const QPointF& lhs, const QPointF& rhs) {
        if (lhs.x() != rhs.x()) return lhs.x() < rhs.x();
        return lhs.y() < rhs.y();
    });

    std::vector<QPointF> hull;
    hull.reserve(points.size() * 2);
    for (const QPointF& point : points) {
        while (hull.size() >= 2
               && cross(hull[hull.size() - 2], hull.back(), point) <= 0.0F) {
            hull.pop_back();
        }
        hull.push_back(point);
    }

    const std::size_t lower_size = hull.size();
    for (auto it = points.rbegin() + 1; it != points.rend(); ++it) {
        while (hull.size() > lower_size
               && cross(hull[hull.size() - 2], hull.back(), *it) <= 0.0F) {
            hull.pop_back();
        }
        hull.push_back(*it);
    }
    if (!hull.empty()) hull.pop_back();

    return polygonFromPoints(hull);
}

QPolygonF sweptHull(const QPolygonF& caster, const QPointF& offset) {
    std::vector<QPointF> points;
    points.reserve(static_cast<std::size_t>(caster.size()) * 2U);
    for (const QPointF& point : caster) {
        points.push_back(point);
        points.push_back(point + offset);
    }
    return convexHull(std::move(points));
}

float safeProjectedLength(const QRectF& bounds, const QPointF& direction, const QSize canvas) {
    float maximum = std::numeric_limits<float>::max();
    const float right = static_cast<float>(canvas.width()) - kFrameSafetyMarginPx;
    const float bottom = static_cast<float>(canvas.height()) - kFrameSafetyMarginPx;

    if (direction.x() > 0.001) {
        maximum = std::min(maximum,
                           static_cast<float>((right - bounds.right()) / direction.x()));
    } else if (direction.x() < -0.001) {
        maximum = std::min(maximum,
                           static_cast<float>((bounds.left() - kFrameSafetyMarginPx) / -direction.x()));
    }

    if (direction.y() > 0.001) {
        maximum = std::min(maximum,
                           static_cast<float>((bottom - bounds.bottom()) / direction.y()));
    } else if (direction.y() < -0.001) {
        maximum = std::min(maximum,
                           static_cast<float>((bounds.top() - kFrameSafetyMarginPx) / -direction.y()));
    }

    return std::max(0.0F, maximum);
}

QColor shadowColor(const int alpha) {
    return QColor(29, 38, 48, std::clamp(alpha, 0, 255));
}

} // namespace

void BuildingProjectedShadowRenderer::draw(QPainter& painter,
                                           const BuildingComposerSpec& spec,
                                           const BuildingView view,
                                           const QSize canvas) {
    if (!spec.cast_shadow || canvas.isEmpty()) return;

    const float half_w = static_cast<float>(std::max(1, spec.footprint_width_tiles)) * 0.5F;
    const float half_d = static_cast<float>(std::max(1, spec.footprint_depth_tiles)) * 0.5F;
    const std::array<Point3, 4> corners = {
        Point3{-half_w, -half_d, 0.0F},
        Point3{ half_w, -half_d, 0.0F},
        Point3{ half_w,  half_d, 0.0F},
        Point3{-half_w,  half_d, 0.0F},
    };

    QPolygonF caster;
    for (const Point3& corner : corners) caster << projectGroundPoint(corner, view, canvas);

    const float wall_h = static_cast<float>(std::max(24, BuildingComposer::effectiveWallHeightPx(spec)));
    const float pitch_factor = std::clamp(spec.roof_pitch_degrees / 35.0F, 0.35F, 1.75F);
    const float roof_h = spec.roof_style == BuildingRoofStyle::Flat
        ? 4.0F
        : static_cast<float>(std::max(8, spec.roof_height_px)) * pitch_factor;
    const float optical_height = wall_h + roof_h * 0.55F;

    const QPointF direction = projectedShadowDirection(view);
    const float desired_core_length = std::clamp(optical_height * kShadowLengthScale,
                                                 kShadowMinLengthPx,
                                                 kShadowMaxLengthPx);
    const float safe_outer_length = safeProjectedLength(caster.boundingRect(), direction, canvas);
    const float core_length = std::min(desired_core_length,
                                       safe_outer_length / kPenumbraExtension);
    if (core_length < 1.0F) return;

    const QPointF core_offset = direction * core_length;
    const QPointF outer_offset = direction * (core_length * kPenumbraExtension);
    const QPointF near_offset = direction * (core_length * 0.46F);

    painter.save();
    painter.setRenderHint(QPainter::Antialiasing, true);
    painter.setPen(Qt::NoPen);

    painter.setBrush(shadowColor(kPenumbraAlpha));
    painter.drawPolygon(sweptHull(caster, outer_offset));

    painter.setBrush(shadowColor(kCoreAlpha));
    painter.drawPolygon(sweptHull(caster, core_offset));

    painter.setBrush(shadowColor(kNearFieldAlpha));
    painter.drawPolygon(sweptHull(caster, near_offset));
    painter.restore();
}

QJsonObject BuildingProjectedShadowRenderer::manifest() {
    return QJsonObject{
        {"version", "fixed_world_cast_shadow_1"},
        {"worldDirectionX", static_cast<double>(kShadowWorldX)},
        {"worldDirectionY", static_cast<double>(kShadowWorldY)},
        {"heightLengthScale", static_cast<double>(kShadowLengthScale)},
        {"minimumLengthPx", static_cast<double>(kShadowMinLengthPx)},
        {"maximumLengthPx", static_cast<double>(kShadowMaxLengthPx)},
        {"penumbraExtension", static_cast<double>(kPenumbraExtension)},
        {"penumbraAlpha", kPenumbraAlpha},
        {"coreAlpha", kCoreAlpha},
        {"nearFieldAlpha", kNearFieldAlpha},
        {"frameSafetyMarginPx", static_cast<double>(kFrameSafetyMarginPx)},
        {"cameraIndependentWorldDirection", true},
        {"gaussianBlur", false},
    };
}

} // namespace ch::studio
