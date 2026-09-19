#pragma once

#include "building_composer.h"

#include <QJsonObject>
#include <QPointF>
#include <QSize>
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

struct AnimatedAssetSpec {
    QString asset_id = QStringLiteral("animated_building");
    QString category = QStringLiteral("building");
    QString palette_profile = QStringLiteral("city_horizon_classic_tycoon");
    QSize frame_size = QSize(420, 420);
    QPointF anchor_normalized = QPointF(0.50, 0.90);
    BuildingView view = BuildingView::South;
    BuildingComposerSpec base_building;
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

struct AnimationFrameSample {
    int frame_index = 0;
    float time_seconds = 0.0F;
    float normalized_time = 0.0F;
    AnimationRootState root;
};

class AnimationCore final {
public:
    static constexpr const char* kVersion = "animation_core_1";

    static QString propertyId(AnimationProperty property);
    static QString interpolationId(AnimationInterpolation interpolation);

    static bool validate(const AnimatedAssetSpec& asset, QString* reason = nullptr);
    static bool validateClip(const AnimationClip& clip, QString* reason = nullptr);

    static float sampleTrack(const AnimationTrack& track, float time_seconds,
                             float duration_seconds, bool loop);
    static AnimationFrameSample sampleFrame(const AnimationClip& clip, int frame_index);

    static QJsonObject manifest(const AnimatedAssetSpec& asset);
    static QJsonObject clipManifest(const AnimationClip& clip);
};

} // namespace ch::studio
