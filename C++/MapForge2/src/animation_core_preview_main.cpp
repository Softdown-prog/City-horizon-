#include "animation_export_pipeline.h"
#include "carousel_part_library.h"

#include <QDir>
#include <QGuiApplication>

#include <iostream>

namespace {

ch::studio::AnimationTrack rotationTrack(const QString& target) {
    using namespace ch::studio;
    AnimationTrack track;
    track.target_id = target;
    track.property = AnimationProperty::RotationDegrees;
    track.interpolation = AnimationInterpolation::Linear;
    track.keyframes = {{0.0F, 0.0F}, {2.0F, 360.0F}};
    return track;
}

ch::studio::AnimationTrack bobTrack(const QString& target, const float phase) {
    using namespace ch::studio;
    AnimationTrack track;
    track.target_id = target;
    track.property = AnimationProperty::OffsetY;
    track.interpolation = AnimationInterpolation::Sine;
    track.keyframes = {
        {0.00F, 0.0F},
        {0.50F, phase},
        {1.00F, 0.0F},
        {1.50F, -phase},
        {2.00F, 0.0F},
    };
    return track;
}

ch::studio::AnimatedAssetSpec makeCarouselLibraryGate() {
    using namespace ch::studio;

    AnimatedAssetSpec asset;
    asset.asset_id = QStringLiteral("carousel_classic_reference");
    asset.category = QStringLiteral("amusement_ride");
    asset.palette_profile = QStringLiteral("amusement_park_classic");
    asset.frame_size = QSize(420, 420);
    asset.anchor_normalized = QPointF(0.50, 0.90);
    asset.view = BuildingView::South;
    asset.render_base_building = false;

    const QColor outline("#343638");
    asset.nodes = {
        CarouselPartLibrary::makeNode(
            QStringLiteral("carousel.base.classic.v1"), QStringLiteral("base"),
            QStringLiteral("root"), QPointF(210.0, 328.0), 0,
            QColor("#785548"), outline),

        CarouselPartLibrary::makeNode(
            QStringLiteral("carousel.platform.classic.v1"), QStringLiteral("platform"),
            QStringLiteral("root"), QPointF(210.0, 286.0), 10,
            QColor("#d29a42"), outline),

        CarouselPartLibrary::makeNode(
            QStringLiteral("carousel.horse.classic.v1"), QStringLiteral("horse_a"),
            QStringLiteral("platform"), QPointF(-72.0, -8.0), 20,
            QColor("#b8524d"), outline),
        CarouselPartLibrary::makeNode(
            QStringLiteral("carousel.horse.classic.v1"), QStringLiteral("horse_b"),
            QStringLiteral("platform"), QPointF(0.0, 20.0), 21,
            QColor("#547a9b"), outline),
        CarouselPartLibrary::makeNode(
            QStringLiteral("carousel.horse.classic.v1"), QStringLiteral("horse_c"),
            QStringLiteral("platform"), QPointF(72.0, -8.0), 22,
            QColor("#71905a"), outline),

        CarouselPartLibrary::makeNode(
            QStringLiteral("carousel.center_pole.classic.v1"), QStringLiteral("center_pole"),
            QStringLiteral("root"), QPointF(210.0, 240.0), 30,
            QColor("#e9dfcf"), outline),

        CarouselPartLibrary::makeNode(
            QStringLiteral("carousel.canopy.classic.v1"), QStringLiteral("canopy"),
            QStringLiteral("root"), QPointF(210.0, 185.0), 40,
            QColor("#b94f49"), outline),

        CarouselPartLibrary::makeNode(
            QStringLiteral("carousel.ornament.rosette.v1"), QStringLiteral("rosette_left"),
            QStringLiteral("canopy"), QPointF(-70.0, 32.0), 41,
            QColor("#dba848"), outline),
        CarouselPartLibrary::makeNode(
            QStringLiteral("carousel.ornament.rosette.v1"), QStringLiteral("rosette_right"),
            QStringLiteral("canopy"), QPointF(70.0, 32.0), 42,
            QColor("#dba848"), outline),
        CarouselPartLibrary::makeNode(
            QStringLiteral("carousel.ornament.finial.v1"), QStringLiteral("finial"),
            QStringLiteral("canopy"), QPointF(0.0, -80.0), 43,
            QColor("#d6a044"), outline),
    };

    AnimationClip clip;
    clip.id = QStringLiteral("carousel_parts_loop");
    clip.name = QStringLiteral("City Horizon classic carousel library loop");
    clip.duration_seconds = 2.0F;
    clip.frame_count = 12;
    clip.loop = true;
    clip.tracks = {
        rotationTrack(QStringLiteral("platform")),
        bobTrack(QStringLiteral("horse_a"), -9.0F),
        bobTrack(QStringLiteral("horse_b"), 9.0F),
        bobTrack(QStringLiteral("horse_c"), -6.0F),
    };

    asset.clips = {clip};
    return asset;
}

} // namespace

int main(int argc, char** argv) {
    QGuiApplication app(argc, argv);
    const QString output_dir = argc > 1
        ? QString::fromLocal8Bit(argv[1])
        : QStringLiteral("animation_core_preview");

    const ch::studio::AnimatedAssetSpec asset = makeCarouselLibraryGate();
    const ch::studio::AnimationExportResult result =
        ch::studio::AnimationExportPipeline::exportClip(
            asset, QStringLiteral("carousel_parts_loop"), output_dir);

    if (!result.success) {
        std::cerr << "Carousel library preview export failed: "
                  << result.reason.toStdString() << "\n";
        return 2;
    }

    QDir directory(output_dir);
    for (const QString& file : result.files)
        std::cout << directory.filePath(file).toStdString() << "\n";
    std::cout << "Carousel library preview package generated.\n";
    return 0;
}
