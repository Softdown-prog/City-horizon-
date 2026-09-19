#include "building_facade_renderer.h"

#include "building_projected_shadow_renderer.h"
#include "building_roof_editor_renderer.h"
#include "src/ch_core/contracts.h"

#include <QFont>
#include <QJsonArray>
#include <QPainter>
#include <QPolygonF>

#include <algorithm>
#include <array>

namespace ch::studio {
namespace {

struct Point3 { float x = 0.0F; float y = 0.0F; float z = 0.0F; };
constexpr std::array<BuildingView, 4> kViews = {BuildingView::South, BuildingView::East, BuildingView::West, BuildingView::North};

Point3 rotatePoint(const Point3 p, const BuildingView view) {
    switch (view) {
        case BuildingView::East: return {-p.y, p.x, p.z};
        case BuildingView::North: return {-p.x, -p.y, p.z};
        case BuildingView::West: return {p.y, -p.x, p.z};
        case BuildingView::South: return p;
    }
    return p;
}

QPointF projectPoint(const Point3 p, const BuildingView view, const QSize canvas) {
    const Point3 r = rotatePoint(p, view);
    const float half_tile_w = static_cast<float>(ch::contracts::kTileWidth) * 0.5F;
    const float half_tile_h = static_cast<float>(ch::contracts::kTileHeight) * 0.5F;
    return {static_cast<float>(canvas.width()) * 0.5F + (r.x - r.y) * half_tile_w,
            static_cast<float>(canvas.height()) - 42.0F + (r.x + r.y) * half_tile_h - r.z};
}

Point3 lerpPoint(const Point3 a, const Point3 b, const float t, const float z) {
    return {a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t, z};
}

int edgeIndex(const BuildingStreetEdge edge) {
    switch (edge) {
        case BuildingStreetEdge::North: return 0;
        case BuildingStreetEdge::East: return 1;
        case BuildingStreetEdge::South: return 2;
        case BuildingStreetEdge::West: return 3;
    }
    return 2;
}

BuildingStreetEdge logicalEdge(const int edge) {
    switch (edge) {
        case 0: return BuildingStreetEdge::North;
        case 1: return BuildingStreetEdge::East;
        case 2: return BuildingStreetEdge::South;
        case 3: return BuildingStreetEdge::West;
    }
    return BuildingStreetEdge::South;
}

Point3 outwardNormal(const int edge) {
    switch (edge) {
        case 0: return {0.0F, -1.0F, 0.0F};
        case 1: return {1.0F, 0.0F, 0.0F};
        case 2: return {0.0F, 1.0F, 0.0F};
        case 3: return {-1.0F, 0.0F, 0.0F};
    }
    return {0.0F, 1.0F, 0.0F};
}

QColor scaledColor(const QColor color, const float factor, const int alpha = -1) {
    QColor result = QColor::fromRgbF(std::clamp(color.redF() * factor, 0.0F, 1.0F),
                                     std::clamp(color.greenF() * factor, 0.0F, 1.0F),
                                     std::clamp(color.blueF() * factor, 0.0F, 1.0F), color.alphaF());
    if (alpha >= 0) result.setAlpha(std::clamp(alpha, 0, 255));
    return result;
}

QColor blendColor(const QColor& base, const QColor& tint, const float amount) {
    const float t = std::clamp(amount, 0.0F, 1.0F);
    return QColor::fromRgbF(base.redF() * (1.0F - t) + tint.redF() * t,
                            base.greenF() * (1.0F - t) + tint.greenF() * t,
                            base.blueF() * (1.0F - t) + tint.blueF() * t,
                            base.alphaF());
}

QColor wallFaceTone(const BuildingComposerSpec& spec, const int edge) {
    if (edge == 3) return blendColor(scaledColor(spec.wall_color, 1.075F), QColor("#f7e7c9"), 0.060F);
    if (edge == 1) return blendColor(scaledColor(spec.wall_color, 0.735F), QColor("#64758a"), 0.095F);
    return scaledColor(spec.wall_color, 0.965F);
}

QPolygonF faceRect(const Point3 a, const Point3 b, const float t0, const float t1,
                   const float z0, const float z1, const BuildingView view, const QSize canvas) {
    return {projectPoint(lerpPoint(a, b, t0, z0), view, canvas), projectPoint(lerpPoint(a, b, t1, z0), view, canvas),
            projectPoint(lerpPoint(a, b, t1, z1), view, canvas), projectPoint(lerpPoint(a, b, t0, z1), view, canvas)};
}

void drawLocalizedAmbientOcclusion(QPainter& painter, const BuildingComposerSpec& spec,
                                   const std::array<Point3, 4>& corners,
                                   const std::array<int, 2>& visible_edges,
                                   const int near_index,
                                   const BuildingView view, const QSize canvas) {
    const float wall_h = static_cast<float>(BuildingComposer::effectiveWallHeightPx(spec));
    const QColor ao = scaledColor(spec.wall_color, 0.42F);

    // Remove the broader legacy contact bands from the composed body first.
    // This tiny neutral strip is intentionally material-free: the eave contact
    // owns this zone and will be repainted immediately below with compact AO.
    painter.save();
    painter.setPen(Qt::NoPen);
    for (const int edge : visible_edges) {
        const Point3 a = corners[edge];
        const Point3 b = corners[(edge + 1) % 4];
        painter.setBrush(wallFaceTone(spec, edge));
        painter.drawPolygon(faceRect(a, b, 0.012F, 0.988F, wall_h - 5.7F, wall_h, view, canvas));
        painter.setPen(QPen(wallFaceTone(spec, edge), 1.30, Qt::SolidLine, Qt::SquareCap, Qt::MiterJoin));
        painter.drawLine(projectPoint(lerpPoint(a, b, 0.015F, 0.80F), view, canvas),
                         projectPoint(lerpPoint(a, b, 0.985F, 0.80F), view, canvas));
        painter.setPen(Qt::NoPen);
    }
    painter.restore();

    constexpr float kEaveDepthPx = 3.4F;
    constexpr std::array<int, 3> kEaveAlpha = {30, 16, 7};
    const float eave_band = kEaveDepthPx / static_cast<float>(kEaveAlpha.size());
    painter.save();
    painter.setPen(Qt::NoPen);
    for (const int edge : visible_edges) {
        const Point3 a = corners[edge];
        const Point3 b = corners[(edge + 1) % 4];
        for (int band = 0; band < static_cast<int>(kEaveAlpha.size()); ++band) {
            const float z1 = wall_h - static_cast<float>(band) * eave_band;
            const float z0 = wall_h - static_cast<float>(band + 1) * eave_band;
            painter.setBrush(scaledColor(ao, 1.0F, kEaveAlpha[band]));
            painter.drawPolygon(faceRect(a, b, 0.015F, 0.985F, z0, z1, view, canvas));
        }
    }

    constexpr std::array<int, 3> kCornerAlpha = {20, 9, 4};
    constexpr float kCornerSpan = 0.036F;
    const float corner_band = kCornerSpan / static_cast<float>(kCornerAlpha.size());
    for (int visible = 0; visible < static_cast<int>(visible_edges.size()); ++visible) {
        const int edge = visible_edges[visible];
        const Point3 a = corners[edge];
        const Point3 b = corners[(edge + 1) % 4];
        const bool contact_at_start = edge == near_index;
        for (int band = 0; band < static_cast<int>(kCornerAlpha.size()); ++band) {
            float t0 = 0.0F;
            float t1 = 0.0F;
            if (contact_at_start) {
                t0 = static_cast<float>(band) * corner_band;
                t1 = static_cast<float>(band + 1) * corner_band;
            } else {
                t0 = 1.0F - static_cast<float>(band + 1) * corner_band;
                t1 = 1.0F - static_cast<float>(band) * corner_band;
            }
            painter.setBrush(scaledColor(ao, 0.94F, kCornerAlpha[band]));
            painter.drawPolygon(faceRect(a, b, t0, t1, 1.0F, wall_h - 1.2F, view, canvas));
        }
    }
    painter.restore();

    painter.save();
    painter.setBrush(Qt::NoBrush);
    painter.setPen(QPen(scaledColor(spec.wall_color, 0.38F, 78), 0.88,
                        Qt::SolidLine, Qt::SquareCap, Qt::MiterJoin));
    for (const int edge : visible_edges) {
        const Point3 a = corners[edge];
        const Point3 b = corners[(edge + 1) % 4];
        painter.drawLine(projectPoint(lerpPoint(a, b, 0.02F, 0.72F), view, canvas),
                         projectPoint(lerpPoint(a, b, 0.98F, 0.72F), view, canvas));
    }
    painter.restore();
}

void drawModule(QPainter& painter, const BuildingComposerSpec& spec,
                const BuildingFacadeModulePlacement& module,
                const Point3 a, const Point3 b, const int edge,
                const BuildingView view, const QSize canvas) {
    if (!module.enabled) return;
    const int floor = std::clamp(module.floor_index, 0, std::clamp(spec.floor_count, 1, 8) - 1);
    const float floor_h = static_cast<float>(std::clamp(spec.floor_height_px, 36, 132));
    const float base_z = floor_h * static_cast<float>(floor);
    const float center = std::clamp(module.position, 0.05F, 0.95F);
    const float width = std::clamp(module.width, 0.06F, 0.90F);
    const float t0 = std::clamp(center - width * 0.5F, 0.03F, 0.94F);
    const float t1 = std::clamp(center + width * 0.5F, 0.06F, 0.97F);

    painter.save();
    painter.setRenderHint(QPainter::Antialiasing, true);
    if (module.kind == BuildingFacadeModuleKind::Window) {
        const float z0 = base_z + floor_h * 0.28F, z1 = base_z + floor_h * 0.74F;
        painter.setPen(QPen(scaledColor(spec.trim_color, 0.52F), 1.15)); painter.setBrush(scaledColor(spec.trim_color, 0.90F));
        painter.drawPolygon(faceRect(a, b, t0, t1, z0, z1, view, canvas));
        const float inset = std::min(0.014F, (t1 - t0) * 0.10F);
        painter.setPen(QPen(scaledColor(spec.glass_color, 0.48F), 0.85)); painter.setBrush(scaledColor(spec.glass_color, 0.86F));
        painter.drawPolygon(faceRect(a, b, t0 + inset, t1 - inset, z0 + floor_h * 0.035F, z1 - floor_h * 0.035F, view, canvas));
        painter.setPen(QPen(scaledColor(spec.wall_color, 0.36F, 68), 0.72));
        painter.drawLine(projectPoint(lerpPoint(a, b, t0 + inset, z1 - floor_h * 0.035F), view, canvas),
                         projectPoint(lerpPoint(a, b, t1 - inset, z1 - floor_h * 0.035F), view, canvas));
        painter.setPen(QPen(scaledColor(spec.trim_color, 0.62F, 155), 0.65));
        painter.drawLine(projectPoint(lerpPoint(a, b, center, z0 + floor_h * 0.035F), view, canvas),
                         projectPoint(lerpPoint(a, b, center, z1 - floor_h * 0.035F), view, canvas));
    } else if (module.kind == BuildingFacadeModuleKind::Door) {
        const float z0 = base_z + 0.8F, z1 = base_z + floor_h * 0.78F;
        painter.setPen(QPen(scaledColor(spec.trim_color, 0.50F), 1.15)); painter.setBrush(scaledColor(spec.trim_color, 0.88F));
        painter.drawPolygon(faceRect(a, b, t0, t1, z0, z1, view, canvas));
        const float inset = std::min(0.014F, (t1 - t0) * 0.10F);
        painter.setPen(QPen(scaledColor(spec.door_color, 0.46F), 0.95)); painter.setBrush(spec.door_color);
        painter.drawPolygon(faceRect(a, b, t0 + inset, t1 - inset, z0 + 1.1F, z1 - floor_h * 0.035F, view, canvas));
        painter.setPen(QPen(scaledColor(spec.wall_color, 0.34F, 72), 0.74));
        painter.drawLine(projectPoint(lerpPoint(a, b, t0 + inset, z1 - floor_h * 0.035F), view, canvas),
                         projectPoint(lerpPoint(a, b, t1 - inset, z1 - floor_h * 0.035F), view, canvas));
    } else if (module.kind == BuildingFacadeModuleKind::Storefront) {
        const float z0 = base_z + floor_h * 0.10F, z1 = base_z + floor_h * 0.78F;
        painter.setPen(QPen(scaledColor(spec.trim_color, 0.50F), 1.0)); painter.setBrush(scaledColor(spec.glass_color, 0.80F));
        painter.drawPolygon(faceRect(a, b, t0, t1, z0, z1, view, canvas));
        painter.setPen(QPen(scaledColor(spec.wall_color, 0.35F, 62), 0.70));
        painter.drawLine(projectPoint(lerpPoint(a, b, t0, z1), view, canvas), projectPoint(lerpPoint(a, b, t1, z1), view, canvas));
        painter.setPen(QPen(scaledColor(spec.trim_color, 0.64F), 0.8));
        painter.drawLine(projectPoint(lerpPoint(a, b, center, z0), view, canvas), projectPoint(lerpPoint(a, b, center, z1), view, canvas));
    } else if (module.kind == BuildingFacadeModuleKind::Sign) {
        painter.setPen(QPen(scaledColor(spec.trim_color, 0.54F), 1.0)); painter.setBrush(spec.accent_color);
        painter.drawPolygon(faceRect(a, b, t0, t1, base_z + floor_h * 0.72F, base_z + floor_h * 0.90F, view, canvas));
    } else if (module.kind == BuildingFacadeModuleKind::Awning) {
        const float z = base_z + floor_h * 0.70F;
        const Point3 n = outwardNormal(edge), i0 = lerpPoint(a, b, t0, z), i1 = lerpPoint(a, b, t1, z);
        const Point3 o0{i0.x + n.x * 0.26F, i0.y + n.y * 0.26F, z - floor_h * 0.08F};
        const Point3 o1{i1.x + n.x * 0.26F, i1.y + n.y * 0.26F, z - floor_h * 0.08F};
        painter.setPen(QPen(scaledColor(spec.trim_color, 0.52F), 1.0)); painter.setBrush(spec.accent_color);
        painter.drawPolygon(QPolygonF{projectPoint(i0, view, canvas), projectPoint(i1, view, canvas),
                                      projectPoint(o1, view, canvas), projectPoint(o0, view, canvas)});
    } else if (module.kind == BuildingFacadeModuleKind::DoubleDoor) {
        const float z0 = base_z + 0.8F, z1 = base_z + floor_h * 0.80F;
        painter.setPen(QPen(scaledColor(spec.trim_color, 0.48F), 1.15));
        painter.setBrush(scaledColor(spec.trim_color, 0.90F));
        painter.drawPolygon(faceRect(a, b, t0, t1, z0, z1, view, canvas));
        const float inset = std::min(0.012F, (t1 - t0) * 0.08F);
        painter.setPen(QPen(scaledColor(spec.glass_color, 0.45F), 0.9));
        painter.setBrush(scaledColor(spec.glass_color, 0.82F));
        painter.drawPolygon(faceRect(a, b, t0 + inset, t1 - inset, z0 + 1.2F, z1 - floor_h * 0.035F, view, canvas));
        painter.setPen(QPen(scaledColor(spec.wall_color, 0.34F, 70), 0.72));
        painter.drawLine(projectPoint(lerpPoint(a, b, t0 + inset, z1 - floor_h * 0.035F), view, canvas),
                         projectPoint(lerpPoint(a, b, t1 - inset, z1 - floor_h * 0.035F), view, canvas));
        painter.setPen(QPen(scaledColor(spec.trim_color, 0.58F), 1.0));
        painter.drawLine(projectPoint(lerpPoint(a, b, center, z0 + 1.2F), view, canvas),
                         projectPoint(lerpPoint(a, b, center, z1 - floor_h * 0.035F), view, canvas));
    } else if (module.kind == BuildingFacadeModuleKind::GarageDoor) {
        const float z0 = base_z + 0.8F, z1 = base_z + floor_h * 0.70F;
        painter.setPen(QPen(scaledColor(spec.trim_color, 0.45F), 1.2));
        painter.setBrush(scaledColor(spec.trim_color, 0.66F));
        painter.drawPolygon(faceRect(a, b, t0, t1, z0, z1, view, canvas));
        painter.setPen(QPen(scaledColor(spec.trim_color, 0.48F, 180), 0.65));
        constexpr int kPanels = 5;
        for (int panel = 1; panel < kPanels; ++panel) {
            const float z = z0 + (z1 - z0) * static_cast<float>(panel) / static_cast<float>(kPanels);
            painter.drawLine(projectPoint(lerpPoint(a, b, t0, z), view, canvas),
                             projectPoint(lerpPoint(a, b, t1, z), view, canvas));
        }
    } else if (module.kind == BuildingFacadeModuleKind::Balcony) {
        const float rail_z0 = base_z + floor_h * 0.26F;
        const float rail_z1 = base_z + floor_h * 0.48F;
        const Point3 n = outwardNormal(edge);
        const Point3 i0 = lerpPoint(a, b, t0, rail_z0), i1 = lerpPoint(a, b, t1, rail_z0);
        const Point3 o0{i0.x + n.x * 0.24F, i0.y + n.y * 0.24F, rail_z0 - 1.2F};
        const Point3 o1{i1.x + n.x * 0.24F, i1.y + n.y * 0.24F, rail_z0 - 1.2F};
        painter.setPen(QPen(scaledColor(spec.trim_color, 0.48F), 0.9));
        painter.setBrush(scaledColor(spec.trim_color, 0.78F));
        painter.drawPolygon(QPolygonF{projectPoint(i0, view, canvas), projectPoint(i1, view, canvas),
                                      projectPoint(o1, view, canvas), projectPoint(o0, view, canvas)});
        painter.setBrush(Qt::NoBrush);
        painter.setPen(QPen(scaledColor(spec.trim_color, 0.42F), 1.0));
        painter.drawLine(projectPoint(lerpPoint(a, b, t0, rail_z1), view, canvas),
                         projectPoint(lerpPoint(a, b, t1, rail_z1), view, canvas));
        for (int i = 0; i <= 4; ++i) {
            const float t = t0 + (t1 - t0) * static_cast<float>(i) / 4.0F;
            painter.drawLine(projectPoint(lerpPoint(a, b, t, rail_z0), view, canvas),
                             projectPoint(lerpPoint(a, b, t, rail_z1), view, canvas));
        }
    } else if (module.kind == BuildingFacadeModuleKind::Marquee) {
        const float z = base_z + floor_h * 0.76F;
        const Point3 n = outwardNormal(edge), i0 = lerpPoint(a, b, t0, z), i1 = lerpPoint(a, b, t1, z);
        const Point3 o0{i0.x + n.x * 0.38F, i0.y + n.y * 0.38F, z - 1.5F};
        const Point3 o1{i1.x + n.x * 0.38F, i1.y + n.y * 0.38F, z - 1.5F};
        painter.setPen(QPen(scaledColor(spec.trim_color, 0.46F), 1.1));
        painter.setBrush(scaledColor(spec.trim_color, 0.84F));
        painter.drawPolygon(QPolygonF{projectPoint(i0, view, canvas), projectPoint(i1, view, canvas),
                                      projectPoint(o1, view, canvas), projectPoint(o0, view, canvas)});
        painter.setPen(QPen(scaledColor(spec.accent_color, 0.72F), 1.0));
        painter.drawLine(projectPoint(o0, view, canvas), projectPoint(o1, view, canvas));
    } else if (module.kind == BuildingFacadeModuleKind::Hvac) {
        const float z0 = base_z + floor_h * 0.40F, z1 = base_z + floor_h * 0.58F;
        painter.setPen(QPen(scaledColor(spec.trim_color, 0.44F), 0.95));
        painter.setBrush(scaledColor(spec.trim_color, 0.70F));
        painter.drawPolygon(faceRect(a, b, t0, t1, z0, z1, view, canvas));
        painter.setPen(QPen(scaledColor(spec.trim_color, 0.40F), 0.6));
        const float mid_z = (z0 + z1) * 0.5F;
        painter.drawLine(projectPoint(lerpPoint(a, b, t0 + (t1 - t0) * 0.15F, mid_z), view, canvas),
                         projectPoint(lerpPoint(a, b, t1 - (t1 - t0) * 0.15F, mid_z), view, canvas));
    } else if (module.kind == BuildingFacadeModuleKind::Planter) {
        const float z0 = base_z + floor_h * 0.18F, z1 = base_z + floor_h * 0.28F;
        painter.setPen(QPen(scaledColor(spec.door_color, 0.54F), 0.9));
        painter.setBrush(scaledColor(spec.door_color, 0.82F));
        painter.drawPolygon(faceRect(a, b, t0, t1, z0, z1, view, canvas));
        painter.setPen(QPen(QColor(71, 105, 63, 220), 1.2));
        for (int i = 1; i <= 3; ++i) {
            const float t = t0 + (t1 - t0) * static_cast<float>(i) / 4.0F;
            const QPointF root = projectPoint(lerpPoint(a, b, t, z1), view, canvas);
            painter.drawLine(root, QPointF(root.x(), root.y() - 4.0));
        }
    }
    painter.restore();
}

void drawFloorBands(QPainter& painter, const BuildingComposerSpec& spec,
                    const std::array<Point3, 4>& corners, const std::array<int, 2>& visible_edges,
                    const BuildingView view, const QSize canvas) {
    if (!spec.floor_bands_enabled || spec.floor_count <= 1) return;
    const float floor_h = static_cast<float>(std::clamp(spec.floor_height_px, 36, 132));
    painter.save(); painter.setPen(QPen(scaledColor(spec.trim_color, 0.54F, 105), 0.85));
    for (int floor = 1; floor < std::clamp(spec.floor_count, 1, 8); ++floor) {
        const float z = floor_h * static_cast<float>(floor);
        for (const int edge : visible_edges)
            painter.drawLine(projectPoint({corners[edge].x, corners[edge].y, z}, view, canvas),
                             projectPoint({corners[(edge + 1) % 4].x, corners[(edge + 1) % 4].y, z}, view, canvas));
    }
    painter.restore();
}

void drawAutomaticFloors(QPainter& painter, const BuildingComposerSpec& spec,
                         const std::array<Point3, 4>& corners, const std::array<int, 2>& visible_edges,
                         const BuildingView view, const QSize canvas) {
    const int floors = std::clamp(spec.floor_count, 1, 8);
    for (const int edge : visible_edges) {
        const BuildingStreetEdge logical = logicalEdge(edge);
        for (int floor = 0; floor < floors; ++floor) {
            const bool ground_south = floor == 0 && logical == BuildingStreetEdge::South && spec.south_door;
            if (ground_south) {
                const float door_position = spec.door_position == BuildingDoorPosition::Left ? 0.24F
                    : spec.door_position == BuildingDoorPosition::Right ? 0.76F : 0.50F;
                drawModule(painter, spec, {BuildingFacadeModuleKind::Door, logical, floor, door_position, 0.22F, true},
                           corners[edge], corners[(edge + 1) % 4], edge, view, canvas);
                if (spec.windows) {
                    const float first_window = spec.door_position == BuildingDoorPosition::Left ? 0.53F : 0.20F;
                    const float second_window = spec.door_position == BuildingDoorPosition::Right ? 0.47F : 0.80F;
                    drawModule(painter, spec, {BuildingFacadeModuleKind::Window, logical, floor, first_window, 0.18F, true},
                               corners[edge], corners[(edge + 1) % 4], edge, view, canvas);
                    drawModule(painter, spec, {BuildingFacadeModuleKind::Window, logical, floor, second_window, 0.18F, true},
                               corners[edge], corners[(edge + 1) % 4], edge, view, canvas);
                }
                if (spec.south_sign)
                    drawModule(painter, spec, {BuildingFacadeModuleKind::Sign, logical, floor, door_position, 0.34F, true},
                               corners[edge], corners[(edge + 1) % 4], edge, view, canvas);
                if (spec.south_awning)
                    drawModule(painter, spec, {BuildingFacadeModuleKind::Awning, logical, floor, door_position, 0.38F, true},
                               corners[edge], corners[(edge + 1) % 4], edge, view, canvas);
            } else if (spec.windows) {
                const bool strip = spec.window_pattern == BuildingWindowPattern::Strip;
                if (strip) {
                    for (const float p : {0.14F, 0.38F, 0.62F, 0.86F})
                        drawModule(painter, spec, {BuildingFacadeModuleKind::Window, logical, floor, p, 0.14F, true},
                                   corners[edge], corners[(edge + 1) % 4], edge, view, canvas);
                } else if (spec.window_pattern == BuildingWindowPattern::Single) {
                    drawModule(painter, spec, {BuildingFacadeModuleKind::Window, logical, floor, 0.50F, 0.24F, true},
                               corners[edge], corners[(edge + 1) % 4], edge, view, canvas);
                } else {
                    drawModule(painter, spec, {BuildingFacadeModuleKind::Window, logical, floor, 0.28F, 0.18F, true},
                               corners[edge], corners[(edge + 1) % 4], edge, view, canvas);
                    drawModule(painter, spec, {BuildingFacadeModuleKind::Window, logical, floor, 0.72F, 0.18F, true},
                               corners[edge], corners[(edge + 1) % 4], edge, view, canvas);
                }
            }
        }
    }
}

} // namespace

QImage BuildingFacadeRenderer::renderView(const BuildingComposerSpec& spec, const BuildingView view, const QSize canvas) {
    BuildingComposerSpec render_spec = spec;
    render_spec.wall_height_px = BuildingComposer::effectiveWallHeightPx(spec);

    // The production facade path owns the global cast shadow. Disable the
    // legacy shadow in the roof/body renderer so only one shadow model is ever
    // composited into exported sprites.
    render_spec.cast_shadow = false;

    // Facade modules are always authored after the body/roof pass. This keeps
    // the Classic Tycoon material ramp free to repaint the wall surface without
    // covering doors, windows, signs or awnings, including single-storey legacy presets.
    render_spec.windows = false;
    render_spec.south_door = false;
    render_spec.south_awning = false;
    render_spec.south_sign = false;

    const QImage building = BuildingRoofEditorRenderer::renderView(render_spec, view, canvas);
    QImage image(canvas, QImage::Format_ARGB32_Premultiplied);
    image.fill(Qt::transparent);
    {
        QPainter composition(&image);
        composition.setRenderHint(QPainter::Antialiasing, true);
        BuildingProjectedShadowRenderer::draw(composition, spec, view, canvas);
        composition.drawImage(QPoint(0, 0), building);
    }

    const float half_w = static_cast<float>(std::max(1, spec.footprint_width_tiles)) * 0.5F;
    const float half_d = static_cast<float>(std::max(1, spec.footprint_depth_tiles)) * 0.5F;
    const std::array<Point3, 4> corners = {Point3{-half_w, -half_d, 0.0F}, Point3{half_w, -half_d, 0.0F},
                                            Point3{half_w, half_d, 0.0F}, Point3{-half_w, half_d, 0.0F}};
    int near_index = 0; float near_y = -1.0e9F;
    for (int i = 0; i < 4; ++i) {
        const float y = static_cast<float>(projectPoint(corners[i], view, canvas).y());
        if (y > near_y) { near_y = y; near_index = i; }
    }
    const std::array<int, 2> visible_edges = {(near_index + 3) % 4, near_index};

    QPainter painter(&image); painter.setRenderHint(QPainter::Antialiasing, true);
    drawLocalizedAmbientOcclusion(painter, spec, corners, visible_edges, near_index, view, canvas);
    drawFloorBands(painter, spec, corners, visible_edges, view, canvas);
    if (spec.facade_editor_enabled) {
        for (const auto& module : spec.facade_modules) {
            const int edge = edgeIndex(module.edge);
            if (edge == visible_edges[0] || edge == visible_edges[1])
                drawModule(painter, spec, module, corners[edge], corners[(edge + 1) % 4], edge, view, canvas);
        }
    } else {
        drawAutomaticFloors(painter, spec, corners, visible_edges, view, canvas);
    }
    painter.end();
    return image;
}

QImage BuildingFacadeRenderer::renderSpriteSheet(const BuildingComposerSpec& spec, const QSize cell) {
    QImage sheet(cell.width() * 4, cell.height(), QImage::Format_ARGB32_Premultiplied); sheet.fill(Qt::transparent);
    QPainter painter(&sheet);
    for (int i = 0; i < static_cast<int>(kViews.size()); ++i) painter.drawImage(i * cell.width(), 0, renderView(spec, kViews[i], cell));
    painter.end(); return sheet;
}

QImage BuildingFacadeRenderer::renderReviewSheet(const BuildingComposerSpec& spec, const QSize cell) {
    constexpr int kHeader = 34;
    QImage sheet(cell.width() * 4, cell.height() + kHeader, QImage::Format_ARGB32_Premultiplied); sheet.fill(QColor("#172025"));
    QPainter painter(&sheet); QFont font(QStringLiteral("Arial")); font.setBold(true); font.setPointSize(9); painter.setFont(font);
    for (int i = 0; i < static_cast<int>(kViews.size()); ++i) {
        const int left = i * cell.width(); painter.fillRect(QRect(left, 0, cell.width(), kHeader), QColor("#243238"));
        painter.setPen(QColor("#dce7ea")); painter.drawText(QRect(left, 0, cell.width(), kHeader), Qt::AlignCenter, BuildingComposer::viewName(kViews[i]));
        painter.drawImage(QPoint(left, kHeader), renderView(spec, kViews[i], cell));
        if (i > 0) { painter.setPen(QPen(QColor(58, 71, 76), 1.0)); painter.drawLine(left, 0, left, sheet.height()); }
    }
    painter.end(); return sheet;
}

QJsonObject BuildingFacadeRenderer::manifest(const BuildingComposerSpec& spec) {
    QJsonObject manifest = BuildingComposer::facadeEditorManifest(spec);
    manifest.insert("ambientOcclusion", QJsonObject{
        {"version", "localized_contact_ao_1"},
        {"eaveDepthPx", 3.4},
        {"eaveAlphaBands", QJsonArray{30, 16, 7}},
        {"cornerNormalizedSpan", 0.036},
        {"cornerAlphaBands", QJsonArray{20, 9, 4}},
        {"wallGroundContactAlpha", 78},
        {"recessContactEnabled", true},
    });
    manifest.insert("castShadow", BuildingProjectedShadowRenderer::manifest());
    return manifest;
}

} // namespace ch::studio
