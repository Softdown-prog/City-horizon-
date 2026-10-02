#pragma once

#include "coaster_render_adapter.h"
#include "src/ch_render/map_renderer.h"

#include <SDL3/SDL.h>

#include <algorithm>
#include <array>
#include <cstddef>
#include <filesystem>
#include <functional>

namespace ch::coaster {

// CH_COASTER_SDL_RENDERER_V1
// Final presentation bridge for the pre-rendered Flame atlas. The simulation
// remains entirely independent from SDL; this layer only resolves one texture,
// projects each car anchor and submits source/destination rectangles.
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
        SDL_RenderTexture(texture ? renderer : nullptr, texture, &geometry.source, &geometry.destination);
    }

    SDL_SetTextureColorMod(texture, 255, 255, 255);
    SDL_SetTextureAlphaMod(texture, SDL_ALPHA_OPAQUE);
}

}  // namespace ch::coaster
