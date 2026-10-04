#pragma once

#include "coaster_render_adapter.h"
#include "src/ch_render/map_renderer.h"

#include <SDL3/SDL.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <filesystem>
#include <functional>
#include <vector>

namespace ch::coaster {

// CH_COASTER_SDL_RENDERER_V2
// Final presentation bridge for the pre-rendered Flame atlas and the dedicated
// world-space coaster track. Simulation remains independent from SDL.
//
// CH_COASTER_TRACK_PRESENTATION_V1 promotes the approved V5.08 visual language
// into the live renderer. Geometry is still owned exclusively by
// CH_COASTER_TRACK_GEOMETRY_V1; this layer only gives those world-space members
// a stable 2.5D material treatment instead of reducing them to one-pixel debug
// lines.
inline constexpr const char* kCoasterTrackPresentationContract =
    "CH_COASTER_TRACK_PRESENTATION_V1";

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
    silhouette,
    body,
    highlight,
};

[[nodiscard]] inline float coaster_track_presentation_scale(
    const CameraState& camera) noexcept {
    // Width changes gently with zoom: track stays readable when zoomed out but
    // does not balloon into a flat ribbon at close zoom levels.
    return std::clamp(0.84F + std::max(0.0F, camera.zoom) * 0.16F, 0.82F, 1.28F);
}

[[nodiscard]] inline int presentation_pass_count(const TrackLineKind kind) noexcept {
    switch (kind) {
        case TrackLineKind::support:
        case TrackLineKind::tie:
            return 2;
        case TrackLineKind::spine:
        case TrackLineKind::left_rail:
        case TrackLineKind::right_rail:
            return 3;
    }
    return 2;
}

[[nodiscard]] inline float presentation_line_width_px(
    const TrackLineKind kind,
    const TrackPresentationPass pass,
    const float scale) noexcept {
    switch (kind) {
        case TrackLineKind::support:
            return (pass == TrackPresentationPass::silhouette ? 3.4F : 1.9F) * scale;
        case TrackLineKind::spine:
            if (pass == TrackPresentationPass::silhouette) return 8.0F * scale;
            if (pass == TrackPresentationPass::body) return 5.2F * scale;
            return std::max(1.0F, 1.25F * scale);
        case TrackLineKind::tie:
            return (pass == TrackPresentationPass::silhouette ? 4.2F : 2.35F) * scale;
        case TrackLineKind::left_rail:
        case TrackLineKind::right_rail:
            if (pass == TrackPresentationPass::silhouette) return 5.0F * scale;
            if (pass == TrackPresentationPass::body) return 3.0F * scale;
            return std::max(1.0F, 1.0F * scale);
    }
    return 1.0F;
}

[[nodiscard]] inline SDL_FColor presentation_line_color(
    const TrackLineKind kind,
    const TrackPresentationPass pass) noexcept {
    const auto rgba = [](const float r, const float g, const float b, const float a = 1.0F) {
        return SDL_FColor{r / 255.0F, g / 255.0F, b / 255.0F, a};
    };

    switch (kind) {
        case TrackLineKind::support:
            if (pass == TrackPresentationPass::silhouette) return rgba(47.0F, 56.0F, 61.0F);
            return rgba(121.0F, 132.0F, 138.0F);
        case TrackLineKind::spine:
            if (pass == TrackPresentationPass::silhouette) return rgba(70.0F, 24.0F, 22.0F);
            if (pass == TrackPresentationPass::body) return rgba(177.0F, 53.0F, 42.0F);
            return rgba(221.0F, 91.0F, 65.0F, 0.90F);
        case TrackLineKind::tie:
            if (pass == TrackPresentationPass::silhouette) return rgba(38.0F, 42.0F, 45.0F);
            return rgba(104.0F, 111.0F, 116.0F);
        case TrackLineKind::left_rail:
        case TrackLineKind::right_rail:
            if (pass == TrackPresentationPass::silhouette) return rgba(68.0F, 76.0F, 81.0F);
            if (pass == TrackPresentationPass::body) return rgba(214.0F, 221.0F, 225.0F);
            return rgba(250.0F, 251.0F, 252.0F, 0.92F);
    }
    return rgba(255.0F, 255.0F, 255.0F);
}

[[nodiscard]] inline SDL_FPoint presentation_pass_offset(
    const TrackLineKind kind,
    const TrackPresentationPass pass,
    const float scale) noexcept {
    // A tiny downward silhouette plus upper highlight is enough to turn the
    // projected members into readable 2.5D material without changing their
    // authoritative world-space position.
    if (pass == TrackPresentationPass::silhouette &&
        (kind == TrackLineKind::spine ||
         kind == TrackLineKind::left_rail ||
         kind == TrackLineKind::right_rail)) {
        return {0.65F * scale, 0.85F * scale};
    }
    if (pass == TrackPresentationPass::highlight) {
        return {-0.20F * scale, -0.45F * scale};
    }
    return {0.0F, 0.0F};
}

inline void append_track_presentation_quad(
    std::vector<SDL_Vertex>& vertices,
    std::vector<int>& indices,
    const TrackScreenLine& line,
    const float width_px,
    const SDL_FColor color,
    const SDL_FPoint offset) {
    const float ax = line.a.x + offset.x;
    const float ay = line.a.y + offset.y;
    const float bx = line.b.x + offset.x;
    const float by = line.b.y + offset.y;
    const float dx = bx - ax;
    const float dy = by - ay;
    const float length = std::hypot(dx, dy);
    if (!(length > 1.0e-4F) || !(width_px > 0.0F)) return;

    const float half_width = width_px * 0.5F;
    const float nx = -dy / length * half_width;
    const float ny = dx / length * half_width;
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

// Draws the exact CH_COASTER_TRACK_GEOMETRY_V1 representation using the live
// CH_COASTER_TRACK_PRESENTATION_V1 material pass. The geometry remains shared
// with simulation/proof code; only final screen-space thickness, steel shading
// and the red structural spine live here.
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

    const float scale = coaster_track_presentation_scale(camera);
    std::vector<SDL_Vertex> vertices;
    std::vector<int> indices;
    vertices.reserve(plan.lines.size() * 10U);
    indices.reserve(plan.lines.size() * 15U);

    for (const TrackLineRenderCommand& command : plan.lines) {
        const TrackScreenLine line = project_track_line(
            command, camera, viewport_width, viewport_height);
        const int pass_count = presentation_pass_count(line.kind);
        for (int pass_index = 0; pass_index < pass_count; ++pass_index) {
            const auto pass = static_cast<TrackPresentationPass>(pass_index);
            append_track_presentation_quad(
                vertices,
                indices,
                line,
                presentation_line_width_px(line.kind, pass, scale),
                presentation_line_color(line.kind, pass),
                presentation_pass_offset(line.kind, pass, scale));
        }
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
