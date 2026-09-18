#include "building_facade_renderer.h"

#include "building_roof_editor_renderer.h"
#include "src/ch_core/contracts.h"

#include <QFont>
#include <QPainter>
#include <QPolygonF>

#include <algorithm>
#include <array>
#include <cmath>

namespace ch::studio {
namespace {

struct Point3 {
    float x = 0.0F;
    float y = 0.0F;
    float z = 0.0F;
};

constexpr std::array<BuildingView, 4> kViews = {
    BuildingView::South, BuildingView::East, BuildingView::West, BuildingView::North,
};

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
    return {
        static_cast<float>(canvas.width()) * 0.5F + (r.x - r.y) * half_tile_w,
        static_cast<float>(canvas.height()) - 42.0F + (r.x + r.y) * half_tile_h - r.z,
    };
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
    QColor result = QColor::fromRgbF(
        std::clamp(color.redF() * factor, 0.0F, 1.0F),
        std::clamp(color.greenF() * factor, 0.0F, 1.0F),
        std::clamp(color.blueF() * factor, 0.0F, 1.0F),
        color.alphaF());
    if (alpha >= 0) result.setAlpha(std::clamp(alpha, 0, 255));
    return result;
}

QPolygonF faceRect(const Point3 a, const Point3 b, const float t0, const float t1,
                   const float z0, const float z1, const BuildingView view, const QSize canvas) {
    return {
        projectPoint(lerpPoint(a, b, t0, z0), view, canvas),
        projectPoint(lerpPoint(a, b, t1, z0), view, canvas),
        projectPoint(lerpPoint(a, b, t1, z1), view, canvas),
        projectPoint(lerpPoint(a, b, t0, z1), view, canvas),
    };
}

void drawModule(QPainter& painter, const BuildingComposerSpec& spec,
                const BuildingFacadeModulePlacement& module,
                const Point3 a, const Point3 b, const int edge,
                const BuildingView view, const QSize canvas) {
    if (!module.enabled) return;
    const int floor_count = std::clamp(spec.floor_count, 1, 8);
    const int floor = std::clamp(module.floor_index, 0, floor_count - 1);
    const float floor_h = static_cast<float>(std::clamp(spec.floor_height_px, 36, 132));
    const float base_z = floor_h * static_cast<float>(floor);
    const float top_z = base_z + floor_h;
    const float center = std::clamp(module.position, 0.05F, 0.95F);
    const float width = std::clamp(module.width, 0.06F, 0.90F);
    const float t0 = std::clamp(center - width * 0.5F, 0.03F, 0.94F);
    const float t1 = std::clamp(center + width * 0.5F, 0.06F, 0.97F);

    painter.save();
    painter.setRenderHint(QPainter::Antialiasing, true);

    if (module.kind == BuildingFacadeModuleKind::Window) {
        const float z0 = base_z + floor_h * 0.28F;
        const float z1 = base_z + floor_h * 0.74F;
        const QPolygonF outer = faceRect(a, b, t0, t1, z0, z1, view, canvas);
        painter.setPen(QPen(scaledColor(spec.trim_color, 0.52F), 1.15));
        painter.setBrush(scaledColor(spec.trim_color, 0.90F));
        painter.drawPolygon(outer);
        const float inset = std::min(0.014F, (t1 - t0) * 0.10F);
        const QPolygonF glass = faceRect(a, b, t0 + inset, t1 - inset,
                                        z0 + floor_h * 0.035F, z1 - floor_h * 0.035F,
                                        view, canvas);
        painter.setPen(QPen(scaledColor(spec.glass_color, 0.48F), 0.85));
        painter.setBrush(scaledColor(spec.glass_color, 0.86F));
        painter.drawPolygon(glass);
        painter.setPen(QPen(scaledColor(spec.trim_color, 0.62F, 155), 0.65));
        const QPointF mid0 = projectPoint(lerpPoint(a, b, center, z0 + floor_h * 0.035F), view, canvas);
        const QPointF mid1 = projectPoint(lerpPoint(a, b, center, z1 - floor_h * 0.035F), view, canvas);
        painter.drawLine(mid0, mid1);
    } else if (module.kind == BuildingFacadeModuleKind::Door) {
        const float z0 = base_z + 0.8F;
        const float z1 = base_z + floor_h * 0.78F;
        painter.setPen(QPen(scaledColor(spec.trim_color, 0.50F), 1.15));
        painter.setBrush(scaledColor(spec.trim_color, 0.88F));
        painter.drawPolygon(faceRect(a, b, t0, t1, z0, z1, view, canvas));
        const float inset = std::min(0.014F, (t1 - t0) * 0.10F);
        painter.setPen(QPen(scaledColor(spec.door_color, 0.46F), 0.95));
        painter.setBrush(spec.door_color);
        painter.drawPolygon(faceRect(a, b, t0 + inset, t1 - inset,
                                     z0 + 1.1F, z1 - floor_h * 0.035F, view, canvas));
    } else if (module.kind == BuildingFacadeModuleKind::Storefront) {
        const float z0 = base_z + floor_h * 0.10F;
        const float z1 = base_z + floor_h * 0.78F;
        painter.setPen(QPen(scaledColor(spec.trim_color, 0.50F), 1.0));
        painter.setBrush(scaledColor(spec.glass_color, 0.80F));
        painter.drawPolygon(faceRect(a, b, t0, t1, z0, z1, view, canvas));
        painter.setPen(QPen(scaledColor(spec.trim_color, 0.64F), 0.8));
        painter.drawLine(projectPoint(lerpPoint(a, b, center, z0), view, canvas),
                         projectPoint(lerpPoint(a, b, center, z1), view, canvas));
    } else if (module.kind == BuildingFacadeModuleKind::Sign) {
        const float z0 = base_z + floor_h * 0.72F;
        const float z1 = base_z + floor_h * 0.90F;
        painter.setPen(QPen(scaledColor(spec.trim_color, 0.54F), 1.0));
        painter.setBrush(spec.accent_color);
        painter.drawPolygon(faceRect(a, b, t0, t1, z0, z1, view, canvas));
    } else if (module.kind == BuildingFacadeModuleKind::Awning) {
        const float z = base_z + floor_h * 0.70F;
        const Point3 n = outwardNormal(edge);
        const Point3 i0 = lerpPoint(a, b, t0, z);
        const Point3 i1 = lerpPoint(a, b, t1, z);
        const Point3 o0{i0.x + n.x * 0.26F, i0.y + n.y * 0.26F, z - floor_h * 0.08F};
        const Point3 o1{i1.x + n.x * 0.26F, i1.y + n.y * 0.26F, z - floor_h * 0.08F};
        QPolygonF canopy{projectPoint(i0, view, canvas), projectPoint(i1, view, canvas),
                         projectPoint(o1, view, canvas), projectPoint(o0, view, canvas)};
        painter.setPen(QPen(scaledColor(spec.trim_color, 0.52F), 1.0));
        painter.setBrush(spec.accent_color);
        painter.drawPolygon(canopy);
    }
    painter.restore();
}

void drawFloorBands(QPainter& painter, const BuildingComposerSpec& spec,
                    const std::array<Point3, 4>& corners,
                    const std::array<int, 2>& visible_edges,
                    const BuildingView view, const QSize canvas) {
    if (!spec.floor_bands_enabled || spec.floor_count <= 1) return;
    const float floor_h = static_cast<float>(std::clamp(spec.floor_height_px, 36, 132));
    painter.save();
    painter.setPen(QPen(scaledColor(spec.trim_color, 0.54F, 105), 0.85));
    for (int floor = 1; floor < std::clamp(spec.floor_count, 1, 8); ++floor) {
        const float z = floor_h * static_cast<float>(floor);
        for (const int edge : visible_edges) {
            const int next = (edge + 1) % 4;
            painter.drawLine(projectPoint({corners[edge].x, corners[edge].y, z}, view, canvas),
                             projectPoint({corners[next].x, corners[next].y, z}, view, canvas));
        }
    }
    painter.restore();
}

} // namespace

