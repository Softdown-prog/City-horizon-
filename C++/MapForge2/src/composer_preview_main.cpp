#include "building_block_preview_renderer.h"
#include "building_composer.h"
#include "building_facade_renderer.h"
#include "building_lod_validator.h"
#include "building_roof_editor_renderer.h"
#include "building_visual_reference_gate.h"
#include "src/ch_core/contracts.h"

#include <QDir>
#include <QFile>
#include <QFont>
#include <QGuiApplication>
#include <QJsonDocument>
#include <QPainter>
#include <QPolygonF>
#include <QString>

#include <iostream>

namespace {

bool writeAsset(const QString& output_dir, const QString& stem,
                const ch::studio::BuildingComposerSpec& spec) {
    const QSize frame(420, 420);
    const QString review_path = QDir(output_dir).filePath(stem + "_review.png");
    const QString sheet_path = QDir(output_dir).filePath(stem + "_4view.png");
    const QString manifest_path = QDir(output_dir).filePath(stem + "_manifest.json");

    if (!ch::studio::BuildingFacadeRenderer::renderReviewSheet(spec, QSize(360, 360)).save(review_path, "PNG")) {
        std::cerr << "Unable to save review image.\n";
        return false;
    }
    if (!ch::studio::BuildingFacadeRenderer::renderSpriteSheet(spec, frame).save(sheet_path, "PNG")) {
        std::cerr << "Unable to save sprite sheet.\n";
        return false;
    }

    QFile manifest_file(manifest_path);
    if (!manifest_file.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
        std::cerr << "Unable to save manifest.\n";
        return false;
    }
    QJsonObject manifest = ch::studio::BuildingComposer::manifest(spec, frame);
    QJsonObject geometry = manifest.value(QStringLiteral("geometry")).toObject();
    geometry.insert(QStringLiteral("roofStyle"), ch::studio::BuildingRoofEditorRenderer::roofProfileName(spec.roof_style));
    geometry.insert(QStringLiteral("floorCount"), spec.floor_count);
    geometry.insert(QStringLiteral("floorHeightPx"), spec.floor_height_px);
    geometry.insert(QStringLiteral("wallHeightPx"), ch::studio::BuildingComposer::effectiveWallHeightPx(spec));
    manifest.insert(QStringLiteral("geometry"), geometry);
    manifest.insert(QStringLiteral("architecturalModules"), ch::studio::BuildingComposer::architecturalModules(spec));
    manifest.insert(QStringLiteral("facadeEditor"), ch::studio::BuildingFacadeRenderer::manifest(spec));
    manifest.insert(QStringLiteral("roofEditor"), ch::studio::BuildingRoofEditorRenderer::roofEditorManifest(spec));
    manifest.insert(QStringLiteral("lodVisualGate"), ch::studio::BuildingLodValidator::manifest(spec));
    manifest_file.write(QJsonDocument(manifest).toJson(QJsonDocument::Indented));
    manifest_file.close();

    std::cout << review_path.toStdString() << "\n" << sheet_path.toStdString() << "\n" << manifest_path.toStdString() << "\n";
    return true;
}

bool writeVisualReferenceGate(const QString& output_dir) {
    using Gate = ch::studio::BuildingVisualReferenceGate;
    struct ImageArtifact {
        QString file_name;
        QImage image;
    };

    const ImageArtifact artifacts[] = {
        {QStringLiteral("building_composer_visual_reference_hero.png"), Gate::renderHeroReview()},
        {QStringLiteral("building_composer_visual_reference_materials.png"), Gate::renderMaterialBoard()},
        {QStringLiteral("building_composer_visual_reference_shadow.png"), Gate::renderShadowBoard()},
        {QStringLiteral("building_composer_visual_reference_lod.png"), Gate::renderLodBoard()},
        {QStringLiteral("building_composer_visual_reference_block.png"), Gate::renderBlockBoard()},
    };

    for (const ImageArtifact& artifact : artifacts) {
        const QString path = QDir(output_dir).filePath(artifact.file_name);
        if (!artifact.image.save(path, "PNG")) {
            std::cerr << "Unable to save full visual reference artifact: "
                      << artifact.file_name.toStdString() << "\n";
            return false;
        }
        std::cout << path.toStdString() << "\n";
    }

    const QString report_path = QDir(output_dir).filePath(
        QStringLiteral("building_composer_visual_reference_report.json"));
    QFile report_file(report_path);
    if (!report_file.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
        std::cerr << "Unable to save full visual reference report.\n";
        return false;
    }
    report_file.write(QJsonDocument(Gate::manifest()).toJson(QJsonDocument::Indented));
    report_file.close();
    std::cout << report_path.toStdString() << "\n";
    return true;
}

QPointF projectSouthGroundPoint(const float x, const float y, const QSize canvas) {
    const float half_tile_w = static_cast<float>(ch::contracts::kTileWidth) * 0.5F;
    const float half_tile_h = static_cast<float>(ch::contracts::kTileHeight) * 0.5F;
    return {static_cast<float>(canvas.width()) * 0.5F + (x - y) * half_tile_w,
            static_cast<float>(canvas.height()) - 42.0F + (x + y) * half_tile_h};
}

void drawNpcScaleSilhouette(QPainter& painter, const QPointF feet, const QString& caption) {
    constexpr qreal kNpcHeight = 56.0;
    const QColor silhouette("#26343b");
    painter.save();
    painter.setRenderHint(QPainter::Antialiasing, true);
    painter.setPen(QPen(QColor("#0d171b"), 1.0));
    painter.setBrush(silhouette);

    painter.drawEllipse(QRectF(feet.x() - 6.0, feet.y() - kNpcHeight, 12.0, 12.0));
    painter.drawRoundedRect(QRectF(feet.x() - 7.0, feet.y() - 44.0, 14.0, 25.0), 3.0, 3.0);
    painter.drawRoundedRect(QRectF(feet.x() - 10.0, feet.y() - 41.0, 4.0, 22.0), 2.0, 2.0);
    painter.drawRoundedRect(QRectF(feet.x() + 6.0, feet.y() - 41.0, 4.0, 22.0), 2.0, 2.0);
    painter.drawRect(QRectF(feet.x() - 6.0, feet.y() - 20.0, 5.0, 20.0));
    painter.drawRect(QRectF(feet.x() + 1.0, feet.y() - 20.0, 5.0, 20.0));

    const qreal ruler_x = feet.x() + 18.0;
    painter.setPen(QPen(QColor("#f6e29a"), 1.4));
    painter.drawLine(QPointF(ruler_x, feet.y() - kNpcHeight), QPointF(ruler_x, feet.y()));
    painter.drawLine(QPointF(ruler_x - 4.0, feet.y() - kNpcHeight), QPointF(ruler_x + 4.0, feet.y() - kNpcHeight));
    painter.drawLine(QPointF(ruler_x - 4.0, feet.y()), QPointF(ruler_x + 4.0, feet.y()));
    painter.setPen(QColor("#f6e29a"));
    QFont font(QStringLiteral("Arial"));
    font.setBold(true);
    font.setPointSize(8);
    painter.setFont(font);
    painter.drawText(QRectF(ruler_x + 6.0, feet.y() - 40.0, 74.0, 20.0), Qt::AlignLeft | Qt::AlignVCenter,
                     QStringLiteral("56 px"));

    painter.setPen(QColor("#e7f0f2"));
    painter.drawText(QRectF(feet.x() - 78.0, feet.y() + 5.0, 156.0, 20.0), Qt::AlignHCenter | Qt::AlignTop,
                     caption);
    painter.restore();
}

bool writeTicketBoothNpcScaleGate(const QString& output_dir,
                                  const ch::studio::BuildingComposerSpec& ticket_booth) {
    using ch::studio::BuildingFacadeRenderer;
    using ch::studio::BuildingView;

    const QSize view_size(420, 420);
    const QImage booth = BuildingFacadeRenderer::renderView(ticket_booth, BuildingView::South, view_size);
    QImage gate(QSize(960, 540), QImage::Format_ARGB32_Premultiplied);
    gate.fill(QColor("#172025"));

    QPainter painter(&gate);
    painter.setRenderHint(QPainter::Antialiasing, true);
    QFont title_font(QStringLiteral("Arial"));
    title_font.setBold(true);
    title_font.setPointSize(12);
    painter.setFont(title_font);
    painter.setPen(QColor("#e5eef0"));
    painter.drawText(QRect(24, 10, gate.width() - 48, 26), Qt::AlignLeft | Qt::AlignVCenter,
                     QStringLiteral("CITY HORIZON - BILHETERIA 2x2 / GATE DE ESCALA NPC"));

    QFont subtitle_font(QStringLiteral("Arial"));
    subtitle_font.setPointSize(9);
    painter.setFont(subtitle_font);
    painter.setPen(QColor("#aebdc1"));
    painter.drawText(QRect(24, 35, gate.width() - 48, 20), Qt::AlignLeft | Qt::AlignVCenter,
                     QStringLiteral("CH_CAMERA_V1 - NPC 56 px - pe ancorado no chao da fachada fisica"));

    const QPoint panel_origins[] = {QPoint(20, 70), QPoint(500, 70)};
    const QString panel_titles[] = {QStringLiteral("PASSAGEM / ARCO EAST"), QStringLiteral("ATENDIMENTO / BALCAO SOUTH")};
    const QPointF local_feet[] = {
        // East facade module is centered at t=0.52. x=1.14 places the NPC just
        // outside the physical wall instead of over the roof/sprite origin.
        projectSouthGroundPoint(1.14F, 0.04F, view_size),
        // South ticket window is centered at t=0.50. y=1.14 is the matching
        // exterior ground point for a customer standing at the counter.
        projectSouthGroundPoint(0.0F, 1.14F, view_size),
    };

    const QPolygonF footprint{
        projectSouthGroundPoint(-1.0F, -1.0F, view_size),
        projectSouthGroundPoint(1.0F, -1.0F, view_size),
        projectSouthGroundPoint(1.0F, 1.0F, view_size),
        projectSouthGroundPoint(-1.0F, 1.0F, view_size),
    };

    for (int i = 0; i < 2; ++i) {
        const QPoint origin = panel_origins[i];
        painter.fillRect(QRect(origin.x(), origin.y(), view_size.width() + 20, 450), QColor("#6f8f5e"));

        QPolygonF translated_footprint;
        for (const QPointF point : footprint) translated_footprint << QPointF(origin) + point;
        painter.setPen(QPen(QColor("#b6a26b"), 1.2));
        painter.setBrush(QColor("#c8c4b7"));
        painter.drawPolygon(translated_footprint);
        painter.drawImage(origin, booth);

        QFont panel_font(QStringLiteral("Arial"));
        panel_font.setBold(true);
        panel_font.setPointSize(9);
        painter.setFont(panel_font);
        painter.setPen(QColor("#f2f7f8"));
        painter.drawText(QRect(origin.x() + 10, origin.y() + 8, view_size.width(), 22),
                         Qt::AlignLeft | Qt::AlignVCenter, panel_titles[i]);

        const QPointF feet = QPointF(origin) + local_feet[i];
        painter.setPen(QPen(QColor("#f6e29a"), 1.0));
        painter.setBrush(QColor("#f6e29a"));
        painter.drawEllipse(feet, 2.5, 2.5);
        drawNpcScaleSilhouette(painter, feet,
                               i == 0 ? QStringLiteral("anchor arco") : QStringLiteral("anchor balcao"));
    }
    painter.end();

    const QString path = QDir(output_dir).filePath(QStringLiteral("building_composer_ticket_booth_npc_scale.png"));
    if (!gate.save(path, "PNG")) {
        std::cerr << "Unable to save ticket booth NPC scale gate.\n";
        return false;
    }
    std::cout << path.toStdString() << "\n";
    return true;
}

} // namespace

