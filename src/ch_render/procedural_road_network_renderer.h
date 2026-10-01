#pragma once

#include "src/ch_core/projection.h"
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
    const ProceduralRoad2DRenderStyle& style = {}) {
    if (renderer == nullptr || mesh.empty()) return true;
    if (mesh.vertices.size() > static_cast<std::size_t>(std::numeric_limits<int>::max()) ||
        mesh.indices.size() > static_cast<std::size_t>(std::numeric_limits<int>::max())) {
        return false;
    }

    std::vector<SDL_Vertex> vertices(mesh.vertices.size());
    for (std::size_t index = 0; index < mesh.vertices.size(); ++index) {
        const ProceduralRoad2DVertex& source = mesh.vertices[index];
        const ScreenPoint screen = world_to_screen_point(
            source.position.x, source.position.y,
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

// Returns false only when SDL rejects one of the flat geometry submissions.
// Callers may still use the legacy tile/PNG renderer as a safety fallback.
[[nodiscard]] inline bool render_procedural_road_ground_plan(
    SDL_Renderer* renderer,
    const ProceduralRoadGroundRenderPlan& plan,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height,
    const ProceduralRoad2DRenderStyle& style = {}) {
    for (const ProceduralRoad2DMesh& mesh : plan.segment_meshes) {
        if (!render_procedural_road_2d_mesh(
                renderer, mesh, camera, viewport_width, viewport_height, style)) {
            return false;
        }
    }

    // Junction fans are drawn after approach ribbons so they own shared raster
    // edges and hide tiny antialiasing seams at intersections.
    for (const ProceduralRoad2DMesh& patch : plan.junction_meshes) {
        if (!render_procedural_road_2d_mesh(
                renderer, patch, camera, viewport_width, viewport_height, style)) {
            return false;
        }
    }
    return true;
}

} // namespace ch
