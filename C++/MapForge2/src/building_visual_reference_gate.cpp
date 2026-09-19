#include "building_visual_reference_gate.h"

#include "building_block_preview_renderer.h"
#include "building_facade_renderer.h"
#include "building_lod_validator.h"
#include "building_projected_shadow_renderer.h"

#include <QFont>
#include <QJsonArray>
#include <QPainter>
#include <QStringList>

#include <algorithm>
#include <array>

namespace ch::studio {
namespace {

constexpr int kNeighborhoodSeed = 401;

struct MaterialCase {
    const char* label;
    BuildingWallMaterial material;
};

constexpr std::array<MaterialCase, 7> kMaterialCases = {{
    {"Plaster", BuildingWallMaterial::Plaster},
    {"Brick", BuildingWallMaterial::Brick},
    {"Concrete", BuildingWallMaterial::Concrete},
    {"Timber", BuildingWallMaterial::Timber},
    {"Stone", BuildingWallMaterial::Stone},
    {"Metal panel", BuildingWallMaterial::MetalPanel},
    {"Glass", BuildingWallMaterial::Glass},
}};

QFont gateFont(const int point_size, const bool bold = false) {
    QFont font(QStringLiteral("Arial"));
    font.setPointSize(point_size);
    font.setBold(bold);
    return font;
}

void drawBoardHeader(QPainter& painter, const QRect& rect,
                     const QString& title, const QString& subtitle) {
    painter.fillRect(rect, QColor("#172025"));
    painter.setFont(gateFont(11, true));
    painter.setPen(QColor("#eef4f5"));
    painter.drawText(QRect(rect.left() + 18, rect.top() + 8, rect.width() - 36, 24),
                     Qt::AlignLeft | Qt::AlignVCenter, title);
    painter.setFont(gateFont(8));
    painter.setPen(QColor("#aebec3"));
    painter.drawText(QRect(rect.left() + 18, rect.top() + 31, rect.width() - 36, 20),
                     Qt::AlignLeft | Qt::AlignVCenter, subtitle);
}

void drawCellLabel(QPainter& painter, const QRect& rect, const QString& text) {
    painter.fillRect(rect, QColor("#243238"));
    painter.setFont(gateFont(8, true));
    painter.setPen(QColor("#dce7ea"));
    painter.drawText(rect.adjusted(8, 0, -8, 0), Qt::AlignLeft | Qt::AlignVCenter, text);
}

QJsonArray materialNames() {
    QJsonArray materials;
    for (const MaterialCase& item : kMaterialCases) materials.append(QString::fromLatin1(item.label));
    return materials;
}

} // namespace

BuildingComposerSpec BuildingVisualReferenceGate::referenceSpec() {
    BuildingComposerSpec spec = BuildingComposer::presetSpec(
        BuildingVisualPreset::CityHorizonClassicTycoon);

    spec.footprint_width_tiles = 2;
    spec.footprint_depth_tiles = 2;
    spec.floor_count = 2;
    spec.floor_height_px = 64;
    spec.wall_height_px = 128;
    spec.floor_bands_enabled = true;

    spec.wall_color = QColor("#d8c3a5");
    spec.roof_color = QColor("#a94e3f");
    spec.trim_color = QColor("#f2eadf");
    spec.glass_color = QColor("#78b9d1");
    spec.door_color = QColor("#6d4c41");
    spec.accent_color = QColor("#d79b38");

    spec.wall_material = BuildingWallMaterial::Plaster;
    spec.roof_material = BuildingRoofMaterial::CeramicTile;
    spec.material_strength = 0.48F;
    spec.material_scale = 1.0F;
    spec.material_variation = 0.28F;
    spec.material_contrast = 0.46F;
    spec.material_seed = 17;

    spec.roof_style = BuildingRoofStyle::Hip;
    spec.roof_height_px = 34;
    spec.roof_pitch_degrees = 35.0F;
    spec.roof_overhang = 0.10F;
    spec.roof_fascia_enabled = true;
    spec.roof_fascia_thickness_px = 2.8F;
    spec.roof_ridge_enabled = true;
    spec.roof_ridge_scale = 1.0F;
    spec.roof_chimney = true;
    spec.cast_shadow = true;

    spec.facade_editor_enabled = true;
    spec.windows = true;
    spec.south_door = true;
    spec.south_awning = false;
    spec.south_sign = false;

    using Kind = BuildingFacadeModuleKind;
    using Edge = BuildingStreetEdge;
    spec.facade_modules = {
        {Kind::Door, Edge::South, 0, 0.50F, 0.20F, true},
        {Kind::Window, Edge::South, 0, 0.22F, 0.17F, true},
        {Kind::Window, Edge::South, 0, 0.78F, 0.17F, true},
        {Kind::Window, Edge::South, 1, 0.28F, 0.18F, true},
        {Kind::Window, Edge::South, 1, 0.72F, 0.18F, true},
        {Kind::Window, Edge::East, 0, 0.30F, 0.18F, true},
        {Kind::Window, Edge::East, 0, 0.70F, 0.18F, true},
        {Kind::Window, Edge::East, 1, 0.30F, 0.18F, true},
        {Kind::Window, Edge::East, 1, 0.70F, 0.18F, true},
    };

    return spec;
}

QImage BuildingVisualReferenceGate::renderHeroReview(const QSize canvas) {
    const BuildingComposerSpec spec = referenceSpec();
    const int cell_width = std::max(180, canvas.width() / 4);
    const int cell_height = std::max(220, canvas.height() - 44);
    return BuildingFacadeRenderer::renderReviewSheet(spec, QSize(cell_width, cell_height));
}

QImage BuildingVisualReferenceGate::renderMaterialBoard(const QSize canvas) {
    QImage board(canvas, QImage::Format_ARGB32_Premultiplied);
    board.fill(QColor("#10171b"));
    QPainter painter(&board);
    painter.setRenderHint(QPainter::Antialiasing, true);

    constexpr int kHeader = 60;
    constexpr int kColumns = 4;
    constexpr int kRows = 2;
    const int cell_w = canvas.width() / kColumns;
    const int cell_h = std::max(1, (canvas.height() - kHeader) / kRows);
    drawBoardHeader(painter, QRect(0, 0, canvas.width(), kHeader),
                    QStringLiteral("Classic Tycoon material structure gate"),
                    QStringLiteral("Same geometry, palette, lighting and camera; only the wall recipe changes."));

    const BuildingComposerSpec base = referenceSpec();
    for (int index = 0; index < static_cast<int>(kMaterialCases.size()); ++index) {
        BuildingComposerSpec sample = base;
        sample.wall_material = kMaterialCases[index].material;
        if (sample.wall_material == BuildingWallMaterial::Glass) {
            sample.wall_color = QColor("#78b9d1");
        }

        const int column = index % kColumns;
        const int row = index / kColumns;
        const QRect cell(column * cell_w, kHeader + row * cell_h, cell_w, cell_h);
        const QRect label(cell.left(), cell.top(), cell.width(), 28);
        drawCellLabel(painter, label, QString::fromLatin1(kMaterialCases[index].label));

        const QSize render_size(std::max(160, cell.width() - 16), std::max(160, cell.height() - 36));
        const QImage rendered = BuildingFacadeRenderer::renderView(sample, BuildingView::South, render_size);
        const QPoint target(cell.left() + (cell.width() - rendered.width()) / 2,
                            label.bottom() + 5);
        painter.drawImage(target, rendered);
    }

    const int empty_index = static_cast<int>(kMaterialCases.size());
    const QRect notes((empty_index % kColumns) * cell_w,
                      kHeader + (empty_index / kColumns) * cell_h,
                      cell_w, cell_h);
    painter.fillRect(notes, QColor("#1b272c"));
    painter.setFont(gateFont(8, true));
    painter.setPen(QColor("#dce7ea"));
    painter.drawText(notes.adjusted(14, 14, -14, -14), Qt::AlignTop | Qt::TextWordWrap,
                     QStringLiteral("PASS CRITERIA\n\n"
                                    "• Material identity comes from courses, boards, seams, panels or reflections.\n"
                                    "• No salt-and-pepper noise.\n"
                                    "• Pattern direction follows the isometric surface.\n"
                                    "• Details survive the medium gameplay scale without turning into moiré."));
    painter.end();
    return board;
}

QImage BuildingVisualReferenceGate::renderShadowBoard(const QSize canvas) {
    QImage board(canvas, QImage::Format_ARGB32_Premultiplied);
    board.fill(QColor("#10171b"));
    QPainter painter(&board);
    painter.setRenderHint(QPainter::Antialiasing, true);

    constexpr int kHeader = 60;
    constexpr int kColumns = 4;
    const int cell_w = canvas.width() / kColumns;
    const int cell_h = canvas.height() - kHeader;
    drawBoardHeader(painter, QRect(0, 0, canvas.width(), kHeader),
                    QStringLiteral("Fixed-world shadow and grounding gate"),
                    QStringLiteral("OFF/ON comparison in two views; direction must rotate only as world projection rotates."));

    const std::array<BuildingView, 4> views = {
        BuildingView::South, BuildingView::South, BuildingView::East, BuildingView::East,
    };
    const std::array<bool, 4> enabled = {false, true, false, true};
    const std::array<const char*, 4> labels = {{"South · shadow OFF", "South · shadow ON",
                                                "East · shadow OFF", "East · shadow ON"}};

    for (int index = 0; index < kColumns; ++index) {
        BuildingComposerSpec sample = referenceSpec();
        sample.cast_shadow = enabled[index];
        const QRect cell(index * cell_w, kHeader, cell_w, cell_h);
        drawCellLabel(painter, QRect(cell.left(), cell.top(), cell.width(), 28),
                      QString::fromLatin1(labels[index]));
        const QSize render_size(std::max(160, cell.width() - 12), std::max(180, cell.height() - 34));
        const QImage rendered = BuildingFacadeRenderer::renderView(sample, views[index], render_size);
        painter.drawImage(QPoint(cell.left() + (cell.width() - rendered.width()) / 2,
                                 cell.top() + 31), rendered);
    }

    painter.end();
    return board;
}

QImage BuildingVisualReferenceGate::renderLodBoard(const QSize canvas) {
    return BuildingLodValidator::renderReviewSheet(referenceSpec(), canvas);
}

QImage BuildingVisualReferenceGate::renderBlockBoard(const QSize canvas) {
    return BuildingBlockPreviewRenderer::render(referenceSpec(), canvas, kNeighborhoodSeed);
}

QJsonObject BuildingVisualReferenceGate::manifest() {
    const BuildingComposerSpec spec = referenceSpec();
    return QJsonObject{
        {"version", "classic_visual_reference_gate_1"},
        {"referenceBuildingId", "classic_tycoon_reference_house_1"},
        {"deterministic", true},
        {"neighborhoodSeed", kNeighborhoodSeed},
        {"geometry", QJsonObject{
            {"footprintWidthTiles", spec.footprint_width_tiles},
            {"footprintDepthTiles", spec.footprint_depth_tiles},
            {"floorCount", spec.floor_count},
            {"floorHeightPx", spec.floor_height_px},
            {"roofProfile", "hip"},
        }},
        {"materialsReviewed", materialNames()},
        {"visualContracts", QJsonArray{
            "structured_directional_materials_1",
            "classic_three_tone_ramp_1",
            "localized_contact_ao_1",
            "fixed_world_cast_shadow_1",
            "building_lod_gate_1",
            "small_block_preview_1",
        }},
        {"shadow", BuildingProjectedShadowRenderer::manifest()},
        {"ambientOcclusion", BuildingFacadeRenderer::manifest(spec).value("ambientOcclusion")},
        {"lod", BuildingLodValidator::manifest(spec)},
        {"artifacts", QJsonArray{
            "building_composer_visual_reference_hero.png",
            "building_composer_visual_reference_materials.png",
            "building_composer_visual_reference_shadow.png",
            "building_composer_visual_reference_lod.png",
            "building_composer_visual_reference_block.png",
            "building_composer_visual_reference_report.json",
        }},
        {"manualReviewChecklist", QJsonArray{
            "silhouette reads before microdetail",
            "wall LIGHT MID SHADOW separation is clear but not cartoon-flat",
            "material direction follows the physical surface",
            "AO stays confined to real contacts",
            "cast shadow grounds the mass without becoming a black blob",
            "distant medium and close LODs remain legible",
            "reference building remains coherent beside deterministic neighbours",
            "no halo clipping or accidental terrain baked into the transparent building sprite",
        }},
    };
}

} // namespace ch::studio
