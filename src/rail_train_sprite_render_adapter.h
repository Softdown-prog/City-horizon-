#pragma once

#include "rail_live_operation_overlay.h"
#include "rail_articulated_consist.h"
#include "src/ch_core/projection.h"

#include <SDL3/SDL.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <filesystem>
#include <string>
#include <vector>

// CH_RAIL_TRAIN_VISUAL_V1
// Keep the existing CH Blender/approved PNG sprites; no procedural remodel.
// Every coach samples the authoritative centerline independently, so it turns
// at its own location rather than inheriting the engine's heading.
namespace ch::rail_train_visual {

enum class View : std::size_t { south = 0, west = 1, north = 2, east = 3 };

[[nodiscard]] inline View select_view(const rail_operation::TrainPose& pose,
                                      const CameraState& camera) noexcept {
    const WorldPoint view = camera_view_point(static_cast<float>(pose.tangent_x),
                                              static_cast<float>(pose.tangent_y),
                                              camera.rotation);
    if (std::abs(view.y) >= std::abs(view.x))
        return view.y >= 0.0F ? View::south : View::north;
    return view.x >= 0.0F ? View::east : View::west;
}

[[nodiscard]] inline std::filesystem::path sprite_path(
    const rail_operation::ConsistUnitKind kind, const View direction) {
    constexpr std::array<const char*, 4> names = {"south", "west", "north", "east"};
    const char* view = names[static_cast<std::size_t>(direction)];
    if (kind == rail_operation::ConsistUnitKind::locomotive)
        return std::filesystem::path("assets/vehicles/steam_train_locomotive_01") /
            (std::string("steam_train_locomotive_") + view + ".png");
    return std::filesystem::path("assets/vehicles/steam_train_coach_01") /
        (std::string("steam_train_coach_") + view + ".png");
}

// Each unit can join the canonical world-depth queue alongside buildings,
// citizens and coaster cars. The renderer owns no images or GPU resources.
template <typename TextureProvider>
inline void render_unit(SDL_Renderer* renderer, const rail_operation::ArticulatedUnitPose& unit,
                        const CameraState& camera, const float viewport_width,
                        const float viewport_height, TextureProvider&& get_texture) {
    if (renderer == nullptr) return;
    const bool is_engine = unit.kind == rail_operation::ConsistUnitKind::locomotive;
    SDL_Texture* texture = get_texture(sprite_path(unit.kind, select_view(unit.pose, camera)));
    if (texture == nullptr) return;
    const float scale = std::max(0.35F, camera.zoom) * (is_engine ? 260.0F : 215.0F);
    const float pivot_y = is_engine ? 678.0F : 732.0F;
    const ScreenPoint origin = world_to_screen_point(
        static_cast<float>(unit.pose.x), static_cast<float>(unit.pose.y),
        static_cast<float>(unit.pose.z), camera, viewport_width, viewport_height);
    const SDL_FRect dst{origin.x - scale * 0.5F, origin.y - scale * pivot_y / 1024.0F, scale, scale};
    if (dst.x + dst.w < -64.0F || dst.y + dst.h < -64.0F ||
        dst.x > viewport_width + 64.0F || dst.y > viewport_height + 64.0F) return;
    (void)SDL_RenderTexture(renderer, texture, nullptr, &dst);
}

// Texture provider uses the engine's existing cache; this adapter never owns,
// reallocates or destroys textures. Caller passes the asset-root-aware loader.
template <typename TextureProvider>
inline void render_articulated_train(
    SDL_Renderer* renderer,
    const rail_live_operation::LiveOperationController& operation,
    const CameraState& camera, const float viewport_width, const float viewport_height,
    TextureProvider&& get_texture) {
    if (renderer == nullptr || viewport_width <= 0.0F || viewport_height <= 0.0F) return;
    const auto* route = operation.operational_route();
    const auto lead = operation.train_pose();
    if (route == nullptr || !lead) return;
    auto units = rail_operation::build_articulated_consist_poses(*route, *lead);
    // Draw from the rear of the isometric contact plane forward. This preserves
    // train-car occlusion within the consist without changing the world queue.
    std::stable_sort(units.begin(), units.end(), [&](const auto& a, const auto& b) {
        return camera_depth_key(static_cast<float>(a.pose.x), static_cast<float>(a.pose.y), camera) <
               camera_depth_key(static_cast<float>(b.pose.x), static_cast<float>(b.pose.y), camera);
    });
    for (const auto& unit : units) {
        render_unit(renderer, unit, camera, viewport_width, viewport_height, get_texture);
    }
}
} // namespace ch::rail_train_visual