QImage BuildingFacadeRenderer::renderView(const BuildingComposerSpec& spec,
                                          const BuildingView view,
                                          const QSize canvas) {
    BuildingComposerSpec render_spec = spec;
    render_spec.wall_height_px = BuildingComposer::effectiveWallHeightPx(spec);
    if (spec.facade_editor_enabled) {
        render_spec.windows = false;
        render_spec.south_door = false;
        render_spec.south_awning = false;
        render_spec.south_sign = false;
    }

    QImage image = BuildingRoofEditorRenderer::renderView(render_spec, view, canvas);
    if (!spec.facade_editor_enabled && spec.floor_count <= 1) return image;

    const float half_w = static_cast<float>(std::max(1, spec.footprint_width_tiles)) * 0.5F;
    const float half_d = static_cast<float>(std::max(1, spec.footprint_depth_tiles)) * 0.5F;
    const std::array<Point3, 4> corners = {
        Point3{-half_w, -half_d, 0.0F}, Point3{half_w, -half_d, 0.0F},
        Point3{half_w, half_d, 0.0F}, Point3{-half_w, half_d, 0.0F},
    };

    int near_index = 0;
    float near_y = -1.0e9F;
    for (int i = 0; i < 4; ++i) {
        const float y = static_cast<float>(projectPoint(corners[i], view, canvas).y());
        if (y > near_y) { near_y = y; near_index = i; }
    }
    const std::array<int, 2> visible_edges = {(near_index + 3) % 4, near_index};

    QPainter painter(&image);
    painter.setRenderHint(QPainter::Antialiasing, true);
    drawFloorBands(painter, spec, corners, visible_edges, view, canvas);

    if (spec.facade_editor_enabled) {
        for (const auto& module : spec.facade_modules) {
            const int edge = edgeIndex(module.edge);
            if (edge != visible_edges[0] && edge != visible_edges[1]) continue;
            drawModule(painter, spec, module, corners[edge], corners[(edge + 1) % 4], edge, view, canvas);
        }
    }
    painter.end();
    return image;
}

