#pragma once

#include "src/ch_render/animated_prop_catalog.h"

#include <algorithm>
#include <cmath>
#include <optional>

namespace ch {

struct AnimatedPropAtlasFrame {
    int index = 0;
    int column = 0;
    int row = 0;
};

struct AnimatedPropAtlasSourceRect {
    float x = 0.0F;
    float y = 0.0F;
    float width = 0.0F;
    float height = 0.0F;

    [[nodiscard]] bool valid() const noexcept { return width > 0.0F && height > 0.0F; }
};

[[nodiscard]] inline float normalized_prop_phase(float phase) noexcept {
    if (!std::isfinite(phase)) return 0.0F;
    phase -= std::floor(phase);
    return phase < 0.0F ? phase + 1.0F : phase;
}

[[nodiscard]] inline std::optional<AnimatedPropAtlasFrame> resolve_animated_prop_atlas_frame(
    const AnimatedPropAtlasDef& atlas,
    float phase
) noexcept {
    if (!atlas.valid()) return std::nullopt;

    phase += atlas.phase_offset;
    float normalized = 0.0F;
    if (atlas.loop) {
        normalized = normalized_prop_phase(phase);
    } else {
        if (!std::isfinite(phase)) phase = 0.0F;
        normalized = std::clamp(phase, 0.0F, 1.0F);
    }

    int frame_index = 0;
    if (!atlas.loop && normalized >= 1.0F) {
        frame_index = atlas.frame_count - 1;
    } else {
        frame_index = std::min(
            atlas.frame_count - 1,
            static_cast<int>(std::floor(normalized * static_cast<float>(atlas.frame_count))));
    }

    return AnimatedPropAtlasFrame{
        .index = frame_index,
        .column = frame_index % atlas.columns,
        .row = frame_index / atlas.columns,
    };
}

[[nodiscard]] inline std::optional<AnimatedPropAtlasSourceRect> animated_prop_atlas_source_rect(
    const AnimatedPropAtlasDef& atlas,
    const AnimatedPropAtlasFrame& frame,
    const float texture_width,
    const float texture_height
) noexcept {
    if (!atlas.valid() || texture_width <= 0.0F || texture_height <= 0.0F ||
        frame.index < 0 || frame.index >= atlas.frame_count ||
        frame.column < 0 || frame.column >= atlas.columns ||
        frame.row < 0 || frame.row >= atlas.rows) {
        return std::nullopt;
    }

    const float frame_width = texture_width / static_cast<float>(atlas.columns);
    const float frame_height = texture_height / static_cast<float>(atlas.rows);
    return AnimatedPropAtlasSourceRect{
        .x = static_cast<float>(frame.column) * frame_width,
        .y = static_cast<float>(frame.row) * frame_height,
        .width = frame_width,
        .height = frame_height,
    };
}

} // namespace ch
