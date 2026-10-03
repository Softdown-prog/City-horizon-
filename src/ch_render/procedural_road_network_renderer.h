#pragma once

#include "src/ch_core/projection.h"
#include "src/ch_core/terrain_projection.h"
#include "src/procedural_road_ground_render_plan.h"

#include <SDL3/SDL.h>

#include <cstddef>
#include <cstdint>
#include <limits>
#include <vector>

namespace ch {

// CH_PROCEDURAL_ROAD_2D_RENDER_V1
//
// The road network is submitted as flat XY triangles. Projection into the
// isometric camera happens only after the 2D road shape has been generated;
// there is no road Z coordinate, support geometry or 3D mesh in this path.
struct ProceduralRoad2DRenderStyle {
    SDL_FColor tint{52.0F / 255.0F, 57.0F / 255.0F, 60.0F / 255.0F, 1.0F};
    SDL_Texture* texture = nullptr;
};

[[nodiscard]] inline bool render_procedural_road_2d_mesh(
    SDL_Renderer* renderer,
    const ProceduralRoad2DMesh& mesh,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height,
    const ProceduralRoad2DRenderStyle& style = {},
    const TerrainHeightField* heightfield = nullptr) {
    if (renderer == nullptr || mesh.empty()) return true;
    if (mesh.vertices.size() > static_cast<std::size_t>(std::numeric_limits<int>::max()) ||
        mesh.indices.size() > static_cast<std::size_t>(std::numeric_limits<int>::max())) {
        return false;
    }

    std::vector<SDL_Vertex> vertices(mesh.vertices.size());
    for (std::size_t index = 0; index < mesh.vertices.size(); ++index) {
        const ProceduralRoad2DVertex& source = mesh.vertices[index];
        const ScreenPoint screen = heightfield != nullptr
            ? terrain_world_to_screen_point(source.position.x, source.position.y, *heightfield,
                                            camera, viewport_width, viewport_height)
            : world_to_screen_point(source.position.x, source.position.y,
                                    camera, viewport_width, viewport_height);
        vertices[index].position = {screen.x, screen.y};
        vertices[index].color = style.tint;
        vertices[index].tex_coord = {source.u, source.v};
    }

    std::vector<int> indices;
    indices.reserve(mesh.indices.size());
    for (const std::uint32_t index : mesh.indices) {
        if (index >= mesh.vertices.size() ||
            index > static_cast<std::uint32_t>(std::numeric_limits<int>::max())) {
            return false;
        }
        indices.push_back(static_cast<int>(index));
    }

    return SDL_RenderGeometry(renderer, style.texture,
                              vertices.data(), static_cast<int>(vertices.size()),
                              indices.data(), static_cast<int>(indices.size()));
}

// Runtime equivalent of the proof's dashed center marking. The marking is
// derived from the same visual spline as the asphalt ribbon and deliberately
// stops before degree-3/4 conflict areas, so a tee/cross does not receive lines
// through its central junction patch. Sampling is visual-only and never changes
// RoadManager topology, traffic or save data.
[[nodiscard]] inline bool render_procedural_road_center_markings(
    SDL_Renderer* renderer,
    const ProceduralRoadGraph& graph,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height,
    const TerrainHeightField* heightfield = nullptr) {
    if (renderer == nullptr) return false;

    Uint8 old_r = 0;
    Uint8 old_g = 0;
    Uint8 old_b = 0;
    Uint8 old_a = 0;
    (void)SDL_GetRenderDrawColor(renderer, &old_r, &old_g, &old_b, &old_a);
    (void)SDL_SetRenderDrawColor(renderer, 236, 221, 159, 220);

    constexpr float kJunctionGapT = 0.34F;
    constexpr int kSamples = 24;
    constexpr int kDashSamples = 3;
    constexpr int kGapSamples = 2;
    constexpr int kPatternSamples = kDashSamples + kGapSamples;

    bool ok = true;
    for (const ProceduralRoadGraphSegment& graph_segment : graph.segments()) {
        const auto spline = procedural_road_visual_spline_2d(graph, graph_segment.id);
        if (!spline || !procedural_road_spline_is_ground_only(*spline)) continue;

        float begin_t = 0.0F;
        float end_t = 1.0F;
        if (graph.degree(graph_segment.start_node) >= 3U) begin_t = kJunctionGapT;
        if (graph.degree(graph_segment.end_node) >= 3U) end_t = 1.0F - kJunctionGapT;
        if (begin_t >= end_t) continue;

        for (int sample = 0; sample < kSamples; ++sample) {
            if ((sample % kPatternSamples) >= kDashSamples) continue;
            const float alpha_a = static_cast<float>(sample) / static_cast<float>(kSamples);
            const float alpha_b = static_cast<float>(sample + 1) / static_cast<float>(kSamples);
            const float t_a = begin_t + (end_t - begin_t) * alpha_a;
            const float t_b = begin_t + (end_t - begin_t) * alpha_b;
            const ProceduralRoad2DPoint point_a = procedural_road_sample_cubic_2d(*spline, t_a);
            const ProceduralRoad2DPoint point_b = procedural_road_sample_cubic_2d(*spline, t_b);
            const ScreenPoint screen_a = heightfield != nullptr
                ? terrain_world_to_screen_point(point_a.x, point_a.y, *heightfield,
                                                camera, viewport_width, viewport_height)
                : world_to_screen_point(point_a.x, point_a.y, camera, viewport_width, viewport_height);
            const ScreenPoint screen_b = heightfield != nullptr
                ? terrain_world_to_screen_point(point_b.x, point_b.y, *heightfield,
                                                camera, viewport_width, viewport_height)
                : world_to_screen_point(point_b.x, point_b.y, camera, viewport_width, viewport_height);
            if (!SDL_RenderLine(renderer, screen_a.x, screen_a.y, screen_b.x, screen_b.y)) ok = false;
        }
    }

    (void)SDL_SetRenderDrawColor(renderer, old_r, old_g, old_b, old_a);
    return ok;
}

// Returns false only when SDL rejects one of the flat geometry submissions.
// Callers may still use the legacy tile/PNG renderer as a safety fallback.
[[nodiscard]] inline bool render_procedural_road_ground_plan(
    SDL_Renderer* renderer,
    const ProceduralRoadGroundRenderPlan& plan,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height,
    const ProceduralRoad2DRenderStyle& style = {},
    const TerrainHeightField* heightfield = nullptr) {
    for (const ProceduralRoad2DMesh& mesh : plan.segment_meshes) {
        if (!render_procedural_road_2d_mesh(
                renderer, mesh, camera, viewport_width, viewport_height, style, heightfield)) {
            return false;
        }
    }

    // Junction fans are drawn after approach ribbons so they own shared raster
    // edges and hide tiny antialiasing seams at intersections.
    for (const ProceduralRoad2DMesh& patch : plan.junction_meshes) {
        if (!render_procedural_road_2d_mesh(
                renderer, patch, camera, viewport_width, viewport_height, style, heightfield)) {
            return false;
        }
    }
    return true;
}

} // namespace ch
