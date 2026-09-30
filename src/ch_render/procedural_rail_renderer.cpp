#include "procedural_rail_renderer.h"

#include <cmath>
#include <cstdint>
#include <limits>
#include <vector>

namespace {

[[nodiscard]] bool finite_positive(const float value) {
    return std::isfinite(value) && value > 0.0F;
}

[[nodiscard]] bool render_mesh(
    SDL_Renderer* renderer,
    const RailMesh& mesh,
    const RailProfile& profile,
    const ch::CameraState& camera,
    const float viewport_width,
    const float viewport_height,
    const SDL_Color color) {
    if (renderer == nullptr || !finite_positive(viewport_width) || !finite_positive(viewport_height)) return false;
    if (!RailMeshBuilder::validate_mesh(mesh, profile).ok()) return false;
    if (mesh.vertices.size() > static_cast<std::size_t>(std::numeric_limits<int>::max()) ||
        mesh.indices.size() > static_cast<std::size_t>(std::numeric_limits<int>::max())) return false;

    std::vector<SDL_Vertex> vertices;
    vertices.reserve(mesh.vertices.size());
    for (const RailMeshVertex& source : mesh.vertices) {
        const ch::ScreenPoint screen = ch::world_to_screen_point(
            source.position.x, source.position.y, source.position.z,
            camera, viewport_width, viewport_height);
        if (!std::isfinite(screen.x) || !std::isfinite(screen.y)) return false;

        SDL_Vertex vertex{};
        vertex.position = SDL_FPoint{screen.x, screen.y};
        vertex.color = SDL_FColor{
            static_cast<float>(color.r) / 255.0F,
            static_cast<float>(color.g) / 255.0F,
            static_cast<float>(color.b) / 255.0F,
            static_cast<float>(color.a) / 255.0F,
        };
        vertex.tex_coord = SDL_FPoint{source.u, source.v};
        vertices.push_back(vertex);
    }

    std::vector<int> indices;
    indices.reserve(mesh.indices.size());
    for (const std::uint32_t source_index : mesh.indices) {
        if (source_index >= vertices.size() || source_index > static_cast<std::uint32_t>(std::numeric_limits<int>::max()))
            return false;
        indices.push_back(static_cast<int>(source_index));
    }

    return SDL_RenderGeometry(
        renderer,
        nullptr,
        vertices.data(), static_cast<int>(vertices.size()),
        indices.data(), static_cast<int>(indices.size()));
}

} // namespace

bool ProceduralRailRenderer::render_geometry(
    SDL_Renderer* renderer,
    const RailGeometry& geometry,
    const RailProfile& profile,
    const ch::CameraState& camera,
    const float viewport_width,
    const float viewport_height,
    const Palette& palette) {
    if (renderer == nullptr || !finite_positive(viewport_width) || !finite_positive(viewport_height)) return false;
    if (geometry.empty()) return false;

    // Render low-to-high material groups. Any rejected SDL submission is
    // propagated to the caller; no hidden fallback geometry is invented.
    if (!render_mesh(renderer, geometry.ballast, profile, camera, viewport_width, viewport_height, palette.ballast)) return false;
    if (!render_mesh(renderer, geometry.sleepers, profile, camera, viewport_width, viewport_height, palette.sleepers)) return false;
    if (!render_mesh(renderer, geometry.left_rail, profile, camera, viewport_width, viewport_height, palette.rails)) return false;
    if (!render_mesh(renderer, geometry.right_rail, profile, camera, viewport_width, viewport_height, palette.rails)) return false;
    return true;
}

bool ProceduralRailRenderer::render_segment(
    SDL_Renderer* renderer,
    const RailSplineSegment& segment,
    const RailProfile& profile,
    const ch::CameraState& camera,
    const float viewport_width,
    const float viewport_height,
    const Palette& palette) {
    if (renderer == nullptr || !finite_positive(viewport_width) || !finite_positive(viewport_height)) return false;
    const RailBuildResult build = RailMeshBuilder::build(segment, profile);
    if (!build.ok()) return false;
    return render_geometry(renderer, build.geometry, profile, camera, viewport_width, viewport_height, palette);
}
