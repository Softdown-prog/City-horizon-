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

bool isNormalizedPoint(const QPointF& point) {
    return point.x() >= 0.0 && point.x() <= 1.0
        && point.y() >= 0.0 && point.y() <= 1.0;
}

bool hasNodeId(const AnimatedAssetSpec& asset, const QString& id) {
    return AnimationCore::findNode(asset, id) != nullptr;
}

void applyProperty(AnimationRootState& state, const AnimationProperty property, const float value) {
    switch (property) {
        case AnimationProperty::OffsetX: state.offset_x_px = value; break;
        case AnimationProperty::OffsetY: state.offset_y_px = value; break;
        case AnimationProperty::RotationDegrees: state.rotation_degrees = value; break;
        case AnimationProperty::Scale: state.scale = std::max(0.01F, value); break;
        case AnimationProperty::Opacity: state.opacity = std::clamp(value, 0.0F, 1.0F); break;
        case AnimationProperty::Visibility: state.visible = value >= 0.5F; break;
    }
}

void applyProperty(AnimationNodeState& state, const AnimationNodeSpec& node,
                   const AnimationProperty property, const float value) {
    switch (property) {
        case AnimationProperty::OffsetX: state.offset_x_px = value; break;
        case AnimationProperty::OffsetY: state.offset_y_px = value; break;
        case AnimationProperty::RotationDegrees: state.rotation_degrees = node.rotation_degrees + value; break;
        case AnimationProperty::Scale: state.scale = std::max(0.01F, node.scale * value); break;
        case AnimationProperty::Opacity: state.opacity = std::clamp(node.opacity * value, 0.0F, 1.0F); break;
        case AnimationProperty::Visibility: state.visible = node.visible && value >= 0.5F; break;
    }
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

QString AnimationCore::nodeVisualKindId(const AnimationNodeVisualKind kind) {
    switch (kind) {
        case AnimationNodeVisualKind::None: return QStringLiteral("none");
        case AnimationNodeVisualKind::PrimitiveRectangle: return QStringLiteral("primitive_rectangle");
        case AnimationNodeVisualKind::PrimitiveEllipse: return QStringLiteral("primitive_ellipse");
        case AnimationNodeVisualKind::RasterSprite: return QStringLiteral("raster_sprite");
        case AnimationNodeVisualKind::BuildingRender: return QStringLiteral("building_render");
    }
    return QStringLiteral("none");
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

    for (std::size_t track_index = 0; track_index < clip.tracks.size(); ++track_index) {
        const AnimationTrack& track = clip.tracks[track_index];
        if (track.target_id.trimmed().isEmpty()) return fail(QStringLiteral("animation track target is empty"));
        if (track.keyframes.empty()) return fail(QStringLiteral("animation track has no keyframes"));

        for (std::size_t other = track_index + 1; other < clip.tracks.size(); ++other) {
            if (track.target_id == clip.tracks[other].target_id
                && track.property == clip.tracks[other].property) {
                return fail(QStringLiteral("duplicate track property '%1' for target '%2'")
                                .arg(propertyId(track.property), track.target_id));
            }
        }

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
    if (!isNormalizedPoint(asset.anchor_normalized))
        return fail(QStringLiteral("animation anchor must remain inside normalized frame bounds"));

    for (std::size_t index = 0; index < asset.nodes.size(); ++index) {
        const AnimationNodeSpec& node = asset.nodes[index];
        if (node.id.trimmed().isEmpty()) return fail(QStringLiteral("animation node id is empty"));
        if (node.id == QStringLiteral("root")) return fail(QStringLiteral("'root' is reserved and cannot be used as a node id"));
        if (node.parent_id.trimmed().isEmpty()) return fail(QStringLiteral("animation node parent id is empty"));
        if (node.parent_id == node.id) return fail(QStringLiteral("animation node cannot parent itself: %1").arg(node.id));
        if (!isNormalizedPoint(node.pivot_normalized))
            return fail(QStringLiteral("animation node '%1' pivot must be normalized inside 0..1").arg(node.id));
        if (!(node.scale > 0.0F)) return fail(QStringLiteral("animation node '%1' scale must be positive").arg(node.id));
        if (node.opacity < 0.0F || node.opacity > 1.0F)
            return fail(QStringLiteral("animation node '%1' opacity must be inside 0..1").arg(node.id));
        if (node.visual_kind != AnimationNodeVisualKind::None
            && (node.visual_size_px.width() <= 0.0 || node.visual_size_px.height() <= 0.0)) {
            return fail(QStringLiteral("animation node '%1' visual size must be positive").arg(node.id));
        }
        if (node.visual_kind == AnimationNodeVisualKind::RasterSprite
            && node.visual_asset_path.trimmed().isEmpty()) {
            return fail(QStringLiteral("animation node '%1' raster source path is empty").arg(node.id));
        }
        if (!node.visual_source_rect_px.isNull()
            && (node.visual_source_rect_px.x() < 0.0 || node.visual_source_rect_px.y() < 0.0
                || node.visual_source_rect_px.width() <= 0.0
                || node.visual_source_rect_px.height() <= 0.0)) {
            return fail(QStringLiteral("animation node '%1' source rect is invalid").arg(node.id));
        }

        for (std::size_t other = index + 1; other < asset.nodes.size(); ++other) {
            if (node.id == asset.nodes[other].id)
                return fail(QStringLiteral("duplicate animation node id: %1").arg(node.id));
        }
        if (node.parent_id != QStringLiteral("root") && !hasNodeId(asset, node.parent_id))
            return fail(QStringLiteral("animation node '%1' references missing parent '%2'")
                            .arg(node.id, node.parent_id));
    }

    // Parent traversal is deliberately iterative and bounded. A chain longer
    // than the number of authored nodes can only exist if the hierarchy cycles.
    for (const AnimationNodeSpec& node : asset.nodes) {
        QString parent = node.parent_id;
        std::size_t hops = 0;
        while (parent != QStringLiteral("root")) {
            const AnimationNodeSpec* parent_node = findNode(asset, parent);
            if (!parent_node)
                return fail(QStringLiteral("animation hierarchy contains a missing parent"));
            parent = parent_node->parent_id;
            ++hops;
            if (hops > asset.nodes.size())
                return fail(QStringLiteral("animation node hierarchy contains a cycle"));
        }
    }

    if (asset.clips.empty()) return fail(QStringLiteral("animated asset has no clips"));
    for (const AnimationClip& clip : asset.clips) {
        QString clip_reason;
        if (!validateClip(clip, &clip_reason))
            return fail(QStringLiteral("clip '%1': %2").arg(clip.id, clip_reason));

        for (const AnimationTrack& track : clip.tracks) {
            if (track.target_id != QStringLiteral("root") && !hasNodeId(asset, track.target_id)) {
                return fail(QStringLiteral("clip '%1' targets unknown node '%2'")
                                .arg(clip.id, track.target_id));
            }
        }
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
    AnimatedAssetSpec root_only;
    root_only.clips = {clip};
    return sampleFrame(root_only, clip, frame_index);
}

AnimationFrameSample AnimationCore::sampleFrame(const AnimatedAssetSpec& asset,
                                                const AnimationClip& clip,
                                                const int frame_index) {
    AnimationFrameSample sample;
    const int frame_count = std::max(2, clip.frame_count);
    sample.frame_index = std::clamp(frame_index, 0, frame_count - 1);

    // Loop clips intentionally omit the duplicated end frame. Non-loop clips include it.
    const float denominator = clip.loop
        ? static_cast<float>(frame_count)
        : static_cast<float>(std::max(1, frame_count - 1));
    sample.normalized_time = static_cast<float>(sample.frame_index) / denominator;
    sample.time_seconds = sample.normalized_time * std::max(0.0001F, clip.duration_seconds);

    sample.nodes.reserve(asset.nodes.size());
    for (const AnimationNodeSpec& node : asset.nodes) {
        AnimationNodeState state;
        state.id = node.id;
        state.parent_id = node.parent_id;
        state.rotation_degrees = node.rotation_degrees;
        state.scale = node.scale;
        state.opacity = node.opacity;
        state.visible = node.visible;
        sample.nodes.push_back(state);
    }

    for (const AnimationTrack& track : clip.tracks) {
        const float value = sampleTrack(track, sample.time_seconds, clip.duration_seconds, clip.loop);
        if (track.target_id == QStringLiteral("root")) {
            applyProperty(sample.root, track.property, value);
            continue;
        }

        AnimationNodeState* state = nullptr;
        const AnimationNodeSpec* node = findNode(asset, track.target_id);
        if (!node) continue;
        for (AnimationNodeState& candidate : sample.nodes) {
            if (candidate.id == track.target_id) {
                state = &candidate;
                break;
            }
        }
        if (state) applyProperty(*state, *node, track.property, value);
    }

    return sample;
}

const AnimationNodeSpec* AnimationCore::findNode(const AnimatedAssetSpec& asset,
                                                 const QString& node_id) {
    for (const AnimationNodeSpec& node : asset.nodes) {
        if (node.id == node_id) return &node;
    }
    return nullptr;
}

const AnimationNodeState* AnimationCore::findNodeState(const AnimationFrameSample& sample,
                                                       const QString& node_id) {
    for (const AnimationNodeState& state : sample.nodes) {
        if (state.id == node_id) return &state;
    }
    return nullptr;
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

QJsonObject AnimationCore::nodeManifest(const AnimationNodeSpec& node) {
    QJsonObject visual{
        {"version", QStringLiteral("animation_visual_sources_1")},
        {"kind", nodeVisualKindId(node.visual_kind)},
        {"widthPx", node.visual_size_px.width()},
        {"heightPx", node.visual_size_px.height()},
        {"trimTransparent", node.visual_trim_transparent},
        {"preserveAspect", node.visual_preserve_aspect},
        {"smoothScaling", node.visual_smooth_scaling},
    };
    if (node.visual_kind == AnimationNodeVisualKind::RasterSprite) {
        visual.insert(QStringLiteral("assetPath"), node.visual_asset_path);
        if (!node.visual_source_rect_px.isNull() && !node.visual_source_rect_px.isEmpty()) {
            visual.insert(QStringLiteral("sourceRectPx"), QJsonObject{
                {"x", node.visual_source_rect_px.x()},
                {"y", node.visual_source_rect_px.y()},
                {"width", node.visual_source_rect_px.width()},
                {"height", node.visual_source_rect_px.height()},
            });
        }
    } else if (node.visual_kind == AnimationNodeVisualKind::BuildingRender) {
        visual.insert(QStringLiteral("view"), BuildingComposer::viewName(node.visual_building_view));
        visual.insert(QStringLiteral("visualPreset"), BuildingComposer::visualPresetId(node.visual_building.visual_preset));
        visual.insert(QStringLiteral("typology"), BuildingComposer::typologyId(node.visual_building.building_typology));
    } else if (node.visual_kind == AnimationNodeVisualKind::PrimitiveRectangle
               || node.visual_kind == AnimationNodeVisualKind::PrimitiveEllipse) {
        visual.insert(QStringLiteral("fill"), node.fill_color.name(QColor::HexArgb));
        visual.insert(QStringLiteral("outline"), node.outline_color.name(QColor::HexArgb));
        visual.insert(QStringLiteral("qaFallbackOnly"), true);
    }

    return QJsonObject{
        {"id", node.id},
        {"parentId", node.parent_id},
        {"positionPx", QJsonObject{{"x", node.position_px.x()}, {"y", node.position_px.y()}}},
        {"pivotNormalized", QJsonObject{{"x", node.pivot_normalized.x()}, {"y", node.pivot_normalized.y()}}},
        {"rotationDegrees", static_cast<double>(node.rotation_degrees)},
        {"scale", static_cast<double>(node.scale)},
        {"opacity", static_cast<double>(node.opacity)},
        {"visible", node.visible},
        {"drawOrder", node.draw_order},
        {"visual", visual},
    };
}

QJsonObject AnimationCore::manifest(const AnimatedAssetSpec& asset) {
    QJsonArray clips;
    for (const AnimationClip& clip : asset.clips) clips.append(clipManifest(clip));

    QJsonArray nodes;
    for (const AnimationNodeSpec& node : asset.nodes) nodes.append(nodeManifest(node));

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
        {"renderBaseBuilding", asset.render_base_building},
        {"baseRenderable", QStringLiteral("BuildingComposerSpec")},
        {"nodeHierarchyVersion", QStringLiteral("animation_node_hierarchy_1")},
        {"visualSourceVersion", QStringLiteral("animation_visual_sources_1")},
        {"visualSourceRoot", asset.visual_source_root},
        {"nodes", nodes},
        {"clips", clips},
        {"valid", valid},
        {"validationReason", reason},
    };
}

} // namespace ch::studio
