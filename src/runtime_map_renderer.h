#pragma once

#include "src/ch_render/map_renderer.h"
#include "src/runtime_procedural_road_renderer.h"
#include "src/ch_core/ground_surface.h"
#include "src/ch_core/shoreline_autotile.h"
#include "src/ch_render/shoreline_catalog.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <unordered_map>
#include <vector>

namespace ch {
namespace runtime_render_detail {

struct TileCullBounds {
    int min_x = contracts::kMapMin;
    int min_y = contracts::kMapMin;
    int max_x = contracts::kMapMax;
    int max_y = contracts::kMapMax;
    bool valid = true;

    [[nodiscard]] bool contains(const int x, const int y) const noexcept {
        return valid && x >= min_x && x <= max_x && y >= min_y && y <= max_y;
    }

    [[nodiscard]] std::size_t cell_count() const noexcept {
        if (!valid) return 0;
        return static_cast<std::size_t>(max_x - min_x + 1) *
               static_cast<std::size_t>(max_y - min_y + 1);
    }
};

[[nodiscard]] inline TileCullBounds visible_tile_bounds(const CameraState& camera,
                                                        const float viewport_width,
                                                        const float viewport_height,
                                                        const int tile_padding = 2,
                                                        const float pixel_guard = 96.0F) {
    if (viewport_width <= 0.0F || viewport_height <= 0.0F || camera.zoom <= 0.0F) {
        return {};
    }

    const std::array<GridCoord, 4> corners = {
        screen_to_tile_coord(-pixel_guard, -pixel_guard, camera, viewport_width, viewport_height),
        screen_to_tile_coord(viewport_width + pixel_guard, -pixel_guard, camera, viewport_width, viewport_height),
        screen_to_tile_coord(-pixel_guard, viewport_height + pixel_guard, camera, viewport_width, viewport_height),
        screen_to_tile_coord(viewport_width + pixel_guard, viewport_height + pixel_guard, camera, viewport_width, viewport_height),
    };

    int raw_min_x = corners[0].x;
    int raw_max_x = corners[0].x;
    int raw_min_y = corners[0].y;
    int raw_max_y = corners[0].y;
    for (const GridCoord& corner : corners) {
        raw_min_x = std::min(raw_min_x, corner.x);
        raw_max_x = std::max(raw_max_x, corner.x);
        raw_min_y = std::min(raw_min_y, corner.y);
        raw_max_y = std::max(raw_max_y, corner.y);
    }

    raw_min_x -= tile_padding;
    raw_max_x += tile_padding;
    raw_min_y -= tile_padding;
    raw_max_y += tile_padding;

    if (raw_max_x < contracts::kMapMin || raw_min_x > contracts::kMapMax ||
        raw_max_y < contracts::kMapMin || raw_min_y > contracts::kMapMax) {
        TileCullBounds empty;
        empty.valid = false;
        return empty;
    }

    TileCullBounds bounds;
    bounds.min_x = std::max(contracts::kMapMin, raw_min_x);
    bounds.max_x = std::min(contracts::kMapMax, raw_max_x);
    bounds.min_y = std::max(contracts::kMapMin, raw_min_y);
    bounds.max_y = std::min(contracts::kMapMax, raw_max_y);
    return bounds;
}

[[nodiscard]] inline TileCullBounds expand_bounds(const TileCullBounds& bounds, const int padding) {
    if (!bounds.valid) return bounds;
    TileCullBounds expanded = bounds;
    expanded.min_x = std::max(contracts::kMapMin, bounds.min_x - padding);
    expanded.max_x = std::min(contracts::kMapMax, bounds.max_x + padding);
    expanded.min_y = std::max(contracts::kMapMin, bounds.min_y - padding);
    expanded.max_y = std::min(contracts::kMapMax, bounds.max_y + padding);
    return expanded;
}

[[nodiscard]] inline bool rect_visible(const SDL_FRect& rect,
                                       const float viewport_width,
                                       const float viewport_height,
                                       const float guard = 96.0F) noexcept {
    return rect.x + rect.w >= -guard && rect.y + rect.h >= -guard &&
           rect.x <= viewport_width + guard && rect.y <= viewport_height + guard;
}

[[nodiscard]] constexpr CardinalDirection camera_visual_direction(const CardinalDirection direction,
                                                                  const CameraRotation rotation) {
    const int index = static_cast<int>(direction);
    const int visual_index = (index - static_cast<int>(rotation) + 4) % 4;
    return static_cast<CardinalDirection>(visual_index);
}

[[nodiscard]] inline TileConnectionMask camera_visual_connections(const TileConnectionMask connections,
                                                                  const CameraRotation rotation) {
    TileConnectionMask visual = 0;
    for (const CardinalDirection direction : kCardinalDirections) {
        if (has_connection(connections, direction)) {
            visual |= connection_bit(camera_visual_direction(direction, rotation));
        }
    }
    return visual;
}

[[nodiscard]] inline BuildingRotation camera_visual_rotation(const BuildingDefinition& definition,
                                                             const BuildingRotation logical_rotation,
                                                             const CameraRotation camera_rotation) {
    const int visual = (static_cast<int>(logical_rotation) - static_cast<int>(camera_rotation) + 4) % 4;
    const BuildingRotation desired = static_cast<BuildingRotation>(visual);
    return definition.supports_rotation(desired) ? desired : logical_rotation;
}

[[nodiscard]] inline std::string dirt_path_sprite(const TileConnectionMask mask) {
    static constexpr std::array<const char*, 16> kSprites = {
        "dirt_path_00_isolated.png", "dirt_path_01_end_n.png", "dirt_path_02_end_e.png", "dirt_path_03_curve_ne.png",
        "dirt_path_04_end_s.png", "dirt_path_05_straight_ns.png", "dirt_path_06_curve_es.png", "dirt_path_07_tee_no_w.png",
        "dirt_path_08_end_w.png", "dirt_path_09_curve_nw.png", "dirt_path_10_straight_ew.png", "dirt_path_11_tee_no_s.png",
        "dirt_path_12_curve_sw.png", "dirt_path_13_tee_no_e.png", "dirt_path_14_tee_no_n.png", "dirt_path_15_cross.png",
    };
    return "assets/terrain/paths/dirt_01/" + std::string(kSprites.at(static_cast<std::size_t>(mask)));
}

[[nodiscard]] inline std::string sidewalk_sprite(const std::string& style_id,
                                                 const TileConnectionMask connections) {
    if (style_id == "cement_path" || style_id == "concrete_01" || style_id == "dirt_path") {
        return dirt_path_sprite(connections);
    }
    if (style_id == "sand_path") {
        std::string filename = dirt_path_sprite(connections).substr(std::string("assets/terrain/paths/dirt_01/").size());
        filename.replace(0, 4, "sand");
        return "assets/terrain/paths/sand_01/" + filename;
    }
    const std::string base = "assets/sidewalks/" + style_id + "/sidewalk_concrete_";
    const int mask = static_cast<int>(connections);
    if (mask == 15) return base + "15_seamless.png";
    const std::string suffix = mask < 10 ? "0" + std::to_string(mask) : std::to_string(mask);
    return base + suffix + ".png";
}

[[nodiscard]] inline SDL_FColor road_placeholder_color(const RoadVisualType type) {
    switch (type) {
        case RoadVisualType::isolated: return {0.25F, 0.29F, 0.30F, 0.94F};
        case RoadVisualType::end: return {0.25F, 0.39F, 0.47F, 0.94F};
        case RoadVisualType::straight: return {0.24F, 0.28F, 0.28F, 0.94F};
        case RoadVisualType::curve: return {0.35F, 0.29F, 0.48F, 0.94F};
        case RoadVisualType::tee: return {0.48F, 0.34F, 0.20F, 0.94F};
        case RoadVisualType::intersection: return {0.43F, 0.24F, 0.20F, 0.94F};
    }
    return {0.24F, 0.28F, 0.28F, 0.94F};
}

struct WaterTile {
    int tile_x = 0;
    int tile_y = 0;
    bool shallow = false;
};

struct GroundSurfaceTile {
    int tile_x = 0;
    int tile_y = 0;
    TileConnectionMask connections = 0;
};

struct ShorelineOverlay {
    int tile_x = 0;
    int tile_y = 0;
    const TextureAsset* texture = nullptr;
};

}  // namespace runtime_render_detail

// Runtime-only presentation facade. It preserves MapRenderer's public contract
// but builds a conservative camera-visible working set before expensive sorting,
// texture lookup and per-tile geometry. Map Forge keeps using canonical
// MapRenderer directly, so editor/geometry verification behavior is unchanged.
class RuntimeMapRenderer : public MapRenderer {
public:
    static void render_map(SDL_Renderer* renderer, const TextureAsset* grass,
                           const std::unordered_map<std::uint64_t, const TextureAsset*>& scenario_terrain_textures,
                           const CameraState& camera, const float viewport_width, const float viewport_height,
                           const MapDocument* document = nullptr) {
        SDL_SetRenderDrawColor(renderer, 74, 104, 83, SDL_ALPHA_OPAQUE);
        const SDL_FRect background = {0.0F, 0.0F, viewport_width, viewport_height};
        SDL_RenderFillRect(renderer, &background);

        const runtime_render_detail::TileCullBounds visible =
            runtime_render_detail::visible_tile_bounds(camera, viewport_width, viewport_height, 2);
        if (!visible.valid) return;

        if (grass == nullptr) {
            SDL_SetRenderDrawColor(renderer, 117, 148, 122, 115);
            for (int y = visible.min_y; y <= visible.max_y; ++y) {
                for (int x = visible.min_x; x <= visible.max_x; ++x) {
                    MapRenderer::render_tile_outline(renderer, x, y, camera, viewport_width, viewport_height);
                }
            }
            return;
        }

        for (int depth = visible.min_x + visible.min_y; depth <= visible.max_x + visible.max_y; ++depth) {
            const int first_x = std::max(visible.min_x, depth - visible.max_y);
            const int last_x = std::min(visible.max_x, depth - visible.min_y);
            for (int x = first_x; x <= last_x; ++x) {
                const int y = depth - x;
                const auto it = scenario_terrain_textures.find(tile_key(x, y));
                const bool deform = document != nullptr && (
                    document->terrain_height_at(x, y) != 0.0F ||
                    document->terrain_height_at(x + 1, y) != 0.0F ||
                    document->terrain_height_at(x + 1, y + 1) != 0.0F ||
                    document->terrain_height_at(x, y + 1) != 0.0F);

                if (it != scenario_terrain_textures.end() && it->second != nullptr) {
                    if (deform) {
                        MapRenderer::render_heightfield_terrain_tile(
                            renderer, *it->second, x, y, *document, camera,
                            viewport_width, viewport_height, it->second == grass);
                    } else {
                        MapRenderer::render_custom_terrain_tile(renderer, *it->second, x, y, camera,
                                                                viewport_width, viewport_height);
                    }
                } else if (deform) {
                    MapRenderer::render_heightfield_terrain_tile(
                        renderer, *grass, x, y, *document, camera,
                        viewport_width, viewport_height, true);
                } else {
                    MapRenderer::render_grass_tile(renderer, *grass, x, y, camera,
                                                  viewport_width, viewport_height);
                }
            }
        }
    }

