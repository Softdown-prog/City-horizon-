#pragma once

#include "coaster_render_adapter.h"
#include "src/ch_render/map_renderer.h"

#include <SDL3/SDL.h>

#include <algorithm>
#include <array>
#include <cstddef>
#include <filesystem>
#include <functional>
#include <vector>

namespace ch::coaster {

// CH_COASTER_SDL_RENDERER_V1
// Final presentation bridge for the pre-rendered Flame atlas and the dedicated
// world-space coaster track. Simulation remains independent from SDL.
struct CarSpriteGeometry {
    ScreenPoint screen_anchor{};
    SDL_FRect source{};
    SDL_FRect destination{};
    float depth_key = 0.0F;
    std::size_t car_index = 0U;
};

[[nodiscard]] inline CarSpriteGeometry build_car_sprite_geometry(
    const CarRenderCommand& command,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height,
    const float sprite_scale = 1.0F) noexcept {
    CarSpriteGeometry geometry;
    geometry.screen_anchor = project_car_anchor(
        command, camera, viewport_width, viewport_height);
    geometry.depth_key = command.depth_key;
    geometry.car_index = command.car_index;

    geometry.source = {
        static_cast<float>(command.source_rect.x),
        static_cast<float>(command.source_rect.y),
        static_cast<float>(command.source_rect.width),
        static_cast<float>(command.source_rect.height),
    };

    const float safe_scale = std::max(0.0F, sprite_scale) * std::max(0.0F, camera.zoom);
    const float width = static_cast<float>(command.source_rect.width) * safe_scale;
    const float height = static_cast<float>(command.source_rect.height) * safe_scale;
    geometry.destination = {
        geometry.screen_anchor.x - width * kFlameCarSpriteAnchorX,
        geometry.screen_anchor.y - height * kFlameCarSpriteAnchorY,
        width,
        height,
    };
    return geometry;
}

[[nodiscard]] inline std::array<std::size_t, kCoasterTrainCarCount> coaster_draw_order(
    const TrainRenderPlan& plan) noexcept {
    std::array<std::size_t, kCoasterTrainCarCount> order{};
    for (std::size_t i = 0; i < order.size(); ++i) order[i] = i;
    std::stable_sort(order.begin(), order.begin() + static_cast<std::ptrdiff_t>(plan.car_count),
        [&plan](const std::size_t lhs, const std::size_t rhs) {
            const CarRenderCommand& left = plan.cars[lhs];
            const CarRenderCommand& right = plan.cars[rhs];
            if (left.depth_key != right.depth_key) return left.depth_key < right.depth_key;
            return left.car_index < right.car_index;
        });
    return order;
}

[[nodiscard]] inline int track_line_layer(const TrackLineKind kind) noexcept {
    switch (kind) {
        case TrackLineKind::support: return 0;
        case TrackLineKind::spine: return 1;
        case TrackLineKind::tie: return 2;
        case TrackLineKind::left_rail:
        case TrackLineKind::right_rail: return 3;
    }
    return 0;
}

inline void set_track_line_color(SDL_Renderer* renderer, const TrackLineKind kind) {
    switch (kind) {
        case TrackLineKind::support:
            SDL_SetRenderDrawColor(renderer, 102, 111, 116, 255);
            break;
        case TrackLineKind::spine:
            SDL_SetRenderDrawColor(renderer, 151, 47, 39, 255);
            break;
        case TrackLineKind::tie:
            SDL_SetRenderDrawColor(renderer, 61, 61, 63, 255);
            break;
        case TrackLineKind::left_rail:
        case TrackLineKind::right_rail:
            SDL_SetRenderDrawColor(renderer, 226, 230, 232, 255);
            break;
    }
}

// Draws the exact CH_COASTER_TRACK_GEOMETRY_V1 representation. The same world
// points can therefore be consumed by the game and proof renderers without
// falling back to the railway max-grade contract or a screen-space mock track.
inline void render_coaster_track(
    SDL_Renderer* renderer,
    const CoasterTrackGeometry& geometry,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height) {
    if (renderer == nullptr || !geometry.valid()) return;

    TrackRenderPlan plan = build_track_render_plan(geometry, camera);
    std::stable_sort(plan.lines.begin(), plan.lines.end(),
        [](const TrackLineRenderCommand& left, const TrackLineRenderCommand& right) {
            if (left.depth_key != right.depth_key) return left.depth_key < right.depth_key;
            return track_line_layer(left.kind) < track_line_layer(right.kind);
        });

    SDL_SetRenderDrawBlendMode(renderer, SDL_BLENDMODE_BLEND);
    for (const TrackLineRenderCommand& command : plan.lines) {
        const TrackScreenLine line = project_track_line(
            command, camera, viewport_width, viewport_height);
        set_track_line_color(renderer, line.kind);
        SDL_RenderLine(renderer, line.a.x, line.a.y, line.b.x, line.b.y);
    }
}

inline void render_flame_train(
    SDL_Renderer* renderer,
    const TrainStepResult& train,
    const std::function<const TextureAsset*(const std::filesystem::path&)>& find_texture,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height,
    const float sprite_scale = 1.0F) {
    if (renderer == nullptr || !train.valid) return;

    const TrainRenderPlan plan = build_train_render_plan(train, camera);
    if (plan.car_count == 0U) return;

    const TextureAsset* atlas = find_texture(std::filesystem::path(kFlameCarPoseAtlasPath));
    if (atlas == nullptr || atlas->texture == nullptr) return;

    SDL_Texture* texture = atlas->texture;
    SDL_SetTextureAlphaMod(texture, SDL_ALPHA_OPAQUE);
    SDL_SetTextureColorMod(texture, 255, 255, 255);

    const auto order = coaster_draw_order(plan);
    for (std::size_t draw_index = 0; draw_index < plan.car_count; ++draw_index) {
        const CarRenderCommand& command = plan.cars[order[draw_index]];
        const CarSpriteGeometry geometry = build_car_sprite_geometry(
            command, camera, viewport_width, viewport_height, sprite_scale);
        if (geometry.destination.w <= 0.0F || geometry.destination.h <= 0.0F) continue;
        SDL_RenderTexture(renderer, texture, &geometry.source, &geometry.destination);
    }

    SDL_SetTextureColorMod(texture, 255, 255, 255);
    SDL_SetTextureAlphaMod(texture, SDL_ALPHA_OPAQUE);
}

}  // namespace ch::coaster
