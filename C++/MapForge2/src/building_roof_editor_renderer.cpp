#include "building_roof_editor_renderer.h"

#include "src/ch_core/contracts.h"

#include <QFont>
#include <QPainter>
#include <QPainterPath>
#include <QPen>
#include <QPolygonF>

#include <algorithm>
#include <array>
#include <cmath>
#include <utility>
#include <vector>

namespace ch::studio {
namespace {

struct Point3 {
    float x = 0.0F;
    float y = 0.0F;
    float z = 0.0F;
};

struct RoofFace {
    QPolygonF polygon;
    int index = 0;
};

constexpr std::array<BuildingView, 4> kViews = {
    BuildingView::South,
    BuildingView::East,
    BuildingView::West,
    BuildingView::North,
};

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

QPointF lerpScreen(const QPointF& a, const QPointF& b, const float t) {
    return {
        a.x() + (b.x() - a.x()) * t,
        a.y() + (b.y() - a.y()) * t,
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

QColor blendColor(const QColor& base, const QColor& tint, const float amount) {
    const float t = std::clamp(amount, 0.0F, 1.0F);
    return QColor::fromRgbF(
        base.redF() * (1.0F - t) + tint.redF() * t,
        base.greenF() * (1.0F - t) + tint.greenF() * t,
        base.blueF() * (1.0F - t) + tint.blueF() * t,
        base.alphaF());
}

QColor classicRampColor(const QColor& base, const bool lit_face) {
    if (lit_face) {
        return blendColor(scaledColor(base, 1.055F), QColor("#f7e7c9"), 0.055F);
    }
    return blendColor(scaledColor(base, 0.765F), QColor("#64758a"), 0.085F);
}

float averageY(const QPolygonF& polygon) {
    float total = 0.0F;
    for (const QPointF& point : polygon) total += static_cast<float>(point.y());
    return polygon.isEmpty() ? 0.0F : total / static_cast<float>(polygon.size());
}

float screenDistance(const QPointF& a, const QPointF& b) {
    return static_cast<float>(std::hypot(b.x() - a.x(), b.y() - a.y()));
}

QPolygonF wallFacePolygon(const Point3& a, const Point3& b, const float z0, const float z1,
                          const BuildingView view, const QSize canvas) {
    return {
        projectPoint({a.x, a.y, z0}, view, canvas),
        projectPoint({b.x, b.y, z0}, view, canvas),
        projectPoint({b.x, b.y, z1}, view, canvas),
        projectPoint({a.x, a.y, z1}, view, canvas),
    };
}

QPointF wallPoint(const Point3& a, const Point3& b, const float t, const float z,
                  const BuildingView view, const QSize canvas) {
    return projectPoint({a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t, z}, view, canvas);
}

std::array<QPointF, 2> roofRowEndpoints(const QPolygonF& polygon, const float v) {
    const float t = std::clamp(v, 0.0F, 1.0F);
    if (polygon.size() == 3) {
        const QPointF apex = polygon[2];
        return {
            lerpScreen(apex, polygon[0], t),
            lerpScreen(apex, polygon[1], t),
        };
    }
    if (polygon.size() >= 4) {
        return {
            lerpScreen(polygon[3], polygon[0], t),
            lerpScreen(polygon[2], polygon[1], t),
        };
    }
    const QPointF fallback = polygon.isEmpty() ? QPointF() : polygon.front();
    return {fallback, fallback};
}

QPointF roofRowPoint(const std::array<QPointF, 2>& row, const float u) {
    return lerpScreen(row[0], row[1], std::clamp(u, 0.0F, 1.0F));
}

void drawProjectedShadow(QPainter& painter, const std::array<Point3, 4>& corners,
                         const float wall_h, const float roof_h,
                         const BuildingView view, const QSize canvas) {
    QPolygonF footprint;
    for (const Point3& corner : corners) footprint << projectPoint(corner, view, canvas);

    const float height = wall_h + roof_h * 0.55F;
    const float length = std::clamp(height * 0.30F, 17.0F, 30.0F);
    const QPointF offset(-length * 0.78F, -length * 0.18F);
    QPolygonF projected;
    for (const QPointF& point : footprint) projected << point + offset;

    QPainterPath shadow_path;
    shadow_path.addPolygon(footprint);
    shadow_path.addPolygon(projected);
    for (int i = 0; i < footprint.size(); ++i) {
        const int next = (i + 1) % footprint.size();
        shadow_path.addPolygon(QPolygonF{
            footprint[i], footprint[next], projected[next], projected[i],
        });
    }

    painter.save();
    painter.setPen(Qt::NoPen);
    painter.translate(1.25, 1.25);
    painter.setBrush(QColor(29, 37, 47, 24));
    painter.drawPath(shadow_path);
    painter.translate(-1.25, -1.25);
    painter.setBrush(QColor(28, 36, 46, 72));
    painter.drawPath(shadow_path);
    painter.setBrush(QColor(24, 30, 36, 74));
    painter.drawPolygon(footprint);
    painter.restore();
}

void drawClassicWallMaterial(QPainter& painter, const BuildingComposerSpec& spec,
                             const Point3& a, const Point3& b, const int edge,
                             const float wall_h, const bool lit_face,
                             const BuildingView view, const QSize canvas) {
    const QPolygonF face = wallFacePolygon(a, b, 0.0F, wall_h, view, canvas);
    QPainterPath clip;
    clip.addPolygon(face);
    clip.closeSubpath();

    const float strength = std::clamp(spec.material_strength, 0.0F, 1.0F);
    const float scale = std::clamp(spec.material_scale, 0.55F, 2.0F);
    const float variation = std::clamp(spec.material_variation, 0.0F, 1.0F);
    const float contrast = std::clamp(spec.material_contrast, 0.0F, 1.0F);
    const float edge_span = std::max(0.5F, std::hypot(b.x - a.x, b.y - a.y));
    const QColor ramp = classicRampColor(
        spec.wall_material == BuildingWallMaterial::Glass ? spec.glass_color : spec.wall_color,
        lit_face);
    const QColor dark = alphaColor(scaledColor(ramp, 0.70F - 0.10F * contrast),
                                   48 + static_cast<int>(100.0F * strength));
    const QColor mid = alphaColor(scaledColor(ramp, 0.90F),
                                  24 + static_cast<int>(58.0F * strength));
    const QColor light = alphaColor(scaledColor(ramp, 1.11F),
                                    18 + static_cast<int>(58.0F * strength));

    painter.save();
    painter.setClipPath(clip);
    painter.setPen(QPen(QColor(45, 49, 51, 215), 1.10, Qt::SolidLine, Qt::SquareCap, Qt::MiterJoin));
    painter.setBrush(ramp);
    painter.drawPolygon(face);

    if (spec.wall_material == BuildingWallMaterial::Plaster) {
        // Broad trowel passes: deterministic, continuous and low frequency.
        const int bands = std::max(3, static_cast<int>(wall_h / std::max(19.0F, 27.0F * scale)));
        for (int band = 0; band < bands; ++band) {
            const float z0 = wall_h * static_cast<float>(band) / static_cast<float>(bands);
            const float z1 = wall_h * static_cast<float>(band + 1) / static_cast<float>(bands);
            const float inset = 0.025F + 0.010F * static_cast<float>((band + edge) % 2);
            painter.setPen(Qt::NoPen);
            painter.setBrush(band % 2 == 0
                                 ? alphaColor(scaledColor(ramp, 1.035F), 8 + static_cast<int>(18.0F * strength))
                                 : alphaColor(scaledColor(ramp, 0.965F), 7 + static_cast<int>(16.0F * strength)));
            painter.drawPolygon(QPolygonF{
                wallPoint(a, b, inset, z0 + 1.0F, view, canvas),
                wallPoint(a, b, 1.0F - inset, z0 + 1.0F, view, canvas),
                wallPoint(a, b, 1.0F - inset, z1 - 1.0F, view, canvas),
                wallPoint(a, b, inset, z1 - 1.0F, view, canvas),
            });
            painter.setPen(QPen(alphaColor(band % 2 == 0 ? light : mid, 30 + static_cast<int>(24.0F * strength)), 0.62));
            painter.drawLine(wallPoint(a, b, 0.05F, z1 - 1.0F, view, canvas),
                             wallPoint(a, b, 0.95F, z1 - 1.0F, view, canvas));
        }
    } else if (spec.wall_material == BuildingWallMaterial::Brick) {
        // Rigid masonry bond: horizontal courses and staggered vertical mortar joints.
        const float course_px = std::max(7.0F, 10.5F * scale);
        const int courses = std::max(4, static_cast<int>(wall_h / course_px));
        const int columns = std::max(4, static_cast<int>(edge_span * 6.5F / scale));
        const QColor mortar = alphaColor(blendColor(scaledColor(ramp, 0.58F), QColor("#c8bda9"), 0.18F),
                                         75 + static_cast<int>(90.0F * strength));
        painter.setPen(QPen(mortar, 0.78 + 0.28 * contrast));
        for (int row = 1; row < courses; ++row) {
            const float z = wall_h * static_cast<float>(row) / static_cast<float>(courses);
            painter.drawLine(wallPoint(a, b, 0.0F, z, view, canvas),
                             wallPoint(a, b, 1.0F, z, view, canvas));
        }
        for (int row = 0; row < courses; ++row) {
            const float z0 = wall_h * static_cast<float>(row) / static_cast<float>(courses);
            const float z1 = wall_h * static_cast<float>(row + 1) / static_cast<float>(courses);
            const float stagger = row % 2 == 0 ? 0.0F : 0.5F;
            for (int col = 1; col <= columns; ++col) {
                const float t = (static_cast<float>(col) + stagger) / static_cast<float>(columns);
                if (t <= 0.025F || t >= 0.975F) continue;
                painter.drawLine(wallPoint(a, b, t, z0 + 0.5F, view, canvas),
                                 wallPoint(a, b, t, z1 - 0.5F, view, canvas));
            }
            if ((row + edge) % 3 == 1) {
                painter.setPen(QPen(alphaColor(light, 24 + static_cast<int>(28.0F * variation)), 0.52));
                painter.drawLine(wallPoint(a, b, 0.02F, z1 - 1.0F, view, canvas),
                                 wallPoint(a, b, 0.98F, z1 - 1.0F, view, canvas));
                painter.setPen(QPen(mortar, 0.78 + 0.28 * contrast));
            }
        }
    } else if (spec.wall_material == BuildingWallMaterial::Concrete) {
        // Cast panels: large bays with recessed joints and a controlled edge highlight.
        const int horizontal_panels = std::max(2, static_cast<int>(edge_span * 1.8F / scale));
        const int vertical_panels = std::max(2, static_cast<int>(wall_h / std::max(30.0F, 42.0F * scale)));
        painter.setPen(QPen(alphaColor(dark, 100 + static_cast<int>(45.0F * strength)), 0.90));
        for (int col = 1; col < horizontal_panels; ++col) {
            const float t = static_cast<float>(col) / static_cast<float>(horizontal_panels);
            painter.drawLine(wallPoint(a, b, t, 0.0F, view, canvas),
                             wallPoint(a, b, t, wall_h, view, canvas));
        }
        for (int row = 1; row < vertical_panels; ++row) {
            const float z = wall_h * static_cast<float>(row) / static_cast<float>(vertical_panels);
            painter.drawLine(wallPoint(a, b, 0.0F, z, view, canvas),
                             wallPoint(a, b, 1.0F, z, view, canvas));
        }
        painter.setPen(QPen(alphaColor(light, 38 + static_cast<int>(30.0F * strength)), 0.70));
        const float highlight_t = std::min(0.985F, 0.012F + 0.004F * contrast);
        for (int col = 1; col < horizontal_panels; ++col) {
            const float t = static_cast<float>(col) / static_cast<float>(horizontal_panels);
            painter.drawLine(wallPoint(a, b, std::min(0.99F, t + highlight_t), 2.0F, view, canvas),
                             wallPoint(a, b, std::min(0.99F, t + highlight_t), wall_h - 2.0F, view, canvas));
        }
    } else if (spec.wall_material == BuildingWallMaterial::Timber) {
        // Horizontal clapboards with a dark overlap and a narrow upper catching edge.
        const float board_px = std::max(5.5F, 8.5F * scale);
        const int boards = std::max(5, static_cast<int>(wall_h / board_px));
        for (int board = 1; board < boards; ++board) {
            const float z = wall_h * static_cast<float>(board) / static_cast<float>(boards);
            painter.setPen(QPen(alphaColor(dark, 72 + static_cast<int>(82.0F * strength)), 1.05));
            painter.drawLine(wallPoint(a, b, 0.0F, z, view, canvas),
                             wallPoint(a, b, 1.0F, z, view, canvas));
            painter.setPen(QPen(alphaColor(light, 22 + static_cast<int>(42.0F * strength)), 0.48));
            painter.drawLine(wallPoint(a, b, 0.0F, z + 1.15F, view, canvas),
                             wallPoint(a, b, 1.0F, z + 1.15F, view, canvas));
        }
        if (variation > 0.35F) {
            const int vertical_breaks = std::max(1, static_cast<int>(edge_span * 1.6F));
            painter.setPen(QPen(alphaColor(mid, 36), 0.55));
            for (int i = 1; i <= vertical_breaks; ++i) {
                const float t = static_cast<float>(i) / static_cast<float>(vertical_breaks + 1);
                painter.drawLine(wallPoint(a, b, t, wall_h * 0.08F, view, canvas),
                                 wallPoint(a, b, t, wall_h * 0.92F, view, canvas));
            }
        }
    } else if (spec.wall_material == BuildingWallMaterial::Stone) {
        // Course stone: alternating block counts, no random flecks or point noise.
        const float course_px = std::max(10.0F, 15.0F * scale);
        const int courses = std::max(3, static_cast<int>(wall_h / course_px));
        painter.setPen(QPen(alphaColor(dark, 105 + static_cast<int>(55.0F * strength)), 0.95));
        for (int row = 1; row < courses; ++row) {
            const float z = wall_h * static_cast<float>(row) / static_cast<float>(courses);
            painter.drawLine(wallPoint(a, b, 0.0F, z, view, canvas),
                             wallPoint(a, b, 1.0F, z, view, canvas));
        }
        for (int row = 0; row < courses; ++row) {
            const float z0 = wall_h * static_cast<float>(row) / static_cast<float>(courses);
            const float z1 = wall_h * static_cast<float>(row + 1) / static_cast<float>(courses);
            const int columns = 3 + ((row + edge) % 3);
            const float stagger = ((row + edge) % 2) ? 0.38F : 0.0F;
            for (int col = 1; col < columns; ++col) {
                const float t = (static_cast<float>(col) + stagger) / static_cast<float>(columns);
                if (t <= 0.05F || t >= 0.95F) continue;
                painter.drawLine(wallPoint(a, b, t, z0 + 0.8F, view, canvas),
                                 wallPoint(a, b, t, z1 - 0.8F, view, canvas));
            }
            if ((row + edge) % 2 == 0) {
                painter.setPen(QPen(alphaColor(light, 26 + static_cast<int>(25.0F * strength)), 0.55));
                painter.drawLine(wallPoint(a, b, 0.06F, z1 - 1.2F, view, canvas),
                                 wallPoint(a, b, 0.94F, z1 - 1.2F, view, canvas));
                painter.setPen(QPen(alphaColor(dark, 105 + static_cast<int>(55.0F * strength)), 0.95));
            }
        }
    } else if (spec.wall_material == BuildingWallMaterial::MetalPanel) {
        // Standing facade panels: dark seam plus a narrow light return on every rib.
        const int panels = std::max(3, static_cast<int>(edge_span * 5.2F / scale));
        for (int panel = 1; panel < panels; ++panel) {
            const float t = static_cast<float>(panel) / static_cast<float>(panels);
            painter.setPen(QPen(alphaColor(dark, 85 + static_cast<int>(90.0F * strength)), 0.92));
            painter.drawLine(wallPoint(a, b, t, 0.0F, view, canvas),
                             wallPoint(a, b, t, wall_h, view, canvas));
            const float highlight_t = std::min(0.994F, t + 0.007F);
            painter.setPen(QPen(alphaColor(light, 28 + static_cast<int>(52.0F * strength)), 0.50));
            painter.drawLine(wallPoint(a, b, highlight_t, 1.0F, view, canvas),
                             wallPoint(a, b, highlight_t, wall_h - 1.0F, view, canvas));
        }
        painter.setPen(QPen(alphaColor(mid, 44), 0.55));
        for (const float zf : {0.32F, 0.68F}) {
            painter.drawLine(wallPoint(a, b, 0.02F, wall_h * zf, view, canvas),
                             wallPoint(a, b, 0.98F, wall_h * zf, view, canvas));
        }
    } else if (spec.wall_material == BuildingWallMaterial::Glass) {
        // Curtain-wall bays with transoms and two broad reflection streaks following the facade plane.
        const int bays = std::max(3, static_cast<int>(edge_span * 5.0F / scale));
        const int levels = std::max(2, static_cast<int>(wall_h / std::max(28.0F, 38.0F * scale)));
        const QColor mullion = alphaColor(scaledColor(spec.trim_color, 0.46F),
                                          145 + static_cast<int>(75.0F * strength));
        painter.setPen(QPen(mullion, 0.82 + 0.25 * contrast));
        for (int bay = 1; bay < bays; ++bay) {
            const float t = static_cast<float>(bay) / static_cast<float>(bays);
            painter.drawLine(wallPoint(a, b, t, 0.0F, view, canvas),
                             wallPoint(a, b, t, wall_h, view, canvas));
        }
        for (int level = 1; level < levels; ++level) {
            const float z = wall_h * static_cast<float>(level) / static_cast<float>(levels);
            painter.drawLine(wallPoint(a, b, 0.0F, z, view, canvas),
                             wallPoint(a, b, 1.0F, z, view, canvas));
        }
        painter.setPen(QPen(alphaColor(scaledColor(spec.glass_color, 1.18F),
                                      55 + static_cast<int>(45.0F * strength)), 1.05));
        painter.drawLine(wallPoint(a, b, 0.08F, wall_h * 0.76F, view, canvas),
                         wallPoint(a, b, 0.44F, wall_h * 0.50F, view, canvas));
        painter.drawLine(wallPoint(a, b, 0.54F, wall_h * 0.60F, view, canvas),
                         wallPoint(a, b, 0.86F, wall_h * 0.37F, view, canvas));
    }

    const float plinth_h = std::clamp(wall_h * 0.075F, 5.0F, 9.0F);
    painter.setPen(Qt::NoPen);
    painter.setBrush(alphaColor(scaledColor(ramp, 0.62F), 215));
    painter.drawPolygon(wallFacePolygon(a, b, 0.0F, plinth_h, view, canvas));
    painter.setPen(QPen(alphaColor(scaledColor(ramp, 0.48F), 145), 0.85));
    painter.drawLine(wallPoint(a, b, 0.0F, plinth_h, view, canvas),
                     wallPoint(a, b, 1.0F, plinth_h, view, canvas));

    painter.setPen(Qt::NoPen);
    painter.setBrush(alphaColor(QColor(35, 42, 48), 42));
    painter.drawPolygon(wallFacePolygon(a, b, wall_h - 5.5F, wall_h, view, canvas));
    painter.setPen(QPen(alphaColor(QColor(31, 37, 42), 105), 1.05));
    painter.drawLine(wallPoint(a, b, 0.0F, 0.8F, view, canvas),
                     wallPoint(a, b, 1.0F, 0.8F, view, canvas));
    painter.restore();
}

void drawRoofMaterial(QPainter& painter, const BuildingComposerSpec& spec,
                      const QPolygonF& polygon, const int face_index) {
    if (spec.roof_material == BuildingRoofMaterial::Solid || polygon.size() < 3) return;

    QPainterPath clip;
    clip.addPolygon(polygon);
    clip.closeSubpath();

    const float strength = std::clamp(spec.material_strength, 0.0F, 1.0F);
    const float scale = std::clamp(spec.material_scale, 0.55F, 2.0F);
    const float variation = std::clamp(spec.material_variation, 0.0F, 1.0F);
    const float contrast = std::clamp(spec.material_contrast, 0.0F, 1.0F);
    const QColor dark = alphaColor(scaledColor(spec.roof_color, 0.58F - 0.12F * contrast),
                                   48 + static_cast<int>(105.0F * strength));
    const QColor mid = alphaColor(scaledColor(spec.roof_color, 0.82F),
                                  28 + static_cast<int>(64.0F * strength));
    const QColor light = alphaColor(scaledColor(spec.roof_color, 1.13F),
                                    20 + static_cast<int>(58.0F * strength));

    const auto ridge_row = roofRowEndpoints(polygon, 0.0F);
    const auto eave_row = roofRowEndpoints(polygon, 1.0F);
    const QPointF ridge_center = lerpScreen(ridge_row[0], ridge_row[1], 0.5F);
    const QPointF eave_center = lerpScreen(eave_row[0], eave_row[1], 0.5F);
    const float slope_length = std::max(8.0F, screenDistance(ridge_center, eave_center));

    painter.save();
    painter.setClipPath(clip);
    painter.setBrush(Qt::NoBrush);

    if (spec.roof_material == BuildingRoofMaterial::MetalSeam) {
        // Standing seams run from ridge to eave, independent of screen axes.
        const float eave_width = std::max(10.0F, screenDistance(eave_row[0], eave_row[1]));
        const int seams = std::max(3, static_cast<int>(std::round(eave_width / std::max(11.0F, 17.0F * scale))));
        for (int seam = 1; seam < seams; ++seam) {
            const float u = static_cast<float>(seam) / static_cast<float>(seams);
            const QPointF start = roofRowPoint(ridge_row, u);
            const QPointF end = roofRowPoint(eave_row, u);
            painter.setPen(QPen(dark, 0.86 + 0.30 * contrast));
            painter.drawLine(start, end);
            const float hu = std::min(0.995F, u + 0.007F);
            painter.setPen(QPen(light, 0.46));
            painter.drawLine(roofRowPoint(ridge_row, hu), roofRowPoint(eave_row, hu));
        }
        const int cross_bands = variation > 0.55F ? 2 : 1;
        painter.setPen(QPen(alphaColor(mid, 42), 0.52));
        for (int band = 1; band <= cross_bands; ++band) {
            const auto row = roofRowEndpoints(polygon, static_cast<float>(band) / static_cast<float>(cross_bands + 1));
            painter.drawLine(row[0], row[1]);
        }
    } else if (spec.roof_material == BuildingRoofMaterial::CeramicTile) {
        // Interlocking ceramic courses follow the roof plane; vertical joints are staggered by row.
        const float nominal_course = std::max(5.0F, 7.5F * scale);
        const int courses = std::max(2, static_cast<int>(std::round(slope_length / nominal_course)));
        for (int row_index = 1; row_index <= courses; ++row_index) {
            const float v0 = static_cast<float>(row_index - 1) / static_cast<float>(courses);
            const float v1 = static_cast<float>(row_index) / static_cast<float>(courses);
            const auto previous_row = roofRowEndpoints(polygon, v0);
            const auto current_row = roofRowEndpoints(polygon, v1);
            painter.setPen(QPen(dark, 0.74 + 0.26 * contrast));
            painter.drawLine(current_row[0], current_row[1]);

            const float row_width = std::max(8.0F, screenDistance(current_row[0], current_row[1]));
            const int tiles = std::max(2, static_cast<int>(std::round(row_width / std::max(8.0F, 12.5F * scale))));
            const float stagger = (row_index + face_index) % 2 == 0 ? 0.5F : 0.0F;
            for (int tile = 1; tile < tiles; ++tile) {
                const float u = (static_cast<float>(tile) + stagger) / static_cast<float>(tiles);
                if (u >= 0.98F) continue;
                const QPointF seam_top = roofRowPoint(previous_row, u);
                const QPointF seam_bottom = roofRowPoint(current_row, u);
                painter.drawLine(lerpScreen(seam_top, seam_bottom, 0.48F), seam_bottom);
            }

            painter.setPen(QPen(alphaColor(light, 28 + static_cast<int>(24.0F * strength)), 0.48));
            const auto highlight_row = roofRowEndpoints(polygon, std::max(0.0F, v1 - 0.012F));
            painter.drawLine(highlight_row[0], highlight_row[1]);
        }
    } else if (spec.roof_material == BuildingRoofMaterial::AsphaltShingle) {
        // Shingle courses remain horizontal to the eave while short tabs step down the slope.
        const float nominal_course = std::max(6.0F, 9.0F * scale);
        const int courses = std::max(2, static_cast<int>(std::round(slope_length / nominal_course)));
        for (int row_index = 1; row_index <= courses; ++row_index) {
            const float v0 = static_cast<float>(row_index - 1) / static_cast<float>(courses);
            const float v1 = static_cast<float>(row_index) / static_cast<float>(courses);
            const auto previous_row = roofRowEndpoints(polygon, v0);
            const auto current_row = roofRowEndpoints(polygon, v1);
            painter.setPen(QPen(dark, 0.64 + 0.28 * contrast));
            painter.drawLine(current_row[0], current_row[1]);

            const float row_width = std::max(8.0F, screenDistance(current_row[0], current_row[1]));
            const int tabs = std::max(2, static_cast<int>(std::round(row_width / std::max(10.0F, 15.0F * scale))));
            const float stagger = (row_index + face_index) % 2 == 0 ? 0.5F : 0.0F;
            for (int tab = 1; tab < tabs; ++tab) {
                const float u = (static_cast<float>(tab) + stagger) / static_cast<float>(tabs);
                if (u >= 0.98F) continue;
                const QPointF top = roofRowPoint(previous_row, u);
                const QPointF bottom = roofRowPoint(current_row, u);
                painter.drawLine(lerpScreen(top, bottom, 0.64F), bottom);
            }
            if ((row_index + face_index) % 3 == 0) {
                painter.setPen(QPen(alphaColor(mid, 38), 0.50));
                painter.drawLine(roofRowPoint(current_row, 0.08F), roofRowPoint(current_row, 0.92F));
            }
        }
    }

    painter.restore();
}

void drawFace(QPainter& painter, const BuildingComposerSpec& spec,
              const RoofFace& face, const QSize canvas) {
    if (face.polygon.size() < 3) return;
    const bool lit_face = face.polygon.boundingRect().center().x() >= canvas.width() * 0.5F;
    const QColor fill = classicRampColor(spec.roof_color, lit_face);
    const QColor outline = alphaColor(scaledColor(spec.roof_color, 0.30F), 225);
    QPen pen(outline, 1.20, Qt::SolidLine, Qt::SquareCap, Qt::MiterJoin);
    pen.setMiterLimit(3.0);
    painter.setPen(pen);
    painter.setBrush(fill);
    painter.drawPolygon(face.polygon);
    drawRoofMaterial(painter, spec, face.polygon, face.index);
}

void drawCapLine(QPainter& painter, const BuildingComposerSpec& spec,
                 const QPointF& a, const QPointF& b, const qreal base_width) {
    if (!spec.roof_ridge_enabled) return;
    const qreal scale = std::clamp<qreal>(static_cast<qreal>(spec.roof_ridge_scale), 0.5, 1.8);
    painter.setPen(QPen(alphaColor(scaledColor(spec.roof_color, 0.30F), 220),
                        base_width * scale, Qt::SolidLine, Qt::RoundCap, Qt::RoundJoin));
    painter.drawLine(a, b);
    painter.setPen(QPen(alphaColor(scaledColor(spec.roof_color, 0.72F), 235),
                        base_width * 0.66 * scale, Qt::SolidLine, Qt::RoundCap, Qt::RoundJoin));
    painter.drawLine(a, b);
    painter.setPen(QPen(alphaColor(scaledColor(spec.roof_color, 1.08F), 145),
                        base_width * 0.22 * scale, Qt::SolidLine, Qt::RoundCap));
    painter.drawLine(a, b);
}

void drawFascia(QPainter& painter, const BuildingComposerSpec& spec,
                const Point3& a, const Point3& b, const float wall_h,
                const BuildingView view, const QSize canvas) {
    if (!spec.roof_fascia_enabled) return;
    const float thickness = std::clamp(spec.roof_fascia_thickness_px, 0.5F, 6.0F);
    const QPointF top_a = projectPoint({a.x, a.y, wall_h}, view, canvas);
    const QPointF top_b = projectPoint({b.x, b.y, wall_h}, view, canvas);
    const QPointF low_a = projectPoint({a.x, a.y, wall_h - thickness}, view, canvas);
    const QPointF low_b = projectPoint({b.x, b.y, wall_h - thickness}, view, canvas);
    const QPolygonF fascia = {top_a, top_b, low_b, low_a};
    painter.setPen(QPen(alphaColor(scaledColor(spec.roof_color, 0.28F), 220), 0.85));
    painter.setBrush(scaledColor(spec.roof_color, 0.48F));
    painter.drawPolygon(fascia);
    painter.setPen(QPen(alphaColor(scaledColor(spec.roof_color, 0.22F), 220), 0.72));
    painter.drawLine(low_a, low_b);
}

QImage renderAdvancedRoof(const BuildingComposerSpec& spec, const BuildingView view, const QSize canvas) {
    BuildingComposerSpec body = spec;
    body.roof_style = BuildingRoofStyle::Flat;
    body.roof_height_px = 8;
    body.roof_material = BuildingRoofMaterial::Solid;
    body.roof_color = spec.wall_color;
    body.wall_material = BuildingWallMaterial::Solid;
    body.material_strength = 0.0F;
    body.cast_shadow = false;

    const float half_w = std::max(1, spec.footprint_width_tiles) * 0.5F;
    const float half_d = std::max(1, spec.footprint_depth_tiles) * 0.5F;
    const float wall_h = static_cast<float>(std::max(24, spec.wall_height_px));
    const float pitch_factor = std::clamp(spec.roof_pitch_degrees / 35.0F, 0.35F, 1.75F);
    const float roof_h = spec.roof_style == BuildingRoofStyle::Flat
        ? 4.0F
        : static_cast<float>(std::max(8, spec.roof_height_px)) * pitch_factor;
    const float overhang = std::clamp(spec.roof_overhang, 0.0F, 0.24F);
    const float roof_half_w = half_w + overhang;
    const float roof_half_d = half_d + overhang;

    const std::array<Point3, 4> corners = {
        Point3{-half_w, -half_d, 0.0F},
        Point3{ half_w, -half_d, 0.0F},
        Point3{ half_w,  half_d, 0.0F},
        Point3{-half_w,  half_d, 0.0F},
    };

    const QImage clean_body = BuildingComposer::renderView(body, view, canvas);
    QImage image(canvas, QImage::Format_ARGB32_Premultiplied);
    image.fill(Qt::transparent);
    QPainter painter(&image);
    painter.setRenderHint(QPainter::Antialiasing, true);

    if (spec.cast_shadow) drawProjectedShadow(painter, corners, wall_h, roof_h, view, canvas);
    painter.drawImage(QPoint(0, 0), clean_body);

    int near_index = 0;
    float near_y = -1.0e9F;
    for (int i = 0; i < 4; ++i) {
        const float y = static_cast<float>(projectPoint(corners[i], view, canvas).y());
        if (y > near_y) {
            near_y = y;
            near_index = i;
        }
    }
    const std::array<int, 2> visible_edges = {(near_index + 3) % 4, near_index};
    for (const int edge : visible_edges) {
        const int next = (edge + 1) % 4;
        const QPolygonF face = wallFacePolygon(corners[edge], corners[next], 0.0F, wall_h, view, canvas);
        const bool lit_face = face.boundingRect().center().x() >= canvas.width() * 0.5F;
        drawClassicWallMaterial(painter, spec, corners[edge], corners[next], edge,
                                wall_h, lit_face, view, canvas);
    }

    const std::array<Point3, 4> eaves = {
        Point3{-roof_half_w, -roof_half_d, wall_h},
        Point3{ roof_half_w, -roof_half_d, wall_h},
        Point3{ roof_half_w,  roof_half_d, wall_h},
        Point3{-roof_half_w,  roof_half_d, wall_h},
    };

    int roof_near_index = 0;
    float roof_near_y = -1.0e9F;
    for (int i = 0; i < 4; ++i) {
        const float y = static_cast<float>(projectPoint(eaves[i], view, canvas).y());
        if (y > roof_near_y) {
            roof_near_y = y;
            roof_near_index = i;
        }
    }
    const std::array<int, 2> roof_visible_edges = {(roof_near_index + 3) % 4, roof_near_index};

    std::vector<RoofFace> faces;
    std::vector<std::pair<QPointF, QPointF>> cap_lines;

    auto pushVisibleEdgeFacesToApex = [&](const Point3 apex) {
        for (const int edge : roof_visible_edges) {
            const int next = (edge + 1) % 4;
            faces.push_back({{
                projectPoint(eaves[edge], view, canvas),
                projectPoint(eaves[next], view, canvas),
                projectPoint(apex, view, canvas),
            }, edge});
        }
        cap_lines.push_back({projectPoint(apex, view, canvas),
                             projectPoint(eaves[roof_near_index], view, canvas)});
    };

    if (spec.roof_style == BuildingRoofStyle::Flat) {
        QPolygonF top;
        for (const Point3& p : eaves) {
            top << projectPoint({p.x, p.y, wall_h + 2.0F}, view, canvas);
        }
        faces.push_back({top, 0});
    } else if (spec.roof_style == BuildingRoofStyle::Pyramid) {
        pushVisibleEdgeFacesToApex({0.0F, 0.0F, wall_h + roof_h});
    } else if (spec.roof_style == BuildingRoofStyle::Shed) {
        const std::array<Point3, 4> shed = {
            Point3{-roof_half_w, -roof_half_d, wall_h + roof_h},
            Point3{ roof_half_w, -roof_half_d, wall_h + roof_h},
            Point3{ roof_half_w,  roof_half_d, wall_h + roof_h * 0.10F},
            Point3{-roof_half_w,  roof_half_d, wall_h + roof_h * 0.10F},
        };
        QPolygonF plane;
        for (const Point3& p : shed) plane << projectPoint(p, view, canvas);
        faces.push_back({plane, 0});
        cap_lines.push_back({projectPoint(shed[0], view, canvas), projectPoint(shed[1], view, canvas)});
    } else if (spec.roof_style == BuildingRoofStyle::Mansard) {
        constexpr float inset_factor = 0.62F;
        const float break_z = wall_h + roof_h * 0.58F;
        const std::array<Point3, 4> inner = {
            Point3{-roof_half_w * inset_factor, -roof_half_d * inset_factor, break_z},
            Point3{ roof_half_w * inset_factor, -roof_half_d * inset_factor, break_z},
            Point3{ roof_half_w * inset_factor,  roof_half_d * inset_factor, break_z},
            Point3{-roof_half_w * inset_factor,  roof_half_d * inset_factor, break_z},
        };
        for (const int edge : roof_visible_edges) {
            const int next = (edge + 1) % 4;
            faces.push_back({{
                projectPoint(eaves[edge], view, canvas),
                projectPoint(eaves[next], view, canvas),
                projectPoint(inner[next], view, canvas),
                projectPoint(inner[edge], view, canvas),
            }, edge});
            cap_lines.push_back({projectPoint(inner[edge], view, canvas),
                                 projectPoint(inner[next], view, canvas)});
        }

        const bool along_x = spec.footprint_width_tiles >= spec.footprint_depth_tiles;
        Point3 ridge0{};
        Point3 ridge1{};
        if (along_x) {
            const float ridge_x = roof_half_w * inset_factor * 0.58F;
            ridge0 = {-ridge_x, 0.0F, wall_h + roof_h};
            ridge1 = { ridge_x, 0.0F, wall_h + roof_h};
        } else {
            const float ridge_y = roof_half_d * inset_factor * 0.58F;
            ridge0 = {0.0F, -ridge_y, wall_h + roof_h};
            ridge1 = {0.0F,  ridge_y, wall_h + roof_h};
        }
        for (const int edge : roof_visible_edges) {
            QPolygonF upper;
            if (along_x) {
                if (edge == 0) upper = {projectPoint(inner[0], view, canvas), projectPoint(inner[1], view, canvas), projectPoint(ridge1, view, canvas), projectPoint(ridge0, view, canvas)};
                else if (edge == 2) upper = {projectPoint(inner[2], view, canvas), projectPoint(inner[3], view, canvas), projectPoint(ridge0, view, canvas), projectPoint(ridge1, view, canvas)};
                else if (edge == 1) upper = {projectPoint(inner[1], view, canvas), projectPoint(inner[2], view, canvas), projectPoint(ridge1, view, canvas)};
                else upper = {projectPoint(inner[3], view, canvas), projectPoint(inner[0], view, canvas), projectPoint(ridge0, view, canvas)};
            } else {
                if (edge == 1) upper = {projectPoint(inner[1], view, canvas), projectPoint(inner[2], view, canvas), projectPoint(ridge1, view, canvas), projectPoint(ridge0, view, canvas)};
                else if (edge == 3) upper = {projectPoint(inner[3], view, canvas), projectPoint(inner[0], view, canvas), projectPoint(ridge0, view, canvas), projectPoint(ridge1, view, canvas)};
                else if (edge == 0) upper = {projectPoint(inner[0], view, canvas), projectPoint(inner[1], view, canvas), projectPoint(ridge0, view, canvas)};
                else upper = {projectPoint(inner[2], view, canvas), projectPoint(inner[3], view, canvas), projectPoint(ridge1, view, canvas)};
            }
            faces.push_back({upper, edge + 10});
        }
        cap_lines.push_back({projectPoint(ridge0, view, canvas), projectPoint(ridge1, view, canvas)});
    } else {
        const bool along_x = spec.footprint_width_tiles >= spec.footprint_depth_tiles;
        Point3 ridge0{};
        Point3 ridge1{};
        if (spec.roof_style == BuildingRoofStyle::Hip) {
            if (along_x) {
                const float ridge_x = std::max(0.0F, roof_half_w - roof_half_d * 0.78F);
                ridge0 = {-ridge_x, 0.0F, wall_h + roof_h};
                ridge1 = { ridge_x, 0.0F, wall_h + roof_h};
            } else {
                const float ridge_y = std::max(0.0F, roof_half_d - roof_half_w * 0.78F);
                ridge0 = {0.0F, -ridge_y, wall_h + roof_h};
                ridge1 = {0.0F,  ridge_y, wall_h + roof_h};
            }
        } else {
            if (along_x) {
                ridge0 = {-roof_half_w, 0.0F, wall_h + roof_h};
                ridge1 = { roof_half_w, 0.0F, wall_h + roof_h};
            } else {
                ridge0 = {0.0F, -roof_half_d, wall_h + roof_h};
                ridge1 = {0.0F,  roof_half_d, wall_h + roof_h};
            }
        }

        for (const int edge : roof_visible_edges) {
            QPolygonF poly;
            if (along_x) {
                if (edge == 0) poly = {projectPoint(eaves[0], view, canvas), projectPoint(eaves[1], view, canvas), projectPoint(ridge1, view, canvas), projectPoint(ridge0, view, canvas)};
                else if (edge == 2) poly = {projectPoint(eaves[2], view, canvas), projectPoint(eaves[3], view, canvas), projectPoint(ridge0, view, canvas), projectPoint(ridge1, view, canvas)};
                else if (edge == 1) poly = {projectPoint(eaves[1], view, canvas), projectPoint(eaves[2], view, canvas), projectPoint(ridge1, view, canvas)};
                else poly = {projectPoint(eaves[3], view, canvas), projectPoint(eaves[0], view, canvas), projectPoint(ridge0, view, canvas)};
            } else {
                if (edge == 1) poly = {projectPoint(eaves[1], view, canvas), projectPoint(eaves[2], view, canvas), projectPoint(ridge1, view, canvas), projectPoint(ridge0, view, canvas)};
                else if (edge == 3) poly = {projectPoint(eaves[3], view, canvas), projectPoint(eaves[0], view, canvas), projectPoint(ridge0, view, canvas), projectPoint(ridge1, view, canvas)};
                else if (edge == 0) poly = {projectPoint(eaves[0], view, canvas), projectPoint(eaves[1], view, canvas), projectPoint(ridge0, view, canvas)};
                else poly = {projectPoint(eaves[2], view, canvas), projectPoint(eaves[3], view, canvas), projectPoint(ridge1, view, canvas)};
            }
            faces.push_back({poly, edge});
        }
        cap_lines.push_back({projectPoint(ridge0, view, canvas), projectPoint(ridge1, view, canvas)});
        if (spec.roof_style == BuildingRoofStyle::Hip) {
            cap_lines.push_back({projectPoint(ridge0, view, canvas),
                                 projectPoint(eaves[(along_x ? 3 : 0)], view, canvas)});
            cap_lines.push_back({projectPoint(ridge1, view, canvas),
                                 projectPoint(eaves[(along_x ? 1 : 2)], view, canvas)});
        }
    }

    std::sort(faces.begin(), faces.end(), [](const RoofFace& lhs, const RoofFace& rhs) {
        return averageY(lhs.polygon) < averageY(rhs.polygon);
    });
    for (const RoofFace& face : faces) drawFace(painter, spec, face, canvas);

    for (const int edge : roof_visible_edges) {
        const int next = (edge + 1) % 4;
        drawFascia(painter, spec, eaves[edge], eaves[next], wall_h, view, canvas);
    }
    for (const auto& line : cap_lines) drawCapLine(painter, spec, line.first, line.second, 3.0);

    painter.end();
    return image;
}

} // namespace

QImage BuildingRoofEditorRenderer::renderView(const BuildingComposerSpec& spec,
                                              const BuildingView view,
                                              const QSize canvas) {
    return renderAdvancedRoof(spec, view, canvas);
}

QImage BuildingRoofEditorRenderer::renderSpriteSheet(const BuildingComposerSpec& spec,
                                                     const QSize cell) {
    QImage sheet(cell.width() * 4, cell.height(), QImage::Format_ARGB32_Premultiplied);
    sheet.fill(Qt::transparent);
    QPainter painter(&sheet);
    for (int i = 0; i < static_cast<int>(kViews.size()); ++i) {
        painter.drawImage(i * cell.width(), 0, renderView(spec, kViews[i], cell));
    }
    painter.end();
    return sheet;
}

QImage BuildingRoofEditorRenderer::renderReviewSheet(const BuildingComposerSpec& spec,
                                                     const QSize cell) {
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
        painter.drawText(QRect(left, 0, cell.width(), kHeader), Qt::AlignCenter,
                         BuildingComposer::viewName(kViews[i]));
        painter.drawImage(QPoint(left, kHeader), renderView(spec, kViews[i], cell));
        if (i > 0) {
            painter.setPen(QPen(QColor(58, 71, 76), 1.0));
            painter.drawLine(left, 0, left, sheet.height());
        }
    }
    painter.end();
    return sheet;
}

QJsonObject BuildingRoofEditorRenderer::roofEditorManifest(const BuildingComposerSpec& spec) {
    return QJsonObject{
        {"version", "roof_editor_1"},
        {"profile", roofProfileName(spec.roof_style)},
        {"pitchDegrees", static_cast<double>(std::clamp(spec.roof_pitch_degrees, 12.0F, 60.0F))},
        {"overhang", static_cast<double>(std::clamp(spec.roof_overhang, 0.0F, 0.24F))},
        {"fasciaEnabled", spec.roof_fascia_enabled},
        {"fasciaThicknessPx", static_cast<double>(std::clamp(spec.roof_fascia_thickness_px, 0.5F, 6.0F))},
        {"ridgeEnabled", spec.roof_ridge_enabled},
        {"ridgeScale", static_cast<double>(std::clamp(spec.roof_ridge_scale, 0.5F, 1.8F))},
        {"singleParametricDefinition", true},
        {"visualRasterPass", "classic_tycoon_renderer_2"},
        {"materialRecipe", "structured_directional_materials_1"},
    };
}

} // namespace ch::studio
