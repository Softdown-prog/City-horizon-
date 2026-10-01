#pragma once

#include "src/runtime_map_renderer.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <filesystem>
#include <functional>
#include <optional>
#include <unordered_map>
#include <vector>

namespace ch {
namespace runtime_terrain_detail {

inline constexpr float kTerrainHeightPixelsPerUnit = 16.0F;
inline constexpr float kHeightEpsilon = 0.0001F;

struct GroundSurfaceDrawEntry {
    int tile_x = 0;
    int tile_y = 0;
    TileConnectionMask connections = 0;
    ProceduralTileRecipe recipe{};
    GroundPathMaterial material = GroundPathMaterial::dirt;
};

[[nodiscard]] inline SDL_FPoint projected_point(
    const MapDocument& document,
    const float world_x,
    const float world_y,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height
) {
    ScreenPoint point = world_to_screen_point(world_x, world_y, camera, viewport_width, viewport_height);
    point.y -= document.terrain_heightfield().sample(world_x, world_y) *
               kTerrainHeightPixelsPerUnit * camera.zoom;
    return {point.x, point.y};
}

[[nodiscard]] inline bool tile_uses_heightfield(
    const MapDocument& document,
    const int tile_x,
    const int tile_y
) {
    return std::abs(document.terrain_height_at(tile_x, tile_y)) > kHeightEpsilon ||
           std::abs(document.terrain_height_at(tile_x + 1, tile_y)) > kHeightEpsilon ||
           std::abs(document.terrain_height_at(tile_x + 1, tile_y + 1)) > kHeightEpsilon ||
           std::abs(document.terrain_height_at(tile_x, tile_y + 1)) > kHeightEpsilon;
}

inline void render_deformed_tile_fill(
    SDL_Renderer* renderer,
    const MapDocument& document,
    const int tile_x,
    const int tile_y,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height,
    const SDL_FColor color
) {
    SDL_Vertex vertices[4] = {};
    vertices[0].position = projected_point(document, static_cast<float>(tile_x),
                                           static_cast<float>(tile_y), camera,
                                           viewport_width, viewport_height);
    vertices[1].position = projected_point(document, static_cast<float>(tile_x + 1),
                                           static_cast<float>(tile_y), camera,
                                           viewport_width, viewport_height);
    vertices[2].position = projected_point(document, static_cast<float>(tile_x + 1),
                                           static_cast<float>(tile_y + 1), camera,
                                           viewport_width, viewport_height);
    vertices[3].position = projected_point(document, static_cast<float>(tile_x),
                                           static_cast<float>(tile_y + 1), camera,
                                           viewport_width, viewport_height);
    for (SDL_Vertex& vertex : vertices) vertex.color = color;
    const int indices[] = {0, 1, 2, 0, 2, 3};
    (void)SDL_RenderGeometry(renderer, nullptr, vertices, 4, indices, 6);
}

inline void render_flat_sprite_at_height(
    SDL_Renderer* renderer,
    const TextureAsset& texture,
    const MapDocument& document,
    const int tile_x,
    const int tile_y,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height
) {
    if (texture.texture == nullptr || texture.source_width <= 0.0F) return;

    const WorldPoint visual_top = tile_visual_top_world(tile_x, tile_y, camera.rotation);
    ScreenPoint top = world_to_screen_point(visual_top.x, visual_top.y, camera,
                                            viewport_width, viewport_height);
    top.y -= document.terrain_heightfield().sample(visual_top.x, visual_top.y) *
             kTerrainHeightPixelsPerUnit * camera.zoom;

    const float tile_width = static_cast<float>(contracts::kTileWidth);
    const float scale = (tile_width / texture.source_width) * camera.zoom;
    const SDL_FRect destination = {
        top.x - tile_width * camera.zoom * 0.5F,
        top.y,
        texture.source_width * scale,
        texture.source_height * scale,
    };
    SDL_RenderTexture(renderer, texture.texture, nullptr, &destination);
}

inline void render_baked_path_slope_sprite(
    SDL_Renderer* renderer,
    const TextureAsset& texture,
    const PathSlopeSpriteSelection& selection,
    const int tile_x,
    const int tile_y,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height
) {
    if (renderer == nullptr || texture.texture == nullptr || texture.source_width <= 0.0F) return;

    const WorldPoint visual_top = tile_visual_top_world(tile_x, tile_y, camera.rotation);
    ScreenPoint top = world_to_screen_point(visual_top.x, visual_top.y, camera,
                                            viewport_width, viewport_height);
    top.y -= selection.base_height * kTerrainHeightPixelsPerUnit * camera.zoom;

    const float tile_width = static_cast<float>(contracts::kTileWidth);
    const float scale = (tile_width / texture.source_width) * camera.zoom;
    const SDL_FRect destination = {
        top.x - tile_width * camera.zoom * 0.5F,
        top.y - kPathSlopeLegacySurfaceY * camera.zoom,
        texture.source_width * scale,
        texture.source_height * scale,
    };
    SDL_RenderTexture(renderer, texture.texture, nullptr, &destination);
}

[[nodiscard]] inline SDL_FPoint edge_midpoint(
    const MapDocument& document,
    const int tile_x,
    const int tile_y,
    const CardinalDirection direction,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height
) {
    switch (direction) {
        case CardinalDirection::north:
            return projected_point(document, static_cast<float>(tile_x) + 0.5F,
                                   static_cast<float>(tile_y), camera,
                                   viewport_width, viewport_height);
        case CardinalDirection::east:
            return projected_point(document, static_cast<float>(tile_x + 1),
                                   static_cast<float>(tile_y) + 0.5F, camera,
                                   viewport_width, viewport_height);
        case CardinalDirection::south:
            return projected_point(document, static_cast<float>(tile_x) + 0.5F,
                                   static_cast<float>(tile_y + 1), camera,
                                   viewport_width, viewport_height);
        case CardinalDirection::west:
            return projected_point(document, static_cast<float>(tile_x),
                                   static_cast<float>(tile_y) + 0.5F, camera,
                                   viewport_width, viewport_height);
    }
    return projected_point(document, static_cast<float>(tile_x) + 0.5F,
                           static_cast<float>(tile_y) + 0.5F, camera,
                           viewport_width, viewport_height);
}

[[nodiscard]] inline SDL_FPoint tile_center(
    const MapDocument& document,
    const int tile_x,
    const int tile_y,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height
) {
    return projected_point(document, static_cast<float>(tile_x) + 0.5F,
                           static_cast<float>(tile_y) + 0.5F, camera,
                           viewport_width, viewport_height);
}

[[nodiscard]] inline bool render_disc(
    SDL_Renderer* renderer,
    const SDL_FPoint center,
    const float radius,
    const SDL_FColor color
) {
    if (renderer == nullptr || radius <= 0.0F) return true;

    constexpr int kSegments = 16;
    constexpr float kTau = 6.28318530717958647692F;
    std::array<SDL_Vertex, kSegments + 1> vertices{};
    std::array<int, kSegments * 3> indices{};
    vertices[0].position = center;
    vertices[0].color = color;

    for (int i = 0; i < kSegments; ++i) {
        const float angle = kTau * static_cast<float>(i) / static_cast<float>(kSegments);
        vertices[static_cast<std::size_t>(i + 1)].position = {
            center.x + std::cos(angle) * radius,
            center.y + std::sin(angle) * radius,
        };
        vertices[static_cast<std::size_t>(i + 1)].color = color;

        const int next = (i + 1) % kSegments;
        indices[static_cast<std::size_t>(i * 3 + 0)] = 0;
        indices[static_cast<std::size_t>(i * 3 + 1)] = i + 1;
        indices[static_cast<std::size_t>(i * 3 + 2)] = next + 1;
    }

    return SDL_RenderGeometry(renderer, nullptr, vertices.data(),
                              static_cast<int>(vertices.size()),
                              indices.data(), static_cast<int>(indices.size()));
}

[[nodiscard]] inline bool render_thick_segment(
    SDL_Renderer* renderer,
    const SDL_FPoint start,
    const SDL_FPoint end,
    const float width,
    const SDL_FColor color
) {
    const float dx = end.x - start.x;
    const float dy = end.y - start.y;
    const float length = std::hypot(dx, dy);
    if (length < 0.01F) return render_disc(renderer, start, width * 0.5F, color);

    const float half_width = width * 0.5F;
    const float nx = -dy / length * half_width;
    const float ny = dx / length * half_width;

    SDL_Vertex vertices[4] = {};
    vertices[0].position = {start.x + nx, start.y + ny};
    vertices[1].position = {end.x + nx, end.y + ny};
    vertices[2].position = {end.x - nx, end.y - ny};
    vertices[3].position = {start.x - nx, start.y - ny};
    for (SDL_Vertex& vertex : vertices) vertex.color = color;
    const int indices[] = {0, 1, 2, 0, 2, 3};
    return SDL_RenderGeometry(renderer, nullptr, vertices, 4, indices, 6);
}

// Reuses the approved dirt-path atlas as a material source instead of inventing
// a flat procedural brown.  A tiny center crop of the cross tile is guaranteed
// to sit inside the dirt material, so it can be stretched along arbitrary 2D
// ramps/stairs without carrying the transparent silhouette of a legacy tile.
[[nodiscard]] inline bool render_textured_segment(
    SDL_Renderer* renderer,
    const TextureAsset& material,
    const SDL_FPoint start,
    const SDL_FPoint end,
    const float width
) {
    if (renderer == nullptr || material.texture == nullptr || width <= 0.0F) return false;

    const float dx = end.x - start.x;
    const float dy = end.y - start.y;
    const float length = std::hypot(dx, dy);
    if (length < 0.01F) return true;

    const float half_width = width * 0.5F;
    const float nx = -dy / length * half_width;
    const float ny = dx / length * half_width;

    constexpr float kU0 = 0.44F;
    constexpr float kV0 = 0.44F;
    constexpr float kU1 = 0.56F;
    constexpr float kV1 = 0.56F;

    SDL_Vertex vertices[4] = {};
    vertices[0].position = {start.x + nx, start.y + ny};
    vertices[1].position = {end.x + nx, end.y + ny};
    vertices[2].position = {end.x - nx, end.y - ny};
    vertices[3].position = {start.x - nx, start.y - ny};
    vertices[0].tex_coord = {kU0, kV0};
    vertices[1].tex_coord = {kU1, kV0};
    vertices[2].tex_coord = {kU1, kV1};
    vertices[3].tex_coord = {kU0, kV1};
    for (SDL_Vertex& vertex : vertices) {
        vertex.color = {1.0F, 1.0F, 1.0F, 1.0F};
    }
    const int indices[] = {0, 1, 2, 0, 2, 3};
    return SDL_RenderGeometry(renderer, material.texture, vertices, 4, indices, 6);
}

inline void render_network_stroke(
    SDL_Renderer* renderer,
    const MapDocument& document,
    const GroundSurfaceDrawEntry& tile,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height,
    const float width,
    const SDL_FColor color
) {
    const SDL_FPoint center = tile_center(document, tile.tile_x, tile.tile_y,
                                         camera, viewport_width, viewport_height);

    if (tile.connections == 0) {
        (void)render_disc(renderer, center, width * 0.5F, color);
        return;
    }

    (void)render_disc(renderer, center, width * 0.5F, color);
    for (const CardinalDirection direction : kCardinalDirections) {
        if (!has_connection(tile.connections, direction)) continue;
        const SDL_FPoint edge = edge_midpoint(document, tile.tile_x, tile.tile_y,
                                              direction, camera,
                                              viewport_width, viewport_height);
        (void)render_thick_segment(renderer, center, edge, width, color);
        (void)render_disc(renderer, edge, width * 0.5F, color);
    }
}

inline void render_network_material(
    SDL_Renderer* renderer,
    const TextureAsset* material,
    const MapDocument& document,
    const GroundSurfaceDrawEntry& tile,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height,
    const float width
) {
    if (material == nullptr || material->texture == nullptr) return;

    const SDL_FPoint center = tile_center(document, tile.tile_x, tile.tile_y,
                                         camera, viewport_width, viewport_height);
    for (const CardinalDirection direction : kCardinalDirections) {
        if (!has_connection(tile.connections, direction)) continue;
        const SDL_FPoint edge = edge_midpoint(document, tile.tile_x, tile.tile_y,
                                              direction, camera,
                                              viewport_width, viewport_height);
        (void)render_textured_segment(renderer, *material, center, edge, width);
    }
}

inline void render_vertical_profile_details(
    SDL_Renderer* renderer,
    const MapDocument& document,
    const GroundSurfaceDrawEntry& tile,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height,
    const float inner_width
) {
    if (tile.recipe.vertical_profile == ProceduralTileVerticalProfile::flat) return;

    const SDL_FPoint low = edge_midpoint(document, tile.tile_x, tile.tile_y,
                                         tile.recipe.low_edge, camera,
                                         viewport_width, viewport_height);
    const SDL_FPoint high = edge_midpoint(document, tile.tile_x, tile.tile_y,
                                          tile.recipe.high_edge, camera,
                                          viewport_width, viewport_height);
    float axis_x = high.x - low.x;
    float axis_y = high.y - low.y;
    const float axis_length = std::hypot(axis_x, axis_y);
    if (axis_length < 0.5F) return;
    axis_x /= axis_length;
    axis_y /= axis_length;

    SDL_SetRenderDrawBlendMode(renderer, SDL_BLENDMODE_BLEND);
    if (tile.recipe.vertical_profile == ProceduralTileVerticalProfile::ramp) {
        const SDL_FPoint start = {low.x + axis_x * axis_length * 0.18F,
                                  low.y + axis_y * axis_length * 0.18F};
        const SDL_FPoint end = {high.x - axis_x * axis_length * 0.18F,
                                high.y - axis_y * axis_length * 0.18F};
        SDL_SetRenderDrawColor(renderer, 220, 176, 112, 72);
        SDL_RenderLine(renderer, start.x, start.y, end.x, end.y);
        return;
    }

    // A stair is still entirely 2D: each riser is a screen-space face whose
    // depth is derived from the canonical height delta. Higher slopes simply
    // receive more risers, so the visual continues automatically with relief.
    const int visible_steps = std::clamp(tile.recipe.stair_count, 2, 18);
    const float perpendicular_x = -axis_y;
    const float perpendicular_y = axis_x;
    const float half_step_width = inner_width * 0.47F;
    const float rise_pixels = tile.recipe.height_delta * kTerrainHeightPixelsPerUnit * camera.zoom /
                              static_cast<float>(visible_steps);
    const float face_depth = std::clamp(rise_pixels, 1.5F * camera.zoom, 5.5F * camera.zoom);

    for (int step = 1; step <= visible_steps; ++step) {
        const float t = static_cast<float>(step) / static_cast<float>(visible_steps + 1);
        const SDL_FPoint center = {low.x + axis_x * axis_length * t,
                                   low.y + axis_y * axis_length * t};
        const SDL_FPoint a = {center.x - perpendicular_x * half_step_width,
                              center.y - perpendicular_y * half_step_width};
        const SDL_FPoint b = {center.x + perpendicular_x * half_step_width,
                              center.y + perpendicular_y * half_step_width};

        SDL_Vertex face[4] = {};
        face[0].position = a;
        face[1].position = b;
        face[2].position = {b.x, b.y + face_depth};
        face[3].position = {a.x, a.y + face_depth};
        face[0].color = {72.0F / 255.0F, 46.0F / 255.0F, 28.0F / 255.0F, 0.90F};
        face[1].color = face[0].color;
        face[2].color = {54.0F / 255.0F, 35.0F / 255.0F, 22.0F / 255.0F, 0.94F};
        face[3].color = face[2].color;
        const int face_indices[] = {0, 1, 2, 0, 2, 3};
        (void)SDL_RenderGeometry(renderer, nullptr, face, 4, face_indices, 6);

        SDL_SetRenderDrawColor(renderer, 229, 185, 119, 145);
        SDL_RenderLine(renderer, a.x, a.y - 0.8F * camera.zoom,
                       b.x, b.y - 0.8F * camera.zoom);
        SDL_SetRenderDrawColor(renderer, 67, 43, 26, 210);
        SDL_RenderLine(renderer, a.x, a.y, b.x, b.y);
    }
}

inline void render_visible_terrain_base(
    SDL_Renderer* renderer,
    const MapDocument& document,
    const TextureAsset* grass,
    const std::unordered_map<std::uint64_t, const TextureAsset*>& scenario_terrain_textures,
    const runtime_render_detail::TileCullBounds& visible,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height
) {
    SDL_SetRenderDrawColor(renderer, 74, 104, 83, SDL_ALPHA_OPAQUE);
    const SDL_FRect background = {0.0F, 0.0F, viewport_width, viewport_height};
    SDL_RenderFillRect(renderer, &background);
    if (!visible.valid) return;

    if (grass == nullptr) {
        SDL_SetRenderDrawColor(renderer, 117, 148, 122, 115);
        for (int y = visible.min_y; y <= visible.max_y; ++y) {
            for (int x = visible.min_x; x <= visible.max_x; ++x) {
                MapRenderer::render_tile_outline(renderer, x, y, camera,
                                                 viewport_width, viewport_height);
            }
        }
        return;
    }

    for (int depth = visible.min_x + visible.min_y;
         depth <= visible.max_x + visible.max_y; ++depth) {
        const int first_x = std::max(visible.min_x, depth - visible.max_y);
        const int last_x = std::min(visible.max_x, depth - visible.min_y);
        for (int x = first_x; x <= last_x; ++x) {
            const int y = depth - x;
            const auto it = scenario_terrain_textures.find(tile_key(x, y));
            const TextureAsset* texture =
                it != scenario_terrain_textures.end() ? it->second : nullptr;
            const bool deformed = tile_uses_heightfield(document, x, y);

            if (texture != nullptr) {
                if (deformed) {
                    MapRenderer::render_heightfield_terrain_tile(
                        renderer, *texture, x, y, document, camera,
                        viewport_width, viewport_height, texture == grass);
                } else {
                    MapRenderer::render_custom_terrain_tile(renderer, *texture, x, y, camera,
                                                            viewport_width, viewport_height);
                }
            } else if (deformed) {
                MapRenderer::render_heightfield_terrain_tile(
                    renderer, *grass, x, y, document, camera,
                    viewport_width, viewport_height, true);
            } else {
                MapRenderer::render_grass_tile(renderer, *grass, x, y, camera,
                                               viewport_width, viewport_height);
            }
        }
    }
}

[[nodiscard]] inline float relief_shadow_alpha(
    const MapDocument& document,
    const int grid_x,
    const int grid_y
) {
    const float west = document.terrain_height_at(grid_x - 1, grid_y);
    const float east = document.terrain_height_at(grid_x + 1, grid_y);
    const float north = document.terrain_height_at(grid_x, grid_y - 1);
    const float south = document.terrain_height_at(grid_x, grid_y + 1);
    const float dx = (east - west) * 0.5F;
    const float dy = (south - north) * 0.5F;
    const float slope = std::hypot(dx, dy);
    if (slope <= kHeightEpsilon) return 0.0F;

    // Stable world-space light from the north-west. Shared grid vertices use
    // the same finite-difference sample in every neighbour, so the shade is
    // smooth across tile boundaries instead of drawing a checkerboard seam.
    const float away_from_light = std::max(0.0F, -(dx * 0.60F + dy * 0.80F));
    return std::clamp(slope * 0.045F + away_from_light * 0.12F, 0.0F, 0.28F);
}

inline void render_relief_shading_tile(
    SDL_Renderer* renderer,
    const MapDocument& document,
    const int tile_x,
    const int tile_y,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height
) {
    if (!tile_uses_heightfield(document, tile_x, tile_y)) return;

    SDL_Vertex vertices[4] = {};
    vertices[0].position = projected_point(document, static_cast<float>(tile_x),
                                           static_cast<float>(tile_y), camera,
                                           viewport_width, viewport_height);
    vertices[1].position = projected_point(document, static_cast<float>(tile_x + 1),
                                           static_cast<float>(tile_y), camera,
                                           viewport_width, viewport_height);
    vertices[2].position = projected_point(document, static_cast<float>(tile_x + 1),
                                           static_cast<float>(tile_y + 1), camera,
                                           viewport_width, viewport_height);
    vertices[3].position = projected_point(document, static_cast<float>(tile_x),
                                           static_cast<float>(tile_y + 1), camera,
                                           viewport_width, viewport_height);

    vertices[0].color = {0.0F, 0.0F, 0.0F, relief_shadow_alpha(document, tile_x, tile_y)};
    vertices[1].color = {0.0F, 0.0F, 0.0F, relief_shadow_alpha(document, tile_x + 1, tile_y)};
    vertices[2].color = {0.0F, 0.0F, 0.0F, relief_shadow_alpha(document, tile_x + 1, tile_y + 1)};
    vertices[3].color = {0.0F, 0.0F, 0.0F, relief_shadow_alpha(document, tile_x, tile_y + 1)};

    const int indices[] = {0, 1, 2, 0, 2, 3};
    (void)SDL_RenderGeometry(renderer, nullptr, vertices, 4, indices, 6);
}

inline void render_visible_relief_shading(
    SDL_Renderer* renderer,
    const MapDocument& document,
    const runtime_render_detail::TileCullBounds& visible,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height
) {
    if (renderer == nullptr || !visible.valid) return;
    SDL_SetRenderDrawBlendMode(renderer, SDL_BLENDMODE_BLEND);

    for (int depth = visible.min_x + visible.min_y;
         depth <= visible.max_x + visible.max_y; ++depth) {
        const int first_x = std::max(visible.min_x, depth - visible.max_y);
        const int last_x = std::min(visible.max_x, depth - visible.min_y);
        for (int x = first_x; x <= last_x; ++x) {
            render_relief_shading_tile(renderer, document, x, depth - x, camera,
                                       viewport_width, viewport_height);
        }
    }
}

} // namespace runtime_terrain_detail

// Runtime bridge for CH_TERRAIN_HEIGHTFIELD_V1 + CH_PATH_SLOPE_SPRITE_V1.
// Flat ground paths keep the approved legacy PNGs. Compatible non-flat straight
// cells select an offline-baked ramp/stair PNG from the same material family.
// The runtime never paints free-form artistic stair geometry.
class TerrainAwareRuntimeMapRenderer : public RuntimeMapRenderer {
public:
    static void render_world_terrain_and_water(
        SDL_Renderer* renderer,
        const MapDocument& document,
        const std::function<const TextureAsset*(const std::filesystem::path&)>& find_texture,
        const std::filesystem::path& asset_root,
        const CameraState& camera,
        const float viewport_width,
        const float viewport_height,
        const float render_time = 0.0F
    ) {
        (void)asset_root;
        if (renderer == nullptr) return;

        const runtime_render_detail::TileCullBounds visible =
            runtime_render_detail::visible_tile_bounds(camera, viewport_width, viewport_height, 2);
        const TextureAsset* grass_base = find_texture("assets/terrain/grass_isometric_01.png");

        std::unordered_map<std::uint64_t, const TextureAsset*> scenario_terrain_textures;
        std::vector<runtime_render_detail::WaterTile> water_tiles;
        std::vector<runtime_terrain_detail::GroundSurfaceDrawEntry> ground_path_tiles;

        if (visible.valid) {
            scenario_terrain_textures.reserve(visible.cell_count());
            for (int y = visible.min_y; y <= visible.max_y; ++y) {
                for (int x = visible.min_x; x <= visible.max_x; ++x) {
                    const std::optional<TerrainTileEntry> tile_opt = document.get_terrain_at(x, y);
                    if (!tile_opt.has_value()) continue;
                    const TerrainTileEntry& tile = *tile_opt;
                    const std::uint64_t key = tile_key(x, y);

                    if (!tile.texture.empty()) {
                        if (const TextureAsset* texture = find_texture(tile.texture)) {
                            scenario_terrain_textures[key] = texture;
                        }
                    }
                    if (!scenario_terrain_textures.contains(key) &&
                        (tile.terrain_definition == "sand" || tile.terrain_definition == "sand_center" ||
                         tile.terrain_definition == "sand_wet")) {
                        if (const TextureAsset* sand = find_texture("assets/terrain/sand_isometric_01.png")) {
                            scenario_terrain_textures[key] = sand;
                        }
                    }

                    const bool shallow = tile.terrain_definition == "water_shallow" ||
                                         tile.terrain_definition == "ocean_shallow";
                    const bool deep = tile.terrain_definition == "water_deep" ||
                                      tile.terrain_definition == "ocean_deep";
                    if (shallow || deep) water_tiles.push_back({x, y, shallow});

                    if (is_connectable_ground_surface(tile)) {
                        const auto material = ground_path_material(tile.terrain_definition);
                        if (material.has_value()) {
                            const TileConnectionMask connections =
                                ground_surface_connection_mask(document, x, y, tile.terrain_definition);
                            ground_path_tiles.push_back({
                                x,
                                y,
                                connections,
                                make_procedural_tile_2d_recipe(document, x, y, connections),
                                *material,
                            });
                        }
                    }
                }
            }
        }

        std::sort(water_tiles.begin(), water_tiles.end(), [](const auto& left, const auto& right) {
            const int left_depth = left.tile_x + left.tile_y;
            const int right_depth = right.tile_x + right.tile_y;
            return left_depth == right_depth ? left.tile_x < right.tile_x : left_depth < right_depth;
        });

        std::vector<runtime_render_detail::ShorelineOverlay> shoreline_overlays;
        if (visible.valid && !water_tiles.empty()) {
            SemanticWorldView world;
            world.map_document = &document;
            const runtime_render_detail::TileCullBounds shoreline_bounds =
                runtime_render_detail::expand_bounds(visible, 1);
            GridBounds evaluate_bounds;
            evaluate_bounds.min_x = shoreline_bounds.min_x;
            evaluate_bounds.max_x = shoreline_bounds.max_x;
            evaluate_bounds.min_y = shoreline_bounds.min_y;
            evaluate_bounds.max_y = shoreline_bounds.max_y;
            const AutotileResult autotile = ShorelineAutotiler::evaluate_shoreline(world, evaluate_bounds);
            for (const auto& edit : autotile.edits) {
                if (!shoreline_bounds.contains(edit.tile.x, edit.tile.y)) continue;
                for (const auto piece : edit.recipe.pieces) {
                    const std::string piece_path =
                        ShorelineCatalog::get_piece_texture_path(piece, "coast_adjusted");
                    if (const TextureAsset* texture = find_texture(piece_path)) {
                        shoreline_overlays.push_back({edit.tile.x, edit.tile.y, texture});
                    }
                }
            }
        }

        runtime_terrain_detail::render_visible_terrain_base(
            renderer, document, grass_base, scenario_terrain_textures, visible,
            camera, viewport_width, viewport_height);
        if (!visible.valid) return;

        // Geometry alone is difficult to read over repeated grass sprites.
        // Apply a subtle, production slope shadow before paths/props so hills
        // and basins remain obvious without debug contours or fake geometry.
        runtime_terrain_detail::render_visible_relief_shading(
            renderer, document, visible, camera, viewport_width, viewport_height);

        constexpr SDL_FColor kDirtUnderlay = {0.50F, 0.35F, 0.20F, 1.0F};
        constexpr SDL_FColor kSandUnderlay = {0.72F, 0.60F, 0.38F, 1.0F};
        for (const auto& tile : ground_path_tiles) {
            if (!tile.recipe.legacy_sprite_compatible) continue;
            const SDL_FColor underlay = tile.material == GroundPathMaterial::sand
                ? kSandUnderlay
                : kDirtUnderlay;
            runtime_terrain_detail::render_deformed_tile_fill(
                renderer, document, tile.tile_x, tile.tile_y, camera,
                viewport_width, viewport_height, underlay);
        }

        for (const auto& tile : ground_path_tiles) {
            const TileConnectionMask visual_connections =
                runtime_render_detail::camera_visual_connections(tile.connections, camera.rotation);
            const PathSlopeSpriteFamily& family = ground_path_sprite_family(tile.material);

            if (!tile.recipe.legacy_sprite_compatible) {
                const CardinalDirection visual_high_edge =
                    runtime_render_detail::camera_visual_direction(tile.recipe.high_edge, camera.rotation);
                const auto selection = select_path_slope_sprite(
                    family, tile.recipe, visual_connections, visual_high_edge);
                if (selection.has_value()) {
                    if (const TextureAsset* sprite = find_texture(selection->path)) {
                        runtime_terrain_detail::render_baked_path_slope_sprite(
                            renderer, *sprite, *selection, tile.tile_x, tile.tile_y,
                            camera, viewport_width, viewport_height);
                        continue;
                    }
                }
            }

            // Flat cells and non-straight slope topologies keep the legacy PNG.
            // Curves/tees/crosses will move to baked slope sprites only after
            // their own approved CH_PATH_SLOPE_SPRITE_V1 library exists.
            if (const TextureAsset* sprite =
                    find_texture(ground_path_flat_filename(family, visual_connections))) {
                runtime_terrain_detail::render_flat_sprite_at_height(
                    renderer, *sprite, document, tile.tile_x, tile.tile_y,
                    camera, viewport_width, viewport_height);
            }
        }

        constexpr SDL_FColor kDeepBase = {
            80.0F / 255.0F, 163.0F / 255.0F, 194.0F / 255.0F, 1.0F};
        constexpr SDL_FColor kShallowBase = {
            115.0F / 255.0F, 200.0F / 255.0F, 210.0F / 255.0F, 1.0F};
        for (const auto& tile : water_tiles) {
            MapRenderer::render_tile_fill(renderer, tile.tile_x, tile.tile_y, camera,
                                          viewport_width, viewport_height,
                                          tile.shallow ? kShallowBase : kDeepBase);
        }

        if (!water_tiles.empty()) {
            const TextureAsset* shallow = find_texture("assets/terrain/water/water_shallow_world.png");
            const TextureAsset* deep = find_texture("assets/terrain/water/water_deep_world.png");
            const TextureAsset* shallow_glint =
                find_texture("assets/terrain/water/water_shallow_glint_cycle_atlas.png");
            const TextureAsset* deep_glint =
                find_texture("assets/terrain/water/water_deep_glint_cycle_atlas.png");

            SDL_TextureAddressMode previous_u = SDL_TEXTURE_ADDRESS_AUTO;
            SDL_TextureAddressMode previous_v = SDL_TEXTURE_ADDRESS_AUTO;
            const bool restore_address =
                SDL_GetRenderTextureAddressMode(renderer, &previous_u, &previous_v);
            (void)SDL_SetRenderTextureAddressMode(
                renderer, SDL_TEXTURE_ADDRESS_WRAP, SDL_TEXTURE_ADDRESS_WRAP);
            for (const auto& tile : water_tiles) {
                const TextureAsset* texture = tile.shallow ? shallow : deep;
                if (texture != nullptr) {
                    MapRenderer::render_water_surface_tile(
                        renderer, *texture, tile.tile_x, tile.tile_y,
                        camera, viewport_width, viewport_height);
                }
            }

            (void)SDL_SetRenderTextureAddressMode(
                renderer, SDL_TEXTURE_ADDRESS_CLAMP, SDL_TEXTURE_ADDRESS_CLAMP);
            const int frame = std::clamp(
                static_cast<int>(std::floor(std::fmod(std::max(0.0F, render_time), 2.0F) * 8.0F)),
                0, 15);
            for (const auto& tile : water_tiles) {
                const TextureAsset* texture = tile.shallow ? shallow_glint : deep_glint;
                if (texture != nullptr) {
                    MapRenderer::render_water_surface_tile(
                        renderer, *texture, tile.tile_x, tile.tile_y,
                        camera, viewport_width, viewport_height, frame);
                }
            }
            (void)SDL_SetRenderTextureAddressMode(
                renderer,
                restore_address ? previous_u : SDL_TEXTURE_ADDRESS_AUTO,
                restore_address ? previous_v : SDL_TEXTURE_ADDRESS_AUTO);
        }

        for (const auto& overlay : shoreline_overlays) {
            if (overlay.texture != nullptr) {
                MapRenderer::render_custom_terrain_tile(
                    renderer, *overlay.texture, overlay.tile_x, overlay.tile_y,
                    camera, viewport_width, viewport_height);
            }
        }
    }
};

} // namespace ch