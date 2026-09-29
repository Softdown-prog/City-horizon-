#pragma once

#include <SDL3/SDL.h>

#include <algorithm>
#include <array>
#include <cstddef>

namespace ch::ui {

struct NineSliceInsets {
    float left = 0.0F;
    float top = 0.0F;
    float right = 0.0F;
    float bottom = 0.0F;
};

// Canonical City Horizon resizable-window contract. New instruction, help,
// information, alert and standard modal screens should reference this contract
// instead of hard-coding the physical PNG name or border values.
inline constexpr const char* kWindowFrameV2ContractId = "CH_WINDOW_FRAME_V2";
inline constexpr const char* kWindowFrameV2AssetStem = "panel_window_9slice_v2";
inline constexpr NineSliceInsets kWindowFrameV2Insets = {
    32.0F,
    32.0F,
    32.0F,
    32.0F,
};
inline constexpr float kWindowFrameV2MinimumWidth =
    kWindowFrameV2Insets.left + kWindowFrameV2Insets.right;
inline constexpr float kWindowFrameV2MinimumHeight =
    kWindowFrameV2Insets.top + kWindowFrameV2Insets.bottom;

enum class NineSlicePatch : std::size_t {
    top_left = 0,
    top,
    top_right,
    left,
    center,
    right,
    bottom_left,
    bottom,
    bottom_right,
};

struct NineSliceRegion {
    SDL_FRect source{};
    SDL_FRect destination{};

    [[nodiscard]] bool drawable() const {
        return source.w > 0.0F && source.h > 0.0F &&
               destination.w > 0.0F && destination.h > 0.0F;
    }
};

using NineSliceRegions = std::array<NineSliceRegion, 9>;

namespace detail {

inline void clamp_pair_to_extent(float& leading, float& trailing, const float extent) {
    leading = std::max(0.0F, leading);
    trailing = std::max(0.0F, trailing);
    if (extent <= 0.0F) {
        leading = 0.0F;
        trailing = 0.0F;
        return;
    }

    const float total = leading + trailing;
    if (total <= extent || total <= 0.0F) return;

    const float scale = extent / total;
    leading *= scale;
    trailing *= scale;
}

}  // namespace detail

[[nodiscard]] inline NineSliceRegions make_nine_slice_regions(
    const float source_width,
    const float source_height,
    const SDL_FRect& destination,
    NineSliceInsets insets) {
    NineSliceRegions regions{};
    if (source_width <= 0.0F || source_height <= 0.0F ||
        destination.w <= 0.0F || destination.h <= 0.0F) {
        return regions;
    }

    detail::clamp_pair_to_extent(insets.left, insets.right, source_width);
    detail::clamp_pair_to_extent(insets.top, insets.bottom, source_height);

    float destination_left = insets.left;
    float destination_right = insets.right;
    float destination_top = insets.top;
    float destination_bottom = insets.bottom;
    detail::clamp_pair_to_extent(destination_left, destination_right, destination.w);
    detail::clamp_pair_to_extent(destination_top, destination_bottom, destination.h);

    const std::array<float, 4> source_x = {
        0.0F,
        insets.left,
        source_width - insets.right,
        source_width,
    };
    const std::array<float, 4> source_y = {
        0.0F,
        insets.top,
        source_height - insets.bottom,
        source_height,
    };
    const std::array<float, 4> destination_x = {
        destination.x,
        destination.x + destination_left,
        destination.x + destination.w - destination_right,
        destination.x + destination.w,
    };
    const std::array<float, 4> destination_y = {
        destination.y,
        destination.y + destination_top,
        destination.y + destination.h - destination_bottom,
        destination.y + destination.h,
    };

    std::size_t patch = 0;
    for (std::size_t row = 0; row < 3; ++row) {
        for (std::size_t column = 0; column < 3; ++column) {
            regions[patch++] = {
                {
                    source_x[column],
                    source_y[row],
                    source_x[column + 1] - source_x[column],
                    source_y[row + 1] - source_y[row],
                },
                {
                    destination_x[column],
                    destination_y[row],
                    destination_x[column + 1] - destination_x[column],
                    destination_y[row + 1] - destination_y[row],
                },
            };
        }
    }

    return regions;
}

[[nodiscard]] inline bool render_nine_slice(
    SDL_Renderer* renderer,
    SDL_Texture* texture,
    const float texture_width,
    const float texture_height,
    const SDL_FRect& destination,
    const NineSliceInsets insets) {
    if (renderer == nullptr || texture == nullptr) return false;

    const NineSliceRegions regions = make_nine_slice_regions(
        texture_width, texture_height, destination, insets);

    bool ok = true;
    bool rendered_any = false;
    for (const NineSliceRegion& region : regions) {
        if (!region.drawable()) continue;
        rendered_any = true;
        ok = SDL_RenderTexture(renderer, texture, &region.source, &region.destination) && ok;
    }
    return rendered_any && ok;
}

}  // namespace ch::ui
