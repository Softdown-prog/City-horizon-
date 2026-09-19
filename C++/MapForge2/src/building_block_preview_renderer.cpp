#include "building_block_preview_renderer.h"

#include "building_facade_renderer.h"
#include "building_procedural_variation.h"
#include "src/ch_core/contracts.h"

#include <QPainter>
#include <QPolygonF>

#include <algorithm>
#include <array>
#include <vector>

namespace ch::studio {
namespace {

struct WorldPoint { float x = 0.0F; float y = 0.0F; };
struct PlacedBuilding { WorldPoint position; BuildingComposerSpec spec; bool focus = false; };

QPointF project(const WorldPoint point, const QSize canvas) {
    const float half_w = static_cast<float>(ch::contracts::kTileWidth) * 0.5F;
    const float half_h = static_cast<float>(ch::contracts::kTileHeight) * 0.5F;
    return {
        static_cast<float>(canvas.width()) * 0.5F + (point.x - point.y) * half_w,
        118.0F + (point.x + point.y) * half_h,
    };
}

QPolygonF quad(float x0, float y0, float x1, float y1, const QSize canvas) {
    return {project({x0, y0}, canvas), project({x1, y0}, canvas), project({x1, y1}, canvas), project({x0, y1}, canvas)};
}

void drawGround(QPainter& painter, const QSize canvas) {
    painter.fillRect(QRect(QPoint(0, 0), canvas), QColor("#172025"));
    painter.setRenderHint(QPainter::Antialiasing, true);
    for (int y = -8; y <= 8; ++y) {
        for (int x = -10; x <= 10; ++x) {
            painter.setPen(QPen(QColor(74, 102, 65, 62), 0.5));
            painter.setBrush(((x + y) & 1) ? QColor("#78995f") : QColor("#73945b"));
            painter.drawPolygon(quad(static_cast<float>(x), static_cast<float>(y),
                                     static_cast<float>(x + 1), static_cast<float>(y + 1), canvas));
        }
    }
}

void drawRoadBand(QPainter& painter, const QSize canvas, float y0, float y1) {
    painter.setPen(QPen(QColor("#31383b"), 1.0));
    painter.setBrush(QColor("#4b5154"));
    painter.drawPolygon(quad(-10.0F, y0, 10.0F, y1, canvas));

    painter.setPen(QPen(QColor("#b8b5ae"), 0.8));
    painter.setBrush(QColor("#b9b5ac"));
    painter.drawPolygon(quad(-10.0F, y0 - 0.28F, 10.0F, y0, canvas));
    painter.drawPolygon(quad(-10.0F, y1, 10.0F, y1 + 0.28F, canvas));

    painter.setPen(QPen(QColor(219, 204, 145, 175), 0.9, Qt::DashLine));
    const float center = (y0 + y1) * 0.5F;
    painter.drawLine(project({-9.4F, center}, canvas), project({9.4F, center}, canvas));
}

void drawCrossStreet(QPainter& painter, const QSize canvas, float x0, float x1) {
    painter.setPen(QPen(QColor("#31383b"), 1.0));
    painter.setBrush(QColor("#4b5154"));
    painter.drawPolygon(quad(x0, -7.5F, x1, 7.5F, canvas));

    painter.setPen(QPen(QColor("#b8b5ae"), 0.8));
    painter.setBrush(QColor("#b9b5ac"));
    painter.drawPolygon(quad(x0 - 0.28F, -7.5F, x0, 7.5F, canvas));
    painter.drawPolygon(quad(x1, -7.5F, x1 + 0.28F, 7.5F, canvas));
}

void drawTree(QPainter& painter, WorldPoint position, const QSize canvas, float scale = 1.0F) {
    const QPointF base = project(position, canvas);
    painter.save();
    painter.setPen(QPen(QColor("#4b3427"), 1.0));
    painter.setBrush(QColor("#72513b"));
    painter.drawRect(QRectF(base.x() - 2.0F * scale, base.y() - 12.0F * scale,
                            4.0F * scale, 12.0F * scale));
    painter.setPen(QPen(QColor(47, 75, 44, 220), 0.9));
    painter.setBrush(QColor("#5f8454"));
    painter.drawEllipse(QPointF(base.x(), base.y() - 18.0F * scale), 10.0F * scale, 8.0F * scale);
    painter.setBrush(QColor("#6f9461"));
    painter.drawEllipse(QPointF(base.x() - 6.0F * scale, base.y() - 14.0F * scale), 7.0F * scale, 6.0F * scale);
    painter.drawEllipse(QPointF(base.x() + 6.0F * scale, base.y() - 14.0F * scale), 7.0F * scale, 6.0F * scale);
    painter.restore();
}

BuildingComposerSpec siblingSpec(const BuildingComposerSpec& base, int seed, float strength) {
    BuildingComposerSpec sibling = base;
    sibling.procedural_variation_enabled = true;
    sibling.procedural_variation_applied = false;
    sibling.procedural_variation_seed = seed;
    sibling.procedural_variation_strength = strength;
    sibling.procedural_vary_palette = true;
    sibling.procedural_vary_materials = true;
    sibling.procedural_vary_roof = true;
    sibling.procedural_vary_modules = true;
    return BuildingProceduralVariation::generate(sibling);
}

void drawBuilding(QPainter& painter, const PlacedBuilding& placed, const QSize canvas) {
    const QSize cell(360, 330);
    const QImage building = BuildingFacadeRenderer::renderView(placed.spec, BuildingView::South, cell);
    const QPointF anchor = project(placed.position, canvas);
    const QPointF top_left(anchor.x() - cell.width() * 0.5F,
                           anchor.y() - static_cast<float>(cell.height() - 42));
    painter.drawImage(top_left, building);

    if (placed.focus) {
        painter.save();
        painter.setPen(QPen(QColor(244, 213, 123, 220), 1.4));
        painter.setBrush(Qt::NoBrush);
        const float hw = std::max(1, placed.spec.footprint_width_tiles) * 0.5F;
        const float hd = std::max(1, placed.spec.footprint_depth_tiles) * 0.5F;
        painter.drawPolygon(quad(placed.position.x - hw, placed.position.y - hd,
                                 placed.position.x + hw, placed.position.y + hd, canvas));
        painter.restore();
    }
}

} // namespace

QImage BuildingBlockPreviewRenderer::render(const BuildingComposerSpec& focus_spec,
                                            const QSize canvas,
                                            const int neighborhood_seed) {
    QImage image(canvas, QImage::Format_ARGB32_Premultiplied);
    image.fill(Qt::transparent);
    QPainter painter(&image);
    painter.setRenderHint(QPainter::Antialiasing, true);

    drawGround(painter, canvas);
    drawRoadBand(painter, canvas, -0.45F, 0.45F);
    drawCrossStreet(painter, canvas, 3.65F, 4.55F);

    const std::array<WorldPoint, 10> trees = {
        WorldPoint{-5.8F, -2.5F}, {-2.6F, -2.4F}, {1.8F, -2.3F}, {6.2F, -2.4F},
        {-5.5F, 2.6F}, {-1.8F, 2.5F}, {1.7F, 2.7F}, {6.1F, 2.5F},
        {3.1F, -4.0F}, {5.1F, 4.0F}
    };
    for (std::size_t i = 0; i < trees.size(); ++i)
        drawTree(painter, trees[i], canvas, 0.92F + static_cast<float>(i % 3) * 0.06F);

    std::vector<PlacedBuilding> buildings;
    buildings.push_back({{-0.2F, -2.0F}, focus_spec, true});
    buildings.push_back({{-4.4F, -2.0F}, siblingSpec(focus_spec, neighborhood_seed + 11, 0.28F), false});
    buildings.push_back({{5.8F, -2.0F}, siblingSpec(focus_spec, neighborhood_seed + 23, 0.34F), false});
    buildings.push_back({{-4.2F, 2.0F}, siblingSpec(focus_spec, neighborhood_seed + 37, 0.30F), false});
    buildings.push_back({{-0.1F, 2.0F}, siblingSpec(focus_spec, neighborhood_seed + 53, 0.38F), false});
    buildings.push_back({{5.9F, 2.0F}, siblingSpec(focus_spec, neighborhood_seed + 71, 0.32F), false});

    std::sort(buildings.begin(), buildings.end(), [&canvas](const PlacedBuilding& a, const PlacedBuilding& b) {
        return project(a.position, canvas).y() < project(b.position, canvas).y();
    });
    for (const auto& placed : buildings) drawBuilding(painter, placed, canvas);

    painter.setPen(QColor("#e7ecee"));
    QFont font(QStringLiteral("Arial"));
    font.setBold(true);
    font.setPointSize(10);
    painter.setFont(font);
    painter.drawText(QRect(14, 10, canvas.width() - 28, 26), Qt::AlignLeft | Qt::AlignVCenter,
                     QStringLiteral("SMALL BLOCK GAMEPLAY PREVIEW — focus lot + 5 deterministic neighbours"));
    painter.setPen(QColor("#b9c4c8"));
    font.setBold(false);
    font.setPointSize(8);
    painter.setFont(font);
    painter.drawText(QRect(14, 34, canvas.width() - 28, 22), Qt::AlignLeft | Qt::AlignVCenter,
                     QStringLiteral("CH_GRID_V1 / roads + sidewalks + trees / preview only / never exported into building PNG"));
    painter.end();
    return image;
}

QJsonObject BuildingBlockPreviewRenderer::manifest(const int neighborhood_seed) {
    return QJsonObject{
        {"version", QStringLiteral("small_block_preview_1")},
        {"previewOnly", true},
        {"exportedIntoBuildingSprite", false},
        {"focusBuildingCount", 1},
        {"neighbourBuildingCount", 5},
        {"neighboursDeterministic", true},
        {"neighborhoodSeed", neighborhood_seed},
        {"usesGridContract", QString::fromLatin1(ch::contracts::kGridContract)},
        {"includesRoads", true},
        {"includesSidewalks", true},
        {"includesTrees", true},
        {"purpose", QStringLiteral("evaluate gameplay-scale density, repetition, silhouette, street integration and neighbour compatibility")},
    };
}

} // namespace ch::studio
