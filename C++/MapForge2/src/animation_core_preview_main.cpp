#include "animation_export_pipeline.h"

#include <QDir>
#include <QGuiApplication>

#include <iostream>

namespace {

ch::studio::BuildingComposerSpec partBuilding(const QColor& wall,
                                              const QColor& roof,
                                              const ch::studio::BuildingRoofStyle roof_style,
                                              const int footprint_width,
                                              const int footprint_depth) {
    using namespace ch::studio;
    BuildingComposerSpec spec = BuildingComposer::presetSpec();
    spec.footprint_width_tiles = footprint_width;
    spec.footprint_depth_tiles = footprint_depth;
    spec.floor_count = 1;
    spec.floor_height_px = 36;
    spec.wall_height_px = 36;
    spec.wall_color = wall;
    spec.roof_color = roof;
    spec.trim_color = QColor("#f2eadf");
    spec.wall_material = BuildingWallMaterial::Solid;
    spec.roof_material = BuildingRoofMaterial::Solid;
    spec.roof_style = roof_style;
    spec.roof_height_px = roof_style == BuildingRoofStyle::Flat ? 8 : 24;
    spec.roof_pitch_degrees = 32.0F;
    spec.roof_overhang = 0.08F;
    spec.windows = false;
    spec.south_door = false;
    spec.south_awning = false;
    spec.south_sign = false;
    spec.roof_chimney = false;
    spec.cast_shadow = false;
    return spec;
}

ch::studio::AnimationNodeSpec buildingNode(const QString& id,
                                           const QString& parent,
                                           const QPointF position,
                                           const QSizeF size,
                                           const ch::studio::BuildingComposerSpec& building,
                                           const int draw_order) {
    using namespace ch::studio;
    AnimationNodeSpec node;
    node.id = id;
    node.parent_id = parent;
    node.position_px = position;
    node.pivot_normalized = QPointF(0.50, 0.62);
    node.visual_kind = AnimationNodeVisualKind::BuildingRender;
    node.visual_size_px = size;
    node.visual_building = building;
    node.visual_building_view = BuildingView::South;
    node.visual_trim_transparent = true;
    node.visual_preserve_aspect = true;
    node.draw_order = draw_order;
    return node;
}

ch::studio::AnimationNodeSpec rasterNode(const QString& id,
                                         const QString& parent,
                                         const QPointF position,
                                         const QSizeF size,
                                         const int draw_order) {
    using namespace ch::studio;
    AnimationNodeSpec node;
    node.id = id;
    node.parent_id = parent;
    node.position_px = position;
    node.pivot_normalized = QPointF(0.50, 0.88);
    node.visual_kind = AnimationNodeVisualKind::RasterSprite;
    node.visual_size_px = size;
    node.visual_asset_path = QStringLiteral("assets/pedestrians/canonical_walk/se/frame_00.png");
    node.visual_trim_transparent = true;
    node.visual_preserve_aspect = true;
    node.visual_smooth_scaling = true;
    node.draw_order = draw_order;
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
    asset.asset_id = QStringLiteral("animation_visual_sources_reference");
    asset.category = QStringLiteral("mechanical_qa_reference");
    asset.palette_profile = QStringLiteral("city_horizon_classic_tycoon");
    asset.frame_size = QSize(420, 420);
    asset.anchor_normalized = QPointF(0.50, 0.90);
    asset.view = BuildingView::South;
    asset.render_base_building = false;
    asset.visual_source_root = QStringLiteral(".");

    const BuildingComposerSpec base = partBuilding(
        QColor("#745348"), QColor("#5c4038"), BuildingRoofStyle::Flat, 2, 2);
    const BuildingComposerSpec platform = partBuilding(
        QColor("#d39b43"), QColor("#b87532"), BuildingRoofStyle::Flat, 2, 2);
    const BuildingComposerSpec canopy = partBuilding(
        QColor("#efe3cf"), QColor("#a94e3f"), BuildingRoofStyle::Hip, 2, 2);
    const BuildingComposerSpec pole = partBuilding(
        QColor("#eee7da"), QColor("#d0c5b6"), BuildingRoofStyle::Flat, 1, 1);

    asset.nodes = {
        buildingNode(QStringLiteral("base"), QStringLiteral("root"), QPointF(210.0, 326.0),
                     QSizeF(220.0, 84.0), base, 0),
        buildingNode(QStringLiteral("platform"), QStringLiteral("root"), QPointF(210.0, 286.0),
                     QSizeF(198.0, 74.0), platform, 10),
        rasterNode(QStringLiteral("horse_a"), QStringLiteral("platform"), QPointF(-68.0, -8.0),
                   QSizeF(30.0, 52.0), 20),
        rasterNode(QStringLiteral("horse_b"), QStringLiteral("platform"), QPointF(0.0, 18.0),
                   QSizeF(30.0, 52.0), 21),
        rasterNode(QStringLiteral("horse_c"), QStringLiteral("platform"), QPointF(68.0, -8.0),
                   QSizeF(30.0, 52.0), 22),
        buildingNode(QStringLiteral("center_pole"), QStringLiteral("root"), QPointF(210.0, 238.0),
                     QSizeF(34.0, 150.0), pole, 30),
        buildingNode(QStringLiteral("canopy"), QStringLiteral("root"), QPointF(210.0, 174.0),
                     QSizeF(220.0, 116.0), canopy, 40),
    };

    AnimationClip clip;
    clip.id = QStringLiteral("carousel_parts_loop");
    clip.name = QStringLiteral("Real visual-source carousel parts loop");
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
        std::cerr << "Animation visual-source preview export failed: "
                  << result.reason.toStdString() << "\n";
        return 2;
    }

    QDir directory(output_dir);
    for (const QString& file : result.files)
        std::cout << directory.filePath(file).toStdString() << "\n";
    std::cout << "Animation visual-source preview package generated.\n";
    return 0;
}