    static void render_world_terrain_and_water(
        SDL_Renderer* renderer, const MapDocument& document,
        const std::function<const TextureAsset*(const std::filesystem::path&)>& find_texture,
        const std::filesystem::path& asset_root, const CameraState& camera,
        const float viewport_width, const float viewport_height, const float render_time = 0.0F) {
        (void)asset_root;
        if (renderer == nullptr) return;

        const runtime_render_detail::TileCullBounds visible =
            runtime_render_detail::visible_tile_bounds(camera, viewport_width, viewport_height, 2);
        const TextureAsset* grass_base = find_texture("assets/terrain/grass_isometric_01.png");

        std::unordered_map<std::uint64_t, const TextureAsset*> scenario_terrain_textures;
        std::vector<runtime_render_detail::WaterTile> water_tiles;
        std::vector<runtime_render_detail::GroundSurfaceTile> dirt_path_tiles;

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
                    if (shallow || deep) {
                        water_tiles.push_back({x, y, shallow});
                    }
                    if (is_connectable_ground_surface(tile)) {
                        dirt_path_tiles.push_back({x, y,
                            ground_surface_connection_mask(document, x, y, tile.terrain_definition)});
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

        RuntimeMapRenderer::render_map(renderer, grass_base, scenario_terrain_textures,
                                       camera, viewport_width, viewport_height, &document);
        if (!visible.valid) return;

        constexpr SDL_FColor kDirtUnderlay = {0.50F, 0.35F, 0.20F, 1.0F};
        for (const auto& tile : dirt_path_tiles) {
            MapRenderer::render_tile_fill(renderer, tile.tile_x, tile.tile_y, camera,
                                          viewport_width, viewport_height, kDirtUnderlay);
        }
        for (const auto& tile : dirt_path_tiles) {
            const TileConnectionMask connections = runtime_render_detail::camera_visual_connections(
                tile.connections, camera.rotation);
            if (const TextureAsset* sprite = find_texture(runtime_render_detail::dirt_path_sprite(connections))) {
                MapRenderer::render_custom_terrain_tile(renderer, *sprite, tile.tile_x, tile.tile_y,
                                                        camera, viewport_width, viewport_height);
            }
        }

        constexpr SDL_FColor kDeepBase = {80.0F / 255.0F, 163.0F / 255.0F, 194.0F / 255.0F, 1.0F};
        constexpr SDL_FColor kShallowBase = {115.0F / 255.0F, 200.0F / 255.0F, 210.0F / 255.0F, 1.0F};
        for (const auto& tile : water_tiles) {
            MapRenderer::render_tile_fill(renderer, tile.tile_x, tile.tile_y, camera,
                                          viewport_width, viewport_height,
                                          tile.shallow ? kShallowBase : kDeepBase);
        }
        if (!water_tiles.empty()) {
            const TextureAsset* shallow = find_texture("assets/terrain/water/water_shallow_world.png");
            const TextureAsset* deep = find_texture("assets/terrain/water/water_deep_world.png");
            const TextureAsset* shallow_glint = find_texture("assets/terrain/water/water_shallow_glint_cycle_atlas.png");
            const TextureAsset* deep_glint = find_texture("assets/terrain/water/water_deep_glint_cycle_atlas.png");
            SDL_TextureAddressMode previous_u = SDL_TEXTURE_ADDRESS_AUTO;
            SDL_TextureAddressMode previous_v = SDL_TEXTURE_ADDRESS_AUTO;
            const bool restore_address = SDL_GetRenderTextureAddressMode(renderer, &previous_u, &previous_v);
            (void)SDL_SetRenderTextureAddressMode(renderer, SDL_TEXTURE_ADDRESS_WRAP, SDL_TEXTURE_ADDRESS_WRAP);
            for (const auto& tile : water_tiles) {
                const TextureAsset* texture = tile.shallow ? shallow : deep;
                if (texture != nullptr)
                    MapRenderer::render_water_surface_tile(renderer, *texture, tile.tile_x, tile.tile_y,
                                                           camera, viewport_width, viewport_height);
            }
            (void)SDL_SetRenderTextureAddressMode(renderer, SDL_TEXTURE_ADDRESS_CLAMP, SDL_TEXTURE_ADDRESS_CLAMP);
            const int frame = std::clamp(static_cast<int>(
                std::floor(std::fmod(std::max(0.0F, render_time), 2.0F) * 8.0F)), 0, 15);
            for (const auto& tile : water_tiles) {
                const TextureAsset* texture = tile.shallow ? shallow_glint : deep_glint;
                if (texture != nullptr)
                    MapRenderer::render_water_surface_tile(renderer, *texture, tile.tile_x, tile.tile_y,
                                                           camera, viewport_width, viewport_height, frame);
            }
            (void)SDL_SetRenderTextureAddressMode(renderer,
                restore_address ? previous_u : SDL_TEXTURE_ADDRESS_AUTO,
                restore_address ? previous_v : SDL_TEXTURE_ADDRESS_AUTO);
        }

        for (const auto& overlay : shoreline_overlays) {
            if (overlay.texture != nullptr) {
                MapRenderer::render_custom_terrain_tile(renderer, *overlay.texture,
                    overlay.tile_x, overlay.tile_y, camera, viewport_width, viewport_height);
            }
        }
    }

    static void render_land_overlays(SDL_Renderer* renderer, const LandManager& lands,
                                     const LandParcel* hovered_parcel, const bool land_mode,
                                     const CameraState& camera, const float viewport_width,
                                     const float viewport_height) {
        const runtime_render_detail::TileCullBounds visible =
            runtime_render_detail::visible_tile_bounds(camera, viewport_width, viewport_height, 1);
        if (!visible.valid) return;

        for (const LandParcel& parcel : lands.parcels()) {
            SDL_FColor color = {0.08F, 0.11F, 0.14F, 0.22F};
            if (land_mode && &parcel == hovered_parcel) {
                if (parcel.owned) {
                    color = {0.22F, 0.58F, 0.92F, 0.28F};
                } else if (lands.can_purchase_parcel(parcel.id)) {
                    color = {0.25F, 0.82F, 0.42F, 0.42F};
                } else {
                    color = {0.92F, 0.25F, 0.25F, 0.38F};
                }
            } else if (parcel.owned) {
                color = {0.22F, 0.58F, 0.92F, 0.15F};
            }

            for (int y = parcel.min_y; y <= parcel.max_y; ++y) {
                for (int x = parcel.min_x; x <= parcel.max_x; ++x) {
                    if (!visible.contains(x, y)) continue;
                    MapRenderer::render_tile_fill(renderer, x, y, camera,
                                                  viewport_width, viewport_height, color);
                }
            }
        }
    }
};

}  // namespace ch
