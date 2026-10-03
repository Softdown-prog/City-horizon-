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
                if (it != scenario_terrain_textures.end() && it->second != nullptr) {
                    if (document != nullptr) {
                        MapRenderer::render_heightfield_terrain_tile(renderer, *it->second, x, y, *document,
                                                                    camera, viewport_width, viewport_height, false);
                    } else {
                        MapRenderer::render_custom_terrain_tile(renderer, *it->second, x, y, camera,
                                                                viewport_width, viewport_height);
                    }
                } else if (document != nullptr) {
                    MapRenderer::render_heightfield_terrain_tile(renderer, *grass, x, y, *document,
                                                                camera, viewport_width, viewport_height, true);
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
            MapRenderer::render_heightfield_tile_fill(renderer, tile.tile_x, tile.tile_y, document,
                                                      camera, viewport_width, viewport_height, kDirtUnderlay);
        }
        for (const auto& tile : dirt_path_tiles) {
            const TileConnectionMask connections = runtime_render_detail::camera_visual_connections(
                tile.connections, camera.rotation);
            if (const TextureAsset* sprite = find_texture(runtime_render_detail::dirt_path_sprite(connections))) {
                MapRenderer::render_heightfield_terrain_tile(renderer, *sprite, tile.tile_x, tile.tile_y, document,
                                                             camera, viewport_width, viewport_height, false);
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
                    color = {0.88F, 0.28F, 0.24F, 0.42F};
                }
            } else if (parcel.owned) {
                continue;
            }

            const int min_y = std::max({contracts::kMapMin, parcel.origin_y, visible.min_y});
            const int max_y = std::min({contracts::kMapMax, parcel.origin_y + parcel.height - 1, visible.max_y});
            const int min_x = std::max({contracts::kMapMin, parcel.origin_x, visible.min_x});
            const int max_x = std::min({contracts::kMapMax, parcel.origin_x + parcel.width - 1, visible.max_x});
            if (min_x > max_x || min_y > max_y) continue;

            for (int y = min_y; y <= max_y; ++y) {
                for (int x = min_x; x <= max_x; ++x) {
                    MapRenderer::render_tile_fill(renderer, x, y, camera,
                                                  viewport_width, viewport_height, color);
                }
            }
        }
    }

    static void render_roads(SDL_Renderer* renderer, const RoadManager& roads,
                             const RoadVisualCatalog& visuals,
                             const std::function<const TextureAsset*(const std::filesystem::path&)>& find_texture,
                             const std::filesystem::path& asset_root, const CameraState& camera,
                             const float viewport_width, const float viewport_height) {
        const runtime_render_detail::TileCullBounds visible =
            runtime_render_detail::visible_tile_bounds(camera, viewport_width, viewport_height, 1);
        if (!visible.valid || roads.tiles().empty()) return;

        if (try_render_procedural_roads_runtime(
                renderer, roads, camera, viewport_width, viewport_height)) {
            return;
        }

        std::vector<const RoadTile*> visible_tiles;
        visible_tiles.reserve(std::min(roads.tiles().size(), visible.cell_count()));
        if (visible.cell_count() < roads.tiles().size()) {
            for (int y = visible.min_y; y <= visible.max_y; ++y) {
                for (int x = visible.min_x; x <= visible.max_x; ++x) {
                    if (const RoadTile* tile = roads.tile_at(x, y)) visible_tiles.push_back(tile);
                }
            }
        } else {
            for (const RoadTile& tile : roads.tiles()) {
                if (visible.contains(tile.tile_x, tile.tile_y)) visible_tiles.push_back(&tile);
            }
        }

        std::sort(visible_tiles.begin(), visible_tiles.end(), [&camera](const RoadTile* left, const RoadTile* right) {
            const float left_depth = camera_depth_key(static_cast<float>(left->tile_x + 1),
                                                      static_cast<float>(left->tile_y + 1), camera);
            const float right_depth = camera_depth_key(static_cast<float>(right->tile_x + 1),
                                                       static_cast<float>(right->tile_y + 1), camera);
            if (left_depth != right_depth) return left_depth < right_depth;
            if (left->tile_y != right->tile_y) return left->tile_y < right->tile_y;
            return left->tile_x < right->tile_x;
        });

        constexpr SDL_FColor kRoadAsphalt = {52.0F / 255.0F, 57.0F / 255.0F, 60.0F / 255.0F, 1.0F};
        for (const RoadTile* tile : visible_tiles) {
            MapRenderer::render_tile_fill(renderer, tile->tile_x, tile->tile_y, camera,
                                          viewport_width, viewport_height, kRoadAsphalt);
        }
        for (const RoadTile* tile : visible_tiles) {
            const TileConnectionMask connections = runtime_render_detail::camera_visual_connections(
                tile->connections, camera.rotation);
            const RoadVisual* visual = visuals.get_for_mask(connections);
            const TextureAsset* texture = visual == nullptr
                ? nullptr : find_texture(asset_root / visual->texture_path);
            if (texture != nullptr) {
                MapRenderer::render_road_sprite(renderer, *texture, tile->tile_x, tile->tile_y,
                                                camera, viewport_width, viewport_height);
            } else {
                MapRenderer::render_road_tile(renderer, tile->tile_x, tile->tile_y, camera,
                    viewport_width, viewport_height,
                    runtime_render_detail::road_placeholder_color(roads.visual_type(tile->tile_x, tile->tile_y)));
            }
        }
    }

    static void render_sidewalks(SDL_Renderer* renderer, const SidewalkManager& sidewalks,
                                 const std::function<const TextureAsset*(const std::filesystem::path&)>& find_texture,
                                 const std::filesystem::path& asset_root, const CameraState& camera,
                                 const float viewport_width, const float viewport_height) {
        const runtime_render_detail::TileCullBounds visible =
            runtime_render_detail::visible_tile_bounds(camera, viewport_width, viewport_height, 1);
        if (!visible.valid || sidewalks.tiles().empty()) return;

        const auto render_tile = [&](const SidewalkTile& tile) {
            const TileConnectionMask connections = runtime_render_detail::camera_visual_connections(
                tile.connections, camera.rotation);
            if (const TextureAsset* texture = find_texture(
                    asset_root / runtime_render_detail::sidewalk_sprite(tile.style_id, connections))) {
                const WorldPoint visual_top = tile_visual_top_world(tile.tile_x, tile.tile_y, camera.rotation);
                const ScreenPoint top = world_to_screen_point(visual_top.x, visual_top.y, camera,
                                                              viewport_width, viewport_height);
                const float scale = (static_cast<float>(contracts::kTileWidth) / texture->source_width) * camera.zoom;
                const SDL_FRect destination = {
                    top.x - texture->source_width * scale * 0.5F,
                    top.y,
                    texture->source_width * scale,
                    texture->source_height * scale,
                };
                SDL_RenderTexture(renderer, texture->texture, nullptr, &destination);
            }
        };

        if (visible.cell_count() < sidewalks.tiles().size()) {
            for (int y = visible.min_y; y <= visible.max_y; ++y) {
                for (int x = visible.min_x; x <= visible.max_x; ++x) {
                    if (const SidewalkTile* tile = sidewalks.tile_at(x, y)) render_tile(*tile);
                }
            }
        } else {
            for (const SidewalkTile& tile : sidewalks.tiles()) {
                if (visible.contains(tile.tile_x, tile.tile_y)) render_tile(tile);
            }
        }
    }

    static void render_farming(SDL_Renderer* renderer, const FarmingSystem& farming,
                               const CropCatalog& crops,
                               const std::function<const TextureAsset*(const std::filesystem::path&)>& find_texture,
                               const std::filesystem::path& root, const CameraState& camera,
                               const float viewport_width, const float viewport_height) {
        (void)crops;
        (void)find_texture;
        (void)root;
        if (renderer == nullptr || farming.tiles().empty()) return;

        const runtime_render_detail::TileCullBounds visible =
            runtime_render_detail::visible_tile_bounds(camera, viewport_width, viewport_height, 1);
        if (!visible.valid) return;

        const auto soil_color = [](const float world_x, const float world_y) -> SDL_FColor {
            const float broad = std::sin(world_x * 0.52F + world_y * 0.38F) * 0.022F;
            const float cross = std::sin(world_x * 1.27F - world_y * 0.73F + 0.8F) * 0.012F;
            const float warm = std::sin(world_x * 0.31F + world_y * 0.91F + 1.7F) * 0.009F;
            const float shade = broad + cross;
            return {
                std::clamp(118.0F / 255.0F + shade + warm, 0.0F, 1.0F),
                std::clamp(78.0F / 255.0F + shade * 0.76F + warm * 0.30F, 0.0F, 1.0F),
                std::clamp(45.0F / 255.0F + shade * 0.52F, 0.0F, 1.0F),
                1.0F,
            };
        };

        for (int y = visible.min_y; y <= visible.max_y; ++y) {
            for (int x = visible.min_x; x <= visible.max_x; ++x) {
                if (farming.tile_at(x, y) == nullptr) continue;
                const ScreenPoint top = world_to_screen_point(static_cast<float>(x), static_cast<float>(y),
                                                              camera, viewport_width, viewport_height);
                const ScreenPoint right = world_to_screen_point(static_cast<float>(x + 1), static_cast<float>(y),
                                                                camera, viewport_width, viewport_height);
                const ScreenPoint bottom = world_to_screen_point(static_cast<float>(x + 1), static_cast<float>(y + 1),
                                                                 camera, viewport_width, viewport_height);
                const ScreenPoint left = world_to_screen_point(static_cast<float>(x), static_cast<float>(y + 1),
                                                               camera, viewport_width, viewport_height);
                SDL_Vertex vertices[4] = {};
                vertices[0].position = {top.x, top.y};
                vertices[1].position = {right.x, right.y};
                vertices[2].position = {bottom.x, bottom.y};
                vertices[3].position = {left.x, left.y};
                vertices[0].color = soil_color(static_cast<float>(x), static_cast<float>(y));
                vertices[1].color = soil_color(static_cast<float>(x + 1), static_cast<float>(y));
                vertices[2].color = soil_color(static_cast<float>(x + 1), static_cast<float>(y + 1));
                vertices[3].color = soil_color(static_cast<float>(x), static_cast<float>(y + 1));
                const int indices[] = {0, 1, 2, 0, 2, 3};
                (void)SDL_RenderGeometry(renderer, nullptr, vertices, 4, indices, 6);
            }
        }

        constexpr std::array<float, 5> kFurrowOffsets = {0.10F, 0.30F, 0.50F, 0.70F, 0.90F};
        constexpr float kHighlightOffset = 0.025F;
        for (int y = visible.min_y; y <= visible.max_y; ++y) {
            int x = visible.min_x;
            while (x <= visible.max_x) {
                while (x <= visible.max_x && !farming.is_occupied(x, y)) ++x;
                if (x > visible.max_x) break;
                const int run_start_x = x;
                while (x <= visible.max_x && farming.is_occupied(x, y)) ++x;
                const int run_end_x = x - 1;

                for (const float offset : kFurrowOffsets) {
                    const ScreenPoint highlight_start = world_to_screen_point(
                        static_cast<float>(run_start_x), static_cast<float>(y) + offset - kHighlightOffset,
                        camera, viewport_width, viewport_height);
                    const ScreenPoint highlight_end = world_to_screen_point(
                        static_cast<float>(run_end_x + 1), static_cast<float>(y) + offset - kHighlightOffset,
                        camera, viewport_width, viewport_height);
                    SDL_SetRenderDrawColor(renderer, 154, 108, 68, 88);
                    SDL_RenderLine(renderer, highlight_start.x, highlight_start.y,
                                   highlight_end.x, highlight_end.y);

                    const ScreenPoint shadow_start = world_to_screen_point(
                        static_cast<float>(run_start_x), static_cast<float>(y) + offset,
                        camera, viewport_width, viewport_height);
                    const ScreenPoint shadow_end = world_to_screen_point(
                        static_cast<float>(run_end_x + 1), static_cast<float>(y) + offset,
                        camera, viewport_width, viewport_height);
                    SDL_SetRenderDrawColor(renderer, 78, 47, 29, 188);
                    SDL_RenderLine(renderer, shadow_start.x, shadow_start.y,
                                   shadow_end.x, shadow_end.y);
                }
            }
        }
    }

    static void render_farming(SDL_Renderer* renderer, const FarmingSystem& farming,
                               const CropCatalog& crops,
                               const std::unordered_map<std::string, TextureAsset>& texture_lookup,
                               const std::filesystem::path& root, const CameraState& camera,
                               const float viewport_width, const float viewport_height) {
        RuntimeMapRenderer::render_farming(
            renderer, farming, crops,
            [&texture_lookup](const std::filesystem::path& path) -> const TextureAsset* {
                const auto found = texture_lookup.find(path.generic_string());
                return found == texture_lookup.end() ? nullptr : &found->second;
            },
            root, camera, viewport_width, viewport_height);
    }

    static void render_buildings(SDL_Renderer* renderer, const BuildingManager& manager,
                                 const BuildingCatalog& catalog, const LandManager& lands,
                                 const std::function<const TextureAsset*(const std::filesystem::path&)>& find_texture,
                                 const std::filesystem::path& asset_root, const CameraState& camera,
                                 const float viewport_width, const float viewport_height) {
        struct VisibleBuilding {
            const BuildingInstance* instance = nullptr;
            const BuildingDefinition* definition = nullptr;
            const TextureAsset* texture = nullptr;
            BuildingRotation visual_rotation = BuildingRotation::r0;
            BuildingSpriteGeometry geometry{};
            float depth = 0.0F;
        };

        std::vector<VisibleBuilding> visible_instances;
        visible_instances.reserve(manager.instances().size());
        for (const BuildingInstance& instance : manager.instances()) {
            const BuildingDefinition* definition = catalog.find(instance.definition_id);
            if (definition == nullptr) continue;
            const BuildingRotation visual_rotation = runtime_render_detail::camera_visual_rotation(
                *definition, instance.rotation, camera.rotation);
            const TextureAsset* texture = find_texture(
                asset_root / definition->texture_path_for(visual_rotation, instance.current_level));
            if (texture == nullptr || texture->texture == nullptr) continue;

            const BuildingSpriteGeometry geometry = MapRenderer::building_sprite_geometry(
                *definition, instance, visual_rotation, texture->source_width, texture->source_height,
                camera, viewport_width, viewport_height);
            if (!runtime_render_detail::rect_visible(geometry.sprite_bounds, viewport_width, viewport_height)) {
                continue;
            }
            visible_instances.push_back({
                &instance,
                definition,
                texture,
                visual_rotation,
                geometry,
                camera_depth_key(geometry.ground_world.x, geometry.ground_world.y, camera),
            });
        }

        std::sort(visible_instances.begin(), visible_instances.end(), [](const VisibleBuilding& left,
                                                                        const VisibleBuilding& right) {
            if (left.depth != right.depth) return left.depth < right.depth;
            return left.instance->instance_id < right.instance->instance_id;
        });

        for (const VisibleBuilding& entry : visible_instances) {
            const BuildingInstance& instance = *entry.instance;
            const BuildingDefinition& definition = *entry.definition;
            const bool is_owned = lands.is_tile_owned(instance.tile_x, instance.tile_y);
            const Uint8 red = is_owned ? 255 : 140;
            const Uint8 green = is_owned ? 255 : 145;
            const Uint8 blue = is_owned ? 255 : 155;
            MapRenderer::render_building(renderer, definition, instance, entry.visual_rotation,
                entry.texture->texture, entry.texture->source_width, entry.texture->source_height,
                camera, viewport_width, viewport_height, SDL_ALPHA_OPAQUE, red, green, blue);

            if (!instance.activity_active() || !definition.activity_overlay.has_value() ||
                !definition.activity_overlay->enabled) {
                continue;
            }
            const BuildingActivityOverlayDefinition& activity = *definition.activity_overlay;
            const std::size_t rotation_index = static_cast<std::size_t>(entry.visual_rotation);
            if (rotation_index >= activity.sprite_paths.size() || activity.sprite_paths[rotation_index].empty()) {
                continue;
            }
            const TextureAsset* overlay_texture = find_texture(asset_root / activity.sprite_paths[rotation_index]);
            if (overlay_texture == nullptr || overlay_texture->texture == nullptr) continue;

            SDL_Texture* overlay = overlay_texture->texture;
            SDL_SetTextureAlphaMod(overlay, SDL_ALPHA_OPAQUE);
            SDL_SetTextureColorMod(overlay, 255, 255, 255);

            if (activity.animation.has_value() && activity.animation->frame_count > 1) {
                const BuildingAnimationDefinition& animation = *activity.animation;
                const int frame_count = std::max(1, animation.frame_count);
                const int duration_ms = std::max(1, animation.frame_duration_ms);
                int frame_index = 0;

                if (animation.playback == "ambient_once") {
                    const int idle_frame = std::clamp(animation.idle_frame, 0, frame_count - 1);
                    const int action_start = std::clamp(animation.action_start_frame, 0, frame_count - 1);
                    const int action_count = std::clamp(animation.action_frame_count, 0, frame_count - action_start);
                    frame_index = idle_frame;
                    if (action_count > 0) {
                        const std::uint64_t idle_hold_ms = static_cast<std::uint64_t>(
                            std::max(0, animation.idle_hold_ms));
                        const std::uint64_t action_duration_ms =
                            static_cast<std::uint64_t>(action_count) * static_cast<std::uint64_t>(duration_ms);
                        const std::uint64_t cycle_duration_ms = idle_hold_ms + action_duration_ms;
                        const std::uint64_t phase_ms = cycle_duration_ms > 0
                            ? (static_cast<std::uint64_t>(SDL_GetTicks()) + instance.instance_id * 977ULL) % cycle_duration_ms
                            : 0;
                        if (phase_ms >= idle_hold_ms && action_duration_ms > 0) {
                            frame_index = action_start + std::min(
                                action_count - 1,
                                static_cast<int>((phase_ms - idle_hold_ms) /
                                                 static_cast<std::uint64_t>(duration_ms)));
                        }
                    }
                } else {
                    frame_index = static_cast<int>((SDL_GetTicks() / duration_ms) % frame_count);
                }

                const float frame_width = overlay_texture->source_width / static_cast<float>(frame_count);
                const SDL_FRect source = {
                    frame_width * frame_index,
                    0.0F,
                    frame_width,
                    overlay_texture->source_height,
                };
                SDL_RenderTexture(renderer, overlay, &source, &entry.geometry.sprite_bounds);
            } else {
                SDL_RenderTexture(renderer, overlay, nullptr, &entry.geometry.sprite_bounds);
            }

            SDL_SetTextureColorMod(overlay, 255, 255, 255);
            SDL_SetTextureAlphaMod(overlay, SDL_ALPHA_OPAQUE);
        }
    }
};

}  // namespace ch
