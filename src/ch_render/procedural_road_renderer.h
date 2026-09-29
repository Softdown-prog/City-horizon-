#ifndef CITY_HORIZON_CH_RENDER_PROCEDURAL_ROAD_RENDERER_H
#define CITY_HORIZON_CH_RENDER_PROCEDURAL_ROAD_RENDERER_H

#include <SDL3/SDL.h>

#include <limits>
#include <vector>

#include "src/ch_core/projection.h"
#include "src/road_system.h"

namespace ch {

struct ProceduralRoadRenderStyle {
    SDL_FColor tint{52.0F / 255.0F, 57.0F / 255.0F, 60.0F / 255.0F, 1.0F};
    SDL_Texture* texture = nullptr;
};

// Thin SDL adapter for CH_PROCEDURAL_ROAD_MESH_V1. The expensive geometry work
// happens in RoadMeshBuilder only when a road changes. A cached RoadMesh can be
// projected every frame through CH_CAMERA_V1 just like the rest of the world.
inline bool render_procedural_road_mesh(SDL_Renderer* renderer, const RoadMesh& mesh,
                                        const CameraState& camera, const float viewport_width,
                                        const float viewport_height,
                                        const ProceduralRoadRenderStyle& style = {}) {
    if (renderer == nullptr || mesh.empty()) return true;
    if (mesh.vertices.size() > static_cast<std::size_t>(std::numeric_limits<int>::max()) ||
        mesh.indices.size() > static_cast<std::size_t>(std::numeric_limits<int>::max())) {
        return false;
    }

    std::vector<SDL_Vertex> vertices;
    vertices.resize(mesh.vertices.size());
    for (std::size_t index = 0; index < mesh.vertices.size(); ++index) {
        const RoadMeshVertex& source = mesh.vertices[index];
        const ScreenPoint screen = world_to_screen_point(
            source.position.x, source.position.y, source.position.z,
            camera, viewport_width, viewport_height);
        vertices[index].position = {screen.x, screen.y};
        vertices[index].color = style.tint;
        vertices[index].tex_coord = {source.u, source.v};
    }

    std::vector<int> indices;
    indices.reserve(mesh.indices.size());
    for (const std::uint32_t index : mesh.indices) {
        if (index >= mesh.vertices.size() || index > static_cast<std::uint32_t>(std::numeric_limits<int>::max())) {
            return false;
        }
        indices.push_back(static_cast<int>(index));
    }

    return SDL_RenderGeometry(renderer, style.texture,
                              vertices.data(), static_cast<int>(vertices.size()),
                              indices.data(), static_cast<int>(indices.size()));
}

} // namespace ch

#endif // CITY_HORIZON_CH_RENDER_PROCEDURAL_ROAD_RENDERER_H
