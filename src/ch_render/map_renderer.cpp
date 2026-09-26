#include "src/ch_render/map_renderer.h"
#include "src/ch_render/semantic_renderer.h"
#include "src/ch_core/shoreline_autotile.h"
#include "src/ch_core/ground_surface.h"
#include "src/ch_render/shoreline_catalog.h"
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <iomanip>
#include <sstream>

namespace ch {

namespace {

struct WaterSurfaceTileEntry {
    int tile_x = 0;
    int tile_y = 0;
    bool shallow = false;
};

struct ShorelineOverlayEntry {
    int tile_x = 0;
    int tile_y = 0;
    const TextureAsset* texture = nullptr;
};

struct GroundSurfaceTileEntry {
    int tile_x = 0;
    int tile_y = 0;
    TileConnectionMask connections = 0;
};

constexpr float kTileWidth = static_cast<float>(contracts::kTileWidth);
constexpr float kGrassOpaqueLeft = 53.0F;
constexpr float kGrassOpaqueTop = 23.0F;
constexpr float kGrassOpaqueWidth = 1175.0F;


constexpr TileCoordinate road_access_offset(const GridDirection direction) {
    switch (direction) {
        case GridDirection::north: return {0, -1};
        case GridDirection::east: return {1, 0};
        case GridDirection::south: return {0, 1};
        case GridDirection::west: return {-1, 0};
    }
    return {};
}

std::string dirt_path_sprite(const TileConnectionMask mask) {
    static constexpr std::array<const char*, 16> kSprites = {
        "dirt_path_00_isolated.png", "dirt_path_01_end_n.png", "dirt_path_02_end_e.png", "dirt_path_03_curve_ne.png",
        "dirt_path_04_end_s.png", "dirt_path_05_straight_ns.png", "dirt_path_06_curve_es.png", "dirt_path_07_tee_no_w.png",
        "dirt_path_08_end_w.png", "dirt_path_09_curve_nw.png", "dirt_path_10_straight_ew.png", "dirt_path_11_tee_no_s.png",
        "dirt_path_12_curve_sw.png", "dirt_path_13_tee_no_e.png", "dirt_path_14_tee_no_n.png", "dirt_path_15_cross.png",
    };
    return "assets/terrain/paths/dirt_01/" + std::string(kSprites.at(static_cast<std::size_t>(mask)));
}

SDL_FColor road_placeholder_color(const RoadVisualType type) {
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

constexpr CardinalDirection camera_visual_direction(const CardinalDirection direction, const CameraRotation rotation) {
    const int index = static_cast<int>(direction);
    const int visual_index = (index - static_cast<int>(rotation) + 4) % 4;
    return static_cast<CardinalDirection>(visual_index);
}

BuildingRotation camera_visual_rotation(const BuildingDefinition& definition, const BuildingRotation logical_rotation,
                                       const CameraRotation camera_rotation) {
    const int visual = (static_cast<int>(logical_rotation) - static_cast<int>(camera_rotation) + 4) % 4;
    const BuildingRotation desired = static_cast<BuildingRotation>(visual);
    return definition.supports_rotation(desired) ? desired : logical_rotation;
}

TileConnectionMask camera_visual_connections(const TileConnectionMask connections, const CameraRotation rotation) {
    TileConnectionMask visual = 0;
    for (const CardinalDirection direction : kCardinalDirections) {
        if (has_connection(connections, direction)) visual |= connection_bit(camera_visual_direction(direction, rotation));
    }
    return visual;
}

std::string sidewalk_sprite(const std::string& style_id, const TileConnectionMask connections) {
    // Old saves may refer to concrete styles whose sprites were never shipped.
    // Keep those walkable cells visible until approved concrete art is promoted.
    if (style_id == "cement_path" || style_id == "concrete_01") {
        return dirt_path_sprite(connections);
    }
    if (style_id == "dirt_path") {
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

} // namespace

void MapRenderer::render_tile_outline(SDL_Renderer* renderer, const int x, const int y, const CameraState& camera,
                                      const float viewport_width, const float viewport_height) {
    const ScreenPoint top = world_to_screen_point(static_cast<float>(x), static_cast<float>(y), camera, viewport_width, viewport_height);
    const ScreenPoint right = world_to_screen_point(static_cast<float>(x + 1), static_cast<float>(y), camera, viewport_width, viewport_height);
    const ScreenPoint bottom = world_to_screen_point(static_cast<float>(x + 1), static_cast<float>(y + 1), camera, viewport_width, viewport_height);
    const ScreenPoint left = world_to_screen_point(static_cast<float>(x), static_cast<float>(y + 1), camera, viewport_width, viewport_height);

    SDL_RenderLine(renderer, top.x, top.y, right.x, right.y);
    SDL_RenderLine(renderer, right.x, right.y, bottom.x, bottom.y);
    SDL_RenderLine(renderer, bottom.x, bottom.y, left.x, left.y);
    SDL_RenderLine(renderer, left.x, left.y, top.x, top.y);
}

void MapRenderer::render_footprint_outline(SDL_Renderer* renderer, const BuildingDefinition& definition, const BuildingRotation rotation,
                                          const int tile_x, const int tile_y, const CameraState& camera,
                                          const float viewport_width, const float viewport_height,
                                          const Uint8 red, const Uint8 green, const Uint8 blue) {
    SDL_SetRenderDrawColor(renderer, red, green, blue, SDL_ALPHA_OPAQUE);
    const BuildingFootprint footprint = rotated_footprint(definition, rotation);
    for (int offset_y = 0; offset_y < footprint.height; ++offset_y) {
        for (int offset_x = 0; offset_x < footprint.width; ++offset_x) {
            render_tile_outline(renderer, tile_x + offset_x, tile_y + offset_y, camera, viewport_width, viewport_height);
        }
    }
}

void MapRenderer::render_tile_fill(SDL_Renderer* renderer, const int tile_x, const int tile_y, const CameraState& camera,
                                  const float viewport_width, const float viewport_height, const SDL_FColor color) {
    const ScreenPoint top = world_to_screen_point(static_cast<float>(tile_x), static_cast<float>(tile_y), camera, viewport_width, viewport_height);
    const ScreenPoint right = world_to_screen_point(static_cast<float>(tile_x + 1), static_cast<float>(tile_y), camera, viewport_width, viewport_height);
    const ScreenPoint bottom = world_to_screen_point(static_cast<float>(tile_x + 1), static_cast<float>(tile_y + 1), camera, viewport_width, viewport_height);
    const ScreenPoint left = world_to_screen_point(static_cast<float>(tile_x), static_cast<float>(tile_y + 1), camera, viewport_width, viewport_height);
    SDL_Vertex vertices[4] = {};
    vertices[0].position = {top.x, top.y};
    vertices[1].position = {right.x, right.y};
    vertices[2].position = {bottom.x, bottom.y};
    vertices[3].position = {left.x, left.y};
    for (SDL_Vertex& vertex : vertices) {
        vertex.color = color;
    }
    const int indices[] = {0, 1, 2, 0, 2, 3};
    (void)SDL_RenderGeometry(renderer, nullptr, vertices, 4, indices, 6);
}

void MapRenderer::render_road_tile(SDL_Renderer* renderer, const int tile_x, const int tile_y, const CameraState& camera,
                                  const float viewport_width, const float viewport_height, const SDL_FColor color) {
    render_tile_fill(renderer, tile_x, tile_y, camera, viewport_width, viewport_height, color);
    SDL_SetRenderDrawColor(renderer, 45, 54, 57, static_cast<Uint8>(color.a * 255.0F));
    render_tile_outline(renderer, tile_x, tile_y, camera, viewport_width, viewport_height);
}

void MapRenderer::render_road_access_candidates(SDL_Renderer* renderer, const BuildingDefinition& definition,
                                               const BuildingRotation rotation, const int tile_x, const int tile_y,
                                               const RoadManager& roads, const CameraState& camera,
                                               const float viewport_width, const float viewport_height) {
    if (!definition.requires_road_access || resolved_road_access_mode(definition) == RoadAccessMode::any_perimeter) return;
    for (const BuildingAccessPoint& access : road_access_candidates(definition, rotation)) {
        const TileCoordinate offset = road_access_offset(access.facing);
        const int road_x = tile_x + access.local_x + offset.x;
        const int road_y = tile_y + access.local_y + offset.y;
        SDL_SetRenderDrawColor(renderer, roads.is_road(road_x, road_y) ? 112 : 255,
                               roads.is_road(road_x, road_y) ? 232 : 160, 96, SDL_ALPHA_OPAQUE);
        render_tile_outline(renderer, road_x, road_y, camera, viewport_width, viewport_height);
    }
}

void MapRenderer::render_grass_tile(SDL_Renderer* renderer, const TextureAsset& grass, const int x, const int y,
                                    const CameraState& camera, const float viewport_width, const float viewport_height) {
    const WorldPoint visual_top = tile_visual_top_world(x, y, camera.rotation);
    const ScreenPoint top = world_to_screen_point(visual_top.x, visual_top.y, camera, viewport_width, viewport_height);
    const float scale = (kTileWidth / kGrassOpaqueWidth) * camera.zoom;
    const SDL_FRect destination = {
        top.x - (kTileWidth * camera.zoom * 0.5F) - (kGrassOpaqueLeft * scale),
        top.y - (kGrassOpaqueTop * scale),
        grass.source_width * scale,
        grass.source_height * scale,
    };
    SDL_RenderTexture(renderer, grass.texture, nullptr, &destination);
}

void MapRenderer::render_custom_terrain_tile(SDL_Renderer* renderer, const TextureAsset& texture, const int x, const int y,
                                           const CameraState& camera, const float viewport_width, const float viewport_height) {
    const WorldPoint visual_top = tile_visual_top_world(x, y, camera.rotation);
    const ScreenPoint top = world_to_screen_point(visual_top.x, visual_top.y, camera, viewport_width, viewport_height);
    const float scale = (kTileWidth / static_cast<float>(texture.source_width)) * camera.zoom;
    const SDL_FRect destination = {
        top.x - (kTileWidth * camera.zoom * 0.5F),
        top.y,
        texture.source_width * scale,
        texture.source_height * scale,
    };
    SDL_RenderTexture(renderer, texture.texture, nullptr, &destination);
}

void MapRenderer::render_water_caustics_overlay_tile(SDL_Renderer* renderer, const TextureAsset& overlay,
                                                     const int x, const int y, const CameraState& camera,
                                                     const float viewport_width, const float viewport_height,
                                                     const float world_period) {
    if (overlay.texture == nullptr || world_period <= 0.0F) return;

    const WorldPoint top_world = camera_view_point(static_cast<float>(x), static_cast<float>(y), camera.rotation);
    const WorldPoint right_world = camera_view_point(static_cast<float>(x + 1), static_cast<float>(y), camera.rotation);
    const WorldPoint bottom_world = camera_view_point(static_cast<float>(x + 1), static_cast<float>(y + 1), camera.rotation);
    const WorldPoint left_world = camera_view_point(static_cast<float>(x), static_cast<float>(y + 1), camera.rotation);
    const ScreenPoint top = world_to_screen_point(static_cast<float>(x), static_cast<float>(y), camera, viewport_width, viewport_height);
    const ScreenPoint right = world_to_screen_point(static_cast<float>(x + 1), static_cast<float>(y), camera, viewport_width, viewport_height);
    const ScreenPoint bottom = world_to_screen_point(static_cast<float>(x + 1), static_cast<float>(y + 1), camera, viewport_width, viewport_height);
    const ScreenPoint left = world_to_screen_point(static_cast<float>(x), static_cast<float>(y + 1), camera, viewport_width, viewport_height);

    // The current pilot stays within one period.  fmod keeps the method valid
    // for an unbounded world while preserving the same UV at a shared edge.
    const auto wrap = [world_period](const float value) {
        const float result = std::fmod(value, world_period);
        return result < 0.0F ? result + world_period : result;
    };
    const auto uv = [&wrap, world_period](const WorldPoint point) {
        // Centre world origin within the repeat domain rather than putting a
        // pilot boundary on zero.  The generated overlay itself is seamless
        // at the period boundary.
        return SDL_FPoint{wrap(point.x + world_period * 0.5F) / world_period,
                          wrap(point.y + world_period * 0.5F) / world_period};
    };
    SDL_Vertex vertices[4] = {};
    vertices[0].position = {top.x, top.y};
    vertices[1].position = {right.x, right.y};
    vertices[2].position = {bottom.x, bottom.y};
    vertices[3].position = {left.x, left.y};
    vertices[0].tex_coord = uv(top_world);
    vertices[1].tex_coord = uv(right_world);
    vertices[2].tex_coord = uv(bottom_world);
    vertices[3].tex_coord = uv(left_world);
    for (SDL_Vertex& vertex : vertices) vertex.color = {1.0F, 1.0F, 1.0F, 1.0F};
    const int indices[] = {0, 1, 2, 0, 2, 3};
    (void)SDL_RenderGeometry(renderer, overlay.texture, vertices, 4, indices, 6);
}

void MapRenderer::render_map(SDL_Renderer* renderer, const TextureAsset* grass,
                            const std::unordered_map<std::uint64_t, const TextureAsset*>& scenario_terrain_textures,
                            const CameraState& camera, const float viewport_width, const float viewport_height) {
    SDL_SetRenderDrawColor(renderer, 74, 104, 83, SDL_ALPHA_OPAQUE);
    const SDL_FRect background = {0.0F, 0.0F, viewport_width, viewport_height};
    SDL_RenderFillRect(renderer, &background);

    if (grass == nullptr) {
        SDL_SetRenderDrawColor(renderer, 117, 148, 122, 115);
        for (int y = contracts::kMapMin; y <= contracts::kMapMax; ++y) {
            for (int x = contracts::kMapMin; x <= contracts::kMapMax; ++x) {
                render_tile_outline(renderer, x, y, camera, viewport_width, viewport_height);
            }
        }
        return;
    }

    for (int depth = contracts::kMapMin * 2; depth <= contracts::kMapMax * 2; ++depth) {
        const int first_x = std::max(contracts::kMapMin, depth - contracts::kMapMax);
        const int last_x = std::min(contracts::kMapMax, depth - contracts::kMapMin);
        for (int x = first_x; x <= last_x; ++x) {
            const int y = depth - x;
            const std::uint64_t key = (static_cast<std::uint64_t>(static_cast<std::uint32_t>(x)) << 32) |
                                      static_cast<std::uint32_t>(y);
            const auto it = scenario_terrain_textures.find(key);
            if (it != scenario_terrain_textures.end() && it->second != nullptr) {
                render_custom_terrain_tile(renderer, *it->second, x, y, camera, viewport_width, viewport_height);
            } else {
                render_grass_tile(renderer, *grass, x, y, camera, viewport_width, viewport_height);
            }
        }
    }
}

void MapRenderer::render_world_terrain_and_water(
    SDL_Renderer* renderer,
    const MapDocument& document,
    const std::function<const TextureAsset*(const std::filesystem::path&)>& find_texture,
    const std::filesystem::path& asset_root,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height,
    const float render_time
) {
    if (renderer == nullptr) return;

    const TextureAsset* grass_base = find_texture("assets/terrain/grass_isometric_01.png");

    std::unordered_map<std::uint64_t, const TextureAsset*> scenario_terrain_textures;
    std::vector<WaterSurfaceTileEntry> water_tiles;
    std::vector<GroundSurfaceTileEntry> dirt_path_tiles;

    for (const auto& tile : document.terrain_tiles()) {
        const std::uint64_t key = tile_key(tile.tile_x, tile.tile_y);
        if (!tile.texture.empty()) {
            if (const TextureAsset* tex = find_texture(tile.texture)) {
                scenario_terrain_textures[key] = tex;
            }
        }
        // Old scenario JSON references an untracked coast_adjusted directory.
        // Preserve its semantic sand cells with the shipped 128x64 tile.
        if (!scenario_terrain_textures.contains(key) &&
            (tile.terrain_definition == "sand" || tile.terrain_definition == "sand_center" ||
             tile.terrain_definition == "sand_wet")) {
            if (const TextureAsset* sand = find_texture("assets/terrain/sand_isometric_01.png"))
                scenario_terrain_textures[key] = sand;
        }

        // Runtime water identity is semantic, never derived from a filename or pixels.
        const bool shallow = tile.terrain_definition == "water_shallow" || tile.terrain_definition == "ocean_shallow";
        const bool deep = tile.terrain_definition == "water_deep" || tile.terrain_definition == "ocean_deep";
        const bool is_water = shallow || deep;

        if (is_water) {
            water_tiles.push_back({tile.tile_x, tile.tile_y, shallow});
        }

        if (is_connectable_ground_surface(tile)) {
            dirt_path_tiles.push_back({tile.tile_x, tile.tile_y,
                ground_surface_connection_mask(document, tile.tile_x, tile.tile_y, tile.terrain_definition)});
        }
    }

    std::sort(water_tiles.begin(), water_tiles.end(), [](const WaterSurfaceTileEntry& left, const WaterSurfaceTileEntry& right) {
        const int left_depth = left.tile_x + left.tile_y;
        const int right_depth = right.tile_x + right.tile_y;
        return left_depth == right_depth ? left.tile_x < right.tile_x : left_depth < right_depth;
    });

    std::vector<ShorelineOverlayEntry> shoreline_overlays;
    SemanticWorldView world;
    world.map_document = &document;

    GridBounds bounds;
    if (!document.terrain_tiles().empty()) {
        bounds.min_x = document.terrain_tiles()[0].tile_x;
        bounds.max_x = document.terrain_tiles()[0].tile_x;
        bounds.min_y = document.terrain_tiles()[0].tile_y;
        bounds.max_y = document.terrain_tiles()[0].tile_y;
        for (const auto& t : document.terrain_tiles()) {
            bounds.min_x = std::min(bounds.min_x, t.tile_x);
            bounds.max_x = std::max(bounds.max_x, t.tile_x);
            bounds.min_y = std::min(bounds.min_y, t.tile_y);
            bounds.max_y = std::max(bounds.max_y, t.tile_y);
        }
    } else {
        bounds.min_x = contracts::kMapMin;
        bounds.max_x = contracts::kMapMax;
        bounds.min_y = contracts::kMapMin;
        bounds.max_y = contracts::kMapMax;
    }

    AutotileResult autotile_res = ShorelineAutotiler::evaluate_shoreline(world, bounds);

    for (const auto& edit : autotile_res.edits) {
        for (const auto piece : edit.recipe.pieces) {
            const std::string piece_path = ShorelineCatalog::get_piece_texture_path(piece, "coast_adjusted");
            if (const TextureAsset* tex = find_texture(piece_path)) {
                shoreline_overlays.push_back({edit.tile.x, edit.tile.y, tex});
            }
        }
    }

    const TextureAsset* water_caustics = find_texture("assets/terrain/coast_adjusted/water_caustics_01.png");
    if (water_caustics == nullptr) {
        water_caustics = find_texture("assets/terrain/coast_adjusted/water_caustics_overlay_01.png");
    }

    // Canonical Layer Execution:
    // 1. Terrain Base
    render_map(renderer, grass_base, scenario_terrain_textures, camera, viewport_width, viewport_height);

    // 1.5 Ground paths. Their connection mask comes from neighbouring
    // ground terrain, never RoadManager. First paint an opaque soil underlay:
    // it owns every shared raster edge, so adjacent sprites cannot reveal a
    // grass/alpha hairline at any camera zoom.
    constexpr SDL_FColor kDirtUnderlay = {0.50F, 0.35F, 0.20F, 1.0F};
    for (const auto& tile : dirt_path_tiles) {
        render_tile_fill(renderer, tile.tile_x, tile.tile_y, camera, viewport_width, viewport_height, kDirtUnderlay);
    }
    for (const auto& tile : dirt_path_tiles) {
        const TileConnectionMask visual_connections = camera_visual_connections(tile.connections, camera.rotation);
        if (const TextureAsset* sprite = find_texture(dirt_path_sprite(visual_connections))) {
            render_custom_terrain_tile(renderer, *sprite, tile.tile_x, tile.tile_y, camera, viewport_width, viewport_height);
        }
    }

    // 2. Water Base (Shallow / Deep)
    constexpr SDL_FColor kDeepBase = {108.0F / 255.0F, 196.0F / 255.0F, 207.0F / 255.0F, 1.0F};
    constexpr SDL_FColor kShallowBase = {115.0F / 255.0F, 200.0F / 255.0F, 210.0F / 255.0F, 1.0F};
    for (const auto& tile : water_tiles) {
        render_tile_fill(renderer, tile.tile_x, tile.tile_y, camera, viewport_width, viewport_height,
                         tile.shallow ? kShallowBase : kDeepBase);
    }

    // 3. Continuous Caustics Overlay
    if (water_caustics != nullptr) {
        for (const auto& tile : water_tiles) {
            render_water_caustics_overlay_tile(renderer, *water_caustics, tile.tile_x, tile.tile_y, camera, viewport_width, viewport_height);
        }
    }

    // 4. Shoreline Edges / Corners
    for (const auto& overlay : shoreline_overlays) {
        if (overlay.texture != nullptr) {
            render_custom_terrain_tile(renderer, *overlay.texture, overlay.tile_x, overlay.tile_y, camera, viewport_width, viewport_height);
        }
    }
}

void MapRenderer::render_road_sprite(SDL_Renderer* renderer, const TextureAsset& texture, const int tile_x, const int tile_y,
                                    const CameraState& camera, const float viewport_width, const float viewport_height) {
    const WorldPoint visual_top = tile_visual_top_world(tile_x, tile_y, camera.rotation);
    const ScreenPoint top = world_to_screen_point(visual_top.x, visual_top.y, camera, viewport_width, viewport_height);
    const float destination_height = kTileWidth * camera.zoom * texture.source_height / texture.source_width;
    const SDL_FRect destination = {
        top.x - kTileWidth * camera.zoom * 0.5F,
        top.y,
        kTileWidth * camera.zoom,
        destination_height,
    };
    SDL_RenderTexture(renderer, texture.texture, nullptr, &destination);
}

void MapRenderer::render_roads(SDL_Renderer* renderer, const RoadManager& roads, const RoadVisualCatalog& visuals,
                              const std::function<const TextureAsset*(const std::filesystem::path&)>& find_texture,
                              const std::filesystem::path& asset_root, const CameraState& camera,
                              const float viewport_width, const float viewport_height) {
    std::vector<const RoadTile*> sorted_tiles;
    sorted_tiles.reserve(roads.tiles().size());
    for (const RoadTile& tile : roads.tiles()) sorted_tiles.push_back(&tile);
    std::sort(sorted_tiles.begin(), sorted_tiles.end(), [&camera](const RoadTile* left, const RoadTile* right) {
        const float left_depth = camera_depth_key(static_cast<float>(left->tile_x + 1), static_cast<float>(left->tile_y + 1), camera);
        const float right_depth = camera_depth_key(static_cast<float>(right->tile_x + 1), static_cast<float>(right->tile_y + 1), camera);
        if (left_depth != right_depth) return left_depth < right_depth;
        if (left->tile_y != right->tile_y) return left->tile_y < right->tile_y;
        return left->tile_x < right->tile_x;
    });
    // Draw the asphalt below the whole connected network first. At fractional
    // zoom, two antialiased PNG edges can leave a subpixel gap on their shared
    // side; the matching asphalt underlay keeps terrain from showing through.
    constexpr SDL_FColor kRoadAsphalt = {52.0F / 255.0F, 57.0F / 255.0F, 60.0F / 255.0F, 1.0F};
    for (const RoadTile* tile : sorted_tiles) {
        render_tile_fill(renderer, tile->tile_x, tile->tile_y, camera, viewport_width, viewport_height, kRoadAsphalt);
    }
    for (const RoadTile* tile : sorted_tiles) {
        const RoadVisual* visual = visuals.get_for_mask(camera_visual_connections(tile->connections, camera.rotation));
        const TextureAsset* texture = visual == nullptr ? nullptr : find_texture(asset_root / visual->texture_path);
        if (texture != nullptr) {
            render_road_sprite(renderer, *texture, tile->tile_x, tile->tile_y, camera, viewport_width, viewport_height);
        } else {
            render_road_tile(renderer, tile->tile_x, tile->tile_y, camera, viewport_width, viewport_height,
                             road_placeholder_color(roads.visual_type(tile->tile_x, tile->tile_y)));
        }
    }
}

void MapRenderer::render_sidewalks(SDL_Renderer* renderer, const SidewalkManager& sidewalks,
                                  const std::function<const TextureAsset*(const std::filesystem::path&)>& find_texture,
                                  const std::filesystem::path& asset_root, const CameraState& camera,
                                  const float viewport_width, const float viewport_height) {
    for (const SidewalkTile& tile : sidewalks.tiles()) {
        const TileConnectionMask visual_connections = camera_visual_connections(tile.connections, camera.rotation);
        if (const TextureAsset* texture = find_texture(asset_root / sidewalk_sprite(tile.style_id, visual_connections))) {
            const WorldPoint visual_top = tile_visual_top_world(tile.tile_x, tile.tile_y, camera.rotation);
            const ScreenPoint top = world_to_screen_point(visual_top.x, visual_top.y, camera, viewport_width, viewport_height);
            const float scale = (kTileWidth / texture->source_width) * camera.zoom;
            const SDL_FRect dst{top.x - texture->source_width * scale * 0.5F, top.y, texture->source_width * scale, texture->source_height * scale};
            SDL_RenderTexture(renderer, texture->texture, nullptr, &dst);
        }
    }
}

BuildingSpriteGeometry MapRenderer::building_sprite_geometry(const BuildingDefinition& definition,
                                                             const BuildingInstance& instance,
                                                             const BuildingRotation visual_rotation,
                                                             const float source_width, const float source_height,
                                                             const CameraState& camera,
                                                             const float viewport_width, const float viewport_height) {
    const BuildingFootprint footprint = rotated_footprint(definition, instance.rotation);
    const WorldPoint ground = building_visual_ground_world(instance.tile_x, instance.tile_y, footprint.width, footprint.height, camera.rotation);
    const ScreenPoint anchor_sp = world_to_screen_point(ground.x, ground.y, camera, viewport_width, viewport_height);
    const SDL_FPoint anchor = {anchor_sp.x, anchor_sp.y};

    const float frame_w = (definition.animation.has_value() && definition.animation->frame_count > 1)
        ? source_width / static_cast<float>(definition.animation->frame_count)
        : source_width;
    const float frame_h = source_height;

    const float scale = definition.art_scale * camera.zoom;
    const SDL_FRect bounds = {
        anchor.x - frame_w * scale * definition.anchor_x_for(visual_rotation, instance.current_level),
        anchor.y - frame_h * scale * definition.anchor_y_for(visual_rotation, instance.current_level),
        frame_w * scale,
        frame_h * scale,
    };
    return {ground, anchor, bounds};
}

void MapRenderer::render_building(SDL_Renderer* renderer, const BuildingDefinition& definition, const BuildingInstance& instance,
                                  const BuildingRotation visual_rotation, SDL_Texture* texture, const float source_width, const float source_height,
                                  const CameraState& camera, const float viewport_width, const float viewport_height,
                                  const Uint8 alpha, const Uint8 red, const Uint8 green, const Uint8 blue) {
    if (texture == nullptr) return;

    const BuildingSpriteGeometry geometry = building_sprite_geometry(definition, instance, visual_rotation,
                                                                       source_width, source_height,
                                                                       camera, viewport_width, viewport_height);
    SDL_SetTextureAlphaMod(texture, alpha);
    SDL_SetTextureColorMod(texture, red, green, blue);

    if (definition.animation.has_value() && definition.animation->frame_count > 1) {
        const BuildingAnimationDefinition& animation = *definition.animation;
        const int frame_count = std::max(1, animation.frame_count);
        const int duration_ms = std::max(1, animation.frame_duration_ms);
        int frame_index = 0;

        if (animation.playback == "ambient_once") {
            const int idle_frame = std::clamp(animation.idle_frame, 0, frame_count - 1);
            const int action_start = std::clamp(animation.action_start_frame, 0, frame_count - 1);
            const int action_count = std::clamp(animation.action_frame_count, 0, frame_count - action_start);
            frame_index = idle_frame;

            if (action_count > 0) {
                const std::uint64_t idle_hold_ms = static_cast<std::uint64_t>(std::max(0, animation.idle_hold_ms));
                const std::uint64_t action_duration_ms =
                    static_cast<std::uint64_t>(action_count) * static_cast<std::uint64_t>(duration_ms);
                const std::uint64_t cycle_duration_ms = idle_hold_ms + action_duration_ms;
                // Stable per-instance staggering avoids a row of vendors waving
                // in perfect synchrony while remaining deterministic across runs.
                const std::uint64_t instance_offset_ms = instance.instance_id * 977ULL;
                const std::uint64_t phase_ms = cycle_duration_ms > 0
                    ? (static_cast<std::uint64_t>(SDL_GetTicks()) + instance_offset_ms) % cycle_duration_ms
                    : 0;
                if (phase_ms >= idle_hold_ms && action_duration_ms > 0) {
                    const std::uint64_t action_elapsed_ms = phase_ms - idle_hold_ms;
                    const int action_index = std::min(
                        action_count - 1,
                        static_cast<int>(action_elapsed_ms / static_cast<std::uint64_t>(duration_ms)));
                    frame_index = action_start + action_index;
                }
            }
        } else if (animation.playback == "activity_loop") {
            frame_index = instance.activity_active()
                ? static_cast<int>((SDL_GetTicks() / duration_ms) % frame_count) : 0;
        } else {
            // Legacy behaviour: every multi-frame building keeps looping exactly
            // as before unless its data explicitly opts into ambient_once.
            frame_index = static_cast<int>((SDL_GetTicks() / duration_ms) % frame_count);
        }

        const float frame_w = source_width / static_cast<float>(frame_count);
        const float frame_h = source_height;
        const SDL_FRect src_rect = { frame_index * frame_w, 0.0F, frame_w, frame_h };
        SDL_RenderTexture(renderer, texture, &src_rect, &geometry.sprite_bounds);
    } else {
        SDL_RenderTexture(renderer, texture, nullptr, &geometry.sprite_bounds);
    }

    SDL_SetTextureColorMod(texture, 255, 255, 255);
    SDL_SetTextureAlphaMod(texture, SDL_ALPHA_OPAQUE);
}

void MapRenderer::render_land_overlays(SDL_Renderer* renderer, const LandManager& lands, const LandParcel* hovered_parcel,
                                      const bool land_mode, const CameraState& camera, const float viewport_width, const float viewport_height) {
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
        for (int y = std::max(contracts::kMapMin, parcel.origin_y); y <= std::min(contracts::kMapMax, parcel.origin_y + parcel.height - 1); ++y) {
            for (int x = std::max(contracts::kMapMin, parcel.origin_x); x <= std::min(contracts::kMapMax, parcel.origin_x + parcel.width - 1); ++x) {
                render_tile_fill(renderer, x, y, camera, viewport_width, viewport_height, color);
            }
        }
    }
}

void MapRenderer::render_farming(SDL_Renderer* renderer, const FarmingSystem& farming, const CropCatalog& crops,
                                const std::function<const TextureAsset*(const std::filesystem::path&)>& find_texture,
                                const std::filesystem::path& root, const CameraState& camera,
                                const float viewport_width, const float viewport_height) {
    // CH_FARM_GROUND_V2 stylized pass: simulation stays tile based while the
    // visual reads as one hand-painted 2D field. Crops remain hidden until the
    // ground itself passes the visual gate.
    (void)crops;
    (void)find_texture;
    (void)root;

    if (renderer == nullptr || farming.tiles().empty()) return;

    // Continuous world-space colour wash. Shared tile vertices sample the same
    // function, so neighbouring cells blend without exposing the logical grid.
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

    for (const FarmTile& tile : farming.tiles()) {
        const float x = static_cast<float>(tile.tile_x);
        const float y = static_cast<float>(tile.tile_y);
        const ScreenPoint top = world_to_screen_point(x, y, camera, viewport_width, viewport_height);
        const ScreenPoint right = world_to_screen_point(x + 1.0F, y, camera, viewport_width, viewport_height);
        const ScreenPoint bottom = world_to_screen_point(x + 1.0F, y + 1.0F, camera, viewport_width, viewport_height);
        const ScreenPoint left = world_to_screen_point(x, y + 1.0F, camera, viewport_width, viewport_height);

        SDL_Vertex vertices[4] = {};
        vertices[0].position = {top.x, top.y};
        vertices[1].position = {right.x, right.y};
        vertices[2].position = {bottom.x, bottom.y};
        vertices[3].position = {left.x, left.y};
        vertices[0].color = soil_color(x, y);
        vertices[1].color = soil_color(x + 1.0F, y);
        vertices[2].color = soil_color(x + 1.0F, y + 1.0F);
        vertices[3].color = soil_color(x, y + 1.0F);
        const int indices[] = {0, 1, 2, 0, 2, 3};
        (void)SDL_RenderGeometry(renderer, nullptr, vertices, 4, indices, 6);
    }

    // Graphic 2D furrows: a soft highlight paired with a darker ink-like line.
    // Both span complete farm runs, so they never restart at tile boundaries.
    constexpr std::array<float, 5> kFurrowOffsets = {0.10F, 0.30F, 0.50F, 0.70F, 0.90F};
    constexpr float kHighlightOffset = 0.025F;

    for (const FarmTile& tile : farming.tiles()) {
        if (farming.is_occupied(tile.tile_x - 1, tile.tile_y)) continue;

        int run_end_x = tile.tile_x;
        while (farming.is_occupied(run_end_x + 1, tile.tile_y)) {
            ++run_end_x;
        }

        for (const float offset : kFurrowOffsets) {
            const ScreenPoint highlight_start = world_to_screen_point(
                static_cast<float>(tile.tile_x),
                static_cast<float>(tile.tile_y) + offset - kHighlightOffset,
                camera, viewport_width, viewport_height);
            const ScreenPoint highlight_end = world_to_screen_point(
                static_cast<float>(run_end_x + 1),
                static_cast<float>(tile.tile_y) + offset - kHighlightOffset,
                camera, viewport_width, viewport_height);
            SDL_SetRenderDrawColor(renderer, 154, 108, 68, 88);
            SDL_RenderLine(renderer, highlight_start.x, highlight_start.y, highlight_end.x, highlight_end.y);

            const ScreenPoint shadow_start = world_to_screen_point(
                static_cast<float>(tile.tile_x),
                static_cast<float>(tile.tile_y) + offset,
                camera, viewport_width, viewport_height);
            const ScreenPoint shadow_end = world_to_screen_point(
                static_cast<float>(run_end_x + 1),
                static_cast<float>(tile.tile_y) + offset,
                camera, viewport_width, viewport_height);
            SDL_SetRenderDrawColor(renderer, 78, 47, 29, 188);
            SDL_RenderLine(renderer, shadow_start.x, shadow_start.y, shadow_end.x, shadow_end.y);
        }
    }
}

void MapRenderer::render_farming(SDL_Renderer* renderer, const FarmingSystem& farming, const CropCatalog& crops,
                                const std::unordered_map<std::string, TextureAsset>& texture_lookup,
                                const std::filesystem::path& root, const CameraState& camera,
                                const float viewport_width, const float viewport_height) {
    return render_farming(renderer, farming, crops,
                          [&texture_lookup](const std::filesystem::path& p) -> const TextureAsset* {
                              const auto it = texture_lookup.find(p.generic_string());
                              return it != texture_lookup.end() ? &it->second : nullptr;
                          },
                          root, camera, viewport_width, viewport_height);
}

void MapRenderer::render_buildings(SDL_Renderer* renderer, const BuildingManager& manager, const BuildingCatalog& catalog,
                                  const LandManager& lands,
                                  const std::function<const TextureAsset*(const std::filesystem::path&)>& find_texture,
                                  const std::filesystem::path& asset_root,
                                  const CameraState& camera, const float viewport_width, const float viewport_height) {
    std::vector<const BuildingInstance*> sorted_instances;
    sorted_instances.reserve(manager.instances().size());
    for (const BuildingInstance& instance : manager.instances()) {
        sorted_instances.push_back(&instance);
    }
    std::sort(sorted_instances.begin(), sorted_instances.end(), [&catalog, &camera](const BuildingInstance* left, const BuildingInstance* right) {
        const BuildingDefinition* left_definition = catalog.find(left->definition_id);
        const BuildingDefinition* right_definition = catalog.find(right->definition_id);
        const BuildingFootprint left_footprint = left_definition == nullptr ? BuildingFootprint{} : rotated_footprint(*left_definition, left->rotation);
        const BuildingFootprint right_footprint = right_definition == nullptr ? BuildingFootprint{} : rotated_footprint(*right_definition, right->rotation);
        const WorldPoint left_ground = building_visual_ground_world(left->tile_x, left->tile_y, left_footprint.width, left_footprint.height, camera.rotation);
        const WorldPoint right_ground = building_visual_ground_world(right->tile_x, right->tile_y, right_footprint.width, right_footprint.height, camera.rotation);
        const float left_depth = camera_depth_key(left_ground.x, left_ground.y, camera);
        const float right_depth = camera_depth_key(right_ground.x, right_ground.y, camera);
        return left_depth == right_depth ? left->instance_id < right->instance_id : left_depth < right_depth;
    });

    for (const BuildingInstance* instance : sorted_instances) {
        const BuildingDefinition* definition = catalog.find(instance->definition_id);
        if (definition == nullptr) continue;
        const BuildingRotation visual_rot = camera_visual_rotation(*definition, instance->rotation, camera.rotation);
        const TextureAsset* texture = find_texture(asset_root / definition->texture_path_for(visual_rot, instance->current_level));
        if (texture != nullptr) {
            const bool is_owned = lands.is_tile_owned(instance->tile_x, instance->tile_y);
            const Uint8 r = is_owned ? 255 : 140;
            const Uint8 g = is_owned ? 255 : 145;
            const Uint8 b = is_owned ? 255 : 155;
            render_building(renderer, *definition, *instance, visual_rot, texture->texture, texture->source_width, texture->source_height,
                            camera, viewport_width, viewport_height, SDL_ALPHA_OPAQUE, r, g, b);


            // CH_BUILDING_ACTIVITY_OVERLAY_V1: transparent temporary effects are
            // rendered over the approved base sprite only while the instance is active.
            if (instance->activity_active() && definition->activity_overlay.has_value() &&
                definition->activity_overlay->enabled) {
                const BuildingActivityOverlayDefinition& activity = *definition->activity_overlay;
                const std::size_t activity_rotation = static_cast<std::size_t>(visual_rot);
                if (activity_rotation < activity.sprite_paths.size() &&
                    !activity.sprite_paths[activity_rotation].empty()) {
                    const TextureAsset* overlay_texture =
                        find_texture(asset_root / activity.sprite_paths[activity_rotation]);
                    if (overlay_texture != nullptr) {
                        // Use the base sprite frame geometry so the effect shares the
                        // exact same ground anchor, scale and rotation alignment.
                        const BuildingSpriteGeometry geometry = building_sprite_geometry(
                            *definition, *instance, visual_rot,
                            texture->source_width, texture->source_height,
                            camera, viewport_width, viewport_height);
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
                                const int action_start = std::clamp(
                                    animation.action_start_frame, 0, frame_count - 1);
                                const int action_count = std::clamp(
                                    animation.action_frame_count, 0, frame_count - action_start);
                                frame_index = idle_frame;
                                if (action_count > 0) {
                                    const std::uint64_t idle_hold_ms = static_cast<std::uint64_t>(
                                        std::max(0, animation.idle_hold_ms));
                                    const std::uint64_t action_duration_ms =
                                        static_cast<std::uint64_t>(action_count) *
                                        static_cast<std::uint64_t>(duration_ms);
                                    const std::uint64_t cycle_duration_ms = idle_hold_ms + action_duration_ms;
                                    const std::uint64_t phase_ms = cycle_duration_ms > 0
                                        ? (static_cast<std::uint64_t>(SDL_GetTicks()) +
                                           instance->instance_id * 977ULL) % cycle_duration_ms
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

                            const float frame_width =
                                overlay_texture->source_width / static_cast<float>(frame_count);
                            const SDL_FRect source = {
                                frame_width * frame_index,
                                0.0F,
                                frame_width,
                                overlay_texture->source_height,
                            };
                            SDL_RenderTexture(renderer, overlay, &source, &geometry.sprite_bounds);
                        } else {
                            SDL_RenderTexture(renderer, overlay, nullptr, &geometry.sprite_bounds);
                        }

                        SDL_SetTextureColorMod(overlay, 255, 255, 255);
                        SDL_SetTextureAlphaMod(overlay, SDL_ALPHA_OPAQUE);
                    }
                }
            }
        }
    }
}

std::string RenderGeometrySignature::compute_hash() const {
    std::uint64_t hash = 14695981039346656037ULL;
    for (const auto& rec : records) {
        std::ostringstream ss;
        ss << rec.layer << ',' << rec.asset_id << ',' << rec.grid_x << ',' << rec.grid_y << ','
           << rec.screen_x << ',' << rec.screen_y << ',' << rec.dest_w << ',' << rec.dest_h << ','
           << rec.depth_key << ',' << rec.anchor_x << ',' << rec.anchor_y << ',' << rec.art_scale << ','
           << rec.footprint_w << ',' << rec.footprint_h << '\n';
        const std::string line = ss.str();
        for (const char c : line) {
            hash ^= static_cast<std::uint8_t>(c);
            hash *= 1099511628211ULL;
        }
    }
    std::ostringstream out;
    out << "FNV64:0x" << std::hex << std::uppercase << std::setfill('0') << std::setw(16) << hash;
    return out.str();
}

RenderGeometryDiff compare_signatures(const RenderGeometrySignature& game_sig,
                                     const RenderGeometrySignature& forge_sig) {
    if (game_sig.records.size() != forge_sig.records.size()) {
        std::ostringstream ss;
        ss << "CH_RENDER_DIVERGENCE: RECORD COUNT MISMATCH\n"
           << "game count: " << game_sig.records.size() << "\n"
           << "map_forge count: " << forge_sig.records.size() << "\n";
        return {false, ss.str()};
    }

    for (std::size_t i = 0; i < game_sig.records.size(); ++i) {
        const auto& g = game_sig.records[i];
        const auto& f = forge_sig.records[i];

        constexpr float kEps = 0.01F;
        bool diff = (g.asset_id != f.asset_id) || (g.grid_x != f.grid_x) || (g.grid_y != f.grid_y) ||
                    (std::abs(g.screen_x - f.screen_x) > kEps) || (std::abs(g.screen_y - f.screen_y) > kEps) ||
                    (std::abs(g.dest_w - f.dest_w) > kEps) || (std::abs(g.dest_h - f.dest_h) > kEps) ||
                    (std::abs(g.anchor_x - f.anchor_x) > kEps) || (std::abs(g.anchor_y - f.anchor_y) > kEps) ||
                    (std::abs(g.art_scale - f.art_scale) > kEps) || (std::abs(g.depth_key - f.depth_key) > kEps) ||
                    (g.footprint_w != f.footprint_w) || (g.footprint_h != f.footprint_h);

        if (diff) {
            std::ostringstream ss;
            ss << "CH_RENDER_DIVERGENCE\n"
               << "layer: " << g.layer << "\n"
               << "asset: " << g.asset_id << "\n"
               << "grid: " << g.grid_x << "," << g.grid_y << "\n";
            if (std::abs(g.screen_x - f.screen_x) > kEps)
                ss << "field: screen_x | game: " << g.screen_x << " | map_forge: " << f.screen_x << " | delta: " << (f.screen_x - g.screen_x) << "\n";
            if (std::abs(g.screen_y - f.screen_y) > kEps)
                ss << "field: screen_y | game: " << g.screen_y << " | map_forge: " << f.screen_y << " | delta: " << (f.screen_y - g.screen_y) << "\n";
            if (g.asset_id != f.asset_id)
                ss << "field: asset_id | game: " << g.asset_id << " | map_forge: " << f.asset_id << "\n";
            return {false, ss.str()};
        }
    }
    return {true, "MATCH"};
}

RenderGeometrySignature MapRenderer::compute_geometry_signature(const BuildingManager& manager, const BuildingCatalog& catalog,
                                                                const CameraState& camera, const float viewport_width, const float viewport_height) {
    RenderGeometrySignature sig;
    sig.records.reserve(manager.instances().size());
    for (const BuildingInstance& instance : manager.instances()) {
        const BuildingDefinition* definition = catalog.find(instance.definition_id);
        if (definition == nullptr) continue;
        const BuildingFootprint footprint = rotated_footprint(*definition, instance.rotation);
        const WorldPoint ground = building_visual_ground_world(instance.tile_x, instance.tile_y, footprint.width, footprint.height, camera.rotation);
        const ScreenPoint sp = world_to_screen_point(ground.x, ground.y, camera, viewport_width, viewport_height);
        const BuildingRotation visual_rot = camera_visual_rotation(*definition, instance.rotation, camera.rotation);
        const float dk = camera_depth_key(ground.x, ground.y, camera);

        RenderGeometryRecord rec;
        rec.layer = "building";
        rec.asset_id = instance.definition_id;
        rec.grid_x = instance.tile_x;
        rec.grid_y = instance.tile_y;
        rec.screen_x = sp.x;
        rec.screen_y = sp.y;
        rec.depth_key = dk;
        rec.anchor_x = definition->anchor_x_for(visual_rot, instance.current_level);
        rec.anchor_y = definition->anchor_y_for(visual_rot, instance.current_level);
        rec.art_scale = definition->art_scale;
        rec.footprint_w = footprint.width;
        rec.footprint_h = footprint.height;
        sig.records.push_back(std::move(rec));
    }
    std::sort(sig.records.begin(), sig.records.end(), [](const RenderGeometryRecord& a, const RenderGeometryRecord& b) {
        if (a.depth_key != b.depth_key) return a.depth_key < b.depth_key;
        if (a.grid_y != b.grid_y) return a.grid_y < b.grid_y;
        if (a.grid_x != b.grid_x) return a.grid_x < b.grid_x;
        return a.asset_id < b.asset_id;
    });
    return sig;
}

RenderGeometrySignature MapRenderer::compute_geometry_signature(const MapDocument& document, const BuildingCatalog& catalog,
                                                                const CameraState& camera, const float viewport_width, const float viewport_height) {
    RenderGeometrySignature sig;
    for (const auto& b : document.buildings()) {
        const BuildingDefinition* definition = catalog.find(b.definition_id);
        if (definition == nullptr) continue;
        const BuildingRotation rotation = static_cast<BuildingRotation>(b.rotation);
        const BuildingFootprint footprint = rotated_footprint(*definition, rotation);
        const WorldPoint ground = building_visual_ground_world(b.tile_x, b.tile_y, footprint.width, footprint.height, camera.rotation);
        const ScreenPoint sp = world_to_screen_point(ground.x, ground.y, camera, viewport_width, viewport_height);
        const BuildingRotation visual_rot = camera_visual_rotation(*definition, rotation, camera.rotation);
        const float dk = camera_depth_key(ground.x, ground.y, camera);

        RenderGeometryRecord rec;
        rec.layer = "building";
        rec.asset_id = b.definition_id;
        rec.grid_x = b.tile_x;
        rec.grid_y = b.tile_y;
        rec.screen_x = sp.x;
        rec.screen_y = sp.y;
        rec.depth_key = dk;
        rec.anchor_x = definition->anchor_x_for(visual_rot, 1);
        rec.anchor_y = definition->anchor_y_for(visual_rot, 1);
        rec.art_scale = definition->art_scale;
        rec.footprint_w = footprint.width;
        rec.footprint_h = footprint.height;
        sig.records.push_back(std::move(rec));
    }
    std::sort(sig.records.begin(), sig.records.end(), [](const RenderGeometryRecord& a, const RenderGeometryRecord& b) {
        if (a.depth_key != b.depth_key) return a.depth_key < b.depth_key;
        if (a.grid_y != b.grid_y) return a.grid_y < b.grid_y;
        if (a.grid_x != b.grid_x) return a.grid_x < b.grid_x;
        return a.asset_id < b.asset_id;
    });
    return sig;
}

MapForgeNativeViewport::~MapForgeNativeViewport() {
    shutdown();
}

void MapForgeNativeViewport::reload_asset_catalogs() {
    overlay_catalog_.load_directory(asset_root_ / "assets" / "overlays");
    animated_prop_catalog_.load_directory(asset_root_ / "assets" / "props");
}

bool MapForgeNativeViewport::initialize(void* win32_hwnd, int physical_width, int physical_height, const std::string& asset_root_path) {
    if (win32_hwnd == nullptr) return false;
    shutdown();

    physical_width_ = physical_width;
    physical_height_ = physical_height;
    asset_root_ = asset_root_path;

    if (!SDL_WasInit(SDL_INIT_VIDEO)) {
        if (!SDL_Init(SDL_INIT_VIDEO)) {
            return false;
        }
    }

    SDL_PropertiesID props = SDL_CreateProperties();
    SDL_SetPointerProperty(props, SDL_PROP_WINDOW_CREATE_WIN32_HWND_POINTER, win32_hwnd);
    SDL_SetNumberProperty(props, SDL_PROP_WINDOW_CREATE_WIDTH_NUMBER, physical_width);
    SDL_SetNumberProperty(props, SDL_PROP_WINDOW_CREATE_HEIGHT_NUMBER, physical_height);

    window_ = SDL_CreateWindowWithProperties(props);
    SDL_DestroyProperties(props);

    if (window_ == nullptr) {
        return false;
    }

    renderer_ = SDL_CreateRenderer(window_, nullptr);
    if (renderer_ == nullptr) {
        SDL_DestroyWindow(window_);
        window_ = nullptr;
        return false;
    }

    reload_asset_catalogs();
    return true;
}

bool MapForgeNativeViewport::initialize_offscreen(int physical_width, int physical_height, const std::string& asset_root_path) {
    shutdown();

    physical_width_ = physical_width;
    physical_height_ = physical_height;
    asset_root_ = asset_root_path;

    if (!SDL_WasInit(SDL_INIT_VIDEO)) {
        if (!SDL_Init(SDL_INIT_VIDEO)) {
            return false;
        }
    }

    offscreen_surface_ = SDL_CreateSurface(physical_width, physical_height, SDL_PIXELFORMAT_RGBA32);
    if (offscreen_surface_ == nullptr) return false;

    renderer_ = SDL_CreateSoftwareRenderer(offscreen_surface_);
    if (renderer_ == nullptr) {
        SDL_DestroySurface(offscreen_surface_);
        offscreen_surface_ = nullptr;
        return false;
    }

    reload_asset_catalogs();
    return true;
}

bool MapForgeNativeViewport::save_frame_to_png(const std::string& filepath) {
    if (renderer_ == nullptr) return false;
    render_frame();
    if (offscreen_surface_ != nullptr) {
        return SDL_SaveBMP(offscreen_surface_, filepath.c_str());
    } else {
        request_frame_capture(filepath);
        render_frame();
        return true;
    }
}

void MapForgeNativeViewport::resize(int physical_width, int physical_height) {
    if (physical_width <= 0 || physical_height <= 0) return;
    if (physical_width_ == physical_width && physical_height_ == physical_height) return;

    physical_width_ = physical_width;
    physical_height_ = physical_height;

    if (window_ != nullptr) {
        SDL_SetWindowSize(window_, physical_width, physical_height);
        SDL_SyncWindow(window_);
        int win_w = 0, win_h = 0;
        SDL_GetWindowSizeInPixels(window_, &win_w, &win_h);
        if (win_w > 0 && win_h > 0) {
            physical_width_ = win_w;
            physical_height_ = win_h;
        }
    }
}

void MapForgeNativeViewport::set_camera(const CameraState& camera) {
    camera_ = camera;
}

bool MapForgeNativeViewport::load_map_document(const MapDocument& document) {
    current_document_ = document;
    return true;
}

const TextureAsset* MapForgeNativeViewport::find_texture(const std::filesystem::path& relative_path) {
    if (renderer_ == nullptr) return nullptr;
    const std::string key = relative_path.generic_string();
    if (const auto it = texture_cache_.find(key); it != texture_cache_.end()) {
        return &it->second;
    }
    const std::filesystem::path full_path = asset_root_ / relative_path;
    SDL_Surface* surface = SDL_LoadPNG(full_path.string().c_str());
    if (surface == nullptr) return nullptr;
    TextureAsset asset;
    asset.texture = SDL_CreateTextureFromSurface(renderer_, surface);
    asset.source_width = static_cast<float>(surface->w);
    asset.source_height = static_cast<float>(surface->h);
    SDL_DestroySurface(surface);
    if (asset.texture == nullptr) return nullptr;
    SDL_SetTextureBlendMode(asset.texture, SDL_BLENDMODE_BLEND);
    SDL_SetTextureScaleMode(asset.texture, SDL_SCALEMODE_LINEAR);
    return &texture_cache_.emplace(key, asset).first->second;
}

void MapForgeNativeViewport::clear_textures() {
    for (auto& [path, asset] : texture_cache_) {
        if (asset.texture != nullptr) {
            SDL_DestroyTexture(asset.texture);
        }
    }
    texture_cache_.clear();

    for (auto& [key, asset] : overlay_texture_cache_) {
        if (asset.texture != nullptr) {
            SDL_DestroyTexture(asset.texture);
        }
    }
    overlay_texture_cache_.clear();
}

const TextureAsset* MapForgeNativeViewport::find_or_create_overlay_texture(const std::string& asset_id, const OverlayDefinition& def, const std::string& overlay_type) {
    if (renderer_ == nullptr) return nullptr;
    const std::string key = asset_id + "_" + overlay_type;
    if (const auto it = overlay_texture_cache_.find(key); it != overlay_texture_cache_.end()) {
        return &it->second;
    }

    if (def.overlays.find(overlay_type) == def.overlays.end()) return nullptr;
    const auto& layer_def = def.overlays.at(overlay_type);

    std::filesystem::path base_path = asset_root_ / ("assets/buildings/" + asset_id + "_lvl1.png");
    if (!std::filesystem::exists(base_path)) {
        base_path = asset_root_ / ("assets/buildings/" + asset_id + ".png");
    }
    SDL_Surface* base_surf = SDL_LoadPNG(base_path.string().c_str());
    if (!base_surf) return nullptr;

    std::filesystem::path mask_path = asset_root_ / def.mask_path;
    SDL_Surface* mask_surf = SDL_LoadPNG(mask_path.string().c_str());
    if (!mask_surf) {
        SDL_DestroySurface(base_surf);
        return nullptr;
    }

    std::filesystem::path snow_path = asset_root_ / layer_def.texture_path;
    SDL_Surface* snow_surf = SDL_LoadPNG(snow_path.string().c_str());
    if (!snow_surf) {
        SDL_DestroySurface(base_surf);
        SDL_DestroySurface(mask_surf);
        return nullptr;
    }

    int w = base_surf->w;
    int h = base_surf->h;

    SDL_Surface* base_rgba = SDL_ConvertSurface(base_surf, SDL_PIXELFORMAT_RGBA32);
    SDL_Surface* mask_rgba = SDL_ConvertSurface(mask_surf, SDL_PIXELFORMAT_RGBA32);
    SDL_Surface* snow_rgba = SDL_ConvertSurface(snow_surf, SDL_PIXELFORMAT_RGBA32);

    SDL_DestroySurface(base_surf);
    SDL_DestroySurface(mask_surf);
    SDL_DestroySurface(snow_surf);

    if (!base_rgba || !mask_rgba || !snow_rgba) {
        if (base_rgba) SDL_DestroySurface(base_rgba);
        if (mask_rgba) SDL_DestroySurface(mask_rgba);
        if (snow_rgba) SDL_DestroySurface(snow_rgba);
        return nullptr;
    }

    SDL_Surface* overlay_surf = SDL_CreateSurface(w, h, SDL_PIXELFORMAT_RGBA32);
    if (!overlay_surf) {
        SDL_DestroySurface(base_rgba);
        SDL_DestroySurface(mask_rgba);
        SDL_DestroySurface(snow_rgba);
        return nullptr;
    }

    const uint8_t* b_pixels = static_cast<const uint8_t*>(base_rgba->pixels);
    const uint8_t* m_pixels = static_cast<const uint8_t*>(mask_rgba->pixels);
    const uint8_t* s_pixels = static_cast<const uint8_t*>(snow_rgba->pixels);
    uint8_t* o_pixels = static_cast<uint8_t*>(overlay_surf->pixels);

    std::vector<uint8_t> active_regions = layer_def.region_ids;

    for (int y = 0; y < h; ++y) {
        for (int x = 0; x < w; ++x) {
            int b_idx = y * base_rgba->pitch + x * 4;
            int m_idx = y * mask_rgba->pitch + x * 4;

            uint8_t b_a = b_pixels[b_idx + 3];
            uint8_t m_val = m_pixels[m_idx + 0];

            if (b_a == 0) m_val = 0;

            int o_idx = y * overlay_surf->pitch + x * 4;

            bool is_active = false;
            for (uint8_t r_id : active_regions) {
                if (r_id == m_val) { is_active = true; break; }
            }

            if (is_active && m_val > 0) {
                int sx = x % snow_rgba->w;
                int sy = y % snow_rgba->h;
                int s_idx = sy * snow_rgba->pitch + sx * 4;

                o_pixels[o_idx + 0] = s_pixels[s_idx + 0];
                o_pixels[o_idx + 1] = s_pixels[s_idx + 1];
                o_pixels[o_idx + 2] = s_pixels[s_idx + 2];
                o_pixels[o_idx + 3] = b_a; // Preserve exact base alpha
            } else {
                o_pixels[o_idx + 0] = 0;
                o_pixels[o_idx + 1] = 0;
                o_pixels[o_idx + 2] = 0;
                o_pixels[o_idx + 3] = 0;
            }
        }
    }

    TextureAsset asset;
    asset.texture = SDL_CreateTextureFromSurface(renderer_, overlay_surf);
    asset.source_width = static_cast<float>(w);
    asset.source_height = static_cast<float>(h);

    SDL_DestroySurface(base_rgba);
    SDL_DestroySurface(mask_rgba);
    SDL_DestroySurface(snow_rgba);
    SDL_DestroySurface(overlay_surf);

    if (asset.texture == nullptr) return nullptr;

    SDL_SetTextureScaleMode(asset.texture, SDL_SCALEMODE_LINEAR);
    return &overlay_texture_cache_.emplace(key, asset).first->second;
}

void MapForgeNativeViewport::render_frame() {
    if (renderer_ == nullptr) return;
    int w = physical_width_;
    int h = physical_height_;
    SDL_GetRenderOutputSize(renderer_, &w, &h);
    const float vw = static_cast<float>(w);
    const float vh = static_cast<float>(h);

    const auto texture_lookup = [this](const std::filesystem::path& relative_path) -> const TextureAsset* {
        return find_texture(relative_path);
    };

    // View mode: 0 = ART, 1 = LOGIC, 2 = ART_AND_LOGIC
    if (view_mode_ == 0 || view_mode_ == 2) {
        if (current_document_.has_value()) {
            MapRenderer::render_world_terrain_and_water(
                renderer_,
                *current_document_,
                texture_lookup,
                asset_root_,
                camera_,
                vw,
                vh
            );

            for (const auto& r : current_document_->roads()) {
                if (const TextureAsset* tex = find_texture("assets/roads/straight_01.png")) {
                    MapRenderer::render_road_sprite(renderer_, *tex, r.tile_x, r.tile_y, camera_, vw, vh);
                }
            }

            // Render buildings in document
            for (const auto& b : current_document_->buildings()) {
                const AnimatedPropDefinition* anim_def = animated_prop_catalog_.find_prop(b.definition_id);
                if (anim_def != nullptr) {
                    const TextureAsset* base_tex = find_texture(anim_def->base_static_path);
                    if (base_tex != nullptr && base_tex->texture != nullptr) {
                        BuildingDefinition def;
                        def.id = b.definition_id;
                        def.footprint_width = 1;
                        def.footprint_height = 1;

                        BuildingInstance inst;
                        inst.tile_x = b.tile_x;
                        inst.tile_y = b.tile_y;

                        BuildingSpriteGeometry geom = MapRenderer::building_sprite_geometry(def, inst, BuildingRotation::r0, base_tex->source_width, base_tex->source_height, camera_, vw, vh);

                        // 1. Draw static base sprite
                        SDL_RenderTexture(renderer_, base_tex->texture, nullptr, &geom.sprite_bounds);

                        // 2. Draw animated layers
                        for (const auto& layer : anim_def->layers) {
                            if (layer.presentation == VisualPresentation::AtlasPhase) {
                                throw std::runtime_error("VisualPresentation::AtlasPhase is unsupported in CH_ANIMATED_PROP_V1 Phase 2");
                            }
                            if (layer.presentation == VisualPresentation::TransformRotation) {
                                const float norm_phase = prop_phase_ - std::floor(prop_phase_);
                                const double angle = static_cast<double>(norm_phase * 360.0F);
                                const TextureAsset* layer_tex = find_texture(layer.sprite_path);
                                if (layer_tex != nullptr && layer_tex->texture != nullptr) {
                                    const float scale_x = geom.sprite_bounds.w / base_tex->source_width;
                                    const float scale_y = geom.sprite_bounds.h / base_tex->source_height;
                                    const float mount_x_dest = layer.mount_point_x * scale_x;
                                    const float mount_y_dest = layer.mount_point_y * scale_y;
                                    const float pivot_x_dest = layer.pivot_x * scale_x;
                                    const float pivot_y_dest = layer.pivot_y * scale_y;

                                    SDL_FRect layer_dest;
                                    layer_dest.w = layer_tex->source_width * scale_x;
                                    layer_dest.h = layer_tex->source_height * scale_y;
                                    layer_dest.x = geom.sprite_bounds.x + mount_x_dest - pivot_x_dest;
                                    layer_dest.y = geom.sprite_bounds.y + mount_y_dest - pivot_y_dest;

                                    SDL_FPoint center = { pivot_x_dest, pivot_y_dest };
                                    SDL_RenderTextureRotated(renderer_, layer_tex->texture, nullptr, &layer_dest, angle, &center, SDL_FLIP_NONE);
                                }
                            }
                        }

                        // 3. Snow Overlay / Diagnostic if applicable
                        if (render_context_.snow_coverage > 0.0F && !render_context_.diagnostic_overlay) {
                            const OverlayDefinition* o_def = overlay_catalog_.find_overlay(b.definition_id);
                            if (o_def != nullptr) {
                                const TextureAsset* ov_tex = find_or_create_overlay_texture(b.definition_id, *o_def, "snow");
                                if (ov_tex != nullptr && ov_tex->texture != nullptr) {
                                    static SDL_BlendMode custom_blend = SDL_ComposeCustomBlendMode(
                                        SDL_BLENDFACTOR_SRC_ALPHA,
                                        SDL_BLENDFACTOR_ONE_MINUS_SRC_ALPHA,
                                        SDL_BLENDOPERATION_ADD,
                                        SDL_BLENDFACTOR_ZERO,
                                        SDL_BLENDFACTOR_ONE,
                                        SDL_BLENDOPERATION_ADD
                                    );
                                    SDL_SetTextureBlendMode(ov_tex->texture, custom_blend);
                                    Uint8 snow_alpha = static_cast<Uint8>(std::clamp(render_context_.snow_coverage, 0.0F, 1.0F) * 255.0F);
                                    SDL_SetTextureAlphaMod(ov_tex->texture, snow_alpha);
                                    SDL_RenderTexture(renderer_, ov_tex->texture, nullptr, &geom.sprite_bounds);
                                }
                            }
                        } else if (render_context_.diagnostic_overlay) {
                            SDL_SetRenderDrawColor(renderer_, 255, 0, 255, 160);
                            SDL_RenderFillRect(renderer_, &geom.sprite_bounds);
                        }
                        continue;
                    }
                }

                std::filesystem::path sprite_path = "assets/buildings/" + b.definition_id + "_lvl1.png";
                if (!std::filesystem::exists(asset_root_ / sprite_path)) {
                    sprite_path = "assets/buildings/" + b.definition_id + ".png";
                }
                const TextureAsset* base_tex = find_texture(sprite_path);
                if (base_tex != nullptr && base_tex->texture != nullptr) {
                    BuildingDefinition def;
                    def.id = b.definition_id;
                    def.footprint_width = 1;
                    def.footprint_height = 1;

                    BuildingInstance inst;
                    inst.tile_x = b.tile_x;
                    inst.tile_y = b.tile_y;

                    BuildingSpriteGeometry geom = MapRenderer::building_sprite_geometry(def, inst, BuildingRotation::r0, base_tex->source_width, base_tex->source_height, camera_, vw, vh);

                    // 1. Draw base sprite
                    SDL_RenderTexture(renderer_, base_tex->texture, nullptr, &geom.sprite_bounds);

                    // 2. Absolute Early Bypass for snow_coverage <= 0.0F
                    if (render_context_.snow_coverage > 0.0F && !render_context_.diagnostic_overlay) {
                        const OverlayDefinition* o_def = overlay_catalog_.find_overlay(b.definition_id);
                        if (o_def != nullptr) {
                            const TextureAsset* ov_tex = find_or_create_overlay_texture(b.definition_id, *o_def, "snow");
                            if (ov_tex != nullptr && ov_tex->texture != nullptr) {
                                static SDL_BlendMode custom_blend = SDL_ComposeCustomBlendMode(
                                    SDL_BLENDFACTOR_SRC_ALPHA,
                                    SDL_BLENDFACTOR_ONE_MINUS_SRC_ALPHA,
                                    SDL_BLENDOPERATION_ADD,
                                    SDL_BLENDFACTOR_ZERO,
                                    SDL_BLENDFACTOR_ONE,
                                    SDL_BLENDOPERATION_ADD
                                );
                                SDL_SetTextureBlendMode(ov_tex->texture, custom_blend);
                                Uint8 snow_alpha = static_cast<Uint8>(std::clamp(render_context_.snow_coverage, 0.0F, 1.0F) * 255.0F);
                                SDL_SetTextureAlphaMod(ov_tex->texture, snow_alpha);
                                SDL_RenderTexture(renderer_, ov_tex->texture, nullptr, &geom.sprite_bounds);
                            }
                        }
                    } else if (render_context_.diagnostic_overlay) {
                        // Diagnostic overlay mode: render extreme color tint over building bounds
                        SDL_SetRenderDrawColor(renderer_, 255, 0, 255, 160);
                        SDL_RenderFillRect(renderer_, &geom.sprite_bounds);
                    }
                }
            }
        } else {
            const TextureAsset* grass = find_texture("assets/terrain/grass_isometric_01.png");
            std::unordered_map<std::uint64_t, const TextureAsset*> scenario_textures;
            MapRenderer::render_map(renderer_, grass, scenario_textures, camera_, vw, vh);
        }
    } else {
        // Pure LOGIC mode: dark background fill
        SDL_SetRenderDrawColor(renderer_, 20, 24, 28, SDL_ALPHA_OPAQUE);
        const SDL_FRect bg = {0.0F, 0.0F, vw, vh};
        SDL_RenderFillRect(renderer_, &bg);
    }

    if ((view_mode_ == 1 || view_mode_ == 2) && current_document_.has_value()) {
        SemanticRenderer::render_semantic_overlays(
            renderer_,
            *current_document_,
            camera_,
            vw,
            vh,
            static_cast<SemanticChannel>(active_channels_),
            channel_opacity_
        );
    }

    if (hover_enabled_ && !pending_capture_path_.has_value()) {
        SDL_SetRenderDrawColor(renderer_, 255, 230, 80, 220);
        for (int dy = -hover_brush_radius_; dy <= hover_brush_radius_; ++dy) {
            for (int dx = -hover_brush_radius_; dx <= hover_brush_radius_; ++dx) {
                MapRenderer::render_tile_outline(renderer_, hover_tile_x_ + dx, hover_tile_y_ + dy, camera_, vw, vh);
            }
        }
    }

    if (pending_capture_path_.has_value()) {
        SDL_Surface* surface = SDL_RenderReadPixels(renderer_, nullptr);
        if (surface != nullptr) {
            SDL_SaveBMP(surface, pending_capture_path_->c_str());
            SDL_DestroySurface(surface);
        }
        pending_capture_path_.reset();
    }

    SDL_RenderPresent(renderer_);
}

RenderGeometrySignature MapForgeNativeViewport::compute_geometry_signature(const BuildingCatalog& catalog) const {
    if (!current_document_.has_value()) return {};
    return MapRenderer::compute_geometry_signature(*current_document_, catalog, camera_, static_cast<float>(physical_width_), static_cast<float>(physical_height_));
}

void MapForgeNativeViewport::shutdown() {
    clear_textures();
    if (renderer_ != nullptr) {
        SDL_DestroyRenderer(renderer_);
        renderer_ = nullptr;
    }
    if (window_ != nullptr) {
        SDL_DestroyWindow(window_);
        window_ = nullptr;
    }
    if (offscreen_surface_ != nullptr) {
        SDL_DestroySurface(offscreen_surface_);
        offscreen_surface_ = nullptr;
    }
}

} // namespace ch
