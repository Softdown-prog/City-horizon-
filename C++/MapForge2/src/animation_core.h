#pragma once

#include "building_composer.h"

#include <QColor>
#include <QJsonObject>
#include <QPointF>
#include <QRectF>
#include <QSize>
#include <QSizeF>
#include <QString>

#include <vector>

namespace ch::studio {

enum class AnimationInterpolation {
    Step,
    Linear,
    SmoothStep,
    Sine,
};

enum class AnimationProperty {
    OffsetX,
    OffsetY,
    RotationDegrees,
    Scale,
    Opacity,
    Visibility,
};

enum class AnimationNodeVisualKind {
    None,
    PrimitiveRectangle,
    PrimitiveEllipse,
    RasterSprite,
    BuildingRender,
    LibraryPart,
};

struct AnimationKeyframe {
    float time_seconds = 0.0F;
    float value = 0.0F;
};

struct AnimationTrack {
    QString target_id = QStringLiteral("root");
    AnimationProperty property = AnimationProperty::OffsetX;
    AnimationInterpolation interpolation = AnimationInterpolation::Linear;
    std::vector<AnimationKeyframe> keyframes;
};

struct AnimationClip {
    QString id = QStringLiteral("idle");
    QString name = QStringLiteral("Idle");
    float duration_seconds = 1.0F;
    int frame_count = 8;
    bool loop = true;
    std::vector<AnimationTrack> tracks;
};

struct AnimationNodeSpec {
    QString id;
    QString parent_id = QStringLiteral("root");
    QPointF position_px = QPointF(0.0, 0.0);
    QPointF pivot_normalized = QPointF(0.50, 0.50);
    float rotation_degrees = 0.0F;
    float scale = 1.0F;
    float opacity = 1.0F;
    bool visible = true;
    int draw_order = 0;

    // Visual source contract. Primitive kinds remain available as a lightweight
    // fallback, but production animated assets should prefer RasterSprite,
    // BuildingRender or LibraryPart so every animated part has a stable source.
    AnimationNodeVisualKind visual_kind = AnimationNodeVisualKind::None;
    QSizeF visual_size_px = QSizeF(24.0, 24.0);
    QColor fill_color = QColor("#d79b38");
    QColor outline_color = QColor("#2d3133");

    // RasterSprite: UTF-8 path relative to AnimatedAssetSpec::visual_source_root
    // (or absolute). A null/empty source rect means the whole image.
    QString visual_asset_path;
    QRectF visual_source_rect_px;

    // LibraryPart: stable catalog ID resolved by a registered authoring library.
    // Carousel IDs use the `carousel.*` namespace. Future libraries can add
    // their own namespace without changing AnimationTrack or hierarchy logic.
    QString visual_library_id;

    // Shared raster/render presentation policy. Transparent borders are removed
    // before fitting the source into visual_size_px so pivots remain meaningful.
    bool visual_trim_transparent = true;
    bool visual_preserve_aspect = true;
    bool visual_smooth_scaling = true;

    // BuildingRender: a completely independent Composer definition for this
    // node. It is rendered once as the node's visual source, not as a new frame
    // generated independently from the animation timeline.
    BuildingComposerSpec visual_building;
    BuildingView visual_building_view = BuildingView::South;
};

struct AnimatedAssetSpec {
    QString asset_id = QStringLiteral("animated_building");
    QString category = QStringLiteral("building");
    QString palette_profile = QStringLiteral("city_horizon_classic_tycoon");
    QSize frame_size = QSize(420, 420);
    QPointF anchor_normalized = QPointF(0.50, 0.90);
    BuildingView view = BuildingView::South;
    BuildingComposerSpec base_building;
    bool render_base_building = true;

    // Root directory used to resolve relative RasterSprite paths. The visual
    // resolver also checks the executable directory and its parent directories
    // so authoring previews remain portable between source and build folders.
    QString visual_source_root = QStringLiteral(".");

    std::vector<AnimationNodeSpec> nodes;
    std::vector<AnimationClip> clips;
};

struct AnimationRootState {
    float offset_x_px = 0.0F;
    float offset_y_px = 0.0F;
    float rotation_degrees = 0.0F;
    float scale = 1.0F;
    float opacity = 1.0F;
    bool visible = true;
};

struct AnimationNodeState {
    QString id;
    QString parent_id;
    float offset_x_px = 0.0F;
    float offset_y_px = 0.0F;
    float rotation_degrees = 0.0F;
    float scale = 1.0F;
    float opacity = 1.0F;
    bool visible = true;
};

struct AnimationFrameSample {
    int frame_index = 0;
    float time_seconds = 0.0F;
    float normalized_time = 0.0F;
    AnimationRootState root;
    std::vector<AnimationNodeState> nodes;
};

class AnimationCore final {
public:
    static constexpr const char* kVersion = "animation_core_4";

    static QString propertyId(AnimationProperty property);
    static QString interpolationId(AnimationInterpolation interpolation);
    static QString nodeVisualKindId(AnimationNodeVisualKind kind);

    static bool validate(const AnimatedAssetSpec& asset, QString* reason = nullptr);
    static bool validateClip(const AnimationClip& clip, QString* reason = nullptr);

    static float sampleTrack(const AnimationTrack& track, float time_seconds,
                             float duration_seconds, bool loop);

    // Legacy root-only sampler retained for callers that do not need a node tree.
    static AnimationFrameSample sampleFrame(const AnimationClip& clip, int frame_index);
    static AnimationFrameSample sampleFrame(const AnimatedAssetSpec& asset,
                                            const AnimationClip& clip,
                                            int frame_index);

    static const AnimationNodeSpec* findNode(const AnimatedAssetSpec& asset,
                                             const QString& node_id);
    static const AnimationNodeState* findNodeState(const AnimationFrameSample& sample,
                                                   const QString& node_id);

    static QJsonObject manifest(const AnimatedAssetSpec& asset);
    static QJsonObject clipManifest(const AnimationClip& clip);
    static QJsonObject nodeManifest(const AnimationNodeSpec& node);
};

} // namespace ch::studio
