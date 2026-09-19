#include "animation_export_pipeline.h"

#include <QDir>
#include <QGuiApplication>

#include <iostream>

namespace {

ch::studio::AnimationNodeSpec primitiveNode(
    const QString& id,
    const QString& parent,
    const QPointF position,
    const QSizeF size,
    const QColor fill,
    const int draw_order,
    const ch::studio::AnimationNodeVisualKind kind = ch::studio::AnimationNodeVisualKind::PrimitiveRectangle) {
    ch::studio::AnimationNodeSpec node;
    node.id = id;
    node.parent_id = parent;
    node.position_px = position;
    node.visual_size_px = size;
    node.fill_color = fill;
    node.outline_color = QColor("#2d3133");
    node.draw_order = draw_order;
    node.visual_kind = kind;
    return node;
}

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

ch::studio::AnimatedAssetSpec makeAnimationCoreGate() {
    using namespace ch::studio;

    AnimatedAssetSpec asset;
    asset.asset_id = QStringLiteral("animation_node_hierarchy_reference");
    asset.category = QStringLiteral("mechanical_qa_reference");
    asset.palette_profile = QStringLiteral("city_horizon_classic_tycoon");
    asset.frame_size = QSize(420, 420);
    asset.anchor_normalized = QPointF(0.50, 0.90);
    asset.view = BuildingView::South;
    asset.render_base_building = false;

    asset.nodes = {
        primitiveNode(QStringLiteral("base"), QStringLiteral("root"), QPointF(210.0, 326.0),
                      QSizeF(236.0, 62.0), QColor("#6d4c41"), 0,
                      AnimationNodeVisualKind::PrimitiveEllipse),
        primitiveNode(QStringLiteral("platform"), QStringLiteral("root"), QPointF(210.0, 282.0),
                      QSizeF(204.0, 58.0), QColor("#d79b38"), 10,
                      AnimationNodeVisualKind::PrimitiveEllipse),
        primitiveNode(QStringLiteral("platform_marker"), QStringLiteral("platform"), QPointF(0.0, 0.0),
                      QSizeF(140.0, 9.0), QColor("#f2eadf"), 11),
        primitiveNode(QStringLiteral("horse_a"), QStringLiteral("platform"), QPointF(-70.0, -8.0),
                      QSizeF(22.0, 42.0), QColor("#b84d4a"), 20),
        primitiveNode(QStringLiteral("horse_b"), QStringLiteral("platform"), QPointF(0.0, 18.0),
                      QSizeF(22.0, 42.0), QColor("#547a9b"), 21),
        primitiveNode(QStringLiteral("horse_c"), QStringLiteral("platform"), QPointF(70.0, -8.0),
                      QSizeF(22.0, 42.0), QColor("#71905a"), 22),
        primitiveNode(QStringLiteral("center_pole"), QStringLiteral("root"), QPointF(210.0, 236.0),
                      QSizeF(14.0, 150.0), QColor("#f2eadf"), 30),
    };

    AnimationClip clip;
    clip.id = QStringLiteral("carousel_parts_loop");
    clip.name = QStringLiteral("Hierarchical parts coherence loop");
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

    const ch::studio::AnimatedAssetSpec asset = makeAnimationCoreGate();
    const ch::studio::AnimationExportResult result =
        ch::studio::AnimationExportPipeline::exportClip(
            asset, QStringLiteral("carousel_parts_loop"), output_dir);

    if (!result.success) {
        std::cerr << "Animation node hierarchy preview export failed: "
                  << result.reason.toStdString() << "\n";
        return 2;
    }

    QDir directory(output_dir);
    for (const QString& file : result.files)
        std::cout << directory.filePath(file).toStdString() << "\n";
    std::cout << "Animation node hierarchy preview package generated.\n";
    return 0;
}