QImage BuildingFacadeRenderer::renderSpriteSheet(const BuildingComposerSpec& spec, const QSize cell) {
    QImage sheet(cell.width() * 4, cell.height(), QImage::Format_ARGB32_Premultiplied);
    sheet.fill(Qt::transparent);
    QPainter painter(&sheet);
    for (int i = 0; i < static_cast<int>(kViews.size()); ++i)
        painter.drawImage(i * cell.width(), 0, renderView(spec, kViews[i], cell));
    painter.end();
    return sheet;
}

QImage BuildingFacadeRenderer::renderReviewSheet(const BuildingComposerSpec& spec, const QSize cell) {
    constexpr int kHeader = 34;
    QImage sheet(cell.width() * 4, cell.height() + kHeader, QImage::Format_ARGB32_Premultiplied);
    sheet.fill(QColor("#172025"));
    QPainter painter(&sheet);
    QFont font(QStringLiteral("Arial")); font.setBold(true); font.setPointSize(9); painter.setFont(font);
    for (int i = 0; i < static_cast<int>(kViews.size()); ++i) {
        const int left = i * cell.width();
        painter.fillRect(QRect(left, 0, cell.width(), kHeader), QColor("#243238"));
        painter.setPen(QColor("#dce7ea"));
        painter.drawText(QRect(left, 0, cell.width(), kHeader), Qt::AlignCenter, BuildingComposer::viewName(kViews[i]));
        painter.drawImage(QPoint(left, kHeader), renderView(spec, kViews[i], cell));
        if (i > 0) { painter.setPen(QPen(QColor(58, 71, 76), 1.0)); painter.drawLine(left, 0, left, sheet.height()); }
    }
    painter.end();
    return sheet;
}

QJsonObject BuildingFacadeRenderer::manifest(const BuildingComposerSpec& spec) {
    return BuildingComposer::facadeEditorManifest(spec);
}

} // namespace ch::studio