int main(int argc, char** argv) {
    QGuiApplication app(argc, argv);
    const QString output_dir = argc > 1 ? QString::fromLocal8Bit(argv[1]) : QStringLiteral(".");
    QDir dir;
    if (!dir.mkpath(output_dir)) {
        std::cerr << "Unable to create output directory.\n";
        return 2;
    }

    ch::studio::BuildingComposerSpec residence = ch::studio::BuildingComposer::presetSpec(
        ch::studio::BuildingVisualPreset::CityHorizonClassicTycoon);
    residence.footprint_width_tiles = 2;
    residence.footprint_depth_tiles = 1;
    residence.floor_count = 1;
    residence.floor_height_px = 82;
    residence.wall_height_px = 82;
    residence.roof_height_px = 34;
    residence.roof_style = ch::studio::BuildingRoofStyle::Gable;
    residence.wall_color = QColor("#d8c3a5");
    residence.roof_color = QColor("#a94e3f");
    residence.trim_color = QColor("#f2eadf");
    residence.glass_color = QColor("#78b9d1");
    residence.door_color = QColor("#6d4c41");
    residence.accent_color = QColor("#d79b38");
    residence.wall_material = ch::studio::BuildingWallMaterial::Plaster;
    residence.roof_material = ch::studio::BuildingRoofMaterial::CeramicTile;
    residence.material_strength = 0.42F;
    residence.material_scale = 1.0F;
    residence.material_seed = 17;
    residence.roof_chimney = true;
    residence.door_position = ch::studio::BuildingDoorPosition::Center;
    residence.window_pattern = ch::studio::BuildingWindowPattern::Pair;

    if (!writeAsset(output_dir, "building_composer_pilot", residence)) return 3;

    ch::studio::BuildingComposerSpec shop = residence;
    shop.wall_color = QColor("#d9d7cf"); shop.roof_color = QColor("#4d5961");
    shop.trim_color = QColor("#f7f7f3"); shop.glass_color = QColor("#7cb5c9");
    shop.door_color = QColor("#3f4b52"); shop.roof_style = ch::studio::BuildingRoofStyle::Flat;
    shop.roof_height_px = 10; shop.wall_material = ch::studio::BuildingWallMaterial::Concrete;
    shop.roof_material = ch::studio::BuildingRoofMaterial::MetalSeam; shop.material_strength = 0.50F;
    shop.roof_chimney = false; shop.south_awning = true; shop.south_sign = true;
    shop.door_position = ch::studio::BuildingDoorPosition::Left; shop.window_pattern = ch::studio::BuildingWindowPattern::Strip;
    if (!writeAsset(output_dir, "building_composer_shop_socket_gate", shop)) return 4;

    ch::studio::BuildingComposerSpec material_gate = residence;
    material_gate.footprint_width_tiles = 2; material_gate.footprint_depth_tiles = 2;
    material_gate.wall_color = QColor("#b97a63"); material_gate.roof_color = QColor("#8f493d");
    material_gate.trim_color = QColor("#f0dfca"); material_gate.door_color = QColor("#684337");
    material_gate.wall_material = ch::studio::BuildingWallMaterial::Brick;
    material_gate.roof_material = ch::studio::BuildingRoofMaterial::CeramicTile;
    material_gate.material_strength = 0.72F; material_gate.material_scale = 0.72F; material_gate.material_seed = 83;
    if (!writeAsset(output_dir, "building_composer_material_gate", material_gate)) return 5;

    ch::studio::BuildingComposerSpec roof_gate = residence;
    roof_gate.footprint_width_tiles = 3; roof_gate.footprint_depth_tiles = 2;
    roof_gate.roof_style = ch::studio::BuildingRoofStyle::Mansard; roof_gate.roof_height_px = 38;
    roof_gate.roof_pitch_degrees = 42.0F; roof_gate.roof_overhang = 0.14F;
    roof_gate.roof_fascia_thickness_px = 3.2F; roof_gate.roof_ridge_scale = 1.15F;
    roof_gate.roof_chimney = true; roof_gate.material_strength = 0.48F;
    if (!writeAsset(output_dir, "building_composer_roof_editor_gate", roof_gate)) return 6;

    ch::studio::BuildingComposerSpec facade_gate = residence;
    facade_gate.footprint_width_tiles = 2;
    facade_gate.footprint_depth_tiles = 2;
    facade_gate.floor_count = 3;
    facade_gate.floor_height_px = 64;
    facade_gate.facade_editor_enabled = true;
    facade_gate.floor_bands_enabled = true;
    facade_gate.roof_style = ch::studio::BuildingRoofStyle::Hip;
    facade_gate.roof_chimney = false;
    using Kind = ch::studio::BuildingFacadeModuleKind;
    using Edge = ch::studio::BuildingStreetEdge;
    facade_gate.facade_modules = {
        {Kind::Storefront, Edge::South, 0, 0.30F, 0.34F, true},
        {Kind::Door, Edge::South, 0, 0.70F, 0.18F, true},
        {Kind::Awning, Edge::South, 0, 0.30F, 0.38F, true},
        {Kind::Sign, Edge::South, 0, 0.30F, 0.32F, true},
        {Kind::Window, Edge::South, 1, 0.28F, 0.18F, true},
        {Kind::Window, Edge::South, 1, 0.72F, 0.18F, true},
        {Kind::Window, Edge::South, 2, 0.28F, 0.18F, true},
        {Kind::Window, Edge::South, 2, 0.72F, 0.18F, true},
        {Kind::Window, Edge::East, 1, 0.30F, 0.18F, true},
        {Kind::Window, Edge::East, 1, 0.70F, 0.18F, true},
        {Kind::Window, Edge::East, 2, 0.30F, 0.18F, true},
        {Kind::Window, Edge::East, 2, 0.70F, 0.18F, true}
    };
    if (!writeAsset(output_dir, "building_composer_facade_floor_gate", facade_gate)) return 7;

    // Park ticket booth reference: static 2D architecture authored entirely in
    // Building Composer. In the canonical South review the ticket counter lives
    // on the left visible face (South edge), while the entrance arch and ornate
    // blue pediment live on the right visible face (East edge), matching the
    // supplied reference instead of flattening both functions onto one wall.
    ch::studio::BuildingComposerSpec ticket_booth = residence;
    ticket_booth.footprint_width_tiles = 2;
    ticket_booth.footprint_depth_tiles = 2;
    ticket_booth.floor_count = 1;
    // Keep the body compact so the roof and entrance silhouette dominate, as in
    // the approved reference, instead of reading as a tall narrow tower.
    ticket_booth.floor_height_px = 80;
    ticket_booth.wall_height_px = 80;
    ticket_booth.floor_bands_enabled = false;
    ticket_booth.roof_style = ch::studio::BuildingRoofStyle::Pyramid;
    ticket_booth.roof_height_px = 50;
    ticket_booth.roof_pitch_degrees = 41.5F;
    ticket_booth.roof_overhang = 0.15F;
    ticket_booth.roof_fascia_thickness_px = 3.4F;
    ticket_booth.roof_chimney = false;
    ticket_booth.wall_color = QColor("#e8dbbe");
    ticket_booth.roof_color = QColor("#c73f31");
    ticket_booth.trim_color = QColor("#f7ebd1");
    ticket_booth.glass_color = QColor("#305b91");
    ticket_booth.door_color = QColor("#af702b");
    ticket_booth.accent_color = QColor("#d34130");
    ticket_booth.secondary_accent_color = QColor("#2c7b32");
    ticket_booth.ornament_color = QColor("#e3a630");
    ticket_booth.wall_material = ch::studio::BuildingWallMaterial::Plaster;
    ticket_booth.roof_material = ch::studio::BuildingRoofMaterial::CeramicTile;
    // Coarser, lighter ceramic courses avoid the dense wireframe read while
    // keeping an authored tile pattern on the pyramid roof.
    ticket_booth.material_strength = 0.48F;
    ticket_booth.material_scale = 1.15F;
    ticket_booth.material_variation = 0.18F;
    ticket_booth.material_contrast = 0.38F;
    ticket_booth.material_seed = 149;
    ticket_booth.windows = false;
    ticket_booth.south_door = false;
    ticket_booth.south_awning = false;
    ticket_booth.south_sign = false;
    ticket_booth.sidewalk_enabled = false;
    ticket_booth.road_socket_enabled = false;
    ticket_booth.facade_editor_enabled = true;
    ticket_booth.facade_modules = {
        {Kind::CornerQuoins, Edge::South, 0, 0.50F, 0.90F, true},
        {Kind::CornerQuoins, Edge::East, 0, 0.50F, 0.90F, true},
        {Kind::CornerQuoins, Edge::North, 0, 0.50F, 0.90F, true},
        {Kind::CornerQuoins, Edge::West, 0, 0.50F, 0.90F, true},

        // Small red corbels continue around the entire building. Keeping them on
        // every edge prevents the canonical rotations from exposing undecorated
        // rear eaves while preserving one physical 2D procedural structure.
        {Kind::Sign, Edge::South, 0, 0.14F, 0.075F, true},
        {Kind::Sign, Edge::South, 0, 0.50F, 0.075F, true},
        {Kind::Sign, Edge::South, 0, 0.86F, 0.075F, true},
        {Kind::Sign, Edge::East, 0, 0.14F, 0.075F, true},
        {Kind::Sign, Edge::East, 0, 0.86F, 0.075F, true},
        {Kind::Sign, Edge::North, 0, 0.14F, 0.075F, true},
        {Kind::Sign, Edge::North, 0, 0.50F, 0.075F, true},
        {Kind::Sign, Edge::North, 0, 0.86F, 0.075F, true},
        {Kind::Sign, Edge::West, 0, 0.14F, 0.075F, true},
        {Kind::Sign, Edge::West, 0, 0.50F, 0.075F, true},
        {Kind::Sign, Edge::West, 0, 0.86F, 0.075F, true},

        // Left visible facade in the canonical South view.
        {Kind::TicketWindow, Edge::South, 0, 0.50F, 0.42F, true},
        {Kind::StripedAwning, Edge::South, 0, 0.50F, 0.50F, true},

        // Right/front facade in the canonical South view.
        {Kind::ArchedPassage, Edge::East, 0, 0.52F, 0.48F, true},
        // The reference pediment is decorative rather than a full-width facade,
        // so keep it narrower than the arch assembly below it.
        {Kind::CurvedPediment, Edge::East, 0, 0.52F, 0.42F, true},
        // Narrow red plaque reads as the reference keystone above the arch.
        {Kind::Sign, Edge::East, 0, 0.52F, 0.09F, true},

        {Kind::EaveTrim, Edge::South, 0, 0.50F, 0.96F, true},
        {Kind::EaveTrim, Edge::East, 0, 0.50F, 0.96F, true},
        {Kind::EaveTrim, Edge::North, 0, 0.50F, 0.96F, true},
        {Kind::EaveTrim, Edge::West, 0, 0.50F, 0.96F, true},
        {Kind::RoofFlag, Edge::South, 0, 0.50F, 0.08F, true},
    };
    if (!writeAsset(output_dir, "building_composer_ticket_booth", ticket_booth)) return 8;
    if (!writeTicketBoothNpcScaleGate(output_dir, ticket_booth)) return 12;

    const QString block_gate_path = QDir(output_dir).filePath(QStringLiteral("building_composer_small_block_gate.png"));
    if (!ch::studio::BuildingBlockPreviewRenderer::render(facade_gate, QSize(960, 560), 401).save(block_gate_path, "PNG")) {
        std::cerr << "Unable to save small block preview gate.\n";
        return 9;
    }
    std::cout << block_gate_path.toStdString() << "\n";

    const QString lod_gate_path = QDir(output_dir).filePath(QStringLiteral("building_composer_lod_gate.png"));
    if (!ch::studio::BuildingLodValidator::renderReviewSheet(facade_gate, QSize(960, 420)).save(lod_gate_path, "PNG")) {
        std::cerr << "Unable to save LOD visual gate.\n";
        return 10;
    }
    std::cout << lod_gate_path.toStdString() << "\n";

    if (!writeVisualReferenceGate(output_dir)) return 11;

    std::cout << "Building Composer visual gates generated.\n";
    return 0;
}
