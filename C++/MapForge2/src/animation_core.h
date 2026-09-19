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
    DrawOrder,
    VisualVariant,
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
    int visual_variant = 0;

    AnimationNodeVisualKind visual_kind = AnimationNodeVisualKind::None;
    QSizeF visual_size_px = QSizeF(24.0, 24.0);
    QColor fill_color = QColor("#d79b38");
    QColor outline_color = QColor("#2d3133");

    QString visual_asset_path;
    QRectF visual_source_rect_px;
    QString visual_library_id;

    bool visual_trim_transparent = true;
    bool visual_preserve_aspect = true;
    bool visual_smooth_scaling = true;

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
    int draw_order = 0;
    int visual_variant = 0;
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
    static constexpr const char* kVersion = "animation_core_5";

    static QString propertyId(AnimationProperty property);
    static QString interpolationId(AnimationInterpolation interpolation);
    static QString nodeVisualKindId(AnimationNodeVisualKind kind);

    static bool validate(const AnimatedAssetSpec& asset, QString* reason = nullptr);
    static bool validateClip(const AnimationClip& clip, QString* reason = nullptr);

    static float sampleTrack(const AnimationTrack& track, float time_seconds,
                             float duration_seconds, bool loop);

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
