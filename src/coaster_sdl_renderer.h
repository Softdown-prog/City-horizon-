#pragma once

#include "coaster_render_adapter.h"
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

// CH_COASTER_SDL_RENDERER_V3
// Final presentation bridge for the pre-rendered Flame atlas and the dedicated
// world-space coaster track. Simulation remains independent from SDL.
//
// CH_COASTER_TRACK_PRESENTATION_V2 keeps CH_COASTER_TRACK_GEOMETRY_V1 fully
// authoritative and improves only the screen-space material treatment. V2
// softens the high-contrast white rail look, adds a subtle outer fringe,
// strengthens the red spine's volume, reduces tie noise, and overlaps adjacent
// rail/spine segments enough to hide tiny wedge gaps on projected curves.
inline constexpr const char* kCoasterTrackPresentationContract =
    "CH_COASTER_TRACK_PRESENTATION_V2";

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
    fringe,
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
            return 4;
    }
    return 2;
}

[[nodiscard]] inline TrackPresentationPass presentation_pass_for_index(
    const TrackLineKind kind,
    const int pass_index) noexcept {
    if (kind == TrackLineKind::support || kind == TrackLineKind::tie) {
        return pass_index == 0 ? TrackPresentationPass::silhouette
                               : TrackPresentationPass::body;
    }
    switch (pass_index) {
        case 0: return TrackPresentationPass::fringe;
        case 1: return TrackPresentationPass::silhouette;
        case 2: return TrackPresentationPass::body;
        default: return TrackPresentationPass::highlight;
    }
}

[[nodiscard]] inline float presentation_line_width_px(
    const TrackLineKind kind,
    const TrackPresentationPass pass,
    const float scale) noexcept {
    switch (kind) {
        case TrackLineKind::support:
            return (pass == TrackPresentationPass::silhouette ? 3.15F : 1.70F) * scale;
        case TrackLineKind::spine:
            if (pass == TrackPresentationPass::fringe) return 9.20F * scale;
            if (pass == TrackPresentationPass::silhouette) return 7.90F * scale;
            if (pass == TrackPresentationPass::body) return 5.35F * scale;
            return std::max(0.70F, 0.88F * scale);
        case TrackLineKind::tie:
            return (pass == TrackPresentationPass::silhouette ? 3.25F : 1.70F) * scale;
        case TrackLineKind::left_rail:
        case TrackLineKind::right_rail:
            if (pass == TrackPresentationPass::fringe) return 5.35F * scale;
            if (pass == TrackPresentationPass::silhouette) return 4.35F * scale;
            if (pass == TrackPresentationPass::body) return 2.55F * scale;
            return std::max(0.52F, 0.64F * scale);
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
            if (pass == TrackPresentationPass::silhouette) return rgba(43.0F, 50.0F, 55.0F);
            return rgba(111.0F, 122.0F, 128.0F);
        case TrackLineKind::spine:
            if (pass == TrackPresentationPass::fringe) return rgba(38.0F, 16.0F, 17.0F, 0.22F);
            if (pass == TrackPresentationPass::silhouette) return rgba(65.0F, 22.0F, 21.0F);
            if (pass == TrackPresentationPass::body) return rgba(166.0F, 48.0F, 39.0F);
            return rgba(221.0F, 86.0F, 63.0F, 0.58F);
        case TrackLineKind::tie:
            if (pass == TrackPresentationPass::silhouette) return rgba(36.0F, 40.0F, 43.0F);
            return rgba(88.0F, 96.0F, 101.0F);
        case TrackLineKind::left_rail:
        case TrackLineKind::right_rail:
            if (pass == TrackPresentationPass::fringe) return rgba(31.0F, 37.0F, 41.0F, 0.18F);
            if (pass == TrackPresentationPass::silhouette) return rgba(57.0F, 65.0F, 70.0F);
            if (pass == TrackPresentationPass::body) return rgba(174.0F, 185.0F, 191.0F);
            return rgba(228.0F, 235.0F, 238.0F, 0.54F);
    }
    return rgba(255.0F, 255.0F, 255.0F);
}

[[nodiscard]] inline SDL_FPoint presentation_pass_offset(
    const TrackLineKind kind,
    const TrackPresentationPass pass,
    const float scale) noexcept {
    // The lower/right silhouette gives the member body depth. The restrained
    // upper highlight reads as steel specular response without becoming a
    // continuous white stripe at normal gameplay zoom.
    if (pass == TrackPresentationPass::silhouette &&
        (kind == TrackLineKind::spine ||
         kind == TrackLineKind::left_rail ||
         kind == TrackLineKind::right_rail)) {
        return {0.60F * scale, 0.88F * scale};
    }
    if (pass == TrackPresentationPass::highlight) {
        return {-0.16F * scale, -0.34F * scale};
    }
    return {0.0F, 0.0F};
}

[[nodiscard]] inline float presentation_cap_extension_px(
    const TrackLineKind kind,
    const TrackPresentationPass pass,
    const float width_px) noexcept {
    // Rails/spine are emitted as many adjacent geometry members. Slightly
    // extending the opaque body/silhouette hides wedge cracks at direction
    // changes while keeping the translucent highlight from forming bright beads.
    if (kind != TrackLineKind::spine &&
        kind != TrackLineKind::left_rail &&
        kind != TrackLineKind::right_rail) {
        return 0.0F;
    }
    if (pass == TrackPresentationPass::silhouette || pass == TrackPresentationPass::body) {
        return std::min(1.65F, width_px * 0.38F);
    }
    if (pass == TrackPresentationPass::fringe) {
        return std::min(0.90F, width_px * 0.16F);
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

// Draws the exact CH_COASTER_TRACK_GEOMETRY_V1 representation using the live
// CH_COASTER_TRACK_PRESENTATION_V2 material pass. The geometry remains shared
// with simulation/proof code; only final screen-space thickness, steel shading,
// red structural spine, and projected join cleanup live here.
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
    vertices.reserve(plan.lines.size() * 14U);
    indices.reserve(plan.lines.size() * 21U);

    for (const TrackLineRenderCommand& command : plan.lines) {
        const TrackScreenLine line = project_track_line(
            command, camera, viewport_width, viewport_height);
        const int pass_count = presentation_pass_count(line.kind);
        for (int pass_index = 0; pass_index < pass_count; ++pass_index) {
            const TrackPresentationPass pass = presentation_pass_for_index(line.kind, pass_index);
            const float width_px = presentation_line_width_px(line.kind, pass, scale);
            append_track_presentation_quad(
                vertices,
                indices,
                line,
                width_px,
                presentation_line_color(line.kind, pass),
                presentation_pass_offset(line.kind, pass, scale),
                presentation_cap_extension_px(line.kind, pass, width_px));
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
