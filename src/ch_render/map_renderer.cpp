#include "src/ch_render/map_renderer.h"
#include "src/ch_core/terrain_projection.h"
#include "src/ch_render/semantic_renderer.h"
#include "src/ch_core/shoreline_autotile.h"
#include "src/ch_core/ground_surface.h"
#include "src/ch_render/shoreline_catalog.h"
#include "src/ch_render/water_surface_runtime.h"
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
constexpr float kGrassOpaqueHeight = 587.0F;

const WaterSurfaceRuntimeCatalog& water_surface_runtime_for_root(const std::filesystem::path& asset_root) {
    thread_local std::unordered_map<std::string, WaterSurfaceRuntimeCatalog> catalogs;
    const std::string key = asset_root.lexically_normal().generic_string();
    auto [it, inserted] = catalogs.try_emplace(key);
    if (inserted) {
        (void)it->second.load_manifest(asset_root / "assets/terrain/water/water_surfaces.json");
    }
    return it->second;
}

const TextureAsset* water_runtime_texture(
    const WaterSurfaceRuntimeCatalog& runtime,
    const std::string& asset_id,
    const std::function<const TextureAsset*(const std::filesystem::path&)>& find_texture) {
    const AssetDescriptor* asset = runtime.find_asset(asset_id);
    return asset == nullptr ? nullptr : find_texture(asset->logical_path);
}

