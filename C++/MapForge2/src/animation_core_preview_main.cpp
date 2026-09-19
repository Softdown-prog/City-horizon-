#include "animation_export_pipeline.h"
#include "carousel_composer.h"
#include "projection_calibration_gate.h"

#include <QDir>
#include <QFile>
#include <QGuiApplication>
#include <QJsonDocument>

#include <iostream>

namespace {

ch::studio::CarouselComposerSpec makeCarouselComposerGate() {
    using namespace ch::studio;

    CarouselComposerSpec spec;
    spec.asset_id = QStringLiteral("carousel_composer_reference");
    spec.clip_id = QStringLiteral("ride_loop");
    spec.clip_name = QStringLiteral("City Horizon Carousel Composer reference loop");
    spec.frame_size = QSize(460, 460);
    spec.anchor_normalized = QPointF(0.50, 0.90);
    spec.horse_count = 8;
    spec.platform_radius_world_tiles = 0.80F;
    spec.horse_bob_amplitude_px = 9.0F;
    spec.duration_seconds = 2.4F;
    spec.frame_count = 16;
    spec.clockwise = true;
    spec.camera_rotation = ch::CameraRotation::r0;
    spec.camera_zoom = 1.0F;
    spec.dynamic_depth_ordering = true;
    spec.directional_horses = true;
    spec.canopy_enabled = true;
    spec.rosettes_enabled = true;
    spec.finial_enabled = true;
    spec.rosette_count = 6;
    spec.palette = CarouselPaletteProfile::ClassicRedCream;
    return spec;
}

bool writeComposerAuthoringManifest(const ch::studio::CarouselComposerSpec& spec,
                                    const QString& output_dir) {
    const QString path = QDir(output_dir).filePath(
        QStringLiteral("carousel_composer_reference_authoring.json"));
    QFile file(path);
    if (!file.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
        std::cerr << "Unable to save Carousel Composer authoring manifest.\n";
        return false;
    }
    file.write(QJsonDocument(ch::studio::CarouselComposer::manifest(spec))
                   .toJson(QJsonDocument::Indented));
    file.close();
    std::cout << path.toStdString() << "\n";
    return true;
}

} // namespace

int main(int argc, char** argv) {
    QGuiApplication app(argc, argv);
    const QString output_dir = argc > 1
        ? QString::fromLocal8Bit(argv[1])
        : QStringLiteral("animation_core_preview");

    const ch::studio::ProjectionCalibrationResult calibration =
        ch::studio::ProjectionCalibrationGate::run();
    QString calibration_save_reason;
    if (!ch::studio::ProjectionCalibrationGate::save(
            calibration, output_dir, &calibration_save_reason)) {
        std::cerr << "Projection calibration output failed: "
                  << calibration_save_reason.toStdString() << "\n";
        return 1;
    }
    if (!calibration.pass) {
        std::cerr << "Projection calibration failed: "
                  << calibration.reason.toStdString() << "\n";
        return 2;
    }

    const ch::studio::CarouselComposerSpec composer_spec =
        makeCarouselComposerGate();

    QString compose_reason;
    const ch::studio::AnimatedAssetSpec asset =
        ch::studio::CarouselComposer::compose(composer_spec, &compose_reason);
    if (!compose_reason.isEmpty()) {
        std::cerr << "Carousel Composer failed: "
                  << compose_reason.toStdString() << "\n";
        return 3;
    }

    const ch::studio::AnimationExportResult result =
        ch::studio::AnimationExportPipeline::exportClip(
            asset, composer_spec.clip_id, output_dir);

    if (!result.success) {
        std::cerr << "Carousel Composer preview export failed: "
                  << result.reason.toStdString() << "\n";
        return 4;
    }

    QDir directory(output_dir);
    for (const QString& file : result.files)
        std::cout << directory.filePath(file).toStdString() << "\n";

    if (!writeComposerAuthoringManifest(composer_spec, output_dir))
        return 5;

    std::cout
        << "Carousel Composer package generated after pixel-identical runtime "
           "projection calibration and with authored modular carousel assets.\n";
    return 0;
}
