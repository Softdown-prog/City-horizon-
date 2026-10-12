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
#include <limits>
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

// V2 diagonal source was framed at 1.28x the cardinal orthographic scale.
// The extra canvas margin must be compensated when rendering, otherwise cars
// suddenly shrink when turning. Pivots are measured directly from CH Blender V2's review metadata
// (512,641 locomotive / 512,684 coach), not guessed from older assets.
inline constexpr float kRailDiagonalV2FramingRatio = 1.28F;
[[nodiscard]] inline constexpr SpriteLayout diagonal_layout(
    rail_operation::ConsistUnitKind kind, int /*direction_index*/) noexcept {
    if (kind == rail_operation::ConsistUnitKind::locomotive)
        return {385.0F * kRailDiagonalV2FramingRatio,512.0F,641.0F};
    return {300.0F * kRailDiagonalV2FramingRatio,512.0F,684.0F};
}

[[nodiscard]] inline std::filesystem::path diagonal_sprite_path(
    rail_operation::ConsistUnitKind kind, int direction_index) {
    const char* role = kind == rail_operation::ConsistUnitKind::locomotive ? "locomotive" : "coach";
    return std::filesystem::path("assets/vehicles") /
        (std::string("steam_train_") + role + "_01") /
        (std::string("steam_train_") + role + "_" +
         rail_train_heading::label(direction_index) + ".png");
}

// Couplers follow the actual front/rear chassis ends rather than connecting
// centre anchors. Paint first, beneath coach sprites, with a bright metal edge.
inline void render_coupler_between(
    SDL_Renderer* renderer, const rail_operation::ArticulatedUnitPose& leading,
    const rail_operation::ArticulatedUnitPose& following,
    const CameraState& camera, float viewport_width, float viewport_height) {
    // Choose the closest CHASSIS ends, not a hardcoded leading/rear label.
    // A run-around returns with wagon 7 nearest the west-facing locomotive,
    // while each coach keeps its original physical heading (+track tangent).
    const double left_length=leading.kind==rail_operation::ConsistUnitKind::locomotive?5.2:3.9;
    const double right_length=following.kind==rail_operation::ConsistUnitKind::locomotive?5.2:3.9;
    constexpr float kCouplerElevation=0.22F;
    auto endpoint=[](const rail_operation::TrainPose& pose,double length,int side){
        return std::array<double,3>{
            pose.x+pose.tangent_x*length*0.5*side,
            pose.y+pose.tangent_y*length*0.5*side,
            pose.z+pose.tangent_z*length*0.5*side};
    };
    std::array<double,3> first{},second{};
    double best=std::numeric_limits<double>::infinity();
    for(const int i:{-1,1})for(const int j:{-1,1}){
        const auto l=endpoint(leading.pose,left_length,i);
        const auto r=endpoint(following.pose,right_length,j);
        const double dx=l[0]-r[0],dy=l[1]-r[1],dz=l[2]-r[2];
        const double d=dx*dx+dy*dy+dz*dz;
        if(d<best){best=d;first=l;second=r;}
    }
    if(!(best<4.0))return; // Coupled stock only; no across-yard links.
    const ScreenPoint a=world_to_screen_point(
        static_cast<float>(first[0]),static_cast<float>(first[1]),
        static_cast<float>(first[2])+kCouplerElevation,
        camera,viewport_width,viewport_height);
    const ScreenPoint b=world_to_screen_point(
        static_cast<float>(second[0]),static_cast<float>(second[1]),
        static_cast<float>(second[2])+kCouplerElevation,
        camera,viewport_width,viewport_height);
    Uint8 old_r=255,old_g=255,old_b=255,old_a=255;
    (void)SDL_GetRenderDrawColor(renderer,&old_r,&old_g,&old_b,&old_a);
    (void)SDL_SetRenderDrawColor(renderer,48,43,36,255);
    (void)SDL_RenderLine(renderer,a.x,a.y+1.0F,b.x,b.y+1.0F);
    (void)SDL_SetRenderDrawColor(renderer,170,154,125,255);
    (void)SDL_RenderLine(renderer,a.x,a.y,b.x,b.y);
    (void)SDL_SetRenderDrawColor(renderer,old_r,old_g,old_b,old_a);
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
    auto units = operation.articulated_poses();
    if (units.empty()) return;
    // Connect adjacent cars before sorting, so links appear beneath chassis.
    for (std::size_t i=1U;i<units.size();++i) {
        // Never draw a giant elastic coupling from the parked coaches to
        // their detached locomotive on the passing siding.
        if (operation.shunting_locomotive() && i==1U) continue;
        // Unit adjacency is determined by physical return order from the
        // controller. Indices intentionally remain stable wagon identities.
        render_coupler_between(renderer,units[i-1U],units[i],camera,
                               viewport_width,viewport_height);
    }
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
