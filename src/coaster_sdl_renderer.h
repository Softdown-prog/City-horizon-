#pragma once

#include "coaster_render_adapter.h"
#include "coaster_track_skin.h"
#include "src/ch_render/map_renderer.h"

#include <SDL3/SDL.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <functional>
#include <string>
#include <unordered_map>
#include <vector>

namespace ch::coaster {

// CH_COASTER_SDL_RENDERER_V4
// Hybrid presentation bridge: CH_COASTER_TRACK_GEOMETRY_V1 remains the
// authoritative procedural track, while CH_COASTER_TRACK_SKIN_V1 supplies an
// independent visual skin. Changing skin never changes route/physics/gauge.
inline constexpr const char* kCoasterTrackPresentationContract =
    "CH_COASTER_TRACK_PRESENTATION_V3";

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

enum class TrackPresentationPass : std::uint8_t {
    shadow,
    side,
    body,
    cap,
};

[[nodiscard]] inline float coaster_track_presentation_scale(
    const CameraState& camera) noexcept {
    return std::clamp(0.84F + std::max(0.0F, camera.zoom) * 0.16F, 0.82F, 1.28F);
}

[[nodiscard]] inline SDL_FColor skin_color(const CoasterSkinColor color) noexcept {
    return SDL_FColor{color.r, color.g, color.b, color.a};
}

[[nodiscard]] inline int presentation_pass_count(const TrackLineKind kind) noexcept {
    switch (kind) {
        case TrackLineKind::support:
        case TrackLineKind::tie:
            return 2;
        case TrackLineKind::spine:
        case TrackLineKind::left_rail:
        case TrackLineKind::right_rail:
            return 4;
    }
    return 2;
}

[[nodiscard]] inline TrackPresentationPass presentation_pass_for_index(
    const TrackLineKind kind,
    const int pass_index) noexcept {
    if (kind == TrackLineKind::support || kind == TrackLineKind::tie) {
        return pass_index == 0 ? TrackPresentationPass::shadow
                               : TrackPresentationPass::body;
    }
    switch (pass_index) {
        case 0: return TrackPresentationPass::shadow;
        case 1: return TrackPresentationPass::side;
        case 2: return TrackPresentationPass::body;
        default: return TrackPresentationPass::cap;
    }
}

[[nodiscard]] inline float presentation_line_width_px(
    const TrackLineKind kind,
    const TrackPresentationPass pass,
    const float scale,
    const CoasterTrackSkin& skin) noexcept {
    float width = 1.0F;
    switch (kind) {
        case TrackLineKind::support:
            width = pass == TrackPresentationPass::shadow
                ? skin.support_shadow_width_px : skin.support_body_width_px;
            break;
        case TrackLineKind::spine:
            if (pass == TrackPresentationPass::shadow) width = skin.spine_shadow_width_px;
            else if (pass == TrackPresentationPass::side) width = skin.spine_side_width_px;
            else if (pass == TrackPresentationPass::body) width = skin.spine_body_width_px;
            else width = skin.spine_cap_width_px;
            break;
        case TrackLineKind::tie:
            width = pass == TrackPresentationPass::shadow
                ? skin.tie_shadow_width_px : skin.tie_body_width_px;
            break;
        case TrackLineKind::left_rail:
        case TrackLineKind::right_rail:
            if (pass == TrackPresentationPass::shadow) width = skin.rail_shadow_width_px;
            else if (pass == TrackPresentationPass::side) width = skin.rail_side_width_px;
            else if (pass == TrackPresentationPass::body) width = skin.rail_body_width_px;
            else width = skin.rail_head_width_px;
            break;
    }
    return std::max(0.35F, width * scale);
}

[[nodiscard]] inline SDL_FColor presentation_line_color(
    const TrackLineKind kind,
    const TrackPresentationPass pass,
    const CoasterTrackSkin& skin) noexcept {
    switch (kind) {
        case TrackLineKind::support:
            return skin_color(pass == TrackPresentationPass::shadow
                ? skin.support_shadow : skin.support_body);
        case TrackLineKind::spine:
            if (pass == TrackPresentationPass::shadow) return skin_color(skin.spine_shadow);
            if (pass == TrackPresentationPass::side) return skin_color(skin.spine_side);
            if (pass == TrackPresentationPass::body) return skin_color(skin.spine_body);
            return skin_color(skin.spine_cap);
        case TrackLineKind::tie:
            return skin_color(pass == TrackPresentationPass::shadow
                ? skin.tie_shadow : skin.tie_body);
        case TrackLineKind::left_rail:
        case TrackLineKind::right_rail:
            if (pass == TrackPresentationPass::shadow) return skin_color(skin.rail_shadow);
            if (pass == TrackPresentationPass::side) return skin_color(skin.rail_side);
            if (pass == TrackPresentationPass::body) return skin_color(skin.rail_body);
            return skin_color(skin.rail_head);
    }
    return SDL_FColor{1.0F, 1.0F, 1.0F, 1.0F};
}

[[nodiscard]] inline SDL_FPoint presentation_pass_offset(
    const TrackLineKind kind,
    const TrackPresentationPass pass,
    const float scale,
    const CoasterTrackSkin& skin) noexcept {
    if (pass == TrackPresentationPass::side &&
        (kind == TrackLineKind::spine ||
         kind == TrackLineKind::left_rail ||
         kind == TrackLineKind::right_rail)) {
        return {skin.side_offset_x_px * scale, skin.side_offset_y_px * scale};
    }
    if (pass == TrackPresentationPass::cap &&
        (kind == TrackLineKind::spine ||
         kind == TrackLineKind::left_rail ||
         kind == TrackLineKind::right_rail)) {
        return {skin.cap_offset_x_px * scale, skin.cap_offset_y_px * scale};
    }
    return {0.0F, 0.0F};
}

[[nodiscard]] inline float presentation_cap_extension_px(
    const TrackLineKind kind,
    const TrackPresentationPass pass,
    const float width_px) noexcept {
    if (kind != TrackLineKind::spine &&
        kind != TrackLineKind::left_rail &&
        kind != TrackLineKind::right_rail) {
        return 0.0F;
    }
    if (pass == TrackPresentationPass::side || pass == TrackPresentationPass::body) {
        return std::min(1.75F, width_px * 0.40F);
    }
    if (pass == TrackPresentationPass::shadow) {
        return std::min(1.05F, width_px * 0.18F);
    }
    return 0.0F;
}

inline void append_track_presentation_quad(
    std::vector<SDL_Vertex>& vertices,
    std::vector<int>& indices,
    const TrackScreenLine& line,
    const float width_px,
    const SDL_FColor color,
    const SDL_FPoint offset,
    const float cap_extension_px) {
    float ax = line.a.x + offset.x;
    float ay = line.a.y + offset.y;
    float bx = line.b.x + offset.x;
    float by = line.b.y + offset.y;
    const float dx = bx - ax;
    const float dy = by - ay;
    const float length = std::hypot(dx, dy);
    if (!(length > 1.0e-4F) || !(width_px > 0.0F)) return;

    const float ux = dx / length;
    const float uy = dy / length;
    const float extension = std::max(0.0F, cap_extension_px);
    ax -= ux * extension;
    ay -= uy * extension;
    bx += ux * extension;
    by += uy * extension;

    const float half_width = width_px * 0.5F;
    const float nx = -uy * half_width;
    const float ny = ux * half_width;
    const int base = static_cast<int>(vertices.size());

    SDL_Vertex v0{};
    v0.position = {ax + nx, ay + ny};
    v0.color = color;
    v0.tex_coord = {0.0F, 0.0F};
    SDL_Vertex v1{};
    v1.position = {ax - nx, ay - ny};
    v1.color = color;
    v1.tex_coord = {0.0F, 0.0F};
    SDL_Vertex v2{};
    v2.position = {bx - nx, by - ny};
    v2.color = color;
    v2.tex_coord = {0.0F, 0.0F};
    SDL_Vertex v3{};
    v3.position = {bx + nx, by + ny};
    v3.color = color;
    v3.tex_coord = {0.0F, 0.0F};
    vertices.push_back(v0);
    vertices.push_back(v1);
    vertices.push_back(v2);
    vertices.push_back(v3);

    indices.push_back(base + 0);
    indices.push_back(base + 1);
    indices.push_back(base + 2);
    indices.push_back(base + 0);
    indices.push_back(base + 2);
    indices.push_back(base + 3);
}

// Base + skin are intentionally kept distinct even though they share one SDL
// geometry batch. The base owns depth/readability; the skin owns appearance.
// Future Blender-baked plates/caps can be added after this vector skin pass.
inline void append_track_structural_base(
    std::vector<SDL_Vertex>& vertices,
    std::vector<int>& indices,
    const TrackScreenLine& line,
    const float scale,
    const CoasterTrackSkin& skin) {
    const TrackPresentationPass pass = TrackPresentationPass::shadow;
    const float width_px = presentation_line_width_px(line.kind, pass, scale, skin);
    append_track_presentation_quad(
        vertices, indices, line, width_px,
        presentation_line_color(line.kind, pass, skin),
        presentation_pass_offset(line.kind, pass, scale, skin),
        presentation_cap_extension_px(line.kind, pass, width_px));
}

inline void append_track_skin_overlay(
    std::vector<SDL_Vertex>& vertices,
    std::vector<int>& indices,
    const TrackScreenLine& line,
    const float scale,
    const CoasterTrackSkin& skin) {
    const int pass_count = presentation_pass_count(line.kind);
    for (int pass_index = 1; pass_index < pass_count; ++pass_index) {
        const TrackPresentationPass pass = presentation_pass_for_index(line.kind, pass_index);
        const float width_px = presentation_line_width_px(line.kind, pass, scale, skin);
        append_track_presentation_quad(
            vertices, indices, line, width_px,
            presentation_line_color(line.kind, pass, skin),
            presentation_pass_offset(line.kind, pass, scale, skin),
            presentation_cap_extension_px(line.kind, pass, width_px));
    }
}

enum class CoasterSkinOverlayModule : std::uint8_t {
    joint_plate = 0,
    chain_lift = 1,
    brake_fin = 2,
};

struct CoasterSkinOverlayDraw {
    SDL_FRect source{};
    SDL_FRect destination{};
    float depth_key = 0.0F;
};

[[nodiscard]] inline SDL_Texture* coaster_skin_overlay_texture(
    SDL_Renderer* renderer,
    const CoasterTrackSkin& skin) {
    if (renderer == nullptr || !skin.overlay_atlas_enabled || skin.overlay_atlas_path.empty()) {
        return nullptr;
    }
    static std::unordered_map<SDL_Renderer*, SDL_Texture*> cache;
    if (const auto found = cache.find(renderer); found != cache.end()) return found->second;

    const std::string path{skin.overlay_atlas_path};
    SDL_Surface* surface = SDL_LoadPNG(path.c_str());
    if (surface == nullptr) return nullptr;  // Vector skin remains the safe fallback.
    SDL_Texture* texture = SDL_CreateTextureFromSurface(renderer, surface);
    SDL_DestroySurface(surface);
    if (texture == nullptr) return nullptr;
    SDL_SetTextureBlendMode(texture, SDL_BLENDMODE_BLEND);
    SDL_SetTextureScaleMode(texture, SDL_SCALEMODE_LINEAR);
    cache.emplace(renderer, texture);
    return texture;
}

[[nodiscard]] inline int coaster_overlay_direction_column(
    const CoasterTrackGeometry& geometry,
    const std::size_t index,
    const CameraState& camera) noexcept {
    if (geometry.frames.size() < 2U) return 0;
    const std::size_t count = geometry.frames.size();
    const std::size_t prev = index == 0U ? (geometry.closed ? count - 1U : 0U) : index - 1U;
    const std::size_t next = index + 1U < count ? index + 1U : (geometry.closed ? 0U : count - 1U);
    const auto& a = geometry.frames[prev].center;
    const auto& b = geometry.frames[next].center;
    const double angle = std::atan2(b.y - a.y, b.x - a.x);
    constexpr double kHalfPi = 1.57079632679489661923;
    int quarter_turns = static_cast<int>(std::lround(angle / kHalfPi));
    quarter_turns = (quarter_turns % 4 + 4) % 4;
    const int camera_turns = static_cast<int>(camera.rotation) & 3;
    const int visual_turns = (quarter_turns - camera_turns + 4) % 4;
    // Atlas order follows CH Blender DIRECTIONS: SOUTH, EAST, WEST, NORTH.
    switch (visual_turns) {
        case 0: return 0;
        case 1: return 1;
        case 2: return 3;
        default: return 2;
    }
}

struct CoasterTrackBodyDraw {
    SDL_Texture* texture = nullptr;
    SDL_FRect destination{};
    float depth_key = 0.0F;
};

[[nodiscard]] inline SDL_Texture* coaster_track_body_texture(
    SDL_Renderer* renderer,
    const CoasterTrackSkin& skin,
    const int direction_index) {
    if (renderer == nullptr || !skin.body_sprite_enabled ||
        direction_index < 0 || direction_index >= static_cast<int>(skin.body_sprite_paths.size())) {
        return nullptr;
    }
    const std::string path{skin.body_sprite_paths[static_cast<std::size_t>(direction_index)]};
    if (path.empty()) return nullptr;

    static std::unordered_map<SDL_Renderer*, std::unordered_map<std::string, SDL_Texture*>> cache;
    auto& renderer_cache = cache[renderer];
    if (const auto found = renderer_cache.find(path); found != renderer_cache.end()) {
        return found->second;
    }

    SDL_Surface* surface = SDL_LoadPNG(path.c_str());
    if (surface == nullptr) {
        renderer_cache.emplace(path, nullptr);
        return nullptr;  // Procedural track remains visible as the fallback.
    }
    SDL_Texture* texture = SDL_CreateTextureFromSurface(renderer, surface);
    SDL_DestroySurface(surface);
    if (texture != nullptr) {
        SDL_SetTextureBlendMode(texture, SDL_BLENDMODE_BLEND);
        SDL_SetTextureScaleMode(texture, SDL_SCALEMODE_LINEAR);
    }
    renderer_cache.emplace(path, texture);
    return texture;
}

inline void append_coaster_track_body_draw(
    std::vector<CoasterTrackBodyDraw>& draws,
    SDL_Renderer* renderer,
    const CoasterTrackGeometry& geometry,
    const std::size_t frame_index,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height,
    const CoasterTrackSkin& skin) {
    if (frame_index >= geometry.frames.size()) return;
    const int direction_index = coaster_overlay_direction_column(geometry, frame_index, camera);
    SDL_Texture* texture = coaster_track_body_texture(renderer, skin, direction_index);
    if (texture == nullptr) return;

    const auto& frame = geometry.frames[frame_index];
    const WorldPoint3 anchor_world = coaster_meters_to_world(
        frame.center.x,
        frame.center.y,
        frame.center.z - skin.body_ground_below_center_m);
    const ScreenPoint anchor = world_to_screen_point(
        anchor_world, camera, viewport_width, viewport_height);
    const float sprite_scale = std::max(
        0.0F, skin.body_sprite_scale_at_zoom1 * std::max(0.0F, camera.zoom));
    const float width = static_cast<float>(skin.body_sprite_width_px) * sprite_scale;
    const float height = static_cast<float>(skin.body_sprite_height_px) * sprite_scale;
    if (!(width > 0.0F) || !(height > 0.0F)) return;

    CoasterTrackBodyDraw draw;
    draw.texture = texture;
    draw.destination = {
        anchor.x - width * skin.body_sprite_anchor_x,
        anchor.y - height * skin.body_sprite_anchor_y,
        width,
        height,
    };
    draw.depth_key = camera_depth_key(anchor_world.x, anchor_world.y, camera);
    draws.push_back(draw);
}

inline void render_coaster_track_body_skin(
    SDL_Renderer* renderer,
    const CoasterTrackGeometry& geometry,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height,
    const CoasterTrackSkin& skin) {
    if (renderer == nullptr || !skin.body_sprite_enabled || geometry.frames.empty() ||
        !(skin.body_sprite_spacing_m > 0.0) || !(geometry.route_length_m > 0.0)) {
        return;
    }

    std::vector<CoasterTrackBodyDraw> draws;
    const std::size_t estimated = static_cast<std::size_t>(
        std::ceil(geometry.route_length_m / skin.body_sprite_spacing_m)) + 1U;
    draws.reserve(estimated);

    std::size_t cursor = 0U;
    std::size_t last_index = geometry.frames.size();
    const double end_distance = geometry.closed
        ? std::max(0.0, geometry.route_length_m - skin.body_sprite_spacing_m * 0.25)
        : geometry.route_length_m;
    for (double target = 0.0; target <= end_distance + 1.0e-6;
         target += skin.body_sprite_spacing_m) {
        while (cursor + 1U < geometry.frames.size() &&
               std::abs(geometry.frames[cursor + 1U].distance_m - target) <=
               std::abs(geometry.frames[cursor].distance_m - target)) {
            ++cursor;
        }
        if (cursor == last_index) continue;
        append_coaster_track_body_draw(
            draws, renderer, geometry, cursor, camera,
            viewport_width, viewport_height, skin);
        last_index = cursor;
    }

    std::stable_sort(draws.begin(), draws.end(), [](const auto& left, const auto& right) {
        return left.depth_key < right.depth_key;
    });
    for (const auto& draw : draws) {
        SDL_SetTextureColorMod(draw.texture, 255, 255, 255);
        SDL_SetTextureAlphaMod(draw.texture, SDL_ALPHA_OPAQUE);
        SDL_RenderTexture(renderer, draw.texture, nullptr, &draw.destination);
    }
}

[[nodiscard]] inline int coaster_overlay_module_row(const CoasterSkinOverlayModule module) noexcept {
    return static_cast<int>(module);
}

inline void append_coaster_overlay_draw(
    std::vector<CoasterSkinOverlayDraw>& draws,
    const CoasterTrackGeometry& geometry,
    const std::size_t frame_index,
    const CoasterSkinOverlayModule module,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height,
    const CoasterTrackSkin& skin) {
    const auto& frame = geometry.frames[frame_index];
    const WorldPoint3 world = coaster_track_world_point(frame.center);
    const ScreenPoint anchor = world_to_screen_point(
        world, camera, viewport_width, viewport_height);
    const int column = coaster_overlay_direction_column(geometry, frame_index, camera);
    const int row = coaster_overlay_module_row(module);
    const float sprite_scale = std::max(0.05F, skin.overlay_sprite_scale * std::max(0.0F, camera.zoom));
    const float width = static_cast<float>(skin.overlay_cell_width_px) * sprite_scale;
    const float height = static_cast<float>(skin.overlay_cell_height_px) * sprite_scale;

    CoasterSkinOverlayDraw draw;
    draw.source = {
        static_cast<float>(column * skin.overlay_cell_width_px),
        static_cast<float>(row * skin.overlay_cell_height_px),
        static_cast<float>(skin.overlay_cell_width_px),
        static_cast<float>(skin.overlay_cell_height_px),
    };
    draw.destination = {
        anchor.x - width * 0.5F,
        anchor.y - height * 0.5F,
        width,
        height,
    };
    draw.depth_key = camera_depth_key(world.x, world.y, camera);
    draws.push_back(draw);
}

inline void render_coaster_track_overlay_modules(
    SDL_Renderer* renderer,
    const CoasterTrackGeometry& geometry,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height,
    const CoasterTrackSkin& skin) {
    SDL_Texture* atlas = coaster_skin_overlay_texture(renderer, skin);
    if (atlas == nullptr || geometry.frames.empty()) return;

    std::vector<CoasterSkinOverlayDraw> draws;
    draws.reserve(geometry.frames.size() / 8U + 32U);
    double last_joint = -1.0e9;
    double last_lift = -1.0e9;
    double last_brake = -1.0e9;

    for (std::size_t i = 0; i < geometry.frames.size(); ++i) {
        const auto& frame = geometry.frames[i];
        if (frame.drive_mode == DriveMode::Lift) {
            if (frame.distance_m - last_lift >= skin.chain_lift_spacing_m) {
                append_coaster_overlay_draw(draws, geometry, i, CoasterSkinOverlayModule::chain_lift,
                                            camera, viewport_width, viewport_height, skin);
                last_lift = frame.distance_m;
            }
            continue;
        }
        if (frame.drive_mode == DriveMode::Brake) {
            if (frame.distance_m - last_brake >= skin.brake_fin_spacing_m) {
                append_coaster_overlay_draw(draws, geometry, i, CoasterSkinOverlayModule::brake_fin,
                                            camera, viewport_width, viewport_height, skin);
                last_brake = frame.distance_m;
            }
            continue;
        }
        if (frame.distance_m - last_joint >= skin.joint_plate_spacing_m) {
            append_coaster_overlay_draw(draws, geometry, i, CoasterSkinOverlayModule::joint_plate,
                                        camera, viewport_width, viewport_height, skin);
            last_joint = frame.distance_m;
        }
    }

    std::stable_sort(draws.begin(), draws.end(), [](const auto& left, const auto& right) {
        return left.depth_key < right.depth_key;
    });
    SDL_SetTextureColorMod(atlas, 255, 255, 255);
    SDL_SetTextureAlphaMod(atlas, SDL_ALPHA_OPAQUE);
    for (const auto& draw : draws) {
        SDL_RenderTexture(renderer, atlas, &draw.source, &draw.destination);
    }
}

// Hybrid track renderer. The procedural geometry underneath is the only source
// of truth; Classic Steel 01 is merely a replaceable visual skin on top.
inline void render_coaster_track(
    SDL_Renderer* renderer,
    const CoasterTrackGeometry& geometry,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height,
    const CoasterTrackSkin& skin = default_coaster_track_skin()) {
    if (renderer == nullptr || !geometry.valid()) return;

    TrackRenderPlan plan = build_track_render_plan(geometry, camera);
    std::stable_sort(plan.lines.begin(), plan.lines.end(),
        [](const TrackLineRenderCommand& left, const TrackLineRenderCommand& right) {
            if (left.depth_key != right.depth_key) return left.depth_key < right.depth_key;
            return track_line_layer(left.kind) < track_line_layer(right.kind);
        });

    const float scale = coaster_track_presentation_scale(camera);
    std::vector<SDL_Vertex> vertices;
    std::vector<int> indices;
    vertices.reserve(plan.lines.size() * 14U);
    indices.reserve(plan.lines.size() * 21U);

    for (const TrackLineRenderCommand& command : plan.lines) {
        const TrackScreenLine line = project_track_line(
            command, camera, viewport_width, viewport_height);
        append_track_structural_base(vertices, indices, line, scale, skin);
        append_track_skin_overlay(vertices, indices, line, scale, skin);
    }

    if (vertices.empty() || indices.empty()) return;
    SDL_SetRenderDrawBlendMode(renderer, SDL_BLENDMODE_BLEND);
    SDL_RenderGeometry(
        renderer,
        nullptr,
        vertices.data(),
        static_cast<int>(vertices.size()),
        indices.data(),
        static_cast<int>(indices.size()));
    // Full Blender body is presentation-only. The procedural geometry above
    // remains authoritative and doubles as the safe fallback when a PNG is absent.
    render_coaster_track_body_skin(
        renderer, geometry, camera, viewport_width, viewport_height, skin);
    render_coaster_track_overlay_modules(
        renderer, geometry, camera, viewport_width, viewport_height, skin);
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
