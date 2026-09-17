#include "building_composer.h"

#include <QDir>
#include <QFile>
#include <QGuiApplication>
#include <QJsonDocument>
#include <QString>

#include <iostream>

namespace {

bool writeAsset(const QString& output_dir, const QString& stem,
                const ch::studio::BuildingComposerSpec& spec) {
    const QSize frame(320, 280);
    const QString review_path = QDir(output_dir).filePath(stem + "_review.png");
    const QString sheet_path = QDir(output_dir).filePath(stem + "_4view.png");
    const QString manifest_path = QDir(output_dir).filePath(stem + "_manifest.json");

    if (!ch::studio::BuildingComposer::renderReviewSheet(spec, QSize(300, 250)).save(review_path, "PNG")) {
        std::cerr << "Unable to save review image.\n";
        return false;
    }
    if (!ch::studio::BuildingComposer::renderSpriteSheet(spec, frame).save(sheet_path, "PNG")) {
        std::cerr << "Unable to save sprite sheet.\n";
        return false;
    }

    QFile manifest_file(manifest_path);
    if (!manifest_file.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
        std::cerr << "Unable to save manifest.\n";
        return false;
    }
    manifest_file.write(QJsonDocument(ch::studio::BuildingComposer::manifest(spec, frame)).toJson(QJsonDocument::Indented));
    manifest_file.close();

    std::cout << review_path.toStdString() << "\n"
              << sheet_path.toStdString() << "\n"
              << manifest_path.toStdString() << "\n";
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

    ch::studio::BuildingComposerSpec residence;
    residence.footprint_width_tiles = 2;
    residence.footprint_depth_tiles = 1;
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
    shop.wall_color = QColor("#d9d7cf");
    shop.roof_color = QColor("#4d5961");
    shop.trim_color = QColor("#f7f7f3");
    shop.glass_color = QColor("#7cb5c9");
    shop.door_color = QColor("#3f4b52");
    shop.accent_color = QColor("#d79b38");
    shop.roof_style = ch::studio::BuildingRoofStyle::Flat;
    shop.roof_height_px = 10;
    shop.wall_material = ch::studio::BuildingWallMaterial::Concrete;
    shop.roof_material = ch::studio::BuildingRoofMaterial::MetalSeam;
    shop.material_strength = 0.50F;
    shop.roof_chimney = false;
    shop.south_awning = true;
    shop.south_sign = true;
    shop.door_position = ch::studio::BuildingDoorPosition::Left;
    shop.window_pattern = ch::studio::BuildingWindowPattern::Strip;

    if (!writeAsset(output_dir, "building_composer_shop_socket_gate", shop)) return 4;

    ch::studio::BuildingComposerSpec material_gate = residence;
    material_gate.footprint_width_tiles = 2;
    material_gate.footprint_depth_tiles = 2;
    material_gate.wall_color = QColor("#b97a63");
    material_gate.roof_color = QColor("#8f493d");
    material_gate.trim_color = QColor("#f0dfca");
    material_gate.door_color = QColor("#684337");
    material_gate.wall_material = ch::studio::BuildingWallMaterial::Brick;
    material_gate.roof_material = ch::studio::BuildingRoofMaterial::CeramicTile;
    material_gate.material_strength = 0.72F;
    material_gate.material_scale = 0.72F;
    material_gate.material_seed = 83;
    material_gate.roof_chimney = true;
    material_gate.window_pattern = ch::studio::BuildingWindowPattern::Pair;

    if (!writeAsset(output_dir, "building_composer_material_gate", material_gate)) return 5;

    // Window gate: isolates facade aperture spacing, frame/glass readability and
    // deterministic placement around an entrance without changing structure.
    ch::studio::BuildingComposerSpec window_gate = residence;
    window_gate.footprint_width_tiles = 2;
    window_gate.footprint_depth_tiles = 1;
    window_gate.wall_color = QColor("#d7c8ad");
    window_gate.roof_color = QColor("#9f5142");
    window_gate.trim_color = QColor("#f4eee4");
    window_gate.glass_color = QColor("#70b8d2");
    window_gate.door_color = QColor("#6a493d");
    window_gate.wall_material = ch::studio::BuildingWallMaterial::Plaster;
    window_gate.roof_material = ch::studio::BuildingRoofMaterial::CeramicTile;
    window_gate.material_strength = 0.38F;
    window_gate.material_scale = 1.0F;
    window_gate.material_seed = 29;
    window_gate.roof_chimney = false;
    window_gate.south_awning = false;
    window_gate.south_sign = false;
    window_gate.south_door = true;
    window_gate.door_position = ch::studio::BuildingDoorPosition::Left;
    window_gate.windows = true;
    window_gate.window_pattern = ch::studio::BuildingWindowPattern::Strip;

    if (!writeAsset(output_dir, "building_composer_window_gate", window_gate)) return 6;

    // Door gate: isolates the entrance frame, inset panel and depth cues. Windows,
    // sign, awning and chimney are disabled so the entrance can be judged alone.
    ch::studio::BuildingComposerSpec door_gate = residence;
    door_gate.footprint_width_tiles = 2;
    door_gate.footprint_depth_tiles = 1;
    door_gate.wall_color = QColor("#d7c8ad");
    door_gate.roof_color = QColor("#9f5142");
    door_gate.trim_color = QColor("#f4eee4");
    door_gate.door_color = QColor("#69483d");
    door_gate.wall_material = ch::studio::BuildingWallMaterial::Plaster;
    door_gate.roof_material = ch::studio::BuildingRoofMaterial::CeramicTile;
    door_gate.material_strength = 0.32F;
    door_gate.material_scale = 1.0F;
    door_gate.material_seed = 31;
    door_gate.roof_chimney = false;
    door_gate.south_awning = false;
    door_gate.south_sign = false;
    door_gate.south_door = true;
    door_gate.door_position = ch::studio::BuildingDoorPosition::Center;
    door_gate.windows = false;

    if (!writeAsset(output_dir, "building_composer_door_gate", door_gate)) return 7;

    // Wall finish gate: isolates the plaster surface and face shading so the
    // house's final wall language can be judged without apertures or add-ons.
    ch::studio::BuildingComposerSpec wall_gate = residence;
    wall_gate.footprint_width_tiles = 2;
    wall_gate.footprint_depth_tiles = 1;
    wall_gate.wall_color = QColor("#d7c8ad");
    wall_gate.roof_color = QColor("#9f5142");
    wall_gate.trim_color = QColor("#f4eee4");
    wall_gate.wall_material = ch::studio::BuildingWallMaterial::Plaster;
    wall_gate.roof_material = ch::studio::BuildingRoofMaterial::CeramicTile;
    wall_gate.material_strength = 0.38F;
    wall_gate.material_scale = 1.0F;
    wall_gate.material_seed = 37;
    wall_gate.windows = false;
    wall_gate.south_door = false;
    wall_gate.south_awning = false;
    wall_gate.south_sign = false;
    wall_gate.roof_chimney = false;

    if (!writeAsset(output_dir, "building_composer_wall_finish_gate", wall_gate)) return 8;

    std::cout << "Building Composer visual gates generated.\n";
    return 0;
}
