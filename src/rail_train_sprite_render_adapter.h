#pragma once

#include "rail_live_operation_overlay.h"
#include "rail_articulated_consist.h"
#include "rail_train_direction_math.h"
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
    // Approved CH_CAMERA_V1 PNGs encode Blender views, not world-axis names.
    // +X moves screen-right/down (NORTH sprite), +Y screen-left/down (EAST).
    if (std::abs(view.x) >= std::abs(view.y))
        return view.x >= 0.0F ? View::north : View::south;
    return view.y >= 0.0F ? View::east : View::west;
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

// CH_RAIL_VISUAL_ALIGNMENT_V2: calibrated from the opaque (alpha >= 128)
 // extents of the eight approved 1024x1024 PNGs. Asset pixels are untouched.
 // Sizes correspond to actual 5.2m locomotive / 3.9m coach on the CH grid.
struct SpriteLayout {
    float canvas_size_px;
    float pivot_x_px;
    float pivot_y_px;
};
[[nodiscard]] inline constexpr SpriteLayout layout_for(
    const rail_operation::ConsistUnitKind kind, const View view) noexcept {
    if (kind == rail_operation::ConsistUnitKind::locomotive) {
        switch (view) {
            case View::south: return {385.0F, 475.0F, 755.0F};
            case View::east:  return {385.0F, 475.0F, 851.0F};
            case View::west:  return {385.0F, 549.0F, 811.0F};
            case View::north: return {385.0F, 549.0F, 844.0F};
        }
    }
    switch (view) {
        case View::south: return {300.0F, 512.0F, 872.0F};
        case View::north: return {300.0F, 512.0F, 872.0F};
        case View::east:  return {300.0F, 512.0F, 882.0F};
        case View::west:  return {300.0F, 512.0F, 882.0F};
    }
    return {300.0F, 512.0F, 872.0F};
}

// Only explicitly promoted diagonal sets can activate the eight-view mode.
// Existing original 4-view assets are the permanent safe fallback.
[[nodiscard]] inline bool diagonal_set_ready(rail_operation::ConsistUnitKind kind) {
    const auto valid = [](const char* role) {
        const auto dir = std::filesystem::path("assets/vehicles") /
            (std::string("steam_train_") + role + "_01");
        if (!std::filesystem::is_regular_file(dir / "steam_train_diagonal_runtime.json"))
            return false;
        for (const char* name : {"north_east","east_south","south_west","west_north"})
            if (!std::filesystem::is_regular_file(
                dir / (std::string("steam_train_") + role + "_" + name + ".png")))
                return false;
        return true;
    };
    static const bool locomotive = valid("locomotive");
    static const bool coach = valid("coach");
    return kind == rail_operation::ConsistUnitKind::locomotive ? locomotive : coach;
}

[[nodiscard]] inline SpriteLayout diagonal_layout(
    rail_operation::ConsistUnitKind kind, int direction_index) noexcept {
    if (kind == rail_operation::ConsistUnitKind::locomotive) {
        switch (direction_index) {
            case 1: return {385.0F,512.0F,848.0F};
            case 3: return {385.0F,475.0F,803.0F};
            case 5: return {385.0F,512.0F,783.0F};
            case 7: return {385.0F,549.0F,828.0F};
            default: break;
        }
    } else {
        return {300.0F,512.0F,877.0F};
    }
    return layout_for(kind, View::north);
}

[[nodiscard]] inline std::filesystem::path diagonal_sprite_path(
    rail_operation::ConsistUnitKind kind, int direction_index) {
    const char* role = kind == rail_operation::ConsistUnitKind::locomotive ? "locomotive" : "coach";
    return std::filesystem::path("assets/vehicles") /
        (std::string("steam_train_") + role + "_01") /
        (std::string("steam_train_") + role + "_" +
         rail_train_heading::label(direction_index) + ".png");
}

// Each unit can join the canonical world-depth queue alongside buildings,
// citizens and coaster cars. The renderer owns no images or GPU resources.
template <typename TextureProvider>
inline void render_unit(SDL_Renderer* renderer, const rail_operation::ArticulatedUnitPose& unit,
                        const CameraState& camera, const float viewport_width,
                        const float viewport_height, TextureProvider&& get_texture) {
    if (renderer == nullptr) return;
    const View fallback_view = select_view(unit.pose, camera);
    const int direction_index = rail_train_heading::octant(
        static_cast<float>(unit.pose.tangent_x),
        static_cast<float>(unit.pose.tangent_y), camera.rotation);
    SDL_Texture* texture = nullptr;
    SpriteLayout layout = layout_for(unit.kind, fallback_view);
    if (rail_train_heading::is_diagonal(direction_index) &&
        diagonal_set_ready(unit.kind)) {
        texture = get_texture(diagonal_sprite_path(unit.kind, direction_index));
        if (texture != nullptr) layout = diagonal_layout(unit.kind, direction_index);
    }
    if (texture == nullptr)
        texture = get_texture(sprite_path(unit.kind, fallback_view));
    if (texture == nullptr) return;
    const float scale = std::max(0.35F, camera.zoom) * layout.canvas_size_px;
    const ScreenPoint origin = world_to_screen_point(
        static_cast<float>(unit.pose.x), static_cast<float>(unit.pose.y),
        static_cast<float>(unit.pose.z), camera, viewport_width, viewport_height);
    const SDL_FRect dst{
        origin.x - scale * layout.pivot_x_px / 1024.0F,
        origin.y - scale * layout.pivot_y_px / 1024.0F,
        scale, scale};
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
