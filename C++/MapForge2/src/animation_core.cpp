#include "animation_core.h"

#include <QJsonArray>

#include <algorithm>
#include <cmath>

namespace ch::studio {
namespace {

float normalizedLoopTime(const float time_seconds, const float duration_seconds, const bool loop) {
    if (duration_seconds <= 0.0F) return 0.0F;
    if (!loop) return std::clamp(time_seconds, 0.0F, duration_seconds);
    float wrapped = std::fmod(time_seconds, duration_seconds);
    if (wrapped < 0.0F) wrapped += duration_seconds;
    return wrapped;
}

float interpolateValue(const float a, const float b, const float t,
                       const AnimationInterpolation interpolation) {
    const float clamped = std::clamp(t, 0.0F, 1.0F);
    float shaped = clamped;
    switch (interpolation) {
        case AnimationInterpolation::Step:
            shaped = 0.0F;
            break;
        case AnimationInterpolation::Linear:
            break;
        case AnimationInterpolation::SmoothStep:
            shaped = clamped * clamped * (3.0F - 2.0F * clamped);
            break;
        case AnimationInterpolation::Sine:
            shaped = 0.5F - 0.5F * std::cos(clamped * 3.14159265358979323846F);
            break;
    }
    return a + (b - a) * shaped;
}

bool loopEndpointsEquivalent(const AnimationTrack& track) {
    if (track.keyframes.empty()) return true;
    const float first = track.keyframes.front().value;
    const float last = track.keyframes.back().value;
    if (track.property == AnimationProperty::RotationDegrees) {
        float delta = std::fmod(last - first, 360.0F);
        if (delta < 0.0F) delta += 360.0F;
        return std::min(delta, 360.0F - delta) <= 0.0001F;
    }
    return std::abs(first - last) <= 0.0001F;
}

QJsonObject keyframeJson(const AnimationKeyframe& key) {
    return QJsonObject{
        {"timeSeconds", static_cast<double>(key.time_seconds)},
        {"value", static_cast<double>(key.value)},
    };
}

} // namespace

QString AnimationCore::propertyId(const AnimationProperty property) {
    switch (property) {
        case AnimationProperty::OffsetX: return QStringLiteral("offset_x_px");
        case AnimationProperty::OffsetY: return QStringLiteral("offset_y_px");
        case AnimationProperty::RotationDegrees: return QStringLiteral("rotation_degrees");
        case AnimationProperty::Scale: return QStringLiteral("scale");
        case AnimationProperty::Opacity: return QStringLiteral("opacity");
        case AnimationProperty::Visibility: return QStringLiteral("visibility");
    }
    return QStringLiteral("offset_x_px");
}

QString AnimationCore::interpolationId(const AnimationInterpolation interpolation) {
    switch (interpolation) {
        case AnimationInterpolation::Step: return QStringLiteral("step");
        case AnimationInterpolation::Linear: return QStringLiteral("linear");
        case AnimationInterpolation::SmoothStep: return QStringLiteral("smooth_step");
        case AnimationInterpolation::Sine: return QStringLiteral("sine");
    }
    return QStringLiteral("linear");
}

bool AnimationCore::validateClip(const AnimationClip& clip, QString* reason) {
    auto fail = [&](const QString& message) {
        if (reason) *reason = message;
        return false;
    };

    if (clip.id.trimmed().isEmpty()) return fail(QStringLiteral("clip id is empty"));
    if (!(clip.duration_seconds > 0.0F)) return fail(QStringLiteral("clip duration must be greater than zero"));
    if (clip.frame_count < 2 || clip.frame_count > 240)
        return fail(QStringLiteral("clip frame count must be between 2 and 240"));

    for (const AnimationTrack& track : clip.tracks) {
        if (track.target_id.trimmed().isEmpty()) return fail(QStringLiteral("animation track target is empty"));
        if (track.keyframes.empty()) return fail(QStringLiteral("animation track has no keyframes"));

        float previous = -1.0F;
        for (const AnimationKeyframe& key : track.keyframes) {
            if (key.time_seconds < 0.0F || key.time_seconds > clip.duration_seconds)
                return fail(QStringLiteral("animation keyframe is outside clip duration"));
            if (key.time_seconds < previous)
                return fail(QStringLiteral("animation keyframes must be sorted by time"));
            previous = key.time_seconds;
        }

        if (clip.loop && track.keyframes.size() > 1) {
            if (std::abs(track.keyframes.front().time_seconds) > 0.0001F
                || std::abs(track.keyframes.back().time_seconds - clip.duration_seconds) > 0.0001F) {
                return fail(QStringLiteral("looping tracks must include keyframes at 0 and clip duration"));
            }
            if (!loopEndpointsEquivalent(track)) {
                return fail(QStringLiteral("looping track endpoints must represent the same state"));
            }
        }
    }

    if (reason) reason->clear();
    return true;
}

bool AnimationCore::validate(const AnimatedAssetSpec& asset, QString* reason) {
    auto fail = [&](const QString& message) {
        if (reason) *reason = message;
        return false;
    };

    if (asset.asset_id.trimmed().isEmpty()) return fail(QStringLiteral("asset id is empty"));
    if (asset.category.trimmed().isEmpty()) return fail(QStringLiteral("asset category is empty"));
    if (asset.frame_size.width() < 32 || asset.frame_size.height() < 32)
        return fail(QStringLiteral("animation frame size is too small"));
    if (asset.anchor_normalized.x() < 0.0 || asset.anchor_normalized.x() > 1.0
        || asset.anchor_normalized.y() < 0.0 || asset.anchor_normalized.y() > 1.0)
        return fail(QStringLiteral("animation anchor must remain inside normalized frame bounds"));
    if (asset.clips.empty()) return fail(QStringLiteral("animated asset has no clips"));

    for (const AnimationClip& clip : asset.clips) {
        QString clip_reason;
        if (!validateClip(clip, &clip_reason))
            return fail(QStringLiteral("clip '%1': %2").arg(clip.id, clip_reason));
    }

    if (reason) reason->clear();
    return true;
}

float AnimationCore::sampleTrack(const AnimationTrack& track, const float time_seconds,
                                 const float duration_seconds, const bool loop) {
    if (track.keyframes.empty()) return 0.0F;
    if (track.keyframes.size() == 1) return track.keyframes.front().value;

    const float t = normalizedLoopTime(time_seconds, duration_seconds, loop);
    if (t <= track.keyframes.front().time_seconds) return track.keyframes.front().value;
    if (t >= track.keyframes.back().time_seconds) return track.keyframes.back().value;

    for (std::size_t i = 1; i < track.keyframes.size(); ++i) {
        const AnimationKeyframe& next = track.keyframes[i];
        if (t > next.time_seconds) continue;
        const AnimationKeyframe& previous = track.keyframes[i - 1];
        const float span = std::max(0.0001F, next.time_seconds - previous.time_seconds);
        const float local_t = (t - previous.time_seconds) / span;
        return interpolateValue(previous.value, next.value, local_t, track.interpolation);
    }

    return track.keyframes.back().value;
}

AnimationFrameSample AnimationCore::sampleFrame(const AnimationClip& clip, const int frame_index) {
    AnimationFrameSample sample;
    const int frame_count = std::max(2, clip.frame_count);
    sample.frame_index = std::clamp(frame_index, 0, frame_count - 1);

    // Loop clips intentionally omit the duplicated end frame. Non-loop clips include it.
    const float denominator = clip.loop
        ? static_cast<float>(frame_count)
        : static_cast<float>(std::max(1, frame_count - 1));
    sample.normalized_time = static_cast<float>(sample.frame_index) / denominator;
    sample.time_seconds = sample.normalized_time * std::max(0.0001F, clip.duration_seconds);

    for (const AnimationTrack& track : clip.tracks) {
        if (track.target_id != QStringLiteral("root")) continue;
        const float value = sampleTrack(track, sample.time_seconds, clip.duration_seconds, clip.loop);
        switch (track.property) {
            case AnimationProperty::OffsetX: sample.root.offset_x_px = value; break;
            case AnimationProperty::OffsetY: sample.root.offset_y_px = value; break;
            case AnimationProperty::RotationDegrees: sample.root.rotation_degrees = value; break;
            case AnimationProperty::Scale: sample.root.scale = std::max(0.01F, value); break;
            case AnimationProperty::Opacity: sample.root.opacity = std::clamp(value, 0.0F, 1.0F); break;
            case AnimationProperty::Visibility: sample.root.visible = value >= 0.5F; break;
        }
    }

    return sample;
}

QJsonObject AnimationCore::clipManifest(const AnimationClip& clip) {
    QJsonArray tracks;
    for (const AnimationTrack& track : clip.tracks) {
        QJsonArray keys;
        for (const AnimationKeyframe& key : track.keyframes) keys.append(keyframeJson(key));
        tracks.append(QJsonObject{
            {"targetId", track.target_id},
            {"property", propertyId(track.property)},
            {"interpolation", interpolationId(track.interpolation)},
            {"keyframes", keys},
        });
    }

    return QJsonObject{
        {"id", clip.id},
        {"name", clip.name},
        {"durationSeconds", static_cast<double>(clip.duration_seconds)},
        {"frameCount", clip.frame_count},
        {"loop", clip.loop},
        {"tracks", tracks},
    };
}

QJsonObject AnimationCore::manifest(const AnimatedAssetSpec& asset) {
    QJsonArray clips;
    for (const AnimationClip& clip : asset.clips) clips.append(clipManifest(clip));

    QString reason;
    const bool valid = validate(asset, &reason);
    return QJsonObject{
        {"version", QString::fromLatin1(kVersion)},
        {"assetId", asset.asset_id},
        {"category", asset.category},
        {"paletteProfile", asset.palette_profile},
        {"frameSize", QJsonObject{{"width", asset.frame_size.width()}, {"height", asset.frame_size.height()}}},
        {"anchorNormalized", QJsonObject{{"x", asset.anchor_normalized.x()}, {"y", asset.anchor_normalized.y()}}},
        {"view", BuildingComposer::viewName(asset.view)},
        {"deterministic", true},
        {"stableAnchorAcrossFrames", true},
        {"loopRotationTreatsFullTurnsAsEquivalent", true},
        {"loopClipsDoNotDuplicateEndFrame", true},
        {"baseRenderable", QStringLiteral("BuildingComposerSpec")},
        {"clips", clips},
        {"valid", valid},
        {"validationReason", reason},
    };
}

} // namespace ch::studio
