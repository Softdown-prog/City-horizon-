#include "animation_export_pipeline.h"
#include "building_visual_reference_gate.h"

#include <QDir>
#include <QGuiApplication>

#include <iostream>

namespace {

ch::studio::AnimatedAssetSpec makeAnimationCoreGate() {
    using namespace ch::studio;

    AnimatedAssetSpec asset;
    asset.asset_id = QStringLiteral("animation_core_reference");
    asset.category = QStringLiteral("qa_reference");
    asset.palette_profile = QStringLiteral("city_horizon_classic_tycoon");
    asset.frame_size = QSize(420, 420);
    asset.anchor_normalized = QPointF(0.50, 0.90);
    asset.view = BuildingView::South;
    asset.base_building = BuildingVisualReferenceGate::referenceSpec();

    AnimationClip clip;
    clip.id = QStringLiteral("coherence_loop");
    clip.name = QStringLiteral("Animation Core coherence loop");
    clip.duration_seconds = 1.0F;
    clip.frame_count = 12;
    clip.loop = true;

    AnimationTrack vertical;
    vertical.target_id = QStringLiteral("root");
    vertical.property = AnimationProperty::OffsetY;
    vertical.interpolation = AnimationInterpolation::Sine;
    vertical.keyframes = {
        {0.00F, 0.0F},
        {0.25F, -4.0F},
        {0.50F, 0.0F},
        {0.75F, 4.0F},
        {1.00F, 0.0F},
    };

    AnimationTrack scale;
    scale.target_id = QStringLiteral("root");
    scale.property = AnimationProperty::Scale;
    scale.interpolation = AnimationInterpolation::SmoothStep;
    scale.keyframes = {
        {0.00F, 1.0F},
        {0.50F, 0.985F},
        {1.00F, 1.0F},
    };

    clip.tracks = {vertical, scale};
    asset.clips = {clip};
    return asset;
}

} // namespace

int main(int argc, char** argv) {
    QGuiApplication app(argc, argv);
    const QString output_dir = argc > 1
        ? QString::fromLocal8Bit(argv[1])
        : QStringLiteral("animation_core_preview");

    const ch::studio::AnimatedAssetSpec asset = makeAnimationCoreGate();
    const ch::studio::AnimationExportResult result =
        ch::studio::AnimationExportPipeline::exportClip(
            asset, QStringLiteral("coherence_loop"), output_dir);

    if (!result.success) {
        std::cerr << "Animation Core preview export failed: "
                  << result.reason.toStdString() << "\n";
        return 2;
    }

    QDir directory(output_dir);
    for (const QString& file : result.files) {
        std::cout << directory.filePath(file).toStdString() << "\n";
    }
    std::cout << "Animation Core preview package generated.\n";
    return 0;
}
