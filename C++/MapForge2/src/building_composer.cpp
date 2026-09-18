#include "building_composer.h"

#include "src/ch_core/contracts.h"

#include <QFont>
#include <QJsonArray>
#include <QLinearGradient>
#include <QPainter>
#include <QPainterPath>
#include <QPen>
#include <QPolygonF>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <vector>

namespace ch::studio {
namespace {

struct Point3 {
    float x = 0.0F;
    float y = 0.0F;
    float z = 0.0F;
};

constexpr std::array<BuildingView, 4> kViews = {
    BuildingView::South,
    BuildingView::East,
    BuildingView::West,
    BuildingView::North,
};

constexpr int kRenderSupersampleScale = 2;
constexpr qreal kStructuralOutlineWidth = 1.20;
constexpr qreal kContactLineWidth = 1.20;
constexpr qreal kRoofEdgeWidth = 1.35;
constexpr float kStructuralPlinthOutset = 1.018F;

int quarterTurns(const BuildingView view) {
    switch (view) {
        case BuildingView::South: return 0;
        case BuildingView::East: return 1;
        case BuildingView::West: return 3;
        case BuildingView::North: return 2;
    }
    return 0;
}

Point3 rotatePoint(const Point3 point, const BuildingView view) {
    switch (quarterTurns(view)) {
        case 1: return {-point.y, point.x, point.z};
        case 2: return {-point.x, -point.y, point.z};
        case 3: return {point.y, -point.x, point.z};
        default: return point;
    }
}

QPointF projectPoint(const Point3 point, const BuildingView view, const QSize canvas) {
    const Point3 rotated = rotatePoint(point, view);
    const float half_tile_w = static_cast<float>(ch::contracts::kTileWidth) * 0.5F;
    const float half_tile_h = static_cast<float>(ch::contracts::kTileHeight) * 0.5F;
    const float center_x = static_cast<float>(canvas.width()) * 0.5F;
    const float ground_y = static_cast<float>(canvas.height()) - 42.0F;
    return {
        center_x + (rotated.x - rotated.y) * half_tile_w,
        ground_y + (rotated.x + rotated.y) * half_tile_h - rotated.z,
    };
}

QColor scaledColor(const QColor color, const float factor) {
    return QColor::fromRgbF(
        std::clamp(color.redF() * factor, 0.0F, 1.0F),
        std::clamp(color.greenF() * factor, 0.0F, 1.0F),
        std::clamp(color.blueF() * factor, 0.0F, 1.0F),
        color.alphaF());
}

QColor alphaColor(QColor color, const int alpha) {
    color.setAlpha(std::clamp(alpha, 0, 255));
    return color;
}

Point3 lerpPoint(const Point3 a, const Point3 b, const float t, const float z) {
    return {
        a.x + (b.x - a.x) * t,
        a.y + (b.y - a.y) * t,
        z,
    };
}

QPointF lerpScreen(const QPointF& a, const QPointF& b, const float t) {
    return {
        a.x() + (b.x() - a.x()) * t,
        a.y() + (b.y() - a.y()) * t,
    };
}

QPolygonF faceQuad(const Point3 a, const Point3 b, const float z0, const float z1,
                   const BuildingView view, const QSize canvas) {
    return {
        projectPoint({a.x, a.y, z0}, view, canvas),
        projectPoint({b.x, b.y, z0}, view, canvas),
        projectPoint({b.x, b.y, z1}, view, canvas),
        projectPoint({a.x, a.y, z1}, view, canvas),
    };
}

float averageY(const QPolygonF& polygon) {
    float total = 0.0F;
    for (const QPointF& point : polygon) total += static_cast<float>(point.y());
    return polygon.isEmpty() ? 0.0F : total / static_cast<float>(polygon.size());
}

void drawOutlinedPolygon(QPainter& painter, const QPolygonF& polygon, const QColor fill,
                         const QColor outline = QColor(45, 49, 51, 220)) {
    QPen outline_pen(outline, kStructuralOutlineWidth, Qt::SolidLine, Qt::SquareCap, Qt::MiterJoin);
    outline_pen.setMiterLimit(3.0);
    painter.setPen(outline_pen);
    painter.setBrush(fill);
    painter.drawPolygon(polygon);
}

void drawLitWallPolygon(QPainter& painter, const QPolygonF& polygon,
                        const QColor wall_color, const float face_shade) {
    if (polygon.isEmpty()) return;

    const QRectF bounds = polygon.boundingRect();
    QLinearGradient gradient(bounds.topLeft(), bounds.bottomRight());
    gradient.setColorAt(0.0, scaledColor(wall_color, face_shade * 1.045F));
    gradient.setColorAt(0.55, scaledColor(wall_color, face_shade));
    gradient.setColorAt(1.0, scaledColor(wall_color, face_shade * 0.94F));

    QPen outline_pen(QColor(45, 49, 51, 220), kStructuralOutlineWidth,
                     Qt::SolidLine, Qt::SquareCap, Qt::MiterJoin);
    outline_pen.setMiterLimit(3.0);
    painter.setPen(outline_pen);
    painter.setBrush(gradient);
    painter.drawPolygon(polygon);
}

void drawFaceDetail(QPainter& painter, const Point3 a, const Point3 b, const float t0, const float t1,
                    const float z0, const float z1, const BuildingView view, const QSize canvas,
                    const QColor fill, const QColor outline) {
    const QPolygonF polygon = {
        projectPoint(lerpPoint(a, b, t0, z0), view, canvas),
        projectPoint(lerpPoint(a, b, t1, z0), view, canvas),
        projectPoint(lerpPoint(a, b, t1, z1), view, canvas),
        projectPoint(lerpPoint(a, b, t0, z1), view, canvas),
    };
    drawOutlinedPolygon(painter, polygon, fill, outline);
}

void drawStructuralPlinth(QPainter& painter, const BuildingComposerSpec& spec,
                          const Point3 a, const Point3 b, const float wall_h,
                          const float face_shade, const BuildingView view, const QSize canvas) {
    const float plinth_h = std::clamp(wall_h * 0.075F, 5.0F, 9.0F);
    const Point3 outer_a{a.x * kStructuralPlinthOutset, a.y * kStructuralPlinthOutset, 0.0F};
    const Point3 outer_b{b.x * kStructuralPlinthOutset, b.y * kStructuralPlinthOutset, 0.0F};
    const QPolygonF plinth_face = faceQuad(outer_a, outer_b, 0.0F, plinth_h, view, canvas);
    const QRectF plinth_bounds = plinth_face.boundingRect();
    QLinearGradient plinth_gradient(plinth_bounds.topLeft(), plinth_bounds.bottomLeft());
    plinth_gradient.setColorAt(0.0, scaledColor(spec.wall_color, face_shade * 0.78F));
    plinth_gradient.setColorAt(0.62, scaledColor(spec.wall_color, face_shade * 0.70F));
    plinth_gradient.setColorAt(1.0, scaledColor(spec.wall_color, face_shade * 0.62F));
    const QColor plinth_cap = scaledColor(spec.wall_color, face_shade * 0.84F);

    painter.save();
    painter.setPen(Qt::NoPen);
    painter.setBrush(plinth_gradient);
    painter.drawPolygon(plinth_face);

    const QPolygonF cap = {
        projectPoint({outer_a.x, outer_a.y, plinth_h}, view, canvas),
        projectPoint({outer_b.x, outer_b.y, plinth_h}, view, canvas),
        projectPoint({b.x, b.y, plinth_h}, view, canvas),
        projectPoint({a.x, a.y, plinth_h}, view, canvas),
    };
    painter.setBrush(plinth_cap);
    painter.drawPolygon(cap);

    painter.setPen(QPen(alphaColor(scaledColor(spec.wall_color, face_shade * 0.52F), 72), 0.75));
    painter.setBrush(Qt::NoBrush);
    painter.drawLine(
        projectPoint({outer_a.x, outer_a.y, plinth_h * 0.28F}, view, canvas),
        projectPoint({outer_b.x, outer_b.y, plinth_h * 0.28F}, view, canvas));
    // A narrow projecting cap makes the plinth read as a built element rather
    // than a painted stripe, while remaining below the facade modules.
    const float cap_lip_z0 = plinth_h - 0.65F;
    const float cap_lip_z1 = plinth_h + 0.85F;
    const Point3 lip_a{a.x * 1.026F, a.y * 1.026F, 0.0F};
    const Point3 lip_b{b.x * 1.026F, b.y * 1.026F, 0.0F};
    painter.setPen(QPen(alphaColor(scaledColor(spec.wall_color, face_shade * 0.58F), 105), 0.65));
    painter.setBrush(scaledColor(spec.wall_color, face_shade * 0.88F));
    painter.drawPolygon(faceQuad(lip_a, lip_b, cap_lip_z0, cap_lip_z1, view, canvas));

    painter.restore();
}

void drawEaveAmbientOcclusion(QPainter& painter, const BuildingComposerSpec& spec,
                              const Point3 a, const Point3 b, const float wall_h,
                              const BuildingView view, const QSize canvas) {
    constexpr float kAoDepth = 6.0F;
    constexpr std::array<int, 5> kAoAlpha = {42, 30, 20, 12, 6};
    const QColor ao_base = scaledColor(spec.wall_color, 0.55F);
    const float band_height = kAoDepth / static_cast<float>(kAoAlpha.size());

    painter.save();
    painter.setPen(Qt::NoPen);
    for (int band = 0; band < static_cast<int>(kAoAlpha.size()); ++band) {
        const float z1 = wall_h - static_cast<float>(band) * band_height;
        const float z0 = wall_h - static_cast<float>(band + 1) * band_height;
        painter.setBrush(alphaColor(ao_base, kAoAlpha[band]));
        painter.drawPolygon(faceQuad(a, b, z0, z1, view, canvas));
    }
    painter.restore();
}

void drawCornerAmbientOcclusion(QPainter& painter, const BuildingComposerSpec& spec,
                                const Point3 a, const Point3 b, const bool shade_start,
                                const float wall_h, const BuildingView view, const QSize canvas) {
    constexpr float kCornerWorldSpan = 0.075F;
    constexpr std::array<int, 4> kCornerAlpha = {30, 20, 12, 5};
    const float edge_span = std::max(0.5F, std::hypot(b.x - a.x, b.y - a.y));
    const float total_t = std::clamp(kCornerWorldSpan / edge_span, 0.018F, 0.075F);
    const float band_t = total_t / static_cast<float>(kCornerAlpha.size());
    const QColor ao_base = scaledColor(spec.wall_color, 0.48F);

    painter.save();
    painter.setPen(Qt::NoPen);
    for (int band = 0; band < static_cast<int>(kCornerAlpha.size()); ++band) {
        float t0 = 0.0F;
        float t1 = 0.0F;
        if (shade_start) {
            t0 = static_cast<float>(band) * band_t;
            t1 = static_cast<float>(band + 1) * band_t;
        } else {
            t0 = 1.0F - static_cast<float>(band + 1) * band_t;
            t1 = 1.0F - static_cast<float>(band) * band_t;
        }

        const QPolygonF band_polygon = {
            projectPoint(lerpPoint(a, b, t0, 0.8F), view, canvas),
            projectPoint(lerpPoint(a, b, t1, 0.8F), view, canvas),
            projectPoint(lerpPoint(a, b, t1, wall_h - 1.0F), view, canvas),
            projectPoint(lerpPoint(a, b, t0, wall_h - 1.0F), view, canvas),
        };
        painter.setBrush(alphaColor(ao_base, kCornerAlpha[band]));
        painter.drawPolygon(band_polygon);
    }
    painter.restore();
}

std::uint32_t hashMix(std::uint32_t value) {
    value ^= value >> 16U;
    value *= 0x7feb352dU;
    value ^= value >> 15U;
    value *= 0x846ca68bU;
    value ^= value >> 16U;
    return value;
}

float hash01(const int seed, const int a, const int b, const int c = 0) {
    std::uint32_t value = static_cast<std::uint32_t>(seed) * 0x9e3779b9U;
    value ^= static_cast<std::uint32_t>(a + 101) * 0x85ebca6bU;
    value ^= static_cast<std::uint32_t>(b + 211) * 0xc2b2ae35U;
    value ^= static_cast<std::uint32_t>(c + 307) * 0x27d4eb2fU;
    return static_cast<float>(hashMix(value) & 0x00ffffffU) / static_cast<float>(0x01000000U);
}

void drawWallMaterial(QPainter& painter, const BuildingComposerSpec& spec,
                      const Point3 a, const Point3 b, const int edge, const float wall_h,
                      const BuildingView view, const QSize canvas) {
    if (spec.wall_material == BuildingWallMaterial::Solid || spec.material_strength <= 0.001F) return;

    const float strength = std::clamp(spec.material_strength, 0.0F, 1.0F);
    const float scale = std::clamp(spec.material_scale, 0.55F, 2.0F);
    QColor dark = alphaColor(scaledColor(spec.wall_color, 0.60F), 35 + static_cast<int>(95.0F * strength));
    QColor light = alphaColor(scaledColor(spec.wall_color, 1.16F), 20 + static_cast<int>(75.0F * strength));
    const float edge_span = std::max(0.5F, std::hypot(b.x - a.x, b.y - a.y));

    painter.save();
    painter.setBrush(Qt::NoBrush);

    if (spec.wall_material == BuildingWallMaterial::Plaster) {
        const int patches = std::max(6, static_cast<int>((8.0F + 10.0F * strength) * edge_span / scale));
        painter.setPen(Qt::NoPen);
        for (int i = 0; i < patches; ++i) {
            const float t = 0.06F + hash01(spec.material_seed + 239, edge, i) * 0.88F;
            const float z = 5.0F + hash01(spec.material_seed + 239, edge, i, 1) * std::max(5.0F, wall_h - 10.0F);
            const float tone_pick = hash01(spec.material_seed + 239, edge, i, 2);
            const float tone = tone_pick < 0.34F ? 0.88F : (tone_pick < 0.68F ? 0.96F : 1.08F);
            const int alpha = 8 + static_cast<int>(17.0F * strength);
            painter.setBrush(alphaColor(scaledColor(spec.wall_color, tone), alpha));
            const QPointF center = projectPoint(lerpPoint(a, b, t, z), view, canvas);
            const qreal radius_x = 0.9 + hash01(spec.material_seed + 239, edge, i, 3) * 1.8;
            const qreal radius_y = 0.55 + hash01(spec.material_seed + 313, edge, i) * 1.0;
            painter.drawEllipse(center, radius_x, radius_y);
        }

        painter.setBrush(Qt::NoBrush);
        const int samples = std::max(14, static_cast<int>((24.0F + 42.0F * strength) * edge_span / scale));
        painter.setPen(QPen(dark, 0.85));
        for (int i = 0; i < samples; ++i) {
            const float t = 0.04F + hash01(spec.material_seed, edge, i) * 0.92F;
            const float z = 3.5F + hash01(spec.material_seed, edge, i, 1) * std::max(5.0F, wall_h - 7.0F);
            painter.drawPoint(projectPoint(lerpPoint(a, b, t, z), view, canvas));
        }
        painter.setPen(QPen(light, 0.85));
        for (int i = 0; i < samples / 2; ++i) {
            const float t = 0.05F + hash01(spec.material_seed + 71, edge, i) * 0.90F;
            const float z = 4.0F + hash01(spec.material_seed + 71, edge, i, 2) * std::max(5.0F, wall_h - 8.0F);
            painter.drawPoint(projectPoint(lerpPoint(a, b, t, z), view, canvas));
        }
    } else if (spec.wall_material == BuildingWallMaterial::Brick) {
        const float course_px = std::max(7.0F, 11.0F * scale);
        const int courses = std::max(3, static_cast<int>(wall_h / course_px));
        const int columns = std::max(3, static_cast<int>((edge_span * 6.0F) / scale));
        painter.setPen(QPen(dark, 0.9));
        for (int row = 1; row < courses; ++row) {
            const float z = wall_h * static_cast<float>(row) / static_cast<float>(courses);
            painter.drawLine(projectPoint(lerpPoint(a, b, 0.0F, z), view, canvas),
                             projectPoint(lerpPoint(a, b, 1.0F, z), view, canvas));
        }
        for (int row = 0; row < courses; ++row) {
            const float z0 = wall_h * static_cast<float>(row) / static_cast<float>(courses);
            const float z1 = wall_h * static_cast<float>(row + 1) / static_cast<float>(courses);
            const float offset = (row % 2 == 0) ? 0.0F : 0.5F;
            for (int col = 1; col < columns; ++col) {
                const float t = (static_cast<float>(col) + offset) / static_cast<float>(columns);
                if (t >= 0.98F) continue;
                painter.drawLine(projectPoint(lerpPoint(a, b, t, z0), view, canvas),
                                 projectPoint(lerpPoint(a, b, t, z1), view, canvas));
            }
        }
    } else if (spec.wall_material == BuildingWallMaterial::Concrete) {
        painter.setPen(QPen(dark, 1.0));
        painter.drawLine(projectPoint(lerpPoint(a, b, 0.50F, 0.0F), view, canvas),
                         projectPoint(lerpPoint(a, b, 0.50F, wall_h), view, canvas));
        painter.drawLine(projectPoint(lerpPoint(a, b, 0.0F, wall_h * 0.50F), view, canvas),
                         projectPoint(lerpPoint(a, b, 1.0F, wall_h * 0.50F), view, canvas));
        painter.setPen(QPen(light, 1.0));
        const int pores = std::max(5, static_cast<int>(10.0F * edge_span * strength / scale));
        for (int i = 0; i < pores; ++i) {
            const float t = 0.08F + hash01(spec.material_seed + 131, edge, i) * 0.84F;
            const float z = 7.0F + hash01(spec.material_seed + 131, edge, i, 1) * std::max(5.0F, wall_h - 14.0F);
            painter.drawPoint(projectPoint(lerpPoint(a, b, t, z), view, canvas));
        }
    } else if (spec.wall_material == BuildingWallMaterial::Timber) {
        const int boards = std::max(4, static_cast<int>((edge_span * 8.0F) / scale));
        painter.setPen(QPen(dark, 1.0));
        for (int i = 1; i < boards; ++i) {
            const float t = static_cast<float>(i) / static_cast<float>(boards);
            painter.drawLine(projectPoint(lerpPoint(a, b, t, 1.0F), view, canvas),
                             projectPoint(lerpPoint(a, b, t, wall_h - 1.0F), view, canvas));
        }
        painter.setPen(QPen(light, 1.0));
        for (int i = 0; i < std::max(2, boards / 3); ++i) {
            const float t = 0.08F + hash01(spec.material_seed + 197, edge, i) * 0.84F;
            const float z = wall_h * (0.18F + hash01(spec.material_seed + 197, edge, i, 1) * 0.64F);
            painter.drawEllipse(projectPoint(lerpPoint(a, b, t, z), view, canvas), 1.4, 0.9);
        }
    }

    painter.restore();
}

std::array<QPointF, 2> roofRowEndpoints(const QPolygonF& polygon, const float v) {
    const float clamped_v = std::clamp(v, 0.0F, 1.0F);
    if (polygon.size() == 3) {
        const QPointF apex = polygon[2];
        return {
            lerpScreen(apex, polygon[0], clamped_v),
            lerpScreen(apex, polygon[1], clamped_v),
        };
    }
    if (polygon.size() >= 4) {
        return {
            lerpScreen(polygon[3], polygon[0], clamped_v),
            lerpScreen(polygon[2], polygon[1], clamped_v),
        };
    }
    const QPointF fallback = polygon.isEmpty() ? QPointF() : polygon.front();
    return {fallback, fallback};
}

QPointF roofRowPoint(const std::array<QPointF, 2>& row, const float u) {
    return lerpScreen(row[0], row[1], std::clamp(u, 0.0F, 1.0F));
}

float screenDistance(const QPointF& a, const QPointF& b) {
    return static_cast<float>(std::hypot(b.x() - a.x(), b.y() - a.y()));
}

void drawRoofMaterial(QPainter& painter, const BuildingComposerSpec& spec,
                      const QPolygonF& polygon, const int face_index) {
    if (spec.roof_material == BuildingRoofMaterial::Solid ||
        spec.material_strength <= 0.001F || polygon.size() < 3) {
        return;
    }

    const float strength = std::clamp(spec.material_strength, 0.0F, 1.0F);
    const float scale = std::clamp(spec.material_scale, 0.55F, 2.0F);
    const QColor dark_base = scaledColor(spec.roof_color, 0.54F);
    const auto ridge_row = roofRowEndpoints(polygon, 0.0F);
    const auto eave_row = roofRowEndpoints(polygon, 1.0F);
    const QPointF ridge_center = lerpScreen(ridge_row[0], ridge_row[1], 0.5F);
    const QPointF eave_center = lerpScreen(eave_row[0], eave_row[1], 0.5F);
    const float slope_length = std::max(8.0F, screenDistance(ridge_center, eave_center));
    const float nominal_course = std::max(5.0F, 8.0F * scale);
    const int courses = std::max(2, static_cast<int>(std::round(slope_length / nominal_course)));

    QPainterPath path;
    path.addPolygon(polygon);
    path.closeSubpath();

    painter.save();
    painter.setClipPath(path);
    painter.setBrush(Qt::NoBrush);

    if (spec.roof_material == BuildingRoofMaterial::CeramicTile) {
        for (int row_index = 1; row_index <= courses; ++row_index) {
            const float v0 = static_cast<float>(row_index - 1) / static_cast<float>(courses);
            const float v1 = static_cast<float>(row_index) / static_cast<float>(courses);
            const auto previous_row = roofRowEndpoints(polygon, v0);
            const auto current_row = roofRowEndpoints(polygon, v1);
            const float row_variation = 0.88F + hash01(spec.material_seed + 401, face_index, row_index) * 0.20F;

            const QPolygonF course_band = {
                previous_row[0], previous_row[1], current_row[1], current_row[0],
            };
            const float band_tone = 0.94F + hash01(spec.material_seed + 557, face_index, row_index) * 0.12F;
            painter.setPen(Qt::NoPen);
            painter.setBrush(alphaColor(
                scaledColor(spec.roof_color, band_tone),
                10 + static_cast<int>(28.0F * strength)));
            painter.drawPolygon(course_band);

            const float width = std::max(8.0F, screenDistance(current_row[0], current_row[1]));
            const int tiles = std::max(2, static_cast<int>(std::round(width / std::max(8.0F, 12.0F * scale))));
            const float stagger = (row_index % 2 == 0) ? 0.5F : 0.0F;
            const float tile_step = 1.0F / static_cast<float>(tiles);
            for (int tile = 0; tile < tiles; ++tile) {
                float u0 = static_cast<float>(tile) * tile_step;
                float u1 = static_cast<float>(tile + 1) * tile_step;
                if (stagger > 0.0F) {
                    u0 = std::clamp(u0 + tile_step * 0.5F, 0.0F, 1.0F);
                    u1 = std::clamp(u1 + tile_step * 0.5F, 0.0F, 1.0F);
                }
                if (u1 - u0 < 0.02F) continue;
                const float tile_tone = 0.90F + hash01(spec.material_seed + 613, face_index, row_index, tile) * 0.20F;
                const QPolygonF tile_body = {
                    roofRowPoint(previous_row, u0),
                    roofRowPoint(previous_row, u1),
                    roofRowPoint(current_row, u1),
                    roofRowPoint(current_row, u0),
                };
                painter.setBrush(alphaColor(
                    scaledColor(spec.roof_color, tile_tone),
                    6 + static_cast<int>(22.0F * strength)));
                painter.drawPolygon(tile_body);
            }
            painter.setBrush(Qt::NoBrush);

            QColor course_color = alphaColor(
                scaledColor(dark_base, row_variation),
                48 + static_cast<int>(118.0F * strength));
            painter.setPen(QPen(course_color, 0.95));
            painter.drawLine(current_row[0], current_row[1]);

            for (int tile = 1; tile < tiles; ++tile) {
                const float u = (static_cast<float>(tile) + stagger) / static_cast<float>(tiles);
                if (u >= 0.98F) continue;
                const QPointF seam_top = roofRowPoint(previous_row, u);
                const QPointF seam_bottom = roofRowPoint(current_row, u);
                const QPointF seam_start = lerpScreen(seam_top, seam_bottom, 0.50F);
                painter.drawLine(seam_start, seam_bottom);
            }

            const QColor lip_shadow = alphaColor(
                scaledColor(spec.roof_color, 0.50F),
                12 + static_cast<int>(38.0F * strength));
            painter.setPen(QPen(lip_shadow, 0.70));
            for (int tile = 0; tile < tiles; ++tile) {
                const float center_u = (static_cast<float>(tile) + 0.5F + stagger) * tile_step;
                if (center_u <= 0.04F || center_u >= 0.96F) continue;
                const float half_lip = tile_step * 0.22F;
                painter.drawLine(
                    roofRowPoint(current_row, center_u - half_lip),
                    roofRowPoint(current_row, center_u + half_lip));
            }
        }
    } else if (spec.roof_material == BuildingRoofMaterial::MetalSeam) {
        const float eave_width = std::max(12.0F, screenDistance(eave_row[0], eave_row[1]));
        const int seams = std::max(3, static_cast<int>(std::round(eave_width / std::max(12.0F, 18.0F * scale))));
        for (int seam = 1; seam < seams; ++seam) {
            const float u = static_cast<float>(seam) / static_cast<float>(seams);
            const QPointF start = roofRowPoint(ridge_row, u);
            const QPointF end = roofRowPoint(eave_row, u);
            painter.setPen(QPen(alphaColor(dark_base, 65 + static_cast<int>(110.0F * strength)), 1.0));
            painter.drawLine(start, end);
        }
    } else if (spec.roof_material == BuildingRoofMaterial::AsphaltShingle) {
        for (int row_index = 1; row_index <= courses; ++row_index) {
            const float v0 = static_cast<float>(row_index - 1) / static_cast<float>(courses);
            const float v1 = static_cast<float>(row_index) / static_cast<float>(courses);
            const auto previous_row = roofRowEndpoints(polygon, v0);
            const auto current_row = roofRowEndpoints(polygon, v1);
            painter.setPen(QPen(alphaColor(dark_base, 45 + static_cast<int>(98.0F * strength)), 0.85));
            painter.drawLine(current_row[0], current_row[1]);

            const float width = std::max(8.0F, screenDistance(current_row[0], current_row[1]));
            const int tabs = std::max(2, static_cast<int>(std::round(width / std::max(11.0F, 16.0F * scale))));
            const float stagger = (row_index % 2 == 0) ? 0.5F : 0.0F;
            for (int tab = 1; tab < tabs; ++tab) {
                const float u = (static_cast<float>(tab) + stagger) / static_cast<float>(tabs);
                if (u >= 0.98F) continue;
                const QPointF top = roofRowPoint(previous_row, u);
                const QPointF bottom = roofRowPoint(current_row, u);
                painter.drawLine(lerpScreen(top, bottom, 0.62F), bottom);
            }
        }
    }

    painter.restore();
}

float doorCenter(const BuildingDoorPosition position) {
    switch (position) {
        case BuildingDoorPosition::Left: return 0.24F;
        case BuildingDoorPosition::Center: return 0.50F;
        case BuildingDoorPosition::Right: return 0.76F;
    }
    return 0.50F;
}

struct FacadeAperture {
    float t0 = 0.0F;
    float t1 = 0.0F;
};

std::vector<FacadeAperture> entranceWindowLayout(const BuildingComposerSpec& spec) {
    const int count = spec.window_pattern == BuildingWindowPattern::Single ? 1
                    : spec.window_pattern == BuildingWindowPattern::Pair ? 2 : 4;

    std::vector<FacadeAperture> result;
    result.reserve(static_cast<std::size_t>(count));

    constexpr float facade_min = 0.06F;
    constexpr float facade_max = 0.94F;
    constexpr float door_clear_half = 0.19F;
    constexpr float side_gap = 0.035F;
    const float center = doorCenter(spec.door_position);
    const float left_end = std::max(facade_min, center - door_clear_half - side_gap);
    const float right_start = std::min(facade_max, center + door_clear_half + side_gap);
    const float left_span = std::max(0.0F, left_end - facade_min);
    const float right_span = std::max(0.0F, facade_max - right_start);

    int left_count = 0;
    if (count == 1) {
        left_count = left_span >= right_span ? 1 : 0;
    } else {
        const float total_span = std::max(0.001F, left_span + right_span);
        left_count = static_cast<int>(std::round(static_cast<float>(count) * left_span / total_span));
        left_count = std::clamp(left_count, left_span >= 0.10F ? 1 : 0, count - (right_span >= 0.10F ? 1 : 0));
    }
    const int right_count = count - left_count;

    auto appendSegment = [&](const float start, const float end, const int segment_count) {
        if (segment_count <= 0 || end <= start) return;
        const float span = end - start;
        const float gap = std::min(0.035F, span / static_cast<float>(segment_count * 4));
        const float width = std::max(0.055F,
            (span - gap * static_cast<float>(segment_count + 1)) / static_cast<float>(segment_count));
        for (int i = 0; i < segment_count; ++i) {
            const float t0 = start + gap + static_cast<float>(i) * (width + gap);
            const float t1 = std::min(end - gap, t0 + width);
            if (t1 - t0 >= 0.05F) result.push_back({t0, t1});
        }
    };

    appendSegment(facade_min, left_end, left_count);
    appendSegment(right_start, facade_max, right_count);
    return result;
}

void drawWindowModule(QPainter& painter, const BuildingComposerSpec& spec,
                      const Point3 a, const Point3 b, const float t0, const float t1,
                      const float wall_h, const BuildingView view, const QSize canvas) {
    const float z0 = wall_h * 0.36F;
    const float z1 = wall_h * 0.70F;
    const float width = std::max(0.04F, t1 - t0);
    const float reveal_t = std::min(width * 0.11F, 0.016F);
    const float reveal_z = wall_h * 0.020F;
    const float frame_t = std::min(width * 0.10F, 0.014F);
    const float frame_z = wall_h * 0.022F;

    const float reveal_t0 = t0 + reveal_t;
    const float reveal_t1 = t1 - reveal_t;
    const float reveal_z0 = z0 + reveal_z;
    const float reveal_z1 = z1 - reveal_z;
    const float glass_t0 = reveal_t0 + frame_t;
    const float glass_t1 = reveal_t1 - frame_t;
    const float glass_z0 = reveal_z0 + frame_z;
    const float glass_z1 = reveal_z1 - frame_z;

    const QColor recess = scaledColor(spec.wall_color, 0.46F);
    const QColor recess_outline = scaledColor(spec.wall_color, 0.38F);
    const QColor frame = scaledColor(spec.trim_color, 0.88F);
    const QColor frame_outline = scaledColor(spec.trim_color, 0.55F);

    drawFaceDetail(painter, a, b, t0, t1, z0, z1,
                   view, canvas, recess, recess_outline);
    drawFaceDetail(painter, a, b, reveal_t0, reveal_t1, reveal_z0, reveal_z1,
                   view, canvas, frame, frame_outline);

    const QPolygonF inner_opening = {
        projectPoint(lerpPoint(a, b, glass_t0, glass_z0), view, canvas),
        projectPoint(lerpPoint(a, b, glass_t1, glass_z0), view, canvas),
        projectPoint(lerpPoint(a, b, glass_t1, glass_z1), view, canvas),
        projectPoint(lerpPoint(a, b, glass_t0, glass_z1), view, canvas),
    };
    const QRectF glass_bounds = inner_opening.boundingRect();
    QLinearGradient glass_gradient(glass_bounds.topLeft(), glass_bounds.bottomRight());
    glass_gradient.setColorAt(0.0, scaledColor(spec.glass_color, 0.60F));
    glass_gradient.setColorAt(0.38, scaledColor(spec.glass_color, 0.78F));
    glass_gradient.setColorAt(0.72, scaledColor(spec.glass_color, 0.94F));
    glass_gradient.setColorAt(1.0, scaledColor(spec.glass_color, 0.70F));
    QPen glass_outline(scaledColor(spec.glass_color, 0.44F), kStructuralOutlineWidth,
                       Qt::SolidLine, Qt::SquareCap, Qt::MiterJoin);
    glass_outline.setMiterLimit(3.0);
    painter.setPen(glass_outline);
    painter.setBrush(glass_gradient);
    painter.drawPolygon(inner_opening);

    painter.save();
    painter.setPen(Qt::NoPen);
    const QColor inner_shadow = alphaColor(scaledColor(spec.wall_color, 0.34F), 105);
    const float shadow_t = std::min((glass_t1 - glass_t0) * 0.08F, 0.007F);
    const float shadow_z = wall_h * 0.012F;

    const QPolygonF top_reveal_shadow = {
        projectPoint(lerpPoint(a, b, glass_t0, glass_z1 - shadow_z), view, canvas),
        projectPoint(lerpPoint(a, b, glass_t1, glass_z1 - shadow_z), view, canvas),
        projectPoint(lerpPoint(a, b, glass_t1, glass_z1), view, canvas),
        projectPoint(lerpPoint(a, b, glass_t0, glass_z1), view, canvas),
    };
    painter.setBrush(inner_shadow);
    painter.drawPolygon(top_reveal_shadow);

    const QPolygonF side_reveal_shadow = {
        projectPoint(lerpPoint(a, b, glass_t0, glass_z0), view, canvas),
        projectPoint(lerpPoint(a, b, glass_t0 + shadow_t, glass_z0), view, canvas),
        projectPoint(lerpPoint(a, b, glass_t0 + shadow_t, glass_z1), view, canvas),
        projectPoint(lerpPoint(a, b, glass_t0, glass_z1), view, canvas),
    };
    painter.setBrush(alphaColor(scaledColor(spec.wall_color, 0.42F), 72));
    painter.drawPolygon(side_reveal_shadow);
    painter.restore();

    // Controlled architectural micro-geometry: a shallow projecting head,
    // narrow jamb returns and a two-step sill. These stay deliberately small so
    // the opening gains thickness without turning into ornamental noise.
    const float trim_projection_t = std::min(width * 0.045F, 0.006F);
    const float head_z0 = z1 - wall_h * 0.010F;
    const float head_z1 = z1 + wall_h * 0.026F;
    drawFaceDetail(painter, a, b,
                   t0 - trim_projection_t, t1 + trim_projection_t,
                   head_z0, head_z1, view, canvas,
                   scaledColor(spec.trim_color, 0.94F),
                   scaledColor(spec.trim_color, 0.56F));

    const float jamb_width = std::min(width * 0.055F, 0.008F);
    drawFaceDetail(painter, a, b,
                   t0 - trim_projection_t, t0 + jamb_width,
                   z0, z1, view, canvas,
                   scaledColor(spec.trim_color, 0.88F),
                   scaledColor(spec.trim_color, 0.54F));
    drawFaceDetail(painter, a, b,
                   t1 - jamb_width, t1 + trim_projection_t,
                   z0, z1, view, canvas,
                   scaledColor(spec.trim_color, 0.84F),
                   scaledColor(spec.trim_color, 0.52F));

    const float sill_t = 0.010F;
    const float sill_z0 = z0 - wall_h * 0.024F;
    const float sill_z1 = z0 + wall_h * 0.010F;
    drawFaceDetail(painter, a, b, t0 - sill_t, t1 + sill_t, sill_z0, sill_z1,
                   view, canvas,
                   scaledColor(spec.trim_color, 0.88F),
                   scaledColor(spec.trim_color, 0.50F));

    // Thin drip edge under the sill gives the projection a readable lower lip.
    drawFaceDetail(painter, a, b, t0 - sill_t * 0.72F, t1 + sill_t * 0.72F,
                   sill_z0 - wall_h * 0.010F, sill_z0,
                   view, canvas,
                   scaledColor(spec.trim_color, 0.70F),
                   scaledColor(spec.trim_color, 0.46F));
}

void drawWindows(QPainter& painter, const BuildingComposerSpec& spec,
                 const Point3 a, const Point3 b, const int edge,
                 const float wall_h, const BuildingView view, const QSize canvas) {
    if (!spec.windows) return;

    const bool entrance_edge = spec.south_door && edge == 2;
    if (entrance_edge) {
        for (const FacadeAperture& aperture : entranceWindowLayout(spec)) {
            drawWindowModule(painter, spec, a, b, aperture.t0, aperture.t1, wall_h, view, canvas);
        }
        return;
    }

    auto window = [&](const float t0, const float t1) {
        drawWindowModule(painter, spec, a, b, t0, t1, wall_h, view, canvas);
    };

    switch (spec.window_pattern) {
        case BuildingWindowPattern::Single:
            window(0.36F, 0.64F);
            break;
        case BuildingWindowPattern::Pair:
            window(0.16F, 0.34F);
            window(0.66F, 0.84F);
            break;
        case BuildingWindowPattern::Strip:
            window(0.08F, 0.22F);
            window(0.29F, 0.43F);
            window(0.57F, 0.71F);
            window(0.78F, 0.92F);
            break;
    }
}

void drawSouthModules(QPainter& painter, const BuildingComposerSpec& spec,
                      const Point3 a, const Point3 b, const float wall_h,
                      const BuildingView view, const QSize canvas) {
    if (!spec.south_door) return;

    const float center = doorCenter(spec.door_position);
    const float half = 0.12F;
    const float t0 = std::clamp(center - half, 0.05F, 0.80F);
    const float t1 = std::clamp(center + half, 0.20F, 0.95F);
    const float opening_t = 0.016F;
    const float frame_t = 0.013F;
    const float opening_z0 = 0.45F;
    const float opening_z1 = wall_h * 0.595F;
    const float frame_z0 = 0.75F;
    const float frame_z1 = wall_h * 0.575F;
    const float leaf_t0 = t0 + opening_t + frame_t;
    const float leaf_t1 = t1 - opening_t - frame_t;
    const float leaf_z0 = 1.15F;
    const float leaf_z1 = wall_h * 0.545F;

    const QColor recess = scaledColor(spec.wall_color, 0.43F);
    const QColor recess_outline = scaledColor(spec.wall_color, 0.34F);
    const QColor frame = scaledColor(spec.trim_color, 0.86F);
    const QColor frame_outline = scaledColor(spec.trim_color, 0.52F);

    drawFaceDetail(painter, a, b, t0, t1, opening_z0, opening_z1,
                   view, canvas, recess, recess_outline);
    drawFaceDetail(painter, a, b, t0 + opening_t, t1 - opening_t, frame_z0, frame_z1,
                   view, canvas, frame, frame_outline);

    const QPolygonF door_leaf = {
        projectPoint(lerpPoint(a, b, leaf_t0, leaf_z0), view, canvas),
        projectPoint(lerpPoint(a, b, leaf_t1, leaf_z0), view, canvas),
        projectPoint(lerpPoint(a, b, leaf_t1, leaf_z1), view, canvas),
        projectPoint(lerpPoint(a, b, leaf_t0, leaf_z1), view, canvas),
    };
    const QRectF door_bounds = door_leaf.boundingRect();
    QLinearGradient door_gradient(door_bounds.topLeft(), door_bounds.bottomRight());
    door_gradient.setColorAt(0.0, scaledColor(spec.door_color, 0.78F));
    door_gradient.setColorAt(0.50, scaledColor(spec.door_color, 0.94F));
    door_gradient.setColorAt(1.0, scaledColor(spec.door_color, 0.72F));
    QPen door_outline(scaledColor(spec.door_color, 0.48F), kStructuralOutlineWidth,
                      Qt::SolidLine, Qt::SquareCap, Qt::MiterJoin);
    door_outline.setMiterLimit(3.0);
    painter.setPen(door_outline);
    painter.setBrush(door_gradient);
    painter.drawPolygon(door_leaf);

    painter.save();
    painter.setBrush(Qt::NoBrush);
    painter.setPen(QPen(alphaColor(scaledColor(spec.door_color, 0.48F), 78), 0.70));
    constexpr int kWoodGrainLines = 4;
    for (int i = 1; i <= kWoodGrainLines; ++i) {
        const float t = leaf_t0 + (leaf_t1 - leaf_t0) * static_cast<float>(i) /
                                     static_cast<float>(kWoodGrainLines + 1);
        const float wobble = (hash01(spec.material_seed + 809, i, 0) - 0.5F) * 0.004F;
        painter.drawLine(
            projectPoint(lerpPoint(a, b, t + wobble, leaf_z0 + wall_h * 0.035F), view, canvas),
            projectPoint(lerpPoint(a, b, t - wobble, leaf_z1 - wall_h * 0.035F), view, canvas));
    }
    painter.restore();

    painter.save();
    painter.setPen(Qt::NoPen);
    const float shadow_t = std::min((leaf_t1 - leaf_t0) * 0.08F, 0.008F);
    const float shadow_z = wall_h * 0.014F;
    const QPolygonF top_reveal_shadow = {
        projectPoint(lerpPoint(a, b, leaf_t0, leaf_z1 - shadow_z), view, canvas),
        projectPoint(lerpPoint(a, b, leaf_t1, leaf_z1 - shadow_z), view, canvas),
        projectPoint(lerpPoint(a, b, leaf_t1, leaf_z1), view, canvas),
        projectPoint(lerpPoint(a, b, leaf_t0, leaf_z1), view, canvas),
    };
    painter.setBrush(alphaColor(scaledColor(spec.wall_color, 0.30F), 112));
    painter.drawPolygon(top_reveal_shadow);

    const QPolygonF side_reveal_shadow = {
        projectPoint(lerpPoint(a, b, leaf_t0, leaf_z0), view, canvas),
        projectPoint(lerpPoint(a, b, leaf_t0 + shadow_t, leaf_z0), view, canvas),
        projectPoint(lerpPoint(a, b, leaf_t0 + shadow_t, leaf_z1), view, canvas),
        projectPoint(lerpPoint(a, b, leaf_t0, leaf_z1), view, canvas),
    };
    painter.setBrush(alphaColor(scaledColor(spec.wall_color, 0.38F), 78));
    painter.drawPolygon(side_reveal_shadow);
    painter.restore();

    // Door surround: restrained projecting header and jambs establish real
    // thickness while preserving the existing door design and proportions.
    const float surround_t = 0.010F;
    const float jamb_t = 0.012F;
    const float surround_top = opening_z1 + wall_h * 0.028F;
    drawFaceDetail(painter, a, b,
                   t0 - surround_t, t1 + surround_t,
                   opening_z1 - wall_h * 0.010F, surround_top,
                   view, canvas,
                   scaledColor(spec.trim_color, 0.92F),
                   scaledColor(spec.trim_color, 0.54F));
    drawFaceDetail(painter, a, b,
                   t0 - surround_t, t0 + jamb_t,
                   0.65F, opening_z1,
                   view, canvas,
                   scaledColor(spec.trim_color, 0.86F),
                   scaledColor(spec.trim_color, 0.52F));
    drawFaceDetail(painter, a, b,
                   t1 - jamb_t, t1 + surround_t,
                   0.65F, opening_z1,
                   view, canvas,
                   scaledColor(spec.trim_color, 0.82F),
                   scaledColor(spec.trim_color, 0.50F));

    const float threshold_t = 0.012F;
    drawFaceDetail(painter, a, b, t0 - threshold_t, t1 + threshold_t,
                   0.24F, 1.35F,
                   view, canvas,
                   scaledColor(spec.trim_color, 0.82F),
                   scaledColor(spec.trim_color, 0.46F));
    drawFaceDetail(painter, a, b, t0 - threshold_t * 0.72F, t1 + threshold_t * 0.72F,
                   0.16F, 0.34F,
                   view, canvas,
                   scaledColor(spec.trim_color, 0.68F),
                   scaledColor(spec.trim_color, 0.44F));

    if (spec.south_sign) {
        const float sign_half = 0.15F;
        drawFaceDetail(painter, a, b,
                       std::clamp(center - sign_half, 0.04F, 0.76F),
                       std::clamp(center + sign_half, 0.24F, 0.96F),
                       wall_h * 0.70F, wall_h * 0.83F,
                       view, canvas, spec.accent_color, scaledColor(spec.trim_color, 0.62F));
    }

    if (spec.south_awning) {
        const float awning_half = 0.18F;
        const Point3 inner0 = lerpPoint(a, b, std::clamp(center - awning_half, 0.03F, 0.70F), wall_h * 0.66F);
        const Point3 inner1 = lerpPoint(a, b, std::clamp(center + awning_half, 0.30F, 0.97F), wall_h * 0.66F);
        const Point3 outer0{inner0.x, inner0.y + 0.28F, wall_h * 0.59F};
        const Point3 outer1{inner1.x, inner1.y + 0.28F, wall_h * 0.59F};

        const QPolygonF canopy = {
            projectPoint(inner0, view, canvas),
            projectPoint(inner1, view, canvas),
            projectPoint(outer1, view, canvas),
            projectPoint(outer0, view, canvas),
        };
        drawOutlinedPolygon(painter, canopy, spec.accent_color, scaledColor(spec.trim_color, 0.62F));
    }
}

void drawChimney(QPainter& painter, const BuildingComposerSpec& spec,
                 const float half_w, const float half_d, const float wall_h, const float roof_h,
                 const BuildingView view, const QSize canvas) {
    if (!spec.roof_chimney) return;

    const float cx = -half_w * 0.30F;
    const float cy = -half_d * 0.18F;
    constexpr float size = 0.16F;
    const float z0 = wall_h + roof_h * 0.48F;
    const float z1 = z0 + 24.0F;

    const std::array<Point3, 4> corners = {
        Point3{cx - size, cy - size, z0},
        Point3{cx + size, cy - size, z0},
        Point3{cx + size, cy + size, z0},
        Point3{cx - size, cy + size, z0},
    };

    int near_index = 0;
    float near_y = -1.0e9F;
    for (int i = 0; i < 4; ++i) {
        const float y = static_cast<float>(projectPoint(corners[i], view, canvas).y());
        if (y > near_y) {
            near_y = y;
            near_index = i;
        }
    }

    const std::array<int, 2> edges = {(near_index + 3) % 4, near_index};
    for (const int edge : edges) {
        const int next = (edge + 1) % 4;
        const QPolygonF face = faceQuad(corners[edge], corners[next], z0, z1, view, canvas);
        const float factor = face.boundingRect().center().x() < canvas.width() * 0.5F ? 0.78F : 0.92F;
        drawOutlinedPolygon(painter, face, scaledColor(spec.door_color, factor));
    }

    QPolygonF cap;
    for (const Point3& corner : corners) cap << projectPoint({corner.x, corner.y, z1}, view, canvas);
    drawOutlinedPolygon(painter, cap, scaledColor(spec.door_color, 1.08F));
}

} // namespace

QString BuildingComposer::viewName(const BuildingView view) {
    switch (view) {
        case BuildingView::South: return "SOUTH";
        case BuildingView::East: return "EAST";
        case BuildingView::West: return "WEST";
        case BuildingView::North: return "NORTH";
    }
    return "UNKNOWN";
}

QString BuildingComposer::roofName(const BuildingRoofStyle style) {
    switch (style) {
        case BuildingRoofStyle::Gable: return "gable";
        case BuildingRoofStyle::Pyramid: return "pyramid";
        case BuildingRoofStyle::Flat: return "flat";
    }
    return "unknown";
}

QString BuildingComposer::doorPositionName(const BuildingDoorPosition position) {
    switch (position) {
        case BuildingDoorPosition::Left: return "left";
        case BuildingDoorPosition::Center: return "center";
        case BuildingDoorPosition::Right: return "right";
    }
    return "center";
}

QString BuildingComposer::windowPatternName(const BuildingWindowPattern pattern) {
    switch (pattern) {
        case BuildingWindowPattern::Single: return "single";
        case BuildingWindowPattern::Pair: return "pair";
        case BuildingWindowPattern::Strip: return "strip";
    }
    return "pair";
}

QString BuildingComposer::wallMaterialName(const BuildingWallMaterial material) {
    switch (material) {
        case BuildingWallMaterial::Solid: return "solid";
        case BuildingWallMaterial::Plaster: return "plaster";
        case BuildingWallMaterial::Brick: return "brick";
        case BuildingWallMaterial::Concrete: return "concrete";
        case BuildingWallMaterial::Timber: return "timber";
    }
    return "solid";
}

QString BuildingComposer::roofMaterialName(const BuildingRoofMaterial material) {
    switch (material) {
        case BuildingRoofMaterial::Solid: return "solid";
        case BuildingRoofMaterial::CeramicTile: return "ceramic_tile";
        case BuildingRoofMaterial::MetalSeam: return "metal_seam";
        case BuildingRoofMaterial::AsphaltShingle: return "asphalt_shingle";
    }
    return "solid";
}

QImage BuildingComposer::renderView(const BuildingComposerSpec& spec, const BuildingView view,
                                    const QSize canvas) {
    const QSize supersampled_canvas(
        canvas.width() * kRenderSupersampleScale,
        canvas.height() * kRenderSupersampleScale);
    QImage image(supersampled_canvas, QImage::Format_ARGB32_Premultiplied);
    image.fill(Qt::transparent);

    QPainter painter(&image);
    painter.setRenderHint(QPainter::Antialiasing, true);
    painter.scale(static_cast<qreal>(kRenderSupersampleScale),
                  static_cast<qreal>(kRenderSupersampleScale));

    const float half_w = std::max(1, spec.footprint_width_tiles) * 0.5F;
    const float half_d = std::max(1, spec.footprint_depth_tiles) * 0.5F;
    const float wall_h = static_cast<float>(std::max(24, spec.wall_height_px));
    const float roof_h = static_cast<float>(std::max(8, spec.roof_height_px));

    const std::array<Point3, 4> corners = {
        Point3{-half_w, -half_d, 0.0F},
        Point3{half_w, -half_d, 0.0F},
        Point3{half_w, half_d, 0.0F},
        Point3{-half_w, half_d, 0.0F},
    };

    std::array<QPointF, 4> ground{};
    std::array<QPointF, 4> top{};
    int near_index = 0;
    float near_y = -1.0e9F;
    for (int i = 0; i < 4; ++i) {
        ground[i] = projectPoint(corners[i], view, canvas);
        top[i] = projectPoint({corners[i].x, corners[i].y, wall_h}, view, canvas);
        if (ground[i].y() > near_y) {
            near_y = static_cast<float>(ground[i].y());
            near_index = i;
        }
    }

    if (spec.cast_shadow) {
        QPolygonF contact_shadow;
        for (const Point3 corner : corners) {
            contact_shadow << projectPoint({corner.x * 1.025F, corner.y * 1.025F, -1.5F}, view, canvas);
        }
        painter.setPen(Qt::NoPen);
        painter.setBrush(QColor(0, 0, 0, 58));
        painter.drawPolygon(contact_shadow);

        QPolygonF shadow;
        for (const Point3 corner : corners) {
            shadow << projectPoint({corner.x * 1.08F, corner.y * 1.08F, -4.0F}, view, canvas);
        }
        painter.setBrush(QColor(0, 0, 0, 46));
        painter.drawPolygon(shadow);
    }

    const std::array<int, 2> visible_edges = {
        (near_index + 3) % 4,
        near_index,
    };

    struct FaceDraw {
        int edge = 0;
        QPolygonF polygon;
        float shade = 1.0F;
    };
    std::vector<FaceDraw> wall_faces;
    wall_faces.reserve(2);
    for (const int edge : visible_edges) {
        const int next = (edge + 1) % 4;
        QPolygonF polygon = faceQuad(corners[edge], corners[next], 0.0F, wall_h, view, canvas);
        const float center_x = static_cast<float>(polygon.boundingRect().center().x());
        const float shade = center_x < canvas.width() * 0.5F ? 0.84F : 1.0F;
        wall_faces.push_back({edge, polygon, shade});
    }
    std::sort(wall_faces.begin(), wall_faces.end(), [](const FaceDraw& lhs, const FaceDraw& rhs) {
        return averageY(lhs.polygon) < averageY(rhs.polygon);
    });

    for (const FaceDraw& face : wall_faces) {
        drawLitWallPolygon(painter, face.polygon, spec.wall_color, face.shade);
        const int next = (face.edge + 1) % 4;
        drawWallMaterial(painter, spec, corners[face.edge], corners[next], face.edge, wall_h, view, canvas);
        drawStructuralPlinth(
            painter, spec, corners[face.edge], corners[next], wall_h, face.shade, view, canvas);
    }

    for (const int edge : visible_edges) {
        const int next = (edge + 1) % 4;
        const bool shade_start = edge == near_index;
        drawCornerAmbientOcclusion(
            painter, spec, corners[edge], corners[next], shade_start, wall_h, view, canvas);
        drawEaveAmbientOcclusion(
            painter, spec, corners[edge], corners[next], wall_h, view, canvas);
    }

    const QColor wall_ground_contact = alphaColor(scaledColor(spec.wall_color, 0.50F), 115);
    QPen wall_ground_contact_pen(wall_ground_contact, kContactLineWidth, Qt::SolidLine, Qt::SquareCap, Qt::MiterJoin);
    wall_ground_contact_pen.setMiterLimit(3.0);
    painter.setPen(wall_ground_contact_pen);
    const float wall_ground_contact_z = 0.85F;
    for (const int edge : visible_edges) {
        const int next = (edge + 1) % 4;
        painter.drawLine(
            projectPoint({corners[edge].x * kStructuralPlinthOutset,
                          corners[edge].y * kStructuralPlinthOutset,
                          wall_ground_contact_z}, view, canvas),
            projectPoint({corners[next].x * kStructuralPlinthOutset,
                          corners[next].y * kStructuralPlinthOutset,
                          wall_ground_contact_z}, view, canvas));
    }

    const QColor roof_wall_contact = alphaColor(scaledColor(spec.roof_color, 0.42F), 135);
    QPen roof_wall_contact_pen(roof_wall_contact, kContactLineWidth, Qt::SolidLine, Qt::SquareCap, Qt::MiterJoin);
    roof_wall_contact_pen.setMiterLimit(3.0);
    painter.setPen(roof_wall_contact_pen);
    const float roof_wall_contact_z = wall_h - 1.25F;
    for (const int edge : visible_edges) {
        const int next = (edge + 1) % 4;
        painter.drawLine(
            projectPoint({corners[edge].x, corners[edge].y, roof_wall_contact_z}, view, canvas),
            projectPoint({corners[next].x, corners[next].y, roof_wall_contact_z}, view, canvas));
    }

    for (const int edge : visible_edges) {
        const int next = (edge + 1) % 4;
        const Point3 a = corners[edge];
        const Point3 b = corners[next];

        drawWindows(painter, spec, a, b, edge, wall_h, view, canvas);
        if (edge == 2) {
            drawSouthModules(painter, spec, a, b, wall_h, view, canvas);
        }
    }

    struct RoofDraw {
        QPolygonF polygon;
        QColor color;
        int face_index = 0;
    };
    std::vector<RoofDraw> roof_faces;

    const float roof_overhang = spec.roof_style == BuildingRoofStyle::Flat ? 0.04F : 0.10F;
    const float roof_half_w = half_w + roof_overhang;
    const float roof_half_d = half_d + roof_overhang;
    const std::array<Point3, 4> roof_corners = {
        Point3{-roof_half_w, -roof_half_d, wall_h},
        Point3{roof_half_w, -roof_half_d, wall_h},
        Point3{roof_half_w, roof_half_d, wall_h},
        Point3{-roof_half_w, roof_half_d, wall_h},
    };
    std::array<QPointF, 4> roof_top{};
    for (int i = 0; i < 4; ++i) roof_top[i] = projectPoint(roof_corners[i], view, canvas);

    Point3 ridge0{};
    Point3 ridge1{};
    bool has_ridge = false;

    if (spec.roof_style == BuildingRoofStyle::Flat) {
        QPolygonF roof;
        for (const QPointF point : roof_top) roof << point;
        roof_faces.push_back({roof, spec.roof_color, 0});
    } else if (spec.roof_style == BuildingRoofStyle::Pyramid) {
        const Point3 apex{0.0F, 0.0F, wall_h + roof_h};
        for (const int edge : visible_edges) {
            const int next = (edge + 1) % 4;
            QPolygonF poly = {
                roof_top[edge],
                roof_top[next],
                projectPoint(apex, view, canvas),
            };
            const float factor = poly.boundingRect().center().x() < canvas.width() * 0.5F ? 0.86F : 1.06F;
            roof_faces.push_back({poly, scaledColor(spec.roof_color, factor), edge});
        }
    } else {
        const bool ridge_along_x = spec.footprint_width_tiles >= spec.footprint_depth_tiles;
        has_ridge = true;
        if (ridge_along_x) {
            ridge0 = {-roof_half_w, 0.0F, wall_h + roof_h};
            ridge1 = {roof_half_w, 0.0F, wall_h + roof_h};
        } else {
            ridge0 = {0.0F, -roof_half_d, wall_h + roof_h};
            ridge1 = {0.0F, roof_half_d, wall_h + roof_h};
        }

        for (const int edge : visible_edges) {
            QPolygonF poly;
            if (ridge_along_x) {
                if (edge == 0) {
                    poly = {roof_top[0], roof_top[1], projectPoint(ridge1, view, canvas), projectPoint(ridge0, view, canvas)};
                } else if (edge == 2) {
                    poly = {roof_top[2], roof_top[3], projectPoint(ridge0, view, canvas), projectPoint(ridge1, view, canvas)};
                } else if (edge == 1) {
                    poly = {roof_top[1], roof_top[2], projectPoint(ridge1, view, canvas)};
                } else {
                    poly = {roof_top[3], roof_top[0], projectPoint(ridge0, view, canvas)};
                }
            } else {
                if (edge == 1) {
                    poly = {roof_top[1], roof_top[2], projectPoint(ridge1, view, canvas), projectPoint(ridge0, view, canvas)};
                } else if (edge == 3) {
                    poly = {roof_top[3], roof_top[0], projectPoint(ridge0, view, canvas), projectPoint(ridge1, view, canvas)};
                } else if (edge == 0) {
                    poly = {roof_top[0], roof_top[1], projectPoint(ridge0, view, canvas)};
                } else {
                    poly = {roof_top[2], roof_top[3], projectPoint(ridge1, view, canvas)};
                }
            }
            const float factor = poly.boundingRect().center().x() < canvas.width() * 0.5F ? 0.86F : 1.06F;
            roof_faces.push_back({poly, scaledColor(spec.roof_color, factor), edge});
        }
    }

    std::sort(roof_faces.begin(), roof_faces.end(), [](const RoofDraw& lhs, const RoofDraw& rhs) {
        return averageY(lhs.polygon) < averageY(rhs.polygon);
    });
    for (const RoofDraw& roof : roof_faces) {
        drawOutlinedPolygon(painter, roof.polygon, roof.color, QColor(52, 45, 43, 225));
        drawRoofMaterial(painter, spec, roof.polygon, roof.face_index);
    }

    constexpr float kEaveThickness = 2.4F;
    const bool gable_ridge_along_x = spec.footprint_width_tiles >= spec.footprint_depth_tiles;
    const QColor eave_fascia = scaledColor(spec.roof_color, 0.43F);
    const QColor eave_fascia_outline = scaledColor(spec.roof_color, 0.32F);
    for (const int edge : visible_edges) {
        const bool physical_eave = spec.roof_style != BuildingRoofStyle::Gable ||
            (gable_ridge_along_x ? (edge == 0 || edge == 2) : (edge == 1 || edge == 3));
        if (!physical_eave) continue;

        const int next = (edge + 1) % 4;
        const QPolygonF fascia = {
            roof_top[edge],
            roof_top[next],
            projectPoint({roof_corners[next].x, roof_corners[next].y, wall_h - kEaveThickness}, view, canvas),
            projectPoint({roof_corners[edge].x, roof_corners[edge].y, wall_h - kEaveThickness}, view, canvas),
        };
        drawOutlinedPolygon(painter, fascia, eave_fascia, eave_fascia_outline);
    }

    const QColor eave_dark = scaledColor(spec.roof_color, 0.48F);
    for (const int edge : visible_edges) {
        const int next = (edge + 1) % 4;
        painter.setPen(QPen(eave_dark, kRoofEdgeWidth, Qt::SolidLine, Qt::RoundCap, Qt::RoundJoin));
        painter.drawLine(roof_top[edge], roof_top[next]);
    }

    if (has_ridge) {
        const QPointF ridge_start = projectPoint(ridge0, view, canvas);
        const QPointF ridge_end = projectPoint(ridge1, view, canvas);
        painter.setPen(QPen(scaledColor(spec.roof_color, 0.46F), kRoofEdgeWidth, Qt::SolidLine, Qt::RoundCap));
        painter.drawLine(ridge_start, ridge_end);
    }

    drawChimney(painter, spec, half_w, half_d, wall_h, roof_h, view, canvas);

    painter.end();
    return image.scaled(canvas, Qt::IgnoreAspectRatio, Qt::SmoothTransformation);
}

QImage BuildingComposer::renderSpriteSheet(const BuildingComposerSpec& spec, const QSize cell) {
    QImage sheet(cell.width() * 4, cell.height(), QImage::Format_ARGB32_Premultiplied);
    sheet.fill(Qt::transparent);
    QPainter painter(&sheet);
    for (int i = 0; i < static_cast<int>(kViews.size()); ++i) {
        painter.drawImage(i * cell.width(), 0, renderView(spec, kViews[i], cell));
    }
    painter.end();
    return sheet;
}

QImage BuildingComposer::renderReviewSheet(const BuildingComposerSpec& spec, const QSize cell) {
    constexpr int kHeader = 34;
    QImage sheet(cell.width() * 4, cell.height() + kHeader, QImage::Format_ARGB32_Premultiplied);
    sheet.fill(QColor("#172025"));

    QPainter painter(&sheet);
    painter.setRenderHint(QPainter::Antialiasing, true);
    QFont font(QStringLiteral("Arial"));
    font.setBold(true);
    font.setPointSize(9);
    painter.setFont(font);

    for (int i = 0; i < static_cast<int>(kViews.size()); ++i) {
        const int left = i * cell.width();
        painter.fillRect(QRect(left, 0, cell.width(), kHeader), QColor("#243238"));
        painter.setPen(QColor("#dce7ea"));
        painter.drawText(QRect(left, 0, cell.width(), kHeader), Qt::AlignCenter, viewName(kViews[i]));

        const QPointF center(left + cell.width() * 0.5F, kHeader + cell.height() - 42.0F);
        QPolygonF guide = {
            QPointF(center.x(), center.y() - ch::contracts::kTileHeight * 0.5F),
            QPointF(center.x() + ch::contracts::kTileWidth * 0.5F, center.y()),
            QPointF(center.x(), center.y() + ch::contracts::kTileHeight * 0.5F),
            QPointF(center.x() - ch::contracts::kTileWidth * 0.5F, center.y()),
        };
        painter.setPen(QPen(QColor(84, 113, 122, 130), 1.0));
        painter.setBrush(QColor(67, 96, 75, 55));
        painter.drawPolygon(guide);
        painter.drawImage(QPoint(left, kHeader), renderView(spec, kViews[i], cell));

        if (i > 0) {
            painter.setPen(QPen(QColor(58, 71, 76), 1.0));
            painter.drawLine(left, 0, left, sheet.height());
        }
    }
    painter.end();
    return sheet;
}

QJsonObject BuildingComposer::manifest(const BuildingComposerSpec& spec, const QSize frame) {
    QJsonArray views;
    for (const BuildingView view : kViews) views.append(viewName(view));

    QJsonArray sockets;
    if (spec.south_door) {
        sockets.append(QJsonObject{
            {"id", "entrance_south"},
            {"kind", "entrance"},
            {"edge", "south"},
            {"position", doorPositionName(spec.door_position)},
        });
    }
    if (spec.south_awning) {
        sockets.append(QJsonObject{
            {"id", "awning_south"},
            {"kind", "awning"},
            {"edge", "south"},
            {"parent", "entrance_south"},
        });
    }
    if (spec.south_sign) {
        sockets.append(QJsonObject{
            {"id", "sign_south"},
            {"kind", "sign"},
            {"edge", "south"},
            {"parent", "entrance_south"},
        });
    }
    if (spec.roof_chimney) {
        sockets.append(QJsonObject{
            {"id", "chimney_roof"},
            {"kind", "chimney"},
            {"surface", "roof"},
        });
    }

    QJsonObject metadata{
        {"generator", "City Horizon Studio Building/Asset Composer"},
        {"contractVersion", "CH_BUILDING_COMPOSER_V0"},
        {"featureRevision", "architectural_microgeometry_1"},
        {"status", "PILOT"},
        {"sourceRepresentation", "parametric_vector_volume"},
        {"runtimeRepresentation", "PNG_RGBA_bitmap"},
    };

    QJsonObject geometry{
        {"footprintWidthTiles", spec.footprint_width_tiles},
        {"footprintDepthTiles", spec.footprint_depth_tiles},
        {"wallHeightPx", spec.wall_height_px},
        {"roofHeightPx", spec.roof_height_px},
        {"roofStyle", roofName(spec.roof_style)},
    };

    QJsonObject projection{
        {"gridContract", ch::contracts::kGridContract},
        {"projection", "isometric_2_to_1"},
        {"logicalTileWidth", ch::contracts::kTileWidth},
        {"logicalTileHeight", ch::contracts::kTileHeight},
        {"frameWidth", frame.width()},
        {"frameHeight", frame.height()},
        {"views", views},
        {"groundAnchorX", frame.width() / 2},
        {"groundAnchorY", frame.height() - 42},
    };

    QJsonObject palette{
        {"wall", spec.wall_color.name(QColor::HexRgb)},
        {"roof", spec.roof_color.name(QColor::HexRgb)},
        {"trim", spec.trim_color.name(QColor::HexRgb)},
        {"glass", spec.glass_color.name(QColor::HexRgb)},
        {"door", spec.door_color.name(QColor::HexRgb)},
        {"accent", spec.accent_color.name(QColor::HexRgb)},
    };

    QJsonObject materials{
        {"wall", wallMaterialName(spec.wall_material)},
        {"roof", roofMaterialName(spec.roof_material)},
        {"strength", static_cast<double>(std::clamp(spec.material_strength, 0.0F, 1.0F))},
        {"scale", static_cast<double>(std::clamp(spec.material_scale, 0.55F, 2.0F))},
        {"seed", spec.material_seed},
        {"sampling", "logical_surface_v0"},
        {"geometryMutation", false},
    };

    QJsonObject features{
        {"windows", spec.windows},
        {"windowPattern", windowPatternName(spec.window_pattern)},
        {"southDoor", spec.south_door},
        {"doorPosition", doorPositionName(spec.door_position)},
        {"southAwning", spec.south_awning},
        {"southSign", spec.south_sign},
        {"roofChimney", spec.roof_chimney},
        {"castShadow", spec.cast_shadow},
    };

    return {
        {"metadata", metadata},
        {"geometry", geometry},
        {"projection", projection},
        {"palette", palette},
        {"materials", materials},
        {"features", features},
        {"sockets", sockets},
    };
}

} // namespace ch::studio