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
    shop.roof_chimney = false;
    shop.south_awning = true;
    shop.south_sign = true;
    shop.door_position = ch::studio::BuildingDoorPosition::Left;
    shop.window_pattern = ch::studio::BuildingWindowPattern::Strip;

    if (!writeAsset(output_dir, "building_composer_shop_socket_gate", shop)) return 4;

    std::cout << "Building Composer visual gates generated.\n";
    return 0;
}
