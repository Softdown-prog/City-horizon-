#include "procedural_rail_renderer.h"
#include "../rail_live_operation_overlay.h"
#include "../rail_2d_visual_catalog.h"
#include <SDL3/SDL.h>
#include <filesystem>

#include <cmath>
#include <cstdint>
#include <limits>
#include <vector>

namespace {

[[nodiscard]] bool finite_positive(const float value) {
    return std::isfinite(value) && value > 0.0F;
}

// Render-path bridge for one canonical Blender straight segment. The native
// spline remains authoritative; curves and mismatched spans use mesh fallback.
// This is a conservative gameplay pilot, not blanket certification of 18 art ports.
[[nodiscard]] bool render_approved_straight_sprite(
    SDL_Renderer* renderer, const RailSplineSegment& segment,
    const ch::CameraState& camera, float width, float height) {
    constexpr float kExpectedWorldLength = 3.0F;
    constexpr float kTolerance = 0.025F;
    const float dx = segment.end.x - segment.start.x;
    const float dy = segment.end.y - segment.start.y;
    const float dz = segment.end.z - segment.start.z;
    const float length = std::hypot(dx, dy);
    if (std::abs(length - kExpectedWorldLength) > kTolerance || std::abs(dz) > kTolerance) return false;
    if (std::abs(dx) > kTolerance && std::abs(dy) > kTolerance) return false;
    if (std::hypot(segment.control_a.x - (segment.start.x + dx / 3.0F),
                   segment.control_a.y - (segment.start.y + dy / 3.0F)) > kTolerance ||
        std::hypot(segment.control_b.x - (segment.start.x + dx * 2.0F / 3.0F),
                   segment.control_b.y - (segment.start.y + dy * 2.0F / 3.0F)) > kTolerance) return false;
    const Rail2dDirection direction = std::abs(dx) > std::abs(dy) ? Rail2dDirection::south : Rail2dDirection::west;
    const auto spec = Rail2dVisualCatalog::resolve(Rail2dPieceKind::straight, direction);
    if (!spec) return false;
    const std::filesystem::path path(spec->png_path);
    SDL_Surface* surface = SDL_LoadPNG(path.string().c_str());
    if (!surface) return false;
    SDL_Texture* texture = SDL_CreateTextureFromSurface(renderer, surface);
    SDL_DestroySurface(surface);
    if (!texture) return false;
    SDL_SetTextureBlendMode(texture, SDL_BLENDMODE_BLEND);
    const float mx = (segment.start.x + segment.end.x) * 0.5F;
    const float my = (segment.start.y + segment.end.y) * 0.5F;
    const auto position = ch::world_to_screen_point(mx, my, segment.start.z, camera, width, height);
    // Historical bake uses a 512px canvas, 256/380 world-origin pivot.
    // Its nominal 3-world-unit module spans 192 projected horizontal pixels
    // before camera.zoom. Per-direction art-port review remains mandatory.
    constexpr float kSourceSize = 512.0F;
    constexpr float kModuleScale = 0.375F;
    const float scale = kModuleScale * camera.zoom;
    const SDL_FRect rect{position.x - 256.0F * scale,
                         position.y - 380.0F * scale,
                         kSourceSize * scale, kSourceSize * scale};
    const bool ok = SDL_RenderTexture(renderer, texture, nullptr, &rect);
    SDL_DestroyTexture(texture);
    return ok;
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
    // Conservative visual promotion: only perfectly axis-aligned 3-unit
    // straight modules use Blender PNGs; spline curves retain safe geometry.
    // Keep staged/invalid/hovered previews colored by the procedural palette.
    // A committed sprite must never mask the red invalid-placement indication.
    const Palette approved_palette{};
    const bool is_committed_visual =
        palette.ballast.r == approved_palette.ballast.r &&
        palette.ballast.g == approved_palette.ballast.g &&
        palette.ballast.b == approved_palette.ballast.b &&
        palette.ballast.a == approved_palette.ballast.a &&
        palette.sleepers.r == approved_palette.sleepers.r &&
        palette.sleepers.g == approved_palette.sleepers.g &&
        palette.sleepers.b == approved_palette.sleepers.b &&
        palette.rails.r == approved_palette.rails.r &&
        palette.rails.g == approved_palette.rails.g &&
        palette.rails.b == approved_palette.rails.b;
    if (is_committed_visual && render_approved_straight_sprite(
            renderer, segment, camera, viewport_width, viewport_height)) {
        ch::rail_live_operation::render_after_segment(renderer, segment, camera, viewport_width, viewport_height);
        return true;
    }
    const bool rendered = render_geometry(
        renderer, build.geometry, profile, camera, viewport_width, viewport_height, palette);
    if (rendered) {
        ch::rail_live_operation::render_after_segment(
            renderer, segment, camera, viewport_width, viewport_height);
    }
    return rendered;
}