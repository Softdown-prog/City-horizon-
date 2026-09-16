#include "building_composer.h"

#include <QDir>
#include <QFile>
#include <QGuiApplication>
#include <QJsonDocument>
#include <QString>

#include <iostream>

int main(int argc, char** argv) {
    QGuiApplication app(argc, argv);

    const QString output_dir = argc > 1 ? QString::fromLocal8Bit(argv[1]) : QStringLiteral(".");
    QDir dir;
    if (!dir.mkpath(output_dir)) {
        std::cerr << "Unable to create output directory.\n";
        return 2;
    }

    ch::studio::BuildingComposerSpec spec;
    spec.footprint_width_tiles = 2;
    spec.footprint_depth_tiles = 1;
    spec.wall_height_px = 82;
    spec.roof_height_px = 34;
    spec.roof_style = ch::studio::BuildingRoofStyle::Gable;
    spec.wall_color = QColor("#d8c3a5");
    spec.roof_color = QColor("#a94e3f");
    spec.trim_color = QColor("#f2eadf");
    spec.glass_color = QColor("#78b9d1");
    spec.door_color = QColor("#6d4c41");

    const QSize frame(320, 280);
    const QString review_path = QDir(output_dir).filePath("building_composer_pilot_review.png");
    const QString sheet_path = QDir(output_dir).filePath("building_composer_pilot_4view.png");
    const QString manifest_path = QDir(output_dir).filePath("building_composer_pilot_manifest.json");

    if (!ch::studio::BuildingComposer::renderReviewSheet(spec, QSize(300, 250)).save(review_path, "PNG")) {
        std::cerr << "Unable to save review image.\n";
        return 3;
    }
    if (!ch::studio::BuildingComposer::renderSpriteSheet(spec, frame).save(sheet_path, "PNG")) {
        std::cerr << "Unable to save sprite sheet.\n";
        return 4;
    }

    QFile manifest_file(manifest_path);
    if (!manifest_file.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
        std::cerr << "Unable to save manifest.\n";
        return 5;
    }
    manifest_file.write(QJsonDocument(ch::studio::BuildingComposer::manifest(spec, frame)).toJson(QJsonDocument::Indented));
    manifest_file.close();

    std::cout << "Building Composer visual gate generated:\n"
              << review_path.toStdString() << "\n"
              << sheet_path.toStdString() << "\n"
              << manifest_path.toStdString() << "\n";
    return 0;
}
