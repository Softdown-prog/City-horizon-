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
