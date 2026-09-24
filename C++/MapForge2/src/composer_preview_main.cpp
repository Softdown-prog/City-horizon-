#include "building_block_preview_renderer.h"
#include "building_composer.h"
#include "building_facade_renderer.h"
#include "building_lod_validator.h"
#include "building_roof_editor_renderer.h"
#include "building_visual_reference_gate.h"

#include <QDir>
#include <QFile>
#include <QGuiApplication>
#include <QJsonDocument>
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
    ticket_booth.floor_height_px = 84;
    ticket_booth.wall_height_px = 84;
    ticket_booth.floor_bands_enabled = false;
    ticket_booth.roof_style = ch::studio::BuildingRoofStyle::Pyramid;
    ticket_booth.roof_height_px = 48;
    ticket_booth.roof_pitch_degrees = 42.0F;
    ticket_booth.roof_overhang = 0.12F;
    ticket_booth.roof_fascia_thickness_px = 3.2F;
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
    ticket_booth.material_strength = 0.50F;
    ticket_booth.material_scale = 0.85F;
    ticket_booth.material_variation = 0.25F;
    ticket_booth.material_contrast = 0.48F;
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

        // Left visible facade in the canonical South view.
        {Kind::TicketWindow, Edge::South, 0, 0.50F, 0.38F, true},
        {Kind::StripedAwning, Edge::South, 0, 0.50F, 0.46F, true},

        // Right/front facade in the canonical South view.
        {Kind::ArchedPassage, Edge::East, 0, 0.52F, 0.48F, true},
        {Kind::CurvedPediment, Edge::East, 0, 0.52F, 0.46F, true},

        {Kind::EaveTrim, Edge::South, 0, 0.50F, 0.96F, true},
        {Kind::EaveTrim, Edge::East, 0, 0.50F, 0.96F, true},
        {Kind::EaveTrim, Edge::North, 0, 0.50F, 0.96F, true},
        {Kind::EaveTrim, Edge::West, 0, 0.50F, 0.96F, true},
        {Kind::RoofFlag, Edge::South, 0, 0.50F, 0.08F, true},
    };
    if (!writeAsset(output_dir, "building_composer_ticket_booth", ticket_booth)) return 8;

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
