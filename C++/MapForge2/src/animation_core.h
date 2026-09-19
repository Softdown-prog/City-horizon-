#pragma once

#include "building_composer.h"

#include <QColor>
#include <QJsonObject>
#include <QPointF>
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

    // The visual payload is intentionally simple in Animation Core 2. It gives
    // the hierarchy a concrete deterministic QA renderer without coupling the
    // data model to future carousel/person/animal asset formats.
    AnimationNodeVisualKind visual_kind = AnimationNodeVisualKind::None;
    QSizeF visual_size_px = QSizeF(24.0, 24.0);
    QColor fill_color = QColor("#d79b38");
    QColor outline_color = QColor("#2d3133");
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
    static constexpr const char* kVersion = "animation_core_2";

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