SDL_FColor water_runtime_color(const WaterSurfaceRuntimeCatalog& runtime,
                               const WaterSurfaceRuntimeDefinition* surface) {
    if (surface == nullptr) return {0.0F, 0.0F, 0.0F, 1.0F};
    const Rgba8* color = runtime.coverage_color(*surface);
    if (color == nullptr) return {0.0F, 0.0F, 0.0F, 1.0F};
    return {
        static_cast<float>(color->r) / 255.0F,
        static_cast<float>(color->g) / 255.0F,
        static_cast<float>(color->b) / 255.0F,
        static_cast<float>(color->a) / 255.0F,
    };
}

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
    if (style_id == "cement_path" || style_id == "concrete_01") {
        static constexpr std::array<const char*, 16> kConcreteSprites = {
            "sidewalk_concrete_00_isolated.png", "sidewalk_concrete_01_end_n.png",
            "sidewalk_concrete_02_end_e.png", "sidewalk_concrete_03_curve_ne.png",
            "sidewalk_concrete_04_end_s.png", "sidewalk_concrete_05_straight_ns.png",
            "sidewalk_concrete_06_curve_es.png", "sidewalk_concrete_07_tee_no_w.png",
            "sidewalk_concrete_08_end_w.png", "sidewalk_concrete_09_curve_nw.png",
            "sidewalk_concrete_10_straight_ew.png", "sidewalk_concrete_11_tee_no_s.png",
            "sidewalk_concrete_12_curve_sw.png", "sidewalk_concrete_13_tee_no_e.png",
            "sidewalk_concrete_14_tee_no_n.png", "sidewalk_concrete_15_seamless.png",
        };
        return "assets/sidewalks/concrete_01/" +
               std::string(kConcreteSprites.at(static_cast<std::size_t>(connections)));
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
    const BuildingFootprint footprint = rotated_footprint(definition, rotation);
    for (int offset_y = 0; offset_y < footprint.height; ++offset_y) {
        for (int offset_x = 0; offset_x < footprint.width; ++offset_x) {
            SDL_SetRenderDrawColor(renderer, red, green, blue, SDL_ALPHA_OPAQUE);
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

void MapRenderer::render_heightfield_tile_outline(
    SDL_Renderer* renderer, const int tile_x, const int tile_y, const MapDocument& document,
    const CameraState& camera, const float viewport_width, const float viewport_height) {
    if (renderer == nullptr) return;
    const TerrainHeightField& heightfield = document.terrain_heightfield();
    const ScreenPoint top = terrain_world_to_screen_point(static_cast<float>(tile_x), static_cast<float>(tile_y), heightfield, camera, viewport_width, viewport_height);
    const ScreenPoint right = terrain_world_to_screen_point(static_cast<float>(tile_x + 1), static_cast<float>(tile_y), heightfield, camera, viewport_width, viewport_height);
    const ScreenPoint bottom = terrain_world_to_screen_point(static_cast<float>(tile_x + 1), static_cast<float>(tile_y + 1), heightfield, camera, viewport_width, viewport_height);
    const ScreenPoint left = terrain_world_to_screen_point(static_cast<float>(tile_x), static_cast<float>(tile_y + 1), heightfield, camera, viewport_width, viewport_height);
    SDL_RenderLine(renderer, top.x, top.y, right.x, right.y);
    SDL_RenderLine(renderer, right.x, right.y, bottom.x, bottom.y);
    SDL_RenderLine(renderer, bottom.x, bottom.y, left.x, left.y);
    SDL_RenderLine(renderer, left.x, left.y, top.x, top.y);
}

void MapRenderer::render_heightfield_tile_fill(
    SDL_Renderer* renderer, const int tile_x, const int tile_y, const MapDocument& document,
    const CameraState& camera, const float viewport_width, const float viewport_height,
    const SDL_FColor color) {
    if (renderer == nullptr) return;
    const TerrainHeightField& heightfield = document.terrain_heightfield();
    const ScreenPoint top = terrain_world_to_screen_point(static_cast<float>(tile_x), static_cast<float>(tile_y), heightfield, camera, viewport_width, viewport_height);
    const ScreenPoint right = terrain_world_to_screen_point(static_cast<float>(tile_x + 1), static_cast<float>(tile_y), heightfield, camera, viewport_width, viewport_height);
    const ScreenPoint bottom = terrain_world_to_screen_point(static_cast<float>(tile_x + 1), static_cast<float>(tile_y + 1), heightfield, camera, viewport_width, viewport_height);
    const ScreenPoint left = terrain_world_to_screen_point(static_cast<float>(tile_x), static_cast<float>(tile_y + 1), heightfield, camera, viewport_width, viewport_height);
    SDL_Vertex vertices[4] = {};
    vertices[0].position = {top.x, top.y};
    vertices[1].position = {right.x, right.y};
    vertices[2].position = {bottom.x, bottom.y};
    vertices[3].position = {left.x, left.y};
    for (SDL_Vertex& vertex : vertices) vertex.color = color;
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
                                               const float viewport_width, const float viewport_height,
                                               const MapDocument* document) {
    if (!definition.requires_road_access || resolved_road_access_mode(definition) == RoadAccessMode::any_perimeter) return;
    for (const BuildingAccessPoint& access : road_access_candidates(definition, rotation)) {
        const TileCoordinate offset = road_access_offset(access.facing);
        const int road_x = tile_x + access.local_x + offset.x;
        const int road_y = tile_y + access.local_y + offset.y;
        SDL_SetRenderDrawColor(renderer, roads.is_road(road_x, road_y) ? 112 : 255,
                               roads.is_road(road_x, road_y) ? 232 : 160, 96, SDL_ALPHA_OPAQUE);
        if (document == nullptr) {
            render_tile_outline(renderer, road_x, road_y, camera, viewport_width, viewport_height);
            continue;
        }
        render_heightfield_tile_outline(renderer, road_x, road_y, *document, camera, viewport_width, viewport_height);
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
    const SDL_FRect destination = {top.x - (kTileWidth * camera.zoom * 0.5F), top.y,
                                   texture.source_width * scale, texture.source_height * scale};
    SDL_RenderTexture(renderer, texture.texture, nullptr, &destination);
}

void MapRenderer::render_heightfield_terrain_tile(
    SDL_Renderer* renderer, const TextureAsset& texture, const int x, const int y,
    const MapDocument& document, const CameraState& camera,
    const float viewport_width, const float viewport_height, const bool grass_source) {
    if (renderer == nullptr || texture.texture == nullptr || texture.source_width <= 0.0F || texture.source_height <= 0.0F) return;
    const TerrainHeightField& heightfield = document.terrain_heightfield();
    const auto screen_corner = [&](const int grid_x, const int grid_y) {
        return terrain_world_to_screen_point(static_cast<float>(grid_x), static_cast<float>(grid_y), heightfield,
                                             camera, viewport_width, viewport_height);
    };
    const ScreenPoint top = screen_corner(x, y);
    const ScreenPoint right = screen_corner(x + 1, y);
    const ScreenPoint bottom = screen_corner(x + 1, y + 1);
    const ScreenPoint left = screen_corner(x, y + 1);
    const float source_width = std::max(1.0F, texture.source_width);
    const float source_height = std::max(1.0F, texture.source_height);
    const float left_u = grass_source ? kGrassOpaqueLeft / source_width : 0.0F;
    const float top_v = grass_source ? kGrassOpaqueTop / source_height : 0.0F;
    const float right_u = grass_source ? (kGrassOpaqueLeft + kGrassOpaqueWidth) / source_width : 1.0F;
    const float bottom_v = grass_source ? (kGrassOpaqueTop + kGrassOpaqueHeight) / source_height : 1.0F;
    SDL_Vertex vertices[4] = {};
    vertices[0].position = {top.x, top.y};
    vertices[1].position = {right.x, right.y};
    vertices[2].position = {bottom.x, bottom.y};
    vertices[3].position = {left.x, left.y};
    vertices[0].tex_coord = {(left_u + right_u) * 0.5F, top_v};
    vertices[1].tex_coord = {right_u, (top_v + bottom_v) * 0.5F};
    vertices[2].tex_coord = {(left_u + right_u) * 0.5F, bottom_v};
    vertices[3].tex_coord = {left_u, (top_v + bottom_v) * 0.5F};
    for (SDL_Vertex& vertex : vertices) vertex.color = {1.0F, 1.0F, 1.0F, 1.0F};
    const int indices[] = {0, 1, 2, 0, 2, 3};
    (void)SDL_RenderGeometry(renderer, texture.texture, vertices, 4, indices, 6);
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
    const auto wrap = [world_period](const float value) {
        const float result = std::fmod(value, world_period);
        return result < 0.0F ? result + world_period : result;
    };
    const auto uv = [&wrap, world_period](const WorldPoint point) {
        return SDL_FPoint{wrap(point.x + world_period * 0.5F) / world_period,
                          wrap(point.y + world_period * 0.5F) / world_period};
    };
    SDL_Vertex vertices[4] = {};
    vertices[0].position = {top.x, top.y}; vertices[0].tex_coord = uv(top_world);
    vertices[1].position = {right.x, right.y}; vertices[1].tex_coord = uv(right_world);
    vertices[2].position = {bottom.x, bottom.y}; vertices[2].tex_coord = uv(bottom_world);
    vertices[3].position = {left.x, left.y}; vertices[3].tex_coord = uv(left_world);
    for (SDL_Vertex& vertex : vertices) vertex.color = {1.0F, 1.0F, 1.0F, 1.0F};
    const int indices[] = {0, 1, 2, 0, 2, 3};
    (void)SDL_RenderGeometry(renderer, overlay.texture, vertices, 4, indices, 6);
}

void MapRenderer::render_water_surface_tile(SDL_Renderer* renderer, const TextureAsset& texture,
                                            const int x, const int y, const CameraState& camera,
                                            const float viewport_width, const float viewport_height,
                                            const int frame) {
    if (renderer == nullptr || texture.texture == nullptr) return;
    constexpr float period = 4.0F;
    constexpr float cell = 256.0F;
    constexpr float stride = 258.0F;
    const float u = std::fmod(std::fmod(static_cast<float>(x), period) + period, period);
    const float v = std::fmod(std::fmod(static_cast<float>(y), period) + period, period);
    const auto uv = [&](const float world_u, const float world_v) {
        if (frame < 0) return SDL_FPoint{world_u / period, world_v / period};
        const float source_x = static_cast<float>(frame % 4) * stride + 1.0F + world_u * (cell / period);
        const float source_y = static_cast<float>(frame / 4) * stride + 1.0F + world_v * (cell / period);
        return SDL_FPoint{source_x / texture.source_width, source_y / texture.source_height};
    };
    SDL_Vertex vertices[4] = {};
    const ScreenPoint top = world_to_screen_point(static_cast<float>(x), static_cast<float>(y), camera, viewport_width, viewport_height);
    const ScreenPoint right = world_to_screen_point(static_cast<float>(x + 1), static_cast<float>(y), camera, viewport_width, viewport_height);
    const ScreenPoint bottom = world_to_screen_point(static_cast<float>(x + 1), static_cast<float>(y + 1), camera, viewport_width, viewport_height);
    const ScreenPoint left = world_to_screen_point(static_cast<float>(x), static_cast<float>(y + 1), camera, viewport_width, viewport_height);
    vertices[0].position = {top.x, top.y}; vertices[0].tex_coord = uv(u, v);
    vertices[1].position = {right.x, right.y}; vertices[1].tex_coord = uv(u + 1.0F, v);
    vertices[2].position = {bottom.x, bottom.y}; vertices[2].tex_coord = uv(u + 1.0F, v + 1.0F);
    vertices[3].position = {left.x, left.y}; vertices[3].tex_coord = uv(u, v + 1.0F);
    for (SDL_Vertex& vertex : vertices) vertex.color = {1.0F, 1.0F, 1.0F, 1.0F};
    const int indices[] = {0, 1, 2, 0, 2, 3};
    (void)SDL_RenderGeometry(renderer, texture.texture, vertices, 4, indices, 6);
}

void MapRenderer::render_map(SDL_Renderer* renderer, const TextureAsset* grass,
                             const std::unordered_map<std::uint64_t, const TextureAsset*>& scenario_terrain_textures,
                             const CameraState& camera, const float viewport_width, const float viewport_height,
                             const MapDocument* document) {
    SDL_SetRenderDrawColor(renderer, 74, 104, 83, SDL_ALPHA_OPAQUE);
    const SDL_FRect background = {0.0F, 0.0F, viewport_width, viewport_height};
    SDL_RenderFillRect(renderer, &background);
    if (grass == nullptr) return;
    for (int depth = contracts::kMapMin * 2; depth <= contracts::kMapMax * 2; ++depth) {
        const int first_x = std::max(contracts::kMapMin, depth - contracts::kMapMax);
        const int last_x = std::min(contracts::kMapMax, depth - contracts::kMapMin);
        for (int x = first_x; x <= last_x; ++x) {
            const int y = depth - x;
            const std::uint64_t key = (static_cast<std::uint64_t>(static_cast<std::uint32_t>(x)) << 32) | static_cast<std::uint32_t>(y);
            const auto it = scenario_terrain_textures.find(key);
            const bool deform = document != nullptr && (document->terrain_height_at(x, y) != 0.0F ||
                document->terrain_height_at(x + 1, y) != 0.0F || document->terrain_height_at(x + 1, y + 1) != 0.0F ||
                document->terrain_height_at(x, y + 1) != 0.0F);
            if (it != scenario_terrain_textures.end() && it->second != nullptr) {
                if (deform) render_heightfield_terrain_tile(renderer, *it->second, x, y, *document, camera, viewport_width, viewport_height, it->second == grass);
                else render_custom_terrain_tile(renderer, *it->second, x, y, camera, viewport_width, viewport_height);
            } else if (deform) render_heightfield_terrain_tile(renderer, *grass, x, y, *document, camera, viewport_width, viewport_height, true);
            else render_grass_tile(renderer, *grass, x, y, camera, viewport_width, viewport_height);
        }
    }
}

void MapRenderer::render_world_terrain_and_water(
    SDL_Renderer* renderer, const MapDocument& document,
    const std::function<const TextureAsset*(const std::filesystem::path&)>& find_texture,
    const std::filesystem::path& asset_root, const CameraState& camera,
    const float viewport_width, const float viewport_height, const float render_time) {
    if (renderer == nullptr) return;

    const WaterSurfaceRuntimeCatalog& water_runtime = water_surface_runtime_for_root(asset_root);
    const WaterSurfaceRuntimeDefinition* shallow_definition = water_runtime.find_surface("water_shallow");
    const WaterSurfaceRuntimeDefinition* deep_definition = water_runtime.find_surface("water_deep");
    const TextureAsset* grass_base = find_texture("assets/terrain/grass_isometric_01.png");
    std::unordered_map<std::uint64_t, const TextureAsset*> scenario_terrain_textures;
    std::vector<WaterSurfaceTileEntry> water_tiles;
    std::vector<GroundSurfaceTileEntry> dirt_path_tiles;
    for (const auto& tile : document.terrain_tiles()) {
        const std::uint64_t key = tile_key(tile.tile_x, tile.tile_y);
        if (!tile.texture.empty()) if (const TextureAsset* tex = find_texture(tile.texture)) scenario_terrain_textures[key] = tex;
        if (!scenario_terrain_textures.contains(key) &&
            (tile.terrain_definition == "sand" || tile.terrain_definition == "sand_center" || tile.terrain_definition == "sand_wet")) {
            if (const TextureAsset* sand = find_texture("assets/terrain/sand_isometric_01.png")) scenario_terrain_textures[key] = sand;
        }
        const bool shallow = tile.terrain_definition == "water_shallow" || tile.terrain_definition == "ocean_shallow";
        const bool deep = tile.terrain_definition == "water_deep" || tile.terrain_definition == "ocean_deep";
        if (shallow || deep) water_tiles.push_back({tile.tile_x, tile.tile_y, shallow});
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
        bounds.min_x = bounds.max_x = document.terrain_tiles()[0].tile_x;
        bounds.min_y = bounds.max_y = document.terrain_tiles()[0].tile_y;
        for (const auto& t : document.terrain_tiles()) {
            bounds.min_x = std::min(bounds.min_x, t.tile_x); bounds.max_x = std::max(bounds.max_x, t.tile_x);
            bounds.min_y = std::min(bounds.min_y, t.tile_y); bounds.max_y = std::max(bounds.max_y, t.tile_y);
        }
    } else {
        bounds.min_x = contracts::kMapMin; bounds.max_x = contracts::kMapMax;
        bounds.min_y = contracts::kMapMin; bounds.max_y = contracts::kMapMax;
    }
    AutotileResult autotile_res = ShorelineAutotiler::evaluate_shoreline(world, bounds);
    for (const auto& edit : autotile_res.edits) {
        for (const auto piece : edit.recipe.pieces) {
            const std::string piece_path = ShorelineCatalog::get_piece_texture_path(piece, "coast_adjusted");
            if (const TextureAsset* tex = find_texture(piece_path)) shoreline_overlays.push_back({edit.tile.x, edit.tile.y, tex});
        }
    }

    const TextureAsset* shallow_surface = (water_tiles.empty() || shallow_definition == nullptr) ? nullptr :
        water_runtime_texture(water_runtime, shallow_definition->base_asset_id, find_texture);
    const TextureAsset* deep_surface = (water_tiles.empty() || deep_definition == nullptr) ? nullptr :
        water_runtime_texture(water_runtime, deep_definition->base_asset_id, find_texture);
    const TextureAsset* shallow_glint = (water_tiles.empty() || shallow_definition == nullptr) ? nullptr :
        water_runtime_texture(water_runtime, shallow_definition->rgba_atlas_asset_id, find_texture);
    const TextureAsset* deep_glint = (water_tiles.empty() || deep_definition == nullptr) ? nullptr :
        water_runtime_texture(water_runtime, deep_definition->rgba_atlas_asset_id, find_texture);

    render_map(renderer, grass_base, scenario_terrain_textures, camera, viewport_width, viewport_height, &document);
    constexpr SDL_FColor kDirtUnderlay = {0.50F, 0.35F, 0.20F, 1.0F};
    for (const auto& tile : dirt_path_tiles) render_heightfield_tile_fill(renderer, tile.tile_x, tile.tile_y, document, camera, viewport_width, viewport_height, kDirtUnderlay);
    for (const auto& tile : dirt_path_tiles) {
        const TileConnectionMask visual_connections = camera_visual_connections(tile.connections, camera.rotation);
        if (const TextureAsset* sprite = find_texture(dirt_path_sprite(visual_connections))) {
            render_heightfield_terrain_tile(renderer, *sprite, tile.tile_x, tile.tile_y, document, camera, viewport_width, viewport_height, false);
        }
    }

    const SDL_FColor shallow_coverage = water_runtime_color(water_runtime, shallow_definition);
    const SDL_FColor deep_coverage = water_runtime_color(water_runtime, deep_definition);
    for (const auto& tile : water_tiles) {
        render_tile_fill(renderer, tile.tile_x, tile.tile_y, camera, viewport_width, viewport_height,
                         tile.shallow ? shallow_coverage : deep_coverage);
    }

    SDL_TextureAddressMode previous_u = SDL_TEXTURE_ADDRESS_AUTO;
    SDL_TextureAddressMode previous_v = SDL_TEXTURE_ADDRESS_AUTO;
    const bool restore_address = SDL_GetRenderTextureAddressMode(renderer, &previous_u, &previous_v);
    (void)SDL_SetRenderTextureAddressMode(renderer, SDL_TEXTURE_ADDRESS_WRAP, SDL_TEXTURE_ADDRESS_WRAP);
    for (const auto& tile : water_tiles) {
        const TextureAsset* base = tile.shallow ? shallow_surface : deep_surface;
        if (base != nullptr) render_water_surface_tile(renderer, *base, tile.tile_x, tile.tile_y, camera, viewport_width, viewport_height);
    }

    (void)SDL_SetRenderTextureAddressMode(renderer, SDL_TEXTURE_ADDRESS_CLAMP, SDL_TEXTURE_ADDRESS_CLAMP);
    const int frame = water_runtime.frame_at_seconds(render_time);
    for (const auto& tile : water_tiles) {
        const TextureAsset* glint = tile.shallow ? shallow_glint : deep_glint;
        if (glint != nullptr) render_water_surface_tile(renderer, *glint, tile.tile_x, tile.tile_y, camera, viewport_width, viewport_height, frame);
    }
    (void)SDL_SetRenderTextureAddressMode(renderer,
        restore_address ? previous_u : SDL_TEXTURE_ADDRESS_AUTO,
        restore_address ? previous_v : SDL_TEXTURE_ADDRESS_AUTO);
    for (const auto& overlay : shoreline_overlays) {
        if (overlay.texture != nullptr) render_custom_terrain_tile(renderer, *overlay.texture, overlay.tile_x, overlay.tile_y, camera, viewport_width, viewport_height);
    }
}

void MapRenderer::render_road_sprite(SDL_Renderer* renderer, const TextureAsset& texture, const int tile_x, const int tile_y,
                                    const CameraState& camera, const float viewport_width, const float viewport_height) {
    const WorldPoint visual_top = tile_visual_top_world(tile_x, tile_y, camera.rotation);
    const ScreenPoint top = world_to_screen_point(visual_top.x, visual_top.y, camera, viewport_width, viewport_height);
    const float destination_height = kTileWidth * camera.zoom * texture.source_height / texture.source_width;
    const SDL_FRect destination = {top.x - kTileWidth * camera.zoom * 0.5F, top.y, kTileWidth * camera.zoom, destination_height};
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
    constexpr SDL_FColor kRoadAsphalt = {52.0F / 255.0F, 57.0F / 255.0F, 60.0F / 255.0F, 1.0F};
    for (const RoadTile* tile : sorted_tiles) render_tile_fill(renderer, tile->tile_x, tile->tile_y, camera, viewport_width, viewport_height, kRoadAsphalt);
    for (const RoadTile* tile : sorted_tiles) {
        const RoadVisual* visual = visuals.get_for_mask(camera_visual_connections(tile->connections, camera.rotation));
        const TextureAsset* texture = visual == nullptr ? nullptr : find_texture(asset_root / visual->texture_path);
        if (texture != nullptr) render_road_sprite(renderer, *texture, tile->tile_x, tile->tile_y, camera, viewport_width, viewport_height);
        else render_road_tile(renderer, tile->tile_x, tile->tile_y, camera, viewport_width, viewport_height,
                             road_placeholder_color(roads.visual_type(tile->tile_x, tile->tile_y)));
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
    const float frame_w = (definition.animation.has_value() && definition.animation->frame_count > 1)
        ? source_width / static_cast<float>(definition.animation->frame_count) : source_width;
    const float frame_h = source_height;
    const float scale = definition.art_scale * camera.zoom;
    const SDL_FRect bounds = {anchor_sp.x - frame_w * scale * definition.anchor_x_for(visual_rotation, instance.current_level),
                              anchor_sp.y - frame_h * scale * definition.anchor_y_for(visual_rotation, instance.current_level),
                              frame_w * scale, frame_h * scale};
    return {ground, {anchor_sp.x, anchor_sp.y}, bounds};
}

void MapRenderer::render_building(SDL_Renderer* renderer, const BuildingDefinition& definition, const BuildingInstance& instance,
                                  const BuildingRotation visual_rotation, SDL_Texture* texture, const float source_width, const float source_height,
                                  const CameraState& camera, const float viewport_width, const float viewport_height,
                                  const Uint8 alpha, const Uint8 red, const Uint8 green, const Uint8 blue) {
    if (texture == nullptr) return;
    const BuildingSpriteGeometry geometry = building_sprite_geometry(definition, instance, visual_rotation, source_width, source_height,
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
                const std::uint64_t action_duration_ms = static_cast<std::uint64_t>(action_count) * static_cast<std::uint64_t>(duration_ms);
                const std::uint64_t cycle_duration_ms = idle_hold_ms + action_duration_ms;
                const std::uint64_t instance_offset_ms = instance.instance_id * 977ULL;
                const std::uint64_t phase_ms = cycle_duration_ms > 0 ?
                    (static_cast<std::uint64_t>(SDL_GetTicks()) + instance_offset_ms) % cycle_duration_ms : 0;
                if (phase_ms >= idle_hold_ms && action_duration_ms > 0) {
                    frame_index = action_start + std::min(action_count - 1,
                        static_cast<int>((phase_ms - idle_hold_ms) / static_cast<std::uint64_t>(duration_ms)));
                }
            }
        } else if (animation.playback == "activity_loop") {
            frame_index = instance.activity_active() ? static_cast<int>((SDL_GetTicks() / duration_ms) % frame_count) : 0;
        } else frame_index = static_cast<int>((SDL_GetTicks() / duration_ms) % frame_count);
        const float frame_w = source_width / static_cast<float>(frame_count);
        const SDL_FRect src_rect = {frame_index * frame_w, 0.0F, frame_w, source_height};
        SDL_RenderTexture(renderer, texture, &src_rect, &geometry.sprite_bounds);
    } else SDL_RenderTexture(renderer, texture, nullptr, &geometry.sprite_bounds);
    SDL_SetTextureColorMod(texture, 255, 255, 255);
    SDL_SetTextureAlphaMod(texture, SDL_ALPHA_OPAQUE);
}

void MapRenderer::render_land_overlays(SDL_Renderer* renderer, const LandManager& lands, const LandParcel* hovered_parcel,
                                      const bool land_mode, const CameraState& camera, const float viewport_width, const float viewport_height) {
    for (const LandParcel& parcel : lands.parcels()) {
        SDL_FColor color = {0.08F, 0.11F, 0.14F, 0.22F};
        if (land_mode && &parcel == hovered_parcel) {
            if (parcel.owned) color = {0.22F, 0.58F, 0.92F, 0.28F};
            else if (lands.can_purchase_parcel(parcel.id)) color = {0.25F, 0.82F, 0.42F, 0.42F};
            else color = {0.88F, 0.28F, 0.24F, 0.42F};
        } else if (parcel.owned) continue;
        for (int y = std::max(contracts::kMapMin, parcel.origin_y); y <= std::min(contracts::kMapMax, parcel.origin_y + parcel.height - 1); ++y)
            for (int x = std::max(contracts::kMapMin, parcel.origin_x); x <= std::min(contracts::kMapMax, parcel.origin_x + parcel.width - 1); ++x)
                render_tile_fill(renderer, x, y, camera, viewport_width, viewport_height, color);
    }
}

void MapRenderer::render_farming(SDL_Renderer* renderer, const FarmingSystem& farming, const CropCatalog& crops,
                                const std::function<const TextureAsset*(const std::filesystem::path&)>& find_texture,
                                const std::filesystem::path& root, const CameraState& camera,
                                const float viewport_width, const float viewport_height) {
    (void)crops; (void)find_texture; (void)root;
    if (renderer == nullptr || farming.tiles().empty()) return;
    const auto soil_color = [](const float world_x, const float world_y) -> SDL_FColor {
        const float broad = std::sin(world_x * 0.52F + world_y * 0.38F) * 0.022F;
        const float cross = std::sin(world_x * 1.27F - world_y * 0.73F + 0.8F) * 0.012F;
        const float warm = std::sin(world_x * 0.31F + world_y * 0.91F + 1.7F) * 0.009F;
        const float shade = broad + cross;
        return {std::clamp(118.0F/255.0F + shade + warm,0.0F,1.0F),
                std::clamp(78.0F/255.0F + shade*0.76F + warm*0.30F,0.0F,1.0F),
                std::clamp(45.0F/255.0F + shade*0.52F,0.0F,1.0F),1.0F};
    };
    for (const FarmTile& tile : farming.tiles()) {
        const float x=static_cast<float>(tile.tile_x), y=static_cast<float>(tile.tile_y);
        const ScreenPoint top=world_to_screen_point(x,y,camera,viewport_width,viewport_height);
        const ScreenPoint right=world_to_screen_point(x+1,y,camera,viewport_width,viewport_height);
        const ScreenPoint bottom=world_to_screen_point(x+1,y+1,camera,viewport_width,viewport_height);
        const ScreenPoint left=world_to_screen_point(x,y+1,camera,viewport_width,viewport_height);
        SDL_Vertex vertices[4] = {};
        vertices[0].position={top.x,top.y}; vertices[0].color=soil_color(x,y);
        vertices[1].position={right.x,right.y}; vertices[1].color=soil_color(x+1,y);
        vertices[2].position={bottom.x,bottom.y}; vertices[2].color=soil_color(x+1,y+1);
        vertices[3].position={left.x,left.y}; vertices[3].color=soil_color(x,y+1);
        const int indices[]={0,1,2,0,2,3}; (void)SDL_RenderGeometry(renderer,nullptr,vertices,4,indices,6);
    }
    constexpr std::array<float,5> kFurrowOffsets={0.10F,0.30F,0.50F,0.70F,0.90F};
    constexpr float kHighlightOffset=0.025F;
    for (const FarmTile& tile : farming.tiles()) {
        if (farming.is_occupied(tile.tile_x-1,tile.tile_y)) continue;
        int run_end_x=tile.tile_x; while (farming.is_occupied(run_end_x+1,tile.tile_y)) ++run_end_x;
        for (const float offset : kFurrowOffsets) {
            const ScreenPoint hs=world_to_screen_point(static_cast<float>(tile.tile_x),static_cast<float>(tile.tile_y)+offset-kHighlightOffset,camera,viewport_width,viewport_height);
            const ScreenPoint he=world_to_screen_point(static_cast<float>(run_end_x+1),static_cast<float>(tile.tile_y)+offset-kHighlightOffset,camera,viewport_width,viewport_height);
            SDL_SetRenderDrawColor(renderer,154,108,68,88); SDL_RenderLine(renderer,hs.x,hs.y,he.x,he.y);
            const ScreenPoint ss=world_to_screen_point(static_cast<float>(tile.tile_x),static_cast<float>(tile.tile_y)+offset,camera,viewport_width,viewport_height);
            const ScreenPoint se=world_to_screen_point(static_cast<float>(run_end_x+1),static_cast<float>(tile.tile_y)+offset,camera,viewport_width,viewport_height);
            SDL_SetRenderDrawColor(renderer,78,47,29,188); SDL_RenderLine(renderer,ss.x,ss.y,se.x,se.y);
        }
    }
}

void MapRenderer::render_farming(SDL_Renderer* renderer, const FarmingSystem& farming, const CropCatalog& crops,
                                const std::unordered_map<std::string, TextureAsset>& texture_lookup,
                                const std::filesystem::path& root, const CameraState& camera,
                                const float viewport_width, const float viewport_height) {
    return render_farming(renderer, farming, crops,
        [&texture_lookup](const std::filesystem::path& p)->const TextureAsset* {auto it=texture_lookup.find(p.generic_string()); return it!=texture_lookup.end()?&it->second:nullptr;},
        root,camera,viewport_width,viewport_height);
}

void MapRenderer::render_buildings(SDL_Renderer* renderer, const BuildingManager& manager, const BuildingCatalog& catalog,
                                  const LandManager& lands,
                                  const std::function<const TextureAsset*(const std::filesystem::path&)>& find_texture,
                                  const std::filesystem::path& asset_root,
                                  const CameraState& camera, const float viewport_width, const float viewport_height) {
    std::vector<const BuildingInstance*> sorted_instances;
    sorted_instances.reserve(manager.instances().size());
    for (const BuildingInstance& instance : manager.instances()) sorted_instances.push_back(&instance);
    std::sort(sorted_instances.begin(), sorted_instances.end(), [&catalog,&camera](const BuildingInstance* left,const BuildingInstance* right){
        const BuildingDefinition* ld=catalog.find(left->definition_id); const BuildingDefinition* rd=catalog.find(right->definition_id);
        const BuildingFootprint lf=ld==nullptr?BuildingFootprint{}:rotated_footprint(*ld,left->rotation);
        const BuildingFootprint rf=rd==nullptr?BuildingFootprint{}:rotated_footprint(*rd,right->rotation);
        const WorldPoint lg=building_visual_ground_world(left->tile_x,left->tile_y,lf.width,lf.height,camera.rotation);
        const WorldPoint rg=building_visual_ground_world(right->tile_x,right->tile_y,rf.width,rf.height,camera.rotation);
        const float ldk=camera_depth_key(lg.x,lg.y,camera), rdk=camera_depth_key(rg.x,rg.y,camera);
        return ldk==rdk?left->instance_id<right->instance_id:ldk<rdk;
    });
    for (const BuildingInstance* instance : sorted_instances) {
        const BuildingDefinition* definition=catalog.find(instance->definition_id); if(definition==nullptr) continue;
        const BuildingRotation visual_rot=camera_visual_rotation(*definition,instance->rotation,camera.rotation);
        const TextureAsset* texture=find_texture(asset_root/definition->texture_path_for(visual_rot,instance->current_level));
        if(texture==nullptr) continue;
        const bool is_owned=lands.is_tile_owned(instance->tile_x,instance->tile_y);
        render_building(renderer,*definition,*instance,visual_rot,texture->texture,texture->source_width,texture->source_height,camera,viewport_width,viewport_height,
                        SDL_ALPHA_OPAQUE,is_owned?255:140,is_owned?255:145,is_owned?255:155);
    }
}

std::string RenderGeometrySignature::compute_hash() const {
    std::uint64_t hash=14695981039346656037ULL;
    for(const auto& rec:records){std::ostringstream ss; ss<<rec.layer<<','<<rec.asset_id<<','<<rec.grid_x<<','<<rec.grid_y<<','<<rec.screen_x<<','<<rec.screen_y<<','<<rec.dest_w<<','<<rec.dest_h<<','<<rec.depth_key<<','<<rec.anchor_x<<','<<rec.anchor_y<<','<<rec.art_scale<<','<<rec.footprint_w<<','<<rec.footprint_h<<'\n'; for(char c:ss.str()){hash^=static_cast<std::uint8_t>(c);hash*=1099511628211ULL;}}
    std::ostringstream out; out<<"FNV64:0x"<<std::hex<<std::uppercase<<std::setfill('0')<<std::setw(16)<<hash; return out.str();
}

RenderGeometryDiff compare_signatures(const RenderGeometrySignature& game_sig,const RenderGeometrySignature& forge_sig){
    if(game_sig.records.size()!=forge_sig.records.size()) return {false,"CH_RENDER_DIVERGENCE: RECORD COUNT MISMATCH"};
    constexpr float kEps=0.01F;
    for(std::size_t i=0;i<game_sig.records.size();++i){const auto& g=game_sig.records[i];const auto& f=forge_sig.records[i]; if(g.asset_id!=f.asset_id||g.grid_x!=f.grid_x||g.grid_y!=f.grid_y||std::abs(g.screen_x-f.screen_x)>kEps||std::abs(g.screen_y-f.screen_y)>kEps||std::abs(g.depth_key-f.depth_key)>kEps) return {false,"CH_RENDER_DIVERGENCE"};}
    return {true,"MATCH"};
}

RenderGeometrySignature MapRenderer::compute_geometry_signature(const BuildingManager& manager,const BuildingCatalog& catalog,const CameraState& camera,const float viewport_width,const float viewport_height){
    RenderGeometrySignature sig; for(const BuildingInstance& instance:manager.instances()){const BuildingDefinition* definition=catalog.find(instance.definition_id);if(!definition)continue;const BuildingFootprint fp=rotated_footprint(*definition,instance.rotation);const WorldPoint ground=building_visual_ground_world(instance.tile_x,instance.tile_y,fp.width,fp.height,camera.rotation);const ScreenPoint sp=world_to_screen_point(ground.x,ground.y,camera,viewport_width,viewport_height);RenderGeometryRecord rec;rec.layer="building";rec.asset_id=instance.definition_id;rec.grid_x=instance.tile_x;rec.grid_y=instance.tile_y;rec.screen_x=sp.x;rec.screen_y=sp.y;rec.depth_key=camera_depth_key(ground.x,ground.y,camera);rec.footprint_w=fp.width;rec.footprint_h=fp.height;sig.records.push_back(std::move(rec));}return sig;
}

RenderGeometrySignature MapRenderer::compute_geometry_signature(const MapDocument& document,const BuildingCatalog& catalog,const CameraState& camera,const float viewport_width,const float viewport_height){
    RenderGeometrySignature sig; for(const auto& b:document.buildings()){const BuildingDefinition* definition=catalog.find(b.definition_id);if(!definition)continue;const BuildingRotation rotation=static_cast<BuildingRotation>(b.rotation);const BuildingFootprint fp=rotated_footprint(*definition,rotation);const WorldPoint ground=building_visual_ground_world(b.tile_x,b.tile_y,fp.width,fp.height,camera.rotation);const ScreenPoint sp=world_to_screen_point(ground.x,ground.y,camera,viewport_width,viewport_height);RenderGeometryRecord rec;rec.layer="building";rec.asset_id=b.definition_id;rec.grid_x=b.tile_x;rec.grid_y=b.tile_y;rec.screen_x=sp.x;rec.screen_y=sp.y;rec.depth_key=camera_depth_key(ground.x,ground.y,camera);rec.footprint_w=fp.width;rec.footprint_h=fp.height;sig.records.push_back(std::move(rec));}return sig;
}

MapForgeNativeViewport::~MapForgeNativeViewport(){shutdown();}
void MapForgeNativeViewport::reload_asset_catalogs(){overlay_catalog_.load_directory(asset_root_/"assets"/"overlays");animated_prop_catalog_.load_directory(asset_root_/"assets"/"props");}

bool MapForgeNativeViewport::initialize(void* win32_hwnd,int physical_width,int physical_height,const std::string& asset_root_path){
    if(!win32_hwnd)return false;shutdown();physical_width_=physical_width;physical_height_=physical_height;asset_root_=asset_root_path;if(!SDL_WasInit(SDL_INIT_VIDEO)&&!SDL_Init(SDL_INIT_VIDEO))return false;SDL_PropertiesID props=SDL_CreateProperties();SDL_SetPointerProperty(props,SDL_PROP_WINDOW_CREATE_WIN32_HWND_POINTER,win32_hwnd);SDL_SetNumberProperty(props,SDL_PROP_WINDOW_CREATE_WIDTH_NUMBER,physical_width);SDL_SetNumberProperty(props,SDL_PROP_WINDOW_CREATE_HEIGHT_NUMBER,physical_height);window_=SDL_CreateWindowWithProperties(props);SDL_DestroyProperties(props);if(!window_)return false;renderer_=SDL_CreateRenderer(window_,nullptr);if(!renderer_){SDL_DestroyWindow(window_);window_=nullptr;return false;}reload_asset_catalogs();return true;
}

bool MapForgeNativeViewport::initialize_offscreen(int physical_width,int physical_height,const std::string& asset_root_path){shutdown();physical_width_=physical_width;physical_height_=physical_height;asset_root_=asset_root_path;if(!SDL_WasInit(SDL_INIT_VIDEO)&&!SDL_Init(SDL_INIT_VIDEO))return false;offscreen_surface_=SDL_CreateSurface(physical_width,physical_height,SDL_PIXELFORMAT_RGBA32);if(!offscreen_surface_)return false;renderer_=SDL_CreateSoftwareRenderer(offscreen_surface_);if(!renderer_){SDL_DestroySurface(offscreen_surface_);offscreen_surface_=nullptr;return false;}reload_asset_catalogs();return true;}

bool MapForgeNativeViewport::save_frame_to_png(const std::string& filepath){if(!renderer_)return false;render_frame();if(offscreen_surface_)return SDL_SaveBMP(offscreen_surface_,filepath.c_str());request_frame_capture(filepath);render_frame();return true;}
void MapForgeNativeViewport::resize(int physical_width,int physical_height){if(physical_width<=0||physical_height<=0)return;physical_width_=physical_width;physical_height_=physical_height;if(window_){SDL_SetWindowSize(window_,physical_width_,physical_height_);SDL_SyncWindow(window_);}}
void MapForgeNativeViewport::set_camera(const CameraState& camera){camera_=camera;}
bool MapForgeNativeViewport::load_map_document(const MapDocument& document){current_document_=document;return true;}

const TextureAsset* MapForgeNativeViewport::find_texture(const std::filesystem::path& relative_path){if(!renderer_)return nullptr;const std::string key=relative_path.generic_string();if(const auto it=texture_cache_.find(key);it!=texture_cache_.end())return &it->second;SDL_Surface* surface=SDL_LoadPNG((asset_root_/relative_path).string().c_str());if(!surface)return nullptr;TextureAsset asset;asset.texture=SDL_CreateTextureFromSurface(renderer_,surface);asset.source_width=static_cast<float>(surface->w);asset.source_height=static_cast<float>(surface->h);SDL_DestroySurface(surface);if(!asset.texture)return nullptr;SDL_SetTextureBlendMode(asset.texture,SDL_BLENDMODE_BLEND);SDL_SetTextureScaleMode(asset.texture,SDL_SCALEMODE_LINEAR);return &texture_cache_.emplace(key,asset).first->second;}

void MapForgeNativeViewport::clear_textures(){for(auto& [path,asset]:texture_cache_)if(asset.texture)SDL_DestroyTexture(asset.texture);texture_cache_.clear();for(auto& [key,asset]:overlay_texture_cache_)if(asset.texture)SDL_DestroyTexture(asset.texture);overlay_texture_cache_.clear();}

const TextureAsset* MapForgeNativeViewport::find_or_create_overlay_texture(const std::string&,const OverlayDefinition&,const std::string&){return nullptr;}

void MapForgeNativeViewport::render_frame(){
    if(!renderer_)return;int w=physical_width_,h=physical_height_;SDL_GetRenderOutputSize(renderer_,&w,&h);const float vw=static_cast<float>(w),vh=static_cast<float>(h);
    const auto texture_lookup=[this](const std::filesystem::path& p)->const TextureAsset*{return find_texture(p);};
    if((view_mode_==0||view_mode_==2)&&current_document_.has_value()){
        MapRenderer::render_world_terrain_and_water(renderer_,*current_document_,texture_lookup,asset_root_,camera_,vw,vh,static_cast<float>(SDL_GetTicks())/1000.0F);
    } else {SDL_SetRenderDrawColor(renderer_,20,24,28,SDL_ALPHA_OPAQUE);const SDL_FRect bg={0,0,vw,vh};SDL_RenderFillRect(renderer_,&bg);}
    if((view_mode_==1||view_mode_==2)&&current_document_.has_value())SemanticRenderer::render_semantic_overlays(renderer_,*current_document_,camera_,vw,vh,static_cast<SemanticChannel>(active_channels_),channel_opacity_);
    if(pending_capture_path_.has_value()){SDL_Surface* surface=SDL_RenderReadPixels(renderer_,nullptr);if(surface){SDL_SaveBMP(surface,pending_capture_path_->c_str());SDL_DestroySurface(surface);}pending_capture_path_.reset();}
    SDL_RenderPresent(renderer_);
}

RenderGeometrySignature MapForgeNativeViewport::compute_geometry_signature(const BuildingCatalog& catalog) const {if(!current_document_.has_value())return {};return MapRenderer::compute_geometry_signature(*current_document_,catalog,camera_,static_cast<float>(physical_width_),static_cast<float>(physical_height_));}
void MapForgeNativeViewport::shutdown(){clear_textures();if(renderer_){SDL_DestroyRenderer(renderer_);renderer_=nullptr;}if(window_){SDL_DestroyWindow(window_);window_=nullptr;}if(offscreen_surface_){SDL_DestroySurface(offscreen_surface_);offscreen_surface_=nullptr;}}

} // namespace ch
