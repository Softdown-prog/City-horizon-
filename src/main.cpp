#include <SDL3/SDL.h>

#include "src/ch_core/contracts.h"
#include "src/ch_core/grid.h"
#include "src/ch_core/projection.h"
#include "src/ch_core/map_document.h"
#include "src/ch_core/validation.h"
#include "src/ch_render/map_renderer.h"

#include "audio_manager.h"
#include "building_system.h"
#include "economy_system.h"
#include "farming_system.h"
#include "land_system.h"
#include "map_tile_occupancy.h"
#include "mission_system.h"
#include "mobile_animation.h"
#include "navigation_network.h"
#include "pedestrian_system.h"
#include "population_system.h"
#include "power_system.h"
#include "road_system.h"
#include "road_visual_catalog.h"
#include "resource_system.h"
#include "save_manager.h"
#include "simulation_clock.h"
#include "simulation_scheduler.h"
#include "sidewalk_system.h"
#include "ui_manager.h"
#include "vehicle_system.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <iostream>
#include <limits>
#include <optional>
#include <string>
#include <string_view>
#include <unordered_map>
#include <utility>
#include <vector>

namespace {

constexpr float kTileWidth = static_cast<float>(ch::contracts::kTileWidth);
constexpr float kTileHeight = static_cast<float>(ch::contracts::kTileHeight);
// A 48x48 logical map leaves a 32x32 owned starting parcel in the centre,
// plus locked land around every side for the expansion flow.
constexpr int kMapMin = ch::contracts::kMapMin;
constexpr int kMapMax = ch::contracts::kMapMax;
constexpr float kCameraKeyboardPanSpeed = 840.0F;
constexpr float kCameraEdgePanSpeed = 720.0F;
constexpr float kCameraEdgePanBand = 28.0F;
constexpr float kCameraPanResponsiveness = 14.0F;
// Temporary SE gait calibration starts with the calm preset: four canonical
// frames at 175 ms. This remains presentation tuning, not a navigation rule.
constexpr float kMixamoWalkSeTestSpeed = 0.80F;
constexpr float kMixamoWalkSeTestRate = 125.0F / 175.0F;

// Opaque bounds recorded by the PNG pipeline for grass_isometric_01_clean.png.
constexpr float kGrassOpaqueLeft = 53.0F;
constexpr float kGrassOpaqueTop = 23.0F;
constexpr float kGrassOpaqueWidth = 1175.0F;

// The logical world never rotates.  CameraRotation only changes how that
// world is projected, so saves, placement, topology and navigation retain
// their existing N/E/S/W meaning.
enum class CameraRotation : std::uint8_t { r0 = 0, r90 = 1, r180 = 2, r270 = 3 };

struct Camera {
    float pan_x = 0.0F;
    float pan_y = 0.0F;
    float pan_velocity_x = 0.0F;
    float pan_velocity_y = 0.0F;
    float zoom = 1.0F;
    CameraRotation rotation = CameraRotation::r0;
};

struct CameraWorldPoint {
    float x = 0.0F;
    float y = 0.0F;
};

// CH_WATER_V2: visual material only.  Logical water remains the terrain tile
// already loaded from the scenario; no placement, navigation or save contract
// changes are implied by this presentation layer.
struct WaterSurfaceTile {
    int tile_x = 0;
    int tile_y = 0;
    bool shallow = false;
};

struct ShorelineOverlayTile {
    int tile_x = 0;
    int tile_y = 0;
    const ch::TextureAsset* texture = nullptr;
};

[[nodiscard]] constexpr std::uint8_t camera_rotation_turns(const CameraRotation rotation) {
    return static_cast<std::uint8_t>(rotation);
}

[[nodiscard]] constexpr CameraRotation rotate_camera_clockwise(const CameraRotation rotation) {
    return static_cast<CameraRotation>((camera_rotation_turns(rotation) + 1U) % 4U);
}

[[nodiscard]] constexpr CameraRotation rotate_camera_counter_clockwise(const CameraRotation rotation) {
    return static_cast<CameraRotation>((camera_rotation_turns(rotation) + 3U) % 4U);
}

[[nodiscard]] const char* camera_rotation_label(const CameraRotation rotation) {
    switch (rotation) {
        case CameraRotation::r0: return "SOUTH";
        case CameraRotation::r90: return "WEST";
        case CameraRotation::r180: return "NORTH";
        case CameraRotation::r270: return "EAST";
    }
    return "SOUTH";
}

// Converts logical world coordinates to camera-local coordinates.  The
// inverse below keeps screen picking exactly aligned with the rotated view.
[[nodiscard]] constexpr CameraWorldPoint camera_view_point(const float x, const float y, const CameraRotation rotation) {
    const ch::WorldPoint wp = ch::camera_view_point(x, y, static_cast<ch::CameraRotation>(rotation));
    return {wp.x, wp.y};
}

[[nodiscard]] constexpr CameraWorldPoint logical_world_point(const float x, const float y, const CameraRotation rotation) {
    const ch::WorldPoint wp = ch::logical_world_point(x, y, static_cast<ch::CameraRotation>(rotation));
    return {wp.x, wp.y};
}

// Sprite sheets use the top point of an isometric diamond as their origin.
// With a rotated camera that point belongs to a different logical corner.
[[nodiscard]] constexpr CameraWorldPoint tile_visual_top_world(const int tile_x, const int tile_y, const CameraRotation rotation) {
    const ch::WorldPoint wp = ch::tile_visual_top_world(tile_x, tile_y, static_cast<ch::CameraRotation>(rotation));
    return {wp.x, wp.y};
}

[[nodiscard]] constexpr CameraWorldPoint building_visual_ground_world(const BuildingInstance& instance,
                                                                        const BuildingFootprint footprint,
                                                                        const CameraRotation rotation) {
    const ch::WorldPoint wp = ch::building_visual_ground_world(instance.tile_x, instance.tile_y, footprint.width, footprint.height, static_cast<ch::CameraRotation>(rotation));
    return {wp.x, wp.y};
}

[[nodiscard]] constexpr float camera_depth_key(const float world_x, const float world_y, const Camera& camera) {
    const ch::CameraState cs{camera.pan_x, camera.pan_y, camera.zoom, static_cast<ch::CameraRotation>(camera.rotation)};
    return ch::camera_depth_key(world_x, world_y, cs);
}

[[nodiscard]] constexpr CardinalDirection camera_visual_direction(const CardinalDirection direction, const CameraRotation rotation) {
    const int index = static_cast<int>(direction);
    const int visual_index = (index - static_cast<int>(camera_rotation_turns(rotation)) + 4) % 4;
    return static_cast<CardinalDirection>(visual_index);
}

[[nodiscard]] TileConnectionMask camera_visual_connections(const TileConnectionMask connections, const CameraRotation rotation) {
    TileConnectionMask visual = 0;
    for (const CardinalDirection direction : kCardinalDirections) {
        if (has_connection(connections, direction)) visual |= connection_bit(camera_visual_direction(direction, rotation));
    }
    return visual;
}

[[nodiscard]] BuildingRotation camera_visual_rotation(const BuildingDefinition& definition, const BuildingRotation logical_rotation,
                                                       const CameraRotation camera_rotation) {
    const int visual = (static_cast<int>(logical_rotation) - static_cast<int>(camera_rotation_turns(camera_rotation)) + 4) % 4;
    const BuildingRotation desired = static_cast<BuildingRotation>(visual);
    // Older single-art definitions remain visible instead of disappearing in
    // a view for which no authored directional variant exists.
    return definition.supports_rotation(desired) ? desired : logical_rotation;
}

[[nodiscard]] int mobile_direction_index(const MobileEntityDirection direction) {
    switch (direction) {
        case MobileEntityDirection::north: return 0;
        case MobileEntityDirection::east: return 1;
        case MobileEntityDirection::south: return 2;
        case MobileEntityDirection::west: return 3;
    }
    return 2;
}

[[nodiscard]] MobileEntityDirection mobile_direction_from_index(const int index) {
    switch ((index + 4) % 4) {
        case 0: return MobileEntityDirection::north;
        case 1: return MobileEntityDirection::east;
        case 2: return MobileEntityDirection::south;
        case 3: return MobileEntityDirection::west;
    }
    return MobileEntityDirection::south;
}

[[nodiscard]] MobileEntityRenderData camera_relative_mobile_entity(const MobileEntityRenderData& entity,
                                                                    const MobileAnimationCatalog& animations,
                                                                    const CameraRotation rotation) {
    MobileEntityRenderData result = entity;
    result.spatial.direction = mobile_direction_from_index(mobile_direction_index(entity.spatial.direction) -
                                                           static_cast<int>(camera_rotation_turns(rotation)));
    if (const MobileAnimationClip* clip = animations.resolve_clip(result.animation_set_id, result.logical_state, result.spatial.direction);
        clip != nullptr && !clip->frames.empty()) {
        result.animation_clip_id = clip->id;
        result.animation_frame_index = std::min(entity.animation_frame_index, clip->frames.size() - 1);
        result.sprite_asset = clip->frames[result.animation_frame_index];
    }
    return result;
}

using TextureAsset = ch::TextureAsset;

class TextureCache {
public:
    [[nodiscard]] const TextureAsset* load(SDL_Renderer* renderer, const std::filesystem::path& path) {
        const std::string key = path.generic_string();
        if (const auto existing = textures_.find(key); existing != textures_.end()) {
            return &existing->second;
        }

        TextureAsset asset;
        SDL_Surface* surface = SDL_LoadPNG(path.string().c_str());
        if (surface == nullptr) {
            std::cerr << "Texture could not be loaded: " << path << "\nSDL error: " << SDL_GetError() << '\n';
            return nullptr;
        }
        asset.texture = SDL_CreateTextureFromSurface(renderer, surface);
        asset.source_width = static_cast<float>(surface->w);
        asset.source_height = static_cast<float>(surface->h);
        SDL_DestroySurface(surface);

        if (asset.texture == nullptr) {
            std::cerr << "Texture could not be created: " << path << "\nSDL error: " << SDL_GetError() << '\n';
            return nullptr;
        }
        SDL_SetTextureBlendMode(asset.texture, SDL_BLENDMODE_BLEND);
        SDL_SetTextureScaleMode(asset.texture, SDL_SCALEMODE_LINEAR);
        return &textures_.emplace(key, asset).first->second;
    }

    [[nodiscard]] const TextureAsset* load_mask_channel(SDL_Renderer* renderer, const std::filesystem::path& path,
                                                        const char channel) {
        if (channel != 'R' && channel != 'G') return nullptr;
        const std::string key = path.generic_string() + "#CH_COLOR_MASK_" + channel;
        if (const auto existing = textures_.find(key); existing != textures_.end()) return &existing->second;

        SDL_Surface* source = SDL_LoadPNG(path.string().c_str());
        if (source == nullptr) {
            std::cerr << "Color mask could not be loaded: " << path << "\nSDL error: " << SDL_GetError() << '\n';
            return nullptr;
        }
        SDL_Surface* extracted = SDL_CreateSurface(source->w, source->h, SDL_PIXELFORMAT_RGBA32);
        if (extracted == nullptr) {
            SDL_DestroySurface(source);
            return nullptr;
        }
        for (int y = 0; y < source->h; ++y) {
            for (int x = 0; x < source->w; ++x) {
                Uint8 r = 0, g = 0, b = 0, a = 0;
                if (!SDL_ReadSurfacePixel(source, x, y, &r, &g, &b, &a)) continue;
                const Uint8 coverage = channel == 'R' ? r : g;
                const Uint8 mask_alpha = static_cast<Uint8>((static_cast<unsigned>(coverage) * static_cast<unsigned>(a)) / 255U);
                (void)SDL_WriteSurfacePixel(extracted, x, y, 255, 255, 255, mask_alpha);
            }
        }
        SDL_DestroySurface(source);

        TextureAsset asset;
        asset.texture = SDL_CreateTextureFromSurface(renderer, extracted);
        asset.source_width = static_cast<float>(extracted->w);
        asset.source_height = static_cast<float>(extracted->h);
        SDL_DestroySurface(extracted);
        if (asset.texture == nullptr) return nullptr;
        SDL_SetTextureBlendMode(asset.texture, SDL_BLENDMODE_BLEND);
        SDL_SetTextureScaleMode(asset.texture, SDL_SCALEMODE_LINEAR);
        return &textures_.emplace(key, asset).first->second;
    }

    [[nodiscard]] const TextureAsset* find_mask_channel(const std::filesystem::path& path, const char channel) const {
        const std::string key = path.generic_string() + "#CH_COLOR_MASK_" + channel;
        const auto found = textures_.find(key);
        return found == textures_.end() ? nullptr : &found->second;
    }

    [[nodiscard]] const TextureAsset* find(const std::filesystem::path& path) const {
        const auto found = textures_.find(path.generic_string());
        return found == textures_.end() ? nullptr : &found->second;
    }

    void clear() {
        for (const auto& [path, asset] : textures_) {
            (void)path;
            if (asset.texture != nullptr) {
                SDL_DestroyTexture(asset.texture);
            }
        }
        textures_.clear();
    }

private:
    std::unordered_map<std::string, TextureAsset> textures_;
};

[[nodiscard]] std::filesystem::path runtime_root() {
    const char* base_path = SDL_GetBasePath();
    return base_path == nullptr ? std::filesystem::path(".") : std::filesystem::path(base_path);
}

[[nodiscard]] SDL_FPoint world_to_screen(float world_x, float world_y, const Camera& camera, float viewport_width, float viewport_height) {
    const ch::CameraState cs{camera.pan_x, camera.pan_y, camera.zoom, static_cast<ch::CameraRotation>(camera.rotation)};
    const ch::ScreenPoint sp = ch::world_to_screen_point(world_x, world_y, cs, viewport_width, viewport_height);
    return {sp.x, sp.y};
}

[[nodiscard]] std::pair<int, int> screen_to_tile(float screen_x, float screen_y, const Camera& camera, float viewport_width, float viewport_height) {
    const ch::CameraState cs{camera.pan_x, camera.pan_y, camera.zoom, static_cast<ch::CameraRotation>(camera.rotation)};
    const ch::GridCoord gc = ch::screen_to_tile_coord(screen_x, screen_y, cs, viewport_width, viewport_height);
    return {gc.x, gc.y};
}

struct OwnedTileBounds {
    int min_x = 0;
    int min_y = 0;
    int max_x = 0; // Exclusive.
    int max_y = 0; // Exclusive.
};

[[nodiscard]] OwnedTileBounds owned_tile_bounds(const LandManager& lands) {
    bool found = false;
    OwnedTileBounds bounds;
    for (const LandParcel& parcel : lands.parcels()) {
        if (!parcel.owned) continue;
        if (!found) {
            bounds = {parcel.origin_x, parcel.origin_y, parcel.origin_x + parcel.width, parcel.origin_y + parcel.height};
            found = true;
        } else {
            bounds.min_x = std::min(bounds.min_x, parcel.origin_x);
            bounds.min_y = std::min(bounds.min_y, parcel.origin_y);
            bounds.max_x = std::max(bounds.max_x, parcel.origin_x + parcel.width);
            bounds.max_y = std::max(bounds.max_y, parcel.origin_y + parcel.height);
        }
    }
    return bounds;
}

[[nodiscard]] std::pair<int, int> nearest_owned_tile(const std::pair<int, int>& requested, const LandManager& lands) {
    if (lands.is_tile_owned(requested.first, requested.second)) return requested;
    int best_x = requested.first;
    int best_y = requested.second;
    int best_distance_squared = std::numeric_limits<int>::max();
    for (const LandParcel& parcel : lands.parcels()) {
        if (!parcel.owned) continue;
        const int x = std::clamp(requested.first, parcel.origin_x, parcel.origin_x + parcel.width - 1);
        const int y = std::clamp(requested.second, parcel.origin_y, parcel.origin_y + parcel.height - 1);
        const int dx = x - requested.first;
        const int dy = y - requested.second;
        const int distance_squared = dx * dx + dy * dy;
        if (distance_squared < best_distance_squared) {
            best_distance_squared = distance_squared;
            best_x = x;
            best_y = y;
        }
    }
    return {best_x, best_y};
}

void clamp_camera_to_owned_land(Camera& camera, const LandManager& lands, const float viewport_width, const float viewport_height) {
    const OwnedTileBounds bounds = owned_tile_bounds(lands);
    const float half_world_span = 0.5F * (
        viewport_width / (kTileWidth * camera.zoom) + viewport_height / (kTileHeight * camera.zoom));
    const float axis_x = -camera.pan_x / (kTileWidth * 0.5F * camera.zoom);
    const float axis_y = -camera.pan_y / (kTileHeight * 0.5F * camera.zoom);
    CameraWorldPoint center = logical_world_point((axis_y + axis_x) * 0.5F, (axis_y - axis_x) * 0.5F, camera.rotation);
    const float min_center_x = static_cast<float>(bounds.min_x) + half_world_span;
    const float max_center_x = static_cast<float>(bounds.max_x) - half_world_span;
    const float min_center_y = static_cast<float>(bounds.min_y) + half_world_span;
    const float max_center_y = static_cast<float>(bounds.max_y) - half_world_span;
    center.x = min_center_x <= max_center_x ? std::clamp(center.x, min_center_x, max_center_x)
                                             : (static_cast<float>(bounds.min_x + bounds.max_x) * 0.5F);
    center.y = min_center_y <= max_center_y ? std::clamp(center.y, min_center_y, max_center_y)
                                             : (static_cast<float>(bounds.min_y + bounds.max_y) * 0.5F);
    const CameraWorldPoint view = camera_view_point(center.x, center.y, camera.rotation);
    camera.pan_x = -(view.x - view.y) * (kTileWidth * 0.5F) * camera.zoom;
    camera.pan_y = -(view.x + view.y) * (kTileHeight * 0.5F) * camera.zoom;
}

void render_tile_outline(SDL_Renderer* renderer, int x, int y, const Camera& camera, float viewport_width, float viewport_height) {
    const ch::CameraState cs{camera.pan_x, camera.pan_y, camera.zoom, static_cast<ch::CameraRotation>(camera.rotation)};
    ch::MapRenderer::render_tile_outline(renderer, x, y, cs, viewport_width, viewport_height);
}

void render_navigation_debug_path(SDL_Renderer* renderer, const NavigationPathResult& path,
                                  const Camera& camera, float viewport_width, float viewport_height) {
    if (path.status != NavigationPathStatus::found || path.tiles.empty()) return;

    SDL_SetRenderDrawColor(renderer, 78, 212, 255, SDL_ALPHA_OPAQUE);
    SDL_FPoint previous{};
    bool has_previous = false;
    for (const NavigationTile& tile : path.tiles) {
        render_tile_outline(renderer, tile.x, tile.y, camera, viewport_width, viewport_height);
        const SDL_FPoint center = world_to_screen(static_cast<float>(tile.x) + 0.5F, static_cast<float>(tile.y) + 0.5F,
                                                  camera, viewport_width, viewport_height);
        if (has_previous) SDL_RenderLine(renderer, previous.x, previous.y, center.x, center.y);
        previous = center;
        has_previous = true;
    }

    SDL_SetRenderDrawColor(renderer, 98, 238, 112, SDL_ALPHA_OPAQUE);
    render_tile_outline(renderer, path.tiles.front().x, path.tiles.front().y, camera, viewport_width, viewport_height);
    SDL_SetRenderDrawColor(renderer, 255, 194, 74, SDL_ALPHA_OPAQUE);
    render_tile_outline(renderer, path.tiles.back().x, path.tiles.back().y, camera, viewport_width, viewport_height);
}

void render_footprint_outline(SDL_Renderer* renderer, const BuildingDefinition& definition, BuildingRotation rotation,
                              int tile_x, int tile_y,
                              const Camera& camera, float viewport_width, float viewport_height,
                              Uint8 red = 255, Uint8 green = 208, Uint8 blue = 92) {
    const ch::CameraState cs{camera.pan_x, camera.pan_y, camera.zoom, static_cast<ch::CameraRotation>(camera.rotation)};
    ch::MapRenderer::render_footprint_outline(renderer, definition, rotation, tile_x, tile_y, cs, viewport_width, viewport_height, red, green, blue);
}

[[nodiscard]] TileCoordinate road_access_offset(const GridDirection direction) {
    switch (direction) {
        case GridDirection::north: return {0, -1};
        case GridDirection::east: return {1, 0};
        case GridDirection::south: return {0, 1};
        case GridDirection::west: return {-1, 0};
    }
    return {};
}

void render_road_access_candidates(SDL_Renderer* renderer, const BuildingDefinition& definition,
                                   const BuildingRotation rotation, const int tile_x, const int tile_y,
                                   const RoadManager& roads, const Camera& camera,
                                   const float viewport_width, const float viewport_height) {
    const ch::CameraState cs{camera.pan_x, camera.pan_y, camera.zoom, static_cast<ch::CameraRotation>(camera.rotation)};
    ch::MapRenderer::render_road_access_candidates(renderer, definition, rotation, tile_x, tile_y, roads, cs, viewport_width, viewport_height);
}

void render_grass_tile(SDL_Renderer* renderer, const TextureAsset& grass, int x, int y,
                       const Camera& camera, float viewport_width, float viewport_height) {
    const ch::CameraState cs{camera.pan_x, camera.pan_y, camera.zoom, static_cast<ch::CameraRotation>(camera.rotation)};
    ch::MapRenderer::render_grass_tile(renderer, grass, x, y, cs, viewport_width, viewport_height);
}

void render_custom_terrain_tile(SDL_Renderer* renderer, const TextureAsset& texture, int x, int y,
                                const Camera& camera, float viewport_width, float viewport_height) {
    const ch::CameraState cs{camera.pan_x, camera.pan_y, camera.zoom, static_cast<ch::CameraRotation>(camera.rotation)};
    ch::MapRenderer::render_custom_terrain_tile(renderer, texture, x, y, cs, viewport_width, viewport_height);
}

void render_map(SDL_Renderer* renderer, const TextureAsset* grass,
                const std::unordered_map<std::uint64_t, const TextureAsset*>& scenario_terrain_textures,
                const Camera& camera, float viewport_width, float viewport_height) {
    const ch::CameraState cs{camera.pan_x, camera.pan_y, camera.zoom, static_cast<ch::CameraRotation>(camera.rotation)};
    ch::MapRenderer::render_map(renderer, grass, scenario_terrain_textures, cs, viewport_width, viewport_height);
}

void render_road_tile(SDL_Renderer* renderer, int tile_x, int tile_y, const Camera& camera,
                      float viewport_width, float viewport_height, SDL_FColor color) {
    const ch::CameraState cs{camera.pan_x, camera.pan_y, camera.zoom, static_cast<ch::CameraRotation>(camera.rotation)};
    ch::MapRenderer::render_road_tile(renderer, tile_x, tile_y, cs, viewport_width, viewport_height, color);
}

void render_tile_fill(SDL_Renderer* renderer, int tile_x, int tile_y, const Camera& camera,
                      float viewport_width, float viewport_height, const SDL_FColor color) {
    const ch::CameraState cs{camera.pan_x, camera.pan_y, camera.zoom, static_cast<ch::CameraRotation>(camera.rotation)};
    ch::MapRenderer::render_tile_fill(renderer, tile_x, tile_y, cs, viewport_width, viewport_height, color);
}

void render_water_v2_layers(SDL_Renderer* renderer, const std::vector<WaterSurfaceTile>& water_tiles,
                            const TextureAsset* caustics, const Camera& camera,
                            const float viewport_width, const float viewport_height) {
    if (water_tiles.empty()) return;
    const ch::CameraState cs{camera.pan_x, camera.pan_y, camera.zoom, static_cast<ch::CameraRotation>(camera.rotation)};
    constexpr SDL_FColor kDeepBase = {108.0F / 255.0F, 196.0F / 255.0F, 207.0F / 255.0F, 1.0F};
    constexpr SDL_FColor kShallowBase = {115.0F / 255.0F, 200.0F / 255.0F, 210.0F / 255.0F, 1.0F};
    for (const WaterSurfaceTile& tile : water_tiles) {
        ch::MapRenderer::render_tile_fill(renderer, tile.tile_x, tile.tile_y, cs, viewport_width, viewport_height,
                                          tile.shallow ? kShallowBase : kDeepBase);
    }
    if (caustics == nullptr) return;
    for (const WaterSurfaceTile& tile : water_tiles) {
        ch::MapRenderer::render_water_caustics_overlay_tile(
            renderer, *caustics, tile.tile_x, tile.tile_y, cs, viewport_width, viewport_height);
    }
}

void render_land_overlays(SDL_Renderer* renderer, const LandManager& lands, const LandParcel* hovered_parcel,
                          const bool land_mode, const Camera& camera, const float viewport_width, const float viewport_height) {
    const ch::CameraState cs{camera.pan_x, camera.pan_y, camera.zoom, static_cast<ch::CameraRotation>(camera.rotation)};
    ch::MapRenderer::render_land_overlays(renderer, lands, hovered_parcel, land_mode, cs, viewport_width, viewport_height);
}

void render_road_sprite(SDL_Renderer* renderer, const TextureAsset& texture, int tile_x, int tile_y,
                        const Camera& camera, float viewport_width, float viewport_height) {
    const ch::CameraState cs{camera.pan_x, camera.pan_y, camera.zoom, static_cast<ch::CameraRotation>(camera.rotation)};
    ch::MapRenderer::render_road_sprite(renderer, texture, tile_x, tile_y, cs, viewport_width, viewport_height);
}

void render_roads(SDL_Renderer* renderer, const RoadManager& roads, const RoadVisualCatalog& visuals,
                  const TextureCache& textures, const std::filesystem::path& asset_root, const Camera& camera,
                  float viewport_width, float viewport_height) {
    const ch::CameraState cs{camera.pan_x, camera.pan_y, camera.zoom, static_cast<ch::CameraRotation>(camera.rotation)};
    ch::MapRenderer::render_roads(renderer, roads, visuals,
                                  [&textures](const std::filesystem::path& p) { return textures.find(p); },
                                  asset_root, cs, viewport_width, viewport_height);
}

void render_sidewalks(SDL_Renderer* renderer, const SidewalkManager& sidewalks, const TextureCache& textures,
                      const std::filesystem::path& root, const Camera& camera, float vw, float vh) {
    const ch::CameraState cs{camera.pan_x, camera.pan_y, camera.zoom, static_cast<ch::CameraRotation>(camera.rotation)};
    ch::MapRenderer::render_sidewalks(renderer, sidewalks,
                                     [&textures](const std::filesystem::path& p) { return textures.find(p); },
                                     root, cs, vw, vh);
}

void render_farming(SDL_Renderer* renderer, const FarmingSystem& farming, const CropCatalog& crops,
                    const TextureCache& textures, const std::filesystem::path& root, const Camera& camera,
                    float viewport_width, float viewport_height) {
    const ch::CameraState cs{camera.pan_x, camera.pan_y, camera.zoom, static_cast<ch::CameraRotation>(camera.rotation)};
    ch::MapRenderer::render_farming(renderer, farming, crops,
                                    [&textures](const std::filesystem::path& p) { return textures.find(p); },
                                    root, cs, viewport_width, viewport_height);
}

[[nodiscard]] bool building_overlaps_road(const BuildingDefinition& definition, BuildingRotation rotation,
                                          int tile_x, int tile_y, const RoadManager& roads) {
    return roads.overlaps_building_footprint(definition, tile_x, tile_y, rotation);
}

[[nodiscard]] bool road_segment_is_valid(const std::vector<TileCoordinate>& tiles, const RoadManager& roads,
                                          const BuildingManager& buildings) {
    return std::all_of(tiles.begin(), tiles.end(), [&roads, &buildings](const TileCoordinate& tile) {
        return roads.validate_placement(tile.x, tile.y, buildings) == RoadPlacementFailure::none;
    });
}

[[nodiscard]] bool building_is_on_owned_land(const BuildingDefinition& definition, const BuildingRotation rotation,
                                              const int tile_x, const int tile_y, const LandManager& lands) {
    const BuildingFootprint footprint = rotated_footprint(definition, rotation);
    return lands.is_area_owned(tile_x, tile_y, footprint.width, footprint.height);
}

[[nodiscard]] bool building_overlaps_sidewalk(const BuildingDefinition& definition, const BuildingRotation rotation,
                                              const int tile_x, const int tile_y, const SidewalkManager& sidewalks) {
    const BuildingFootprint footprint = rotated_footprint(definition, rotation);
    for (int y = 0; y < footprint.height; ++y) {
        for (int x = 0; x < footprint.width; ++x) {
            if (sidewalks.is_sidewalk(tile_x + x, tile_y + y)) return true;
        }
    }
    return false;
}

[[nodiscard]] bool building_overlaps_farm(const BuildingDefinition& definition, const BuildingRotation rotation,
                                          const int tile_x, const int tile_y, const FarmingSystem& farming) {
    const BuildingFootprint footprint = rotated_footprint(definition, rotation);
    for (int y = 0; y < footprint.height; ++y) {
        for (int x = 0; x < footprint.width; ++x) {
            if (farming.is_occupied(tile_x + x, tile_y + y)) return true;
        }
    }
    return false;
}

[[nodiscard]] bool building_has_required_edge_access(const BuildingDefinition& definition,
                                                        const BuildingRotation rotation,
                                                        const int tile_x, const int tile_y,
                                                        const RoadManager& roads,
                                                        const SidewalkManager& sidewalks) {
    if (!definition.requires_road_or_path_access) {
        return roads.has_required_road_access(definition, tile_x, tile_y, rotation);
    }

    const BuildingFootprint footprint = rotated_footprint(definition, rotation);
    const auto edge_is_accessible = [&](const int x, const int y) {
        return roads.is_road(x, y) || sidewalks.is_sidewalk(x, y);
    };
    for (int x = 0; x < footprint.width; ++x) {
        if (edge_is_accessible(tile_x + x, tile_y - 1) ||
            edge_is_accessible(tile_x + x, tile_y + footprint.height)) {
            return true;
        }
    }
    for (int y = 0; y < footprint.height; ++y) {
        if (edge_is_accessible(tile_x - 1, tile_y + y) ||
            edge_is_accessible(tile_x + footprint.width, tile_y + y)) {
            return true;
        }
    }
    return false;
}

[[nodiscard]] bool building_footprint_is_grass(const BuildingDefinition& definition,
                                                const BuildingRotation rotation,
                                                const int tile_x, const int tile_y,
                                                const ch::MapDocument* map_document) {
    if (!definition.grass_only || map_document == nullptr) return true;
    const BuildingFootprint footprint = rotated_footprint(definition, rotation);
    for (int y = 0; y < footprint.height; ++y) {
        for (int x = 0; x < footprint.width; ++x) {
            const auto terrain = map_document->get_terrain_at(tile_x + x, tile_y + y);
            // The runtime's implicit base terrain is grass. Explicit terrain
            // entries must identify themselves as grass; water, sand and
            // unresolved legacy terrain fail closed for grass-only props.
            if (terrain && terrain->terrain_definition != "grass") return false;
        }
    }
    return true;
}

[[nodiscard]] const char* placement_failure_text(PlacementFailure failure);

struct BuildingPlacementValidation {
    PlacementFailure failure = PlacementFailure::none;
    bool affordable = false;
    bool on_road = false;
    bool on_sidewalk = false;
    bool on_farm = false;
    bool on_owned_land = false;
    bool on_allowed_terrain = true;
    bool accepts_path_access = false;
    bool has_road_access = false;
    bool has_power = false;

    [[nodiscard]] bool valid() const {
        // Buildings remain placeable during a power shortage.  Power is a
        // city-wide operating state, not a spatial placement rule: blocking
        // the catalogue at the base capacity made most civic/commercial
        // buildings impossible to add before the player could expand power.
        return failure == PlacementFailure::none && affordable && !on_road && !on_sidewalk && !on_farm &&
               on_owned_land && on_allowed_terrain && has_road_access;
    }
};

[[nodiscard]] BuildingPlacementValidation validate_building_placement(
    const BuildingDefinition& definition, const BuildingRotation rotation, const int tile_x, const int tile_y,
    const BuildingManager& buildings, const RoadManager& roads, const LandManager& lands,
    const SidewalkManager& sidewalks, const FarmingSystem& farming, const CityEconomy& economy, const PowerSystem& power,
    const ch::MapDocument* map_document) {
    return {
        buildings.validate(definition, tile_x, tile_y, rotation),
        economy.can_afford(definition.build_cost),
        building_overlaps_road(definition, rotation, tile_x, tile_y, roads),
        building_overlaps_sidewalk(definition, rotation, tile_x, tile_y, sidewalks),
        building_overlaps_farm(definition, rotation, tile_x, tile_y, farming),
        building_is_on_owned_land(definition, rotation, tile_x, tile_y, lands),
        building_footprint_is_grass(definition, rotation, tile_x, tile_y, map_document),
        definition.requires_road_or_path_access,
        building_has_required_edge_access(definition, rotation, tile_x, tile_y, roads, sidewalks),
        power.can_support(definition),
    };
}

[[nodiscard]] std::string placement_validation_text(const BuildingPlacementValidation& validation) {
    if (validation.failure != PlacementFailure::none) {
        return placement_failure_text(validation.failure);
    }
    if (!validation.on_owned_land) {
        return "LAND NOT OWNED";
    }
    if (validation.on_road) {
        return "AREA HAS ROAD";
    }
    if (validation.on_sidewalk) {
        return "AREA HAS SIDEWALK";
    }
    if (validation.on_farm) {
        return "BUILDING BLOCKED BY FARM TILE";
    }
    if (!validation.on_allowed_terrain) {
        return "REQUIRES GRASS TILE";
    }
    if (!validation.has_road_access) {
        return validation.accepts_path_access ? "ROAD OR PATH ADJACENCY REQUIRED" : "ROAD AT ENTRANCE REQUIRED";
    }
    if (!validation.affordable) {
        return "NOT ENOUGH FUNDS";
    }
    return "VALID AREA";
}

[[nodiscard]] bool road_segment_is_on_owned_land(const std::vector<TileCoordinate>& tiles, const LandManager& lands) {
    return !tiles.empty() && std::all_of(tiles.begin(), tiles.end(), [&lands](const TileCoordinate& tile) {
        return lands.is_tile_owned(tile.x, tile.y);
    });
}

[[nodiscard]] const char* tile_occupancy_label(const BuildingManager& buildings, const RoadManager& roads,
                                                const SidewalkManager& sidewalks, const FarmingSystem& farming,
                                                const int tile_x, const int tile_y) {
    // A single diagnostic ordering makes layer conflicts visible in one place.
    // Placement systems still validate their own footprint-specific rules.
    const MapTileOccupancy occupancy = inspect_map_tile(buildings, roads, sidewalks, farming, tile_x, tile_y);
    if (occupancy.building) return "BUILDING";
    if (occupancy.road) return "ROAD";
    if (occupancy.sidewalk) return "SIDEWALK";
    if (occupancy.farm) return "FARM";
    return "EMPTY";
}

[[nodiscard]] std::string connection_label(const TileConnectionMask mask) {
    return "N" + std::to_string(has_connection(mask, CardinalDirection::north)) +
           " E" + std::to_string(has_connection(mask, CardinalDirection::east)) +
           " S" + std::to_string(has_connection(mask, CardinalDirection::south)) +
           " W" + std::to_string(has_connection(mask, CardinalDirection::west));
}

[[nodiscard]] const char* mobile_direction_label(const MobileEntityDirection direction) {
    switch (direction) {
        case MobileEntityDirection::north: return "NORTH";
        case MobileEntityDirection::east: return "EAST";
        case MobileEntityDirection::south: return "SOUTH";
        case MobileEntityDirection::west: return "WEST";
    }
    return "SOUTH";
}

// This is the single visual geometry contract for every building sprite.  The
// footprint is logical; the PNG may extend beyond it, but its declared anchor
// always lands on the same footprint ground point.
struct BuildingSpriteGeometry {
    CameraWorldPoint ground;
    SDL_FPoint screen_anchor;
    SDL_FRect sprite_bounds;
};

void draw_text(SDL_Renderer* renderer, float x, float y, const std::string& text,
               Uint8 red, Uint8 green, Uint8 blue);

[[nodiscard]] BuildingSpriteGeometry building_sprite_geometry(const BuildingDefinition& definition,
                                                               const BuildingInstance& instance,
                                                               const BuildingRotation visual_rotation,
                                                               const TextureAsset& texture,
                                                               const Camera& camera,
                                                               const float viewport_width,
                                                               const float viewport_height) {
    const BuildingFootprint footprint = rotated_footprint(definition, instance.rotation);
    const CameraWorldPoint ground = building_visual_ground_world(instance, footprint, camera.rotation);
    const SDL_FPoint anchor = world_to_screen(ground.x, ground.y, camera, viewport_width, viewport_height);
    const float scale = definition.art_scale * camera.zoom;
    const float frame_w = definition.animation.has_value() && definition.animation->frame_count > 1
        ? static_cast<float>(texture.source_width) / static_cast<float>(definition.animation->frame_count)
        : static_cast<float>(texture.source_width);
    const float frame_h = static_cast<float>(texture.source_height);
    const SDL_FRect bounds = {
        anchor.x - frame_w * scale * definition.anchor_x_for(visual_rotation, instance.current_level),
        anchor.y - frame_h * scale * definition.anchor_y_for(visual_rotation, instance.current_level),
        frame_w * scale,
        frame_h * scale,
    };
    return {ground, anchor, bounds};
}

void render_building(SDL_Renderer* renderer, const BuildingDefinition& definition, const BuildingInstance& instance,
                     const BuildingRotation visual_rotation, const TextureAsset& texture, const Camera& camera,
                     float viewport_width, float viewport_height,
                     Uint8 alpha = SDL_ALPHA_OPAQUE,
                     Uint8 red = 255, Uint8 green = 255, Uint8 blue = 255) {
    const ch::CameraState cs{camera.pan_x, camera.pan_y, camera.zoom, static_cast<ch::CameraRotation>(camera.rotation)};
    ch::MapRenderer::render_building(renderer, definition, instance, visual_rotation, texture.texture,
                                     texture.source_width, texture.source_height, cs, viewport_width, viewport_height,
                                     alpha, red, green, blue);
}


void render_building_activity_overlay(SDL_Renderer* renderer, const BuildingDefinition& definition,
                                      const BuildingInstance& instance, const BuildingRotation visual_rotation,
                                      const TextureCache& textures, const std::filesystem::path& asset_root,
                                      const Camera& camera, const float viewport_width, const float viewport_height) {
    if (!instance.activity_active() || !definition.activity_overlay || !definition.activity_overlay->enabled) return;
    const std::size_t rotation_index = static_cast<std::size_t>(visual_rotation);
    if (rotation_index >= definition.activity_overlay->sprite_paths.size()) return;
    const std::string& relative_path = definition.activity_overlay->sprite_paths[rotation_index];
    if (relative_path.empty()) return;
    const TextureAsset* texture = textures.find(asset_root / relative_path);
    if (texture == nullptr || texture->texture == nullptr) return;

    const BuildingAnimationDefinition* animation = definition.activity_overlay->animation
        ? &*definition.activity_overlay->animation : nullptr;
    const int frame_count = animation == nullptr ? 1 : std::max(1, animation->frame_count);
    const int frame_duration_ms = animation == nullptr ? 1 : std::max(1, animation->frame_duration_ms);
    int frame_index = 0;
    if (frame_count > 1) {
        const Uint64 elapsed_ms = SDL_GetTicks();
        if (animation->playback == "ambient_once") {
            frame_index = std::min(frame_count - 1, static_cast<int>(elapsed_ms / static_cast<Uint64>(frame_duration_ms)));
        } else {
            frame_index = static_cast<int>((elapsed_ms / static_cast<Uint64>(frame_duration_ms)) % static_cast<Uint64>(frame_count));
        }
    }

    const float frame_width = texture->source_width / static_cast<float>(frame_count);
    const float frame_height = texture->source_height;
    const SDL_FRect source = {frame_width * static_cast<float>(frame_index), 0.0F, frame_width, frame_height};
    const BuildingFootprint footprint = rotated_footprint(definition, instance.rotation);
    const CameraWorldPoint ground = building_visual_ground_world(instance, footprint, camera.rotation);
    const SDL_FPoint anchor = world_to_screen(ground.x, ground.y, camera, viewport_width, viewport_height);
    const float scale = definition.art_scale * camera.zoom;
    const SDL_FRect destination = {
        anchor.x - frame_width * scale * definition.anchor_x_for(visual_rotation, instance.current_level),
        anchor.y - frame_height * scale * definition.anchor_y_for(visual_rotation, instance.current_level),
        frame_width * scale,
        frame_height * scale,
    };
    SDL_RenderTexture(renderer, texture->texture, &source, &destination);
}

void render_anchor_cross(SDL_Renderer* renderer, const SDL_FPoint point, const float radius,
                         const Uint8 red, const Uint8 green, const Uint8 blue) {
    SDL_SetRenderDrawColor(renderer, red, green, blue, SDL_ALPHA_OPAQUE);
    SDL_RenderLine(renderer, point.x - radius, point.y, point.x + radius, point.y);
    SDL_RenderLine(renderer, point.x, point.y - radius, point.x, point.y + radius);
}

// F1 calibration overlay: it draws diagnostic geometry over exactly the same
// projection and anchor calculation used by render_building above.  It must
// never alter placement or asset offsets.
void render_building_calibration_debug(SDL_Renderer* renderer, const BuildingDefinition& definition,
                                       const BuildingInstance& instance, const BuildingRotation visual_rotation,
                                       const TextureAsset& texture, const RoadManager& roads,
                                       const Camera& camera, const float viewport_width, const float viewport_height) {
    const BuildingFootprint footprint = rotated_footprint(definition, instance.rotation);

    // A deliberately small 2:1 reference grid makes a bad base/asset obvious
    // without obscuring the actual map.
    SDL_SetRenderDrawColor(renderer, 54, 134, 164, 175);
    for (int y = instance.tile_y - 2; y < instance.tile_y + footprint.height + 2; ++y) {
        for (int x = instance.tile_x - 2; x < instance.tile_x + footprint.width + 2; ++x) {
            render_tile_outline(renderer, x, y, camera, viewport_width, viewport_height);
        }
    }

    render_footprint_outline(renderer, definition, instance.rotation, instance.tile_x, instance.tile_y,
                             camera, viewport_width, viewport_height, 255, 208, 92);
    render_road_access_candidates(renderer, definition, instance.rotation, instance.tile_x, instance.tile_y,
                                  roads, camera, viewport_width, viewport_height);

    const BuildingSpriteGeometry geometry = building_sprite_geometry(definition, instance, visual_rotation, texture, camera,
                                                                       viewport_width, viewport_height);
    SDL_SetRenderDrawColor(renderer, 238, 94, 224, SDL_ALPHA_OPAQUE);
    SDL_RenderRect(renderer, &geometry.sprite_bounds);
    render_anchor_cross(renderer, geometry.screen_anchor, 8.0F, 72, 236, 255);

    // The two projected world axes start at the logical footprint centre.
    const float centre_x = static_cast<float>(instance.tile_x) + static_cast<float>(footprint.width) * 0.5F;
    const float centre_y = static_cast<float>(instance.tile_y) + static_cast<float>(footprint.height) * 0.5F;
    const SDL_FPoint centre = world_to_screen(centre_x, centre_y, camera, viewport_width, viewport_height);
    const SDL_FPoint axis_x = world_to_screen(centre_x + 1.0F, centre_y, camera, viewport_width, viewport_height);
    const SDL_FPoint axis_y = world_to_screen(centre_x, centre_y + 1.0F, camera, viewport_width, viewport_height);
    render_anchor_cross(renderer, centre, 5.0F, 255, 255, 255);
    SDL_SetRenderDrawColor(renderer, 255, 92, 92, SDL_ALPHA_OPAQUE);
    SDL_RenderLine(renderer, centre.x, centre.y, axis_x.x, axis_x.y);
    SDL_SetRenderDrawColor(renderer, 104, 236, 124, SDL_ALPHA_OPAQUE);
    SDL_RenderLine(renderer, centre.x, centre.y, axis_y.x, axis_y.y);
    draw_text(renderer, axis_x.x + 4.0F, axis_x.y - 8.0F, "X", 255, 92, 92);
    draw_text(renderer, axis_y.x + 4.0F, axis_y.y - 8.0F, "Y", 104, 236, 124);
    draw_text(renderer, geometry.screen_anchor.x + 10.0F, geometry.screen_anchor.y - 10.0F, "A", 72, 236, 255);
}

void render_buildings(SDL_Renderer* renderer, const BuildingManager& manager, const BuildingCatalog& catalog,
                      const LandManager& lands, const TextureCache& textures, const std::filesystem::path& asset_root,
                      const Camera& camera, float viewport_width, float viewport_height) {
    const ch::CameraState cs{camera.pan_x, camera.pan_y, camera.zoom, static_cast<ch::CameraRotation>(camera.rotation)};
    ch::MapRenderer::render_buildings(renderer, manager, catalog, lands,
                                      [&textures](const std::filesystem::path& p) { return textures.find(p); },
                                      asset_root, cs, viewport_width, viewport_height);
}

void render_world_entities(SDL_Renderer* renderer, const BuildingManager& buildings,
                           const BuildingCatalog& building_catalog, const LandManager& lands,
                           const std::vector<MobileEntityRenderData>& mobile_entities,
                           const MobileAnimationCatalog& animations, const TextureCache& textures,
                           const std::filesystem::path& root, const Camera& camera,
                           float viewport_width, float viewport_height) {
    struct EntityDraw {
        enum class Kind { building, mobile_entity } kind = Kind::building;
        float depth = 0.0F;
        const BuildingInstance* building = nullptr;
        const MobileEntityRenderData* mobile_entity = nullptr;
    };
    std::vector<EntityDraw> draws;
    draws.reserve(buildings.instances().size() + mobile_entities.size());
    for (const BuildingInstance& instance : buildings.instances()) {
        const BuildingDefinition* definition = building_catalog.find(instance.definition_id);
        if (definition == nullptr) continue;
        const BuildingFootprint footprint = rotated_footprint(*definition, instance.rotation);
        const CameraWorldPoint ground = building_visual_ground_world(instance, footprint, camera.rotation);
        draws.push_back({EntityDraw::Kind::building, camera_depth_key(ground.x, ground.y, camera), &instance, nullptr});
    }
    std::vector<MobileEntityRenderData> camera_relative_mobiles;
    camera_relative_mobiles.reserve(mobile_entities.size());
    for (const MobileEntityRenderData& entity : mobile_entities) {
        camera_relative_mobiles.push_back(camera_relative_mobile_entity(entity, animations, camera.rotation));
        const MobileEntityRenderData& visual = camera_relative_mobiles.back();
        draws.push_back({EntityDraw::Kind::mobile_entity,
                         camera_depth_key(visual.spatial.visual_world_x + visual.spatial.ground_anchor_x,
                                          visual.spatial.visual_world_y + visual.spatial.ground_anchor_y, camera),
                         nullptr, &visual});
    }
    std::stable_sort(draws.begin(), draws.end(), [](const EntityDraw& left, const EntityDraw& right) {
        return left.depth < right.depth;
    });
    for (const EntityDraw& draw : draws) {
        if (draw.kind == EntityDraw::Kind::building) {
            const BuildingDefinition* definition = building_catalog.find(draw.building->definition_id);
            if (definition == nullptr) continue;
            const BuildingRotation visual_rotation = camera_visual_rotation(*definition, draw.building->rotation, camera.rotation);
            const TextureAsset* texture = textures.find(root / definition->texture_path_for(visual_rotation));
            if (texture != nullptr) {
                const bool is_owned = lands.is_tile_owned(draw.building->tile_x, draw.building->tile_y);
                const Uint8 r = is_owned ? 255 : 140;
                const Uint8 g = is_owned ? 255 : 145;
                const Uint8 b = is_owned ? 255 : 155;
                render_building(renderer, *definition, *draw.building, visual_rotation, *texture, camera, viewport_width, viewport_height, SDL_ALPHA_OPAQUE, r, g, b);

                // CH_COLOR_MASK_V1 is opt-in. The approved source sprite stays
                // untouched until this concrete instance has player colors.
                if ((draw.building->wall_color_customized || draw.building->roof_color_customized) &&
                    definition->supports_color_mask(visual_rotation)) {
                    constexpr Uint8 kTintOverlayAlpha = 184;
                    const auto mask_path = root / definition->color_mask_path_for(visual_rotation);
                    if (draw.building->wall_color_customized) {
                        if (const TextureAsset* wall = textures.find_mask_channel(mask_path, 'R')) {
                            render_building(renderer, *definition, *draw.building, visual_rotation, *wall, camera,
                                            viewport_width, viewport_height, kTintOverlayAlpha,
                                            draw.building->wall_tint.r, draw.building->wall_tint.g, draw.building->wall_tint.b);
                        }
                    }
                    if (draw.building->roof_color_customized) {
                        if (const TextureAsset* roof = textures.find_mask_channel(mask_path, 'G')) {
                            render_building(renderer, *definition, *draw.building, visual_rotation, *roof, camera,
                                            viewport_width, viewport_height, kTintOverlayAlpha,
                                            draw.building->roof_tint.r, draw.building->roof_tint.g, draw.building->roof_tint.b);
                        }
                    }
                }
                render_building_activity_overlay(renderer, *definition, *draw.building, visual_rotation,
                                                 textures, root, camera, viewport_width, viewport_height);
            }
            continue;
        }
        const MobileEntityRenderData& entity = *draw.mobile_entity;
        const TextureAsset* texture = textures.find(root / entity.sprite_asset);
        if (texture == nullptr) continue;
        const SDL_FPoint anchor = world_to_screen(entity.spatial.visual_world_x + entity.spatial.ground_anchor_x,
                                                  entity.spatial.visual_world_y + entity.spatial.ground_anchor_y,
                                                  camera, viewport_width, viewport_height);
        const float scale = entity.art_scale * camera.zoom;
        const SDL_FRect destination = {anchor.x - texture->source_width * scale * entity.sprite_anchor_x,
                                       anchor.y - texture->source_height * scale * entity.sprite_anchor_y,
                                       texture->source_width * scale, texture->source_height * scale};
        SDL_RenderTexture(renderer, texture->texture, nullptr, &destination);
    }
}

void render_seagull_flight(SDL_Renderer* renderer, const TextureCache& textures, const std::filesystem::path& root,
                           const char* variant_id, const char* filename_prefix, const char* filename_suffix, const float time_seconds,
                           const float route_x, const float route_start_y, const float route_end_y, const float route_progress,
                           const Camera& camera, const float viewport_width, const float viewport_height) {
    const int frame = static_cast<int>(time_seconds * 3.5F) % 8;
    const std::string filename = std::string(filename_prefix) + (frame < 10 ? "0" : "") + std::to_string(frame) + filename_suffix + ".png";
    const auto path = root / "assets/ambient" / variant_id / "frames" / filename;
    const TextureAsset* texture = textures.find(path);
    if (texture == nullptr) return;
    // Ambient aerial pass is presentation-only: no navigation, placement,
    // occupancy, or simulation state is attached to the sprite.
    const float y = route_start_y + (route_end_y - route_start_y) * std::clamp(route_progress, 0.0F, 1.0F);
    const SDL_FPoint screen = world_to_screen(route_x, y, camera, viewport_width, viewport_height);
    const float size = 54.0F * camera.zoom;
    const SDL_FRect destination = {screen.x - size * 0.5F, screen.y - 86.0F * camera.zoom, size, size};
    SDL_RenderTexture(renderer, texture->texture, nullptr, &destination);
}

void render_seagull_north(SDL_Renderer* renderer, const TextureCache& textures, const std::filesystem::path& root,
                          const float time_seconds, const float route_x, const float route_start_y, const float route_end_y,
                          const float route_progress, const Camera& camera, const float viewport_width, const float viewport_height) {
    render_seagull_flight(renderer, textures, root, "seagull_north", "flight_north_", "", time_seconds,
                          route_x, route_start_y, route_end_y, route_progress, camera, viewport_width, viewport_height);
}

void render_seagull_south(SDL_Renderer* renderer, const TextureCache& textures, const std::filesystem::path& root,
                          const float time_seconds, const float route_x, const float route_start_y, const float route_end_y,
                          const float route_progress, const Camera& camera, const float viewport_width, const float viewport_height) {
    render_seagull_flight(renderer, textures, root, "seagull_south", "seagull_south_frame_", "_ocean_blue", time_seconds,
                          route_x, route_start_y, route_end_y, route_progress, camera, viewport_width, viewport_height);
}

[[nodiscard]] std::string format_money(std::int64_t value) {
    const bool negative = value < 0;
    const std::uint64_t magnitude = negative
        ? static_cast<std::uint64_t>(-(value + 1)) + 1U
        : static_cast<std::uint64_t>(value);
    std::string digits = std::to_string(magnitude);
    for (int index = static_cast<int>(digits.size()) - 3; index > 0; index -= 3) {
        digits.insert(static_cast<std::size_t>(index), ".");
    }
    return negative ? "-$" + digits : "$" + digits;
}

[[nodiscard]] std::string format_balance(const std::int64_t value) {
    return value >= 0 ? "+" + format_money(value) : format_money(value);
}

[[nodiscard]] std::string format_date(const GameDate& date) {
    return "DAY " + std::to_string(date.day) + " | MONTH " + std::to_string(date.month) + " | YEAR " + std::to_string(date.year);
}

[[nodiscard]] const char* placement_failure_text(PlacementFailure failure) {
    switch (failure) {
        case PlacementFailure::none: return "VALID AREA";
        case PlacementFailure::unavailable_rotation: return "ROTATION NOT AVAILABLE";
        case PlacementFailure::outside_map: return "OUTSIDE MAP";
        case PlacementFailure::occupied: return "AREA OCCUPIED";
    }
    return "UNKNOWN";
}

[[nodiscard]] const char* category_label(std::string_view category) {
    if (category == "commercial") {
        return "COMERCIO";
    }
    if (category == "residential") {
        return "RESIDENCIAL";
    }
    if (category == "agriculture") {
        return "AGRICULTURA";
    }
    if (category == "civic" || category == "service") {
        return "SERVICOS";
    }
    if (category == "infrastructure") {
        return "INFRAESTRUTURA";
    }
    if (category == "decor") {
        return "DECORACAO";
    }
    return "OUTRO";
}

// Some waterfront assets are authored as `decor` because they do not affect
// city simulation.  They are nevertheless player-built structures (rather
// than small landscape props), so the construction catalogue must expose
// them alongside buildings.  Keep this a UI classification only: changing
// the simulation category would incorrectly make a pier or lighthouse behave
// like a civic/commercial building.
[[nodiscard]] bool belongs_in_construction_catalog(const BuildingDefinition& definition) {
    if (definition.category != "decor") {
        return true;
    }

    static constexpr std::array<std::string_view, 9> kBuiltStructures = {
        "beach_lifeguard_tower",
        "beach_lighthouse",
        "beach_pier_small",
        "beach_pier_large",
        "dock_medium_01",
        "dock_large_01",
        "gazebo_01",
        "gazebo_island_01",
        "beach_dock_stairs",
    };
    return std::find(kBuiltStructures.begin(), kBuiltStructures.end(), definition.id) != kBuiltStructures.end();
}

[[nodiscard]] const char* construction_catalog_label(const BuildingDefinition& definition) {
    return definition.category == "decor" ? "ESTRUTURA" : category_label(definition.category);
}

[[nodiscard]] std::string catalog_thumbnail_path(const std::filesystem::path& asset_root,
                                                  const BuildingDefinition& definition) {
    const std::filesystem::path dedicated = asset_root / "assets" / "ui" / "thumbnails" / "buildings" /
                                            (definition.id + ".png");
    // The catalog deliberately prefers its fixed-canvas thumbnail. The world
    // sprite remains a fallback for third-party or unfinished definitions.
    // The old bakery card was a different building. Show the installed sprite.
    return definition.id != "bakery_01" && std::filesystem::exists(dedicated)
        ? dedicated.string()
        : (asset_root / definition.texture_path_for(BuildingRotation::r0)).string();
}

[[nodiscard]] std::string catalog_footprint_label(const BuildingDefinition& definition) {
    return "LOTE " + std::to_string(definition.footprint_width) + "x" +
           std::to_string(definition.footprint_height);
}

[[nodiscard]] std::string catalog_requirements_label(const BuildingDefinition& definition) {
    std::string label = definition.requires_road_or_path_access
        ? "RUA OU CAMINHO ADJACENTE"
        : (definition.requires_road_access ? "RUA OBRIGATORIA" : "SEM RUA");
    if (definition.grass_only) label += " | SOMENTE GRAMA";
    if (definition.power_consumption != 0) {
        label += " | ENERGIA " + std::to_string(definition.power_consumption);
    } else if (definition.power_production != 0) {
        label += " | GERA +" + std::to_string(definition.power_production);
    }
    return label;
}

[[nodiscard]] const char* direction_label(const GridDirection direction) {
    switch (direction) {
        case GridDirection::north: return "N";
        case GridDirection::east: return "E";
        case GridDirection::south: return "S";
        case GridDirection::west: return "W";
    }
    return "?";
}

[[nodiscard]] std::string access_points_label(const BuildingDefinition& definition, const BuildingRotation rotation) {
    const RoadAccessMode mode = resolved_road_access_mode(definition);
    if (mode == RoadAccessMode::any_perimeter) return "ROAD ACCESS: ANY PERIMETER";
    const std::vector<BuildingAccessPoint> access_points = road_access_candidates(definition, rotation);
    if (access_points.empty()) {
        return "ROAD ACCESS: " + std::string(road_access_mode_label(mode)) + " (NONE)";
    }
    std::string text = "ROAD ACCESS " + std::string(road_access_mode_label(mode)) + ":";
    for (const BuildingAccessPoint& access_point : access_points) {
        text += " (" + std::to_string(access_point.local_x) + "," + std::to_string(access_point.local_y) + ") " +
                direction_label(access_point.facing);
    }
    return text;
}

void draw_panel(SDL_Renderer* renderer, float x, float y, float width, float height) {
    SDL_SetRenderDrawColor(renderer, 16, 25, 30, 220);
    const SDL_FRect panel = {x, y, width, height};
    SDL_RenderFillRect(renderer, &panel);
    SDL_SetRenderDrawColor(renderer, 178, 217, 186, SDL_ALPHA_OPAQUE);
    SDL_RenderRect(renderer, &panel);
}

void draw_text(SDL_Renderer* renderer, float x, float y, const std::string& text, Uint8 red = 238, Uint8 green = 244, Uint8 blue = 238) {
    SDL_SetRenderDrawColor(renderer, red, green, blue, SDL_ALPHA_OPAQUE);
    SDL_RenderDebugText(renderer, x, y, text.c_str());
}

// Lightweight runtime loading UI. Progress advances only after real startup
// milestones complete; no full-screen raster artwork or artificial delay is used.
void render_loading_screen(SDL_Renderer* renderer, const int viewport_width, const int viewport_height,
                           const float progress, const std::string& stage) {
    const float width = static_cast<float>(viewport_width);
    const float height = static_cast<float>(viewport_height);
    const float clamped_progress = std::clamp(progress, 0.0F, 1.0F);

    SDL_SetRenderDrawColor(renderer, 4, 14, 20, SDL_ALPHA_OPAQUE);
    SDL_RenderClear(renderer);

    const float panel_width = std::min(720.0F, std::max(340.0F, width - 80.0F));
    const float panel_height = std::min(320.0F, std::max(250.0F, height - 120.0F));
    const float panel_x = (width - panel_width) * 0.5F;
    const float panel_y = (height - panel_height) * 0.5F;

    const SDL_FRect shadow = {panel_x + 8.0F, panel_y + 10.0F, panel_width, panel_height};
    SDL_SetRenderDrawColor(renderer, 0, 0, 0, 90);
    SDL_RenderFillRect(renderer, &shadow);

    const SDL_FRect panel = {panel_x, panel_y, panel_width, panel_height};
    SDL_SetRenderDrawColor(renderer, 15, 33, 45, 250);
    SDL_RenderFillRect(renderer, &panel);
    SDL_SetRenderDrawColor(renderer, 70, 119, 145, SDL_ALPHA_OPAQUE);
    SDL_RenderRect(renderer, &panel);

    const SDL_FRect accent = {panel_x, panel_y, panel_width, 4.0F};
    SDL_SetRenderDrawColor(renderer, 91, 188, 211, SDL_ALPHA_OPAQUE);
    SDL_RenderFillRect(renderer, &accent);

    draw_text(renderer, panel_x + 32.0F, panel_y + 38.0F, "CITY HORIZON", 238, 246, 249);
    draw_text(renderer, panel_x + 32.0F, panel_y + 64.0F, "PREPARANDO A CIDADE", 158, 186, 199);

    const float track_x = panel_x + 32.0F;
    const float track_y = panel_y + 132.0F;
    const float track_width = panel_width - 64.0F;
    const SDL_FRect track = {track_x, track_y, track_width, 22.0F};
    SDL_SetRenderDrawColor(renderer, 25, 48, 61, SDL_ALPHA_OPAQUE);
    SDL_RenderFillRect(renderer, &track);
    SDL_SetRenderDrawColor(renderer, 64, 103, 123, SDL_ALPHA_OPAQUE);
    SDL_RenderRect(renderer, &track);

    if (clamped_progress > 0.0F) {
        const SDL_FRect fill = {track_x + 2.0F, track_y + 2.0F,
                                (track_width - 4.0F) * clamped_progress, 18.0F};
        SDL_SetRenderDrawColor(renderer, 91, 188, 211, SDL_ALPHA_OPAQUE);
        SDL_RenderFillRect(renderer, &fill);
    }

    const int percent = static_cast<int>(std::lround(clamped_progress * 100.0F));
    draw_text(renderer, panel_x + 32.0F, panel_y + 170.0F, stage, 219, 232, 238);
    draw_text(renderer, panel_x + panel_width - 86.0F, panel_y + 170.0F,
              std::to_string(percent) + "%", 158, 186, 199);
    draw_text(renderer, panel_x + 32.0F, panel_y + panel_height - 48.0F,
              "DICA: CONECTE BAIRROS COM RUAS E CAMINHOS.", 118, 151, 166);
}

void render_ui(SDL_Renderer* renderer, int viewport_width, const CityEconomy& economy, const SimulationClock& clock,
               const BuildingManager& manager,
               const RoadManager& roads, const LandManager& lands, const BuildingCatalog& catalog, const RoadVisual* hovered_road_visual,
               bool hovered_road_uses_asset, std::optional<std::uint64_t> selected_instance_id,
               const std::pair<int, int>& mouse_tile, const BuildingDefinition* placement_definition,
               BuildingRotation placement_rotation, PlacementFailure placement_failure,
               bool placement_affordable, bool placement_on_road, bool placement_on_owned_land,
               bool road_mode, bool road_removal_mode, bool road_preview_valid, bool road_preview_on_owned_land,
               bool land_mode, bool debug_visible, const std::string& status) {
    const float mode_panel_y = debug_visible ? 442.0F : 134.0F;
    const float status_panel_y = debug_visible ? 516.0F : 208.0F;
    draw_panel(renderer, 12.0F, 12.0F, debug_visible ? 590.0F : 350.0F, debug_visible ? 420.0F : 42.0F);
    draw_text(renderer, 22.0F, 22.0F, "FUNDS: " + format_money(economy.funds()));
    if (debug_visible) {
        const MonthlyEconomySummary& monthly = economy.monthly_summary();
        draw_text(renderer, 22.0F, 40.0F, format_date(clock.date()) + " | " + simulation_speed_label(clock.speed()));
        draw_text(renderer, 22.0F, 58.0F, "MONTHLY REVENUE: " + format_money(monthly.revenue));
        draw_text(renderer, 22.0F, 76.0F, "MONTHLY EXPENSES: " + format_money(monthly.expenses));
        draw_text(renderer, 22.0F, 94.0F, "MONTHLY BALANCE: " + format_balance(monthly.balance));
        draw_text(renderer, 22.0F, 112.0F, "TILE: " + std::to_string(mouse_tile.first) + "," + std::to_string(mouse_tile.second));
        draw_text(renderer, 22.0F, 130.0F, "BUILDINGS: " + std::to_string(manager.instances().size()));
        draw_text(renderer, 22.0F, 148.0F, "ROADS: " + std::to_string(roads.tiles().size()));
        const TileOccupancy legacy_occupancy = roads.occupancy_at(mouse_tile.first, mouse_tile.second, manager);
        const char* legacy_label = legacy_occupancy == TileOccupancy::building ? "BUILDING" :
            (legacy_occupancy == TileOccupancy::road ? "ROAD" : "EMPTY");
        draw_text(renderer, 22.0F, 166.0F, "OCCUPANCY: " + std::string(legacy_label));
        if (const RoadTile* road = roads.tile_at(mouse_tile.first, mouse_tile.second)) {
            draw_text(renderer, 22.0F, 184.0F, "ROAD: MASK " + std::to_string(road->connections) + " " + connection_label(road->connections));
            const std::string resource = hovered_road_visual == nullptr ? "UNRESOLVED" : hovered_road_visual->texture_path;
            draw_text(renderer, 22.0F, 202.0F, "VISUAL: " + std::string(hovered_road_uses_asset ? "ASSET " : "FALLBACK ") + resource);
        }
        const LandParcel* parcel = lands.parcel_at(mouse_tile.first, mouse_tile.second);
        if (parcel != nullptr) {
            draw_text(renderer, 22.0F, 220.0F, "PARCEL: " + std::to_string(parcel->id) +
                      (parcel->owned ? " OWNED" : " AVAILABLE") + " | COST " + format_money(parcel->purchase_cost));
            draw_text(renderer, 22.0F, 238.0F, "ADJACENT TO OWNED: " + std::string(lands.is_adjacent_to_owned(*parcel) ? "YES" : "NO"));
        } else {
            draw_text(renderer, 22.0F, 220.0F, "PARCEL: OUTSIDE MAP");
        }
        draw_text(renderer, 22.0F, 256.0F, "TILE OWNED: " + std::string(lands.is_tile_owned(mouse_tile.first, mouse_tile.second) ? "YES" : "NO") +
                  " | OWNED PARCELS: " + std::to_string(lands.owned_parcel_count()));
        const BuildingDefinition* debug_definition = placement_definition;
        BuildingRotation debug_rotation = placement_rotation;
        if (debug_definition == nullptr && selected_instance_id) {
            if (const BuildingInstance* selected = manager.find_by_id(*selected_instance_id)) {
                debug_definition = catalog.find(selected->definition_id);
                debug_rotation = selected->rotation;
            }
        }
        if (debug_definition != nullptr) {
            const BuildingFootprint footprint = rotated_footprint(*debug_definition, debug_rotation);
            draw_text(renderer, 22.0F, 274.0F, "BUILDING: " + debug_definition->id + " " + rotation_label(debug_rotation));
            draw_text(renderer, 22.0F, 292.0F, "FOOTPRINT: " + std::to_string(debug_definition->footprint_width) + "x" +
                      std::to_string(debug_definition->footprint_height) + " -> " +
                      std::to_string(footprint.width) + "x" + std::to_string(footprint.height));
            draw_text(renderer, 22.0F, 310.0F, "SPRITE: " + debug_definition->texture_path_for(debug_rotation));
            draw_text(renderer, 22.0F, 328.0F, access_points_label(*debug_definition, debug_rotation));
        }
        draw_text(renderer, 22.0F, 364.0F, "COMMA/PERIOD CAMERA | HOME RESET | F5 SAVE | F9 LOAD | F1 DEBUG | Q QUIT");
    }

    if (placement_definition != nullptr) {
        draw_panel(renderer, 12.0F, mode_panel_y, 360.0F, 58.0F);
        draw_text(renderer, 22.0F, mode_panel_y + 10.0F, "BUILD MODE: " + placement_definition->name + " " +
                  rotation_label(placement_rotation) + (placement_definition->rotatable ? " | Z/X ROTATE" : " | FIXED"));
        const bool valid = placement_failure == PlacementFailure::none && placement_affordable && !placement_on_road && placement_on_owned_land;
        const std::string state = valid
            ? "VALID - LCLICK PLACE | RIGHT/ESC CANCEL"
            : "INVALID - " + std::string(!placement_on_owned_land ? "LAND NOT OWNED" : placement_on_road ? "AREA HAS ROAD" :
                (placement_failure == PlacementFailure::none ? "NOT ENOUGH FUNDS" : placement_failure_text(placement_failure)));
        draw_text(renderer, 22.0F, mode_panel_y + 28.0F, state, valid ? 135 : 255, valid ? 230 : 125, 125);
    }

    if (road_mode) {
        draw_panel(renderer, 12.0F, mode_panel_y, 420.0F, 58.0F);
        draw_text(renderer, 22.0F, mode_panel_y + 10.0F, road_removal_mode ? "ROAD REMOVE: LCLICK A ROAD TILE" :
                                                         "ROAD MODE: $100/TILE, DRAG LMB TO DRAW");
        draw_text(renderer, 22.0F, mode_panel_y + 28.0F, road_preview_valid ? "VALID - RIGHT/ESC CANCEL" :
                      (road_removal_mode ? "INVALID - NO ROAD ON TILE" : (!road_preview_on_owned_land ? "INVALID - LAND NOT OWNED" : "INVALID - ROAD, BUILDING OR MAP LIMIT")),
                  road_preview_valid ? 135 : 255, road_preview_valid ? 230 : 125, 125);
    }

    if (land_mode) {
        const LandParcel* parcel = lands.parcel_at(mouse_tile.first, mouse_tile.second);
        draw_panel(renderer, 12.0F, mode_panel_y, 440.0F, 58.0F);
        draw_text(renderer, 22.0F, mode_panel_y + 10.0F, "LAND MODE: SELECT A PARCEL | RIGHT/ESC CANCEL");
        if (parcel == nullptr) {
            draw_text(renderer, 22.0F, mode_panel_y + 28.0F, "INVALID - OUTSIDE MAP", 255, 125, 125);
        } else if (parcel->owned) {
            draw_text(renderer, 22.0F, mode_panel_y + 28.0F, "PARCEL " + std::to_string(parcel->id) + " OWNED", 135, 230, 125);
        } else if (!lands.can_purchase_parcel(parcel->id)) {
            draw_text(renderer, 22.0F, mode_panel_y + 28.0F, "LOCKED - MUST TOUCH OWNED LAND", 255, 125, 125);
        } else if (!economy.can_afford(parcel->purchase_cost)) {
            draw_text(renderer, 22.0F, mode_panel_y + 28.0F, "NOT ENOUGH FUNDS: " + format_money(parcel->purchase_cost), 255, 125, 125);
        } else {
            draw_text(renderer, 22.0F, mode_panel_y + 28.0F, "PARCEL " + std::to_string(parcel->id) + " - " +
                      format_money(parcel->purchase_cost) + " | LCLICK BUY", 135, 230, 125);
        }
    }

    if (selected_instance_id) {
        const BuildingInstance* instance = manager.find_by_id(*selected_instance_id);
        const BuildingDefinition* definition = instance == nullptr ? nullptr : catalog.find(instance->definition_id);
        if (instance != nullptr && definition != nullptr) {
            const float panel_x = static_cast<float>(viewport_width) - 270.0F;
            draw_panel(renderer, panel_x, 12.0F, 258.0F, 176.0F);
            draw_text(renderer, panel_x + 10.0F, 22.0F, definition->name);
            draw_text(renderer, panel_x + 10.0F, 40.0F, category_label(definition->category));
            draw_text(renderer, panel_x + 10.0F, 58.0F, "COST: " + format_money(definition->build_cost));
            draw_text(renderer, panel_x + 10.0F, 76.0F, "MONTHLY TAX: " + format_money(definition->tax_revenue_per_month));
            draw_text(renderer, panel_x + 10.0F, 94.0F, "MONTHLY MAINT: " + format_money(definition->maintenance_per_month));
            draw_text(renderer, panel_x + 10.0F, 112.0F, "MONTHLY NET: " +
                      format_balance(definition->tax_revenue_per_month - definition->maintenance_per_month));
            draw_text(renderer, panel_x + 10.0F, 130.0F, "POSITION: " + std::to_string(instance->tile_x) + "," + std::to_string(instance->tile_y));
            draw_text(renderer, panel_x + 10.0F, 148.0F,
                      roads.has_required_road_access(*definition, instance->tile_x, instance->tile_y, instance->rotation)
                          ? "ACCESS: ROAD CONNECTED"
                          : "ACCESS: NO ROAD");
            draw_text(renderer, panel_x + 10.0F, 166.0F, "ESC CLOSE | ID " + std::to_string(instance->instance_id));
        }
    }

    if (!status.empty()) {
        draw_panel(renderer, 12.0F, status_panel_y, 400.0F, 28.0F);
        draw_text(renderer, 22.0F, status_panel_y + 10.0F, status);
    }
}

}  // namespace

int main() {
    if (!SDL_Init(SDL_INIT_VIDEO)) {
        std::cerr << "SDL initialization failed: " << SDL_GetError() << '\n';
        return 1;
    }

    SDL_Window* window = SDL_CreateWindow(
        "City Builder - WASD/Drag: pan | Wheel: zoom | F5: save | F9: load | F10: calibration | B: build | ESC: cancel",
        1280,
        800,
        SDL_WINDOW_RESIZABLE
    );
    if (window == nullptr) {
        std::cerr << "Window creation failed: " << SDL_GetError() << '\n';
        SDL_Quit();
        return 1;
    }

    SDL_Renderer* renderer = SDL_CreateRenderer(window, nullptr);
    if (renderer == nullptr) {
        std::cerr << "Renderer creation failed: " << SDL_GetError() << '\n';
        SDL_DestroyWindow(window);
        SDL_Quit();
        return 1;
    }
    SDL_SetRenderVSync(renderer, 1);
    SDL_SetRenderDrawBlendMode(renderer, SDL_BLENDMODE_BLEND);

    const std::filesystem::path asset_root = runtime_root();
    AudioManager audio;
    (void)audio.initialize(asset_root / "assets/audio");
    (void)audio.play_loading_music();

    TextureCache textures;
    const auto show_loading = [&](const float progress, const char* stage) {
        int loading_width = 1280;
        int loading_height = 800;
        SDL_GetWindowSize(window, &loading_width, &loading_height);
        render_loading_screen(renderer, loading_width, loading_height, progress, stage);
        SDL_RenderPresent(renderer);
    };
    show_loading(0.08F, "INICIALIZANDO RENDER E AUDIO");
    // This authored RGBA grass tile is versioned and its opaque bounds match
    // kGrassOpaque*. The old *_clean path was never packaged in GitHub builds.
    const TextureAsset* grass = textures.load(renderer, asset_root / "assets/terrain/grass_isometric_01.png");
    const TextureAsset* paintable_sand = textures.load(renderer, asset_root / "assets/terrain/sand_isometric_01.png");

    RoadVisualCatalog road_visuals;
    (void)road_visuals.load_from_file(asset_root / "assets/definitions/road_visual_catalog.json");
    for (std::uint8_t mask = 0; mask < 16; ++mask) {
        const RoadVisual* visual = road_visuals.get_for_mask(mask);
        if (visual != nullptr) {
            const std::filesystem::path texture_path = asset_root / visual->texture_path;
            if (std::filesystem::is_regular_file(texture_path)) {
                (void)textures.load(renderer, texture_path);
            }
        }
    }
    for (int connections = 0; connections < 16; ++connections) {
        const std::string suffix = connections < 10 ? "0" + std::to_string(connections) : std::to_string(connections);
        (void)textures.load(renderer, asset_root / ("assets/sidewalks/concrete_01/sidewalk_concrete_" + suffix + ".png"));
    }
    (void)textures.load(renderer, asset_root / "assets/sidewalks/concrete_01/sidewalk_concrete_15_seamless.png");
    (void)textures.load(renderer, asset_root / "assets/terrain/paths/grass_to_concrete_path_01_concrete_path.png");
    static constexpr std::array<const char*, 16> kDirtPathSprites = {
        "dirt_path_00_isolated.png", "dirt_path_01_end_n.png", "dirt_path_02_end_e.png", "dirt_path_03_curve_ne.png",
        "dirt_path_04_end_s.png", "dirt_path_05_straight_ns.png", "dirt_path_06_curve_es.png", "dirt_path_07_tee_no_w.png",
        "dirt_path_08_end_w.png", "dirt_path_09_curve_nw.png", "dirt_path_10_straight_ew.png", "dirt_path_11_tee_no_s.png",
        "dirt_path_12_curve_sw.png", "dirt_path_13_tee_no_e.png", "dirt_path_14_tee_no_n.png", "dirt_path_15_cross.png",
    };
    for (const char* sprite : kDirtPathSprites) {
        (void)textures.load(renderer, asset_root / "assets/terrain/paths/dirt_01" / sprite);
    }
    (void)textures.load(renderer, asset_root / "assets/farming/prepared_soil/prepared_soil_01.png");
    show_loading(0.30F, "CARREGANDO TERRENO, RUAS E CAMINHOS");

    BuildingCatalog catalog;
    if (!catalog.load_from_directory(asset_root / "assets/definitions")) {
        std::cerr << "No valid building definitions were loaded.\n";
        audio.shutdown();
        textures.clear();
        SDL_DestroyRenderer(renderer);
        SDL_DestroyWindow(window);
        SDL_Quit();
        return 1;
    }
    CropCatalog crop_catalog;
    if (!crop_catalog.load_from_directory(asset_root / "assets/farming/crops")) {
        std::cerr << "No valid crop definitions were loaded; planting remains unavailable until crop data/art is restored.\n";
    }
    AgriculturalResourceCatalog resource_catalog;
    if (!resource_catalog.load_from_directory(asset_root / "assets/farming/resources")) {
        std::cerr << "No valid agricultural resource definitions were loaded.\n";
        audio.shutdown(); textures.clear(); SDL_DestroyRenderer(renderer); SDL_DestroyWindow(window); SDL_Quit(); return 1;
    }
    for (const CropDefinition& crop : crop_catalog.definitions()) {
        for (const std::string& sprite : crop.stage_overlay_sprites) {
            (void)textures.load(renderer, asset_root / sprite);
        }
        for (const std::string& sprite : crop.legacy_composite_stage_sprites) {
            (void)textures.load(renderer, asset_root / sprite);
        }
    }
    for (const BuildingDefinition& definition : catalog.definitions()) {
        for (const auto& lvl : definition.levels) {
            for (std::uint8_t rotation = 0; rotation < 4; ++rotation) {
                const BuildingRotation logical_rotation = static_cast<BuildingRotation>(rotation);
                if (definition.supports_rotation(logical_rotation)) {
                    (void)textures.load(renderer, asset_root / definition.texture_path_for(logical_rotation, lvl.level));
                    if (lvl.level == 1 && definition.supports_color_mask(logical_rotation)) {
                        const auto mask_path = asset_root / definition.color_mask_path_for(logical_rotation);
                        (void)textures.load_mask_channel(renderer, mask_path, 'R');
                        (void)textures.load_mask_channel(renderer, mask_path, 'G');
                    }
                    if (lvl.level == 1 && definition.activity_overlay && definition.activity_overlay->enabled) {
                        const std::string& overlay_path = definition.activity_overlay->sprite_paths[rotation];
                        if (!overlay_path.empty()) {
                            (void)textures.load(renderer, asset_root / overlay_path);
                        }
                    }
                }
            }
        }
    }
    show_loading(0.58F, "CARREGANDO CATALOGO E CONSTRUCOES");
    ServiceVehicleCatalog service_vehicle_catalog;
    if (!service_vehicle_catalog.load_from_directory(asset_root / "assets/definitions/vehicles")) {
        std::cerr << "No valid service vehicle definitions were loaded.\n";
    }
    MobileAnimationCatalog mobile_animations;
    const bool approved_animations_loaded = mobile_animations.load_from_directory(asset_root / "assets/definitions/animations");
    bool preview_animations_loaded = false;
#if defined(CH_VISITOR_FORGE_PREVIEW)
    // Visitor Forge remains a review candidate: only the F8 test selects this set.
    preview_animations_loaded = mobile_animations.append_from_directory(asset_root / "tools/visitor_forge_2d/runtime_preview");
#endif
    if (!approved_animations_loaded && !preview_animations_loaded) {
        std::cerr << "No valid mobile animation sets were loaded; directional static sprites remain available.\n";
    }
    for (const ServiceVehicleDefinition& definition : service_vehicle_catalog.definitions()) {
        for (const VehicleDirection direction : {VehicleDirection::south, VehicleDirection::east, VehicleDirection::north, VehicleDirection::west}) {
            (void)textures.load(renderer, asset_root / definition.sprite_for(direction));
        }
    }
    for (const std::string& frame_asset : mobile_animations.frame_assets()) {
        (void)textures.load(renderer, asset_root / frame_asset);
    }
    show_loading(0.72F, "CARREGANDO VEICULOS E ENTIDADES");

    BuildingManager buildings(kMapMin, kMapMax);
    RoadManager roads(kMapMin, kMapMax);
    SidewalkManager sidewalks(kMapMin, kMapMax);
    FarmingSystem farming(kMapMin, kMapMax);
    std::unordered_map<std::string, std::string> resource_storage_classes;
    for (const AgriculturalResourceDefinition& resource : resource_catalog.definitions()) resource_storage_classes[resource.id] = resource.storage_class;
    farming.register_resource_storage_classes(resource_storage_classes);
    ServiceVehicleManager service_vehicles;
    PedestrianSystem pedestrians{{"worker_cleaner_female", 1.0F, 0.5F, 0.862F, kMixamoWalkSeTestSpeed, kMixamoWalkSeTestRate, 0.5F, 0.72F}};
    LandManager lands(kMapMin, kMapMax);
    CityEconomy economy;
    PopulationSystem population;
    MissionManager mission_manager;
    (void)mission_manager.load_missions_from_directory(asset_root / "assets/missions");
    PowerSystem power;
    SimulationClock simulation_clock;
    SimulationScheduler simulation_scheduler(15.0F);
    SaveManager save_manager;
    const std::filesystem::path save_path = SaveManager::default_save_path();
    const std::filesystem::path calibration_scenario_path = asset_root / "assets/scenarios/isometric_calibration.json";
    const auto agricultural_infrastructure = [&]() {
        struct State { bool barn = false; bool silo = false; } state;
        for (const BuildingInstance& instance : buildings.instances()) {
            const BuildingDefinition* definition = catalog.find(instance.definition_id);
            if (definition == nullptr || !definition->provides_agricultural_storage) continue;
            state.barn = state.barn || (definition->agricultural_infrastructure_role == "barn" &&
                                        definition->agricultural_storage_capacity > 0);
            state.silo = state.silo || (definition->agricultural_infrastructure_role == "silo" &&
                                        definition->grain_storage_capacity > 0);
        }
        return state;
    };
    const auto rebuild_agricultural_storage = [&]() {
        int general_capacity = 20;
        int grain_capacity = 0;
        for (const BuildingInstance& instance : buildings.instances()) {
            if (const BuildingDefinition* definition = catalog.find(instance.definition_id)) {
                if (!definition->provides_agricultural_storage) continue;
                general_capacity += static_cast<int>(definition->agricultural_storage_capacity);
                grain_capacity += static_cast<int>(definition->grain_storage_capacity);
            }
        }
        farming.set_storage_capacities(general_capacity, grain_capacity);
    };
    for (const BuildingDefinition& definition : catalog.definitions()) {
        if (!definition.initial_placement) {
            continue;
        }
        const InitialBuildingPlacement& placement = *definition.initial_placement;
        if (!buildings.place(definition, placement.tile_x, placement.tile_y, placement.rotation)) {
            std::cerr << "Initial building could not be created from data: " << definition.id << '\n';
            audio.shutdown();
            textures.clear();
            SDL_DestroyRenderer(renderer);
            SDL_DestroyWindow(window);
            SDL_Quit();
            return 1;
        }
    }
    population.rebuild_capacity(buildings, catalog);
    power.rebuild(buildings, catalog);
    show_loading(0.84F, "PREPARANDO ECONOMIA, POPULACAO E ENERGIA");

    std::unordered_map<std::uint64_t, const TextureAsset*> scenario_terrain_textures;
    std::vector<WaterSurfaceTile> scenario_water_tiles;
    std::unordered_map<std::uint64_t, std::string> scenario_terrain_paths;
    std::vector<ShorelineOverlayTile> shoreline_overlays;
    // The two opaque PNGs are material records generated from the approved
    // Water V2 master. World coverage deliberately remains render_tile_fill,
    // the seam-proven CH_GRID_V1 geometry, rather than their PNG rectangle.
    const TextureAsset* water_base_deep = textures.load(renderer, asset_root / "assets/terrain/coast_adjusted/water_base_deep.png");
    const TextureAsset* water_base_shallow = textures.load(renderer, asset_root / "assets/terrain/coast_adjusted/water_base_shallow.png");
    const TextureAsset* water_caustics = textures.load(renderer, asset_root / "assets/terrain/coast_adjusted/water_caustics_01.png");
    if (water_base_deep == nullptr || water_base_shallow == nullptr || water_caustics == nullptr) {
        std::cerr << "CH_WATER_V2 assets unavailable; continuing with legacy terrain visuals\n";
    }
    const std::filesystem::path scenarios_root = asset_root / "assets/scenarios";
    std::filesystem::path initial_city_path = scenarios_root / "initial_city.json";
    // Map Forge exports this one-line runtime selection marker.  Only a plain
    // filename under the canonical scenario directory is accepted, so an
    // external path can never be injected into the game's asset lookup.
    const std::filesystem::path active_scenario_marker = scenarios_root / "active_scenario.txt";
    if (std::ifstream marker{active_scenario_marker}; marker.good()) {
        std::string selected_name;
        std::getline(marker, selected_name);
        const std::filesystem::path selected_path{selected_name};
        if (selected_path.filename() == selected_path && selected_path.extension() == ".json" &&
            std::filesystem::exists(scenarios_root / selected_path)) {
            initial_city_path = scenarios_root / selected_path;
        }
    }
    std::optional<ch::MapDocument> active_map_doc = ch::MapDocument::load_from_file(initial_city_path.string());
    if (!active_map_doc) active_map_doc = ch::MapDocument::create_empty("City", kMapMax - kMapMin + 1, kMapMax - kMapMin + 1);
    if (active_map_doc.has_value()) {
        for (const auto& tile : active_map_doc->terrain_tiles()) {
            const TextureAsset* loaded_tex = !tile.texture.empty() && std::filesystem::is_regular_file(asset_root / tile.texture)
                ? textures.load(renderer, asset_root / tile.texture) : nullptr;
            const std::uint64_t key = ch::tile_key(tile.tile_x, tile.tile_y);
            scenario_terrain_textures[key] = loaded_tex;
            scenario_terrain_paths[key] = tile.terrain_definition;
            const bool shallow = tile.terrain_definition == "water_shallow";
            const bool deep = tile.terrain_definition == "water_deep";
            if (shallow || deep) scenario_water_tiles.push_back({tile.tile_x, tile.tile_y, shallow});
        }
    }
    std::sort(scenario_water_tiles.begin(), scenario_water_tiles.end(), [](const WaterSurfaceTile& left, const WaterSurfaceTile& right) {
        const int left_depth = left.tile_x + left.tile_y;
        const int right_depth = right.tile_x + right.tile_y;
        return left_depth == right_depth ? left.tile_x < right.tile_x : left_depth < right_depth;
    });
    // CH_SHORELINE_V1: choose existing directional art from topology.  This is
    // intentionally separate from Water V2 and does not alter water tiles.
    const auto has_water_at = [&scenario_terrain_paths](const int x, const int y) {
        const auto it = scenario_terrain_paths.find(ch::tile_key(x, y));
        return it != scenario_terrain_paths.end() &&
               (it->second == "water_shallow" || it->second == "water_deep");
    };
    for (const auto& [key, texture_path] : scenario_terrain_paths) {
        if (texture_path != "sand") continue;
        const int x = static_cast<int>(static_cast<std::uint32_t>(key >> 32));
        const int y = static_cast<int>(static_cast<std::uint32_t>(key));
        const bool north = has_water_at(x, y - 1), east = has_water_at(x + 1, y);
        const bool south = has_water_at(x, y + 1), west = has_water_at(x - 1, y);
        const int adjacent = static_cast<int>(north) + static_cast<int>(east) + static_cast<int>(south) + static_cast<int>(west);
        std::string suffix;
        if (adjacent == 1) suffix = north ? "north" : east ? "east" : south ? "south" : "west";
        else if (adjacent == 2 && ((north && east) || (east && south) || (south && west) || (west && north))) {
            suffix = north && east ? "inner_ne" : east && south ? "inner_se" : south && west ? "inner_sw" : "inner_nw";
        } else if (adjacent == 0) {
            if (has_water_at(x + 1, y - 1)) suffix = "outer_ne";
            else if (has_water_at(x + 1, y + 1)) suffix = "outer_se";
            else if (has_water_at(x - 1, y + 1)) suffix = "outer_sw";
            else if (has_water_at(x - 1, y - 1)) suffix = "outer_nw";
        }
        if (suffix.empty()) continue;
        const std::string name = suffix.rfind("inner_", 0) == 0 || suffix.rfind("outer_", 0) == 0
            ? "coast_corner_" + suffix + ".png" : "coast_border_" + suffix + ".png";
        if (const TextureAsset* overlay = textures.load(renderer, asset_root / "assets/terrain/coast_adjusted" / name)) {
            shoreline_overlays.push_back({x, y, overlay});
        }
    }
    show_loading(0.97F, "FINALIZANDO CENARIO E MAPA");

    Camera camera;
    float seagull_seconds = 0.0F;
    float seagull_pass_elapsed = 0.0F;
    float seagull_next_pass_in = 8.0F;
    std::uint32_t seagull_pass_index = 0;
    bool seagull_pass_active = false;
    std::optional<std::uint64_t> selected_instance_id;
    std::string placement_definition_id;
    BuildingRotation placement_rotation = BuildingRotation::r0;
    bool road_mode = false;
    bool road_removal_mode = false;
    bool road_dragging = false;
    bool sidewalk_dragging = false;
    bool harvest_dragging = false;
    bool preparation_dragging = false;
    bool planting_dragging = false;
    bool camera_dragging = false;
    bool land_mode = false;
    std::string terrain_paint_style;
    std::vector<TerrainPaintTile> terrain_paint;
    bool sidewalk_mode = false;
    bool decoration_mode = false;
    bool agriculture_mode = false;
    bool agriculture_panel_open = false;
    std::string farming_selection_id;
    bool build_panel_open = false;
    TileCoordinate road_drag_start;
    TileCoordinate sidewalk_drag_start;
    TileCoordinate harvest_drag_start;
    TileCoordinate preparation_drag_start;
    TileCoordinate planting_drag_start;
    std::string status = "MAIN MENU";
    UiOverlay active_overlay = UiOverlay::main_menu;
    bool startup_main_menu = true;
    simulation_clock.set_speed(SimulationSpeed::paused);
    UiOverlay settings_return_overlay = UiOverlay::none;
    UiOverlay save_load_return_overlay = UiOverlay::pause;
    UiOverlay quit_return_overlay = UiOverlay::pause;
    bool debug_visible = false;
    bool navigation_debug_uses_roads = true;
    std::optional<NavigationTile> navigation_debug_start;
    std::optional<NavigationTile> navigation_debug_goal;
    bool running = true;
    Uint64 last_simulation_ticks = SDL_GetTicks();
    GameplayUi gameplay_ui;
    show_loading(1.0F, "PRONTO");
    const auto vehicle_traversable = [&](const int x, const int y) {
        const MapTileOccupancy occupancy = inspect_map_tile(buildings, roads, sidewalks, farming, x, y);
        if (!lands.is_tile_owned(x, y) || occupancy.building || occupancy.road || occupancy.sidewalk) {
            return false;
        }
        const FarmTile* tile = farming.tile_at(x, y);
        return tile == nullptr || tile->state == FarmTileState::prepared_soil;
    };
    const auto mobile_render_entities = [&]() {
        std::vector<MobileEntityRenderData> entities = service_vehicles.render_entities(service_vehicle_catalog, mobile_animations);
        std::vector<MobileEntityRenderData> pedestrian_entities = pedestrians.render_entities(mobile_animations);
        entities.insert(entities.end(), std::make_move_iterator(pedestrian_entities.begin()), std::make_move_iterator(pedestrian_entities.end()));
        return entities;
    };
    // A non-mutating runtime proof: F7 searches the current map for six road
    // tiles along +X. PedestrianLaneNavigationNetwork derives its route from
    // that road topology while the per-entity ground offset puts the sprite on
    // the integrated sidewalk edge rather than in the vehicle lane.
    // Every preset keeps the approved 175 ms canonical cycle. Only world
    // velocity varies for runtime foot-skating calibration of the new skin.
    int mixamo_gait_preset_index = 2;
    // Start the explicit F7 test with the character the player is reviewing.
    // Other looks remain available through F8; no NPC is spawned automatically.
    int pedestrian_visual_index = mobile_animations.find_set("visitor_male_01_south_front_candidate") == nullptr ? 0 : 4;
    const auto pedestrian_visual_id = [&]() -> std::string_view {
        switch (pedestrian_visual_index) {
            case 1: return "citizen_female_light_blue";
            case 2: return "citizen_female_dark_coral";
            case 3: return "visitor_male_01_forge_preview";
            case 4: return "visitor_male_01_south_front_candidate";
            default: return "worker_cleaner_female";
        }
    };
    const auto pedestrian_visual_label = [&]() -> std::string_view {
        switch (pedestrian_visual_index) {
            case 1: return "CITIZEN LIGHT BLUE";
            case 2: return "CITIZEN DARK CORAL";
            case 3: return "VISITOR FORGE PREVIEW";
            case 4: return "VISITOR FOUR DIRECTION GAIT";
            default: return "CLEANER";
        }
    };
    const auto pedestrian_visual_preset = [&](const float speed) {
        if (pedestrian_visual_index >= 3) {
            // 128 px canvas, 97 px body: 97 * (56 / 97) = 56 px at zoom 1.
            // The shared foot pivot is [64, 116] in every direction and pose.
            return PedestrianVisualDefinition{std::string(pedestrian_visual_id()), 56.0F / 97.0F,
                                              0.5F, 116.0F / 128.0F, speed, 1.0F, 0.5F, 0.72F};
        }
        return PedestrianVisualDefinition{std::string(pedestrian_visual_id()), 1.0F,
                                          0.5F, 0.862F, speed, 125.0F / 175.0F, 0.5F, 0.72F};
    };
    const auto send_mixamo_se_test = [&]() {
        const float speed = [&]() {
            switch (mixamo_gait_preset_index) {
                case 0: return 0.50F;
                case 1: return 0.65F;
                default: return 0.80F;
            }
        }();
        const PedestrianVisualDefinition preset = pedestrian_visual_preset(speed);
        const char* preset_name = mixamo_gait_preset_index == 0 ? "A 0.50" : mixamo_gait_preset_index == 1 ? "B 0.65" : "C 0.80";
        const bool visitor_preview = pedestrian_visual_index >= 3;
        const int duration_ms = visitor_preview ? 220 : 175;
        pedestrians.configure_visual_test(preset);
        constexpr int kRequiredSidewalkTiles = 6;
        const PedestrianLaneNavigationNetwork network{roads};
        for (int y = kMapMin; y <= kMapMax; ++y) {
            for (int x = kMapMin; x <= kMapMax - (kRequiredSidewalkTiles - 1); ++x) {
                bool straight_road = true;
                for (int offset = 0; offset < kRequiredSidewalkTiles; ++offset) {
                    if (!roads.is_road(x + offset, y)) {
                        straight_road = false;
                        break;
                    }
                }
                if (straight_road && pedestrians.send_test_pedestrian({x, y}, {x + kRequiredSidewalkTiles - 1, y}, network)) {
                    status = std::string(pedestrian_visual_label()) + " " + preset_name + ": " + std::to_string(duration_ms) + " MS | " +
                             std::to_string(preset.movement_speed_tiles_per_second) +
                             (visitor_preview ? " T/S | 56 PX PREVIEW" : " T/S | 32 PX");
                    mixamo_gait_preset_index = (mixamo_gait_preset_index + 1) % 3;
                    return;
                }
            }
        }
        status = "MIXAMO SE TEST: DRAW 6 STRAIGHT ROAD TILES ALONG +X";
    };

    const auto clear_map_modes = [&]() {
        placement_definition_id.clear();
        road_mode = false;
        road_removal_mode = false;
        road_dragging = false;
        sidewalk_dragging = false;
        harvest_dragging = false;
        preparation_dragging = false;
        planting_dragging = false;
        land_mode = false;
        terrain_paint_style.clear();
        sidewalk_mode = false;
        agriculture_mode = false;
        agriculture_panel_open = false;
        farming_selection_id.clear();
        decoration_mode = false;
    };
    const auto open_build_panel = [&]() {
        clear_map_modes();
        build_panel_open = true;
        selected_instance_id.reset();
        status = "BUILDINGS PANEL OPEN";
        (void)audio.play(SoundEvent::ui_open_panel);
    };
    const auto begin_build_placement = [&](const std::string& definition_id) {
        const BuildingDefinition* definition = catalog.find(definition_id);
        if (definition == nullptr) {
            status = "UNKNOWN BUILDING DEFINITION";
            (void)audio.play(SoundEvent::ui_error);
            return;
        }
        clear_map_modes();
        build_panel_open = true;
        placement_definition_id = definition->id;
        placement_rotation = BuildingRotation::r0;
        selected_instance_id.reset();
        status = "BUILD MODE: " + definition->name;
        (void)audio.play(SoundEvent::ui_confirm);
    };
    const auto begin_road_mode = [&]() {
        clear_map_modes();
        build_panel_open = false;
        road_mode = true;
        selected_instance_id.reset();
        status = "ROAD MODE: DRAG TO DRAW";
        (void)audio.play(SoundEvent::ui_select);
    };
    const auto begin_remove_mode = [&]() {
        clear_map_modes();
        build_panel_open = false;
        road_mode = true;
        road_removal_mode = true;
        selected_instance_id.reset();
        status = "DEMOLISH MODE: CLICK A BUILDING, SIDEWALK OR ROAD";
        (void)audio.play(SoundEvent::ui_select);
    };
    const auto begin_land_mode = [&]() {
        clear_map_modes();
        build_panel_open = false;
        land_mode = true;
        selected_instance_id.reset();
        status = "LAND MODE: SELECT A NEIGHBORING PARCEL";
        (void)audio.play(SoundEvent::ui_open_panel);
    };
    const auto begin_terrain_paint = [&](const std::string& style) {
        clear_map_modes();
        build_panel_open = false;
        terrain_paint_style = style;
        selected_instance_id.reset();
        status = style == "sand" ? "SAND: CLICK OWNED EMPTY GROUND" : "GRASS: CLICK OWNED EMPTY GROUND";
        (void)audio.play(SoundEvent::ui_select);
    };
    const auto begin_sidewalk_mode = [&]() {
        clear_map_modes(); build_panel_open = false; sidewalk_mode = true; selected_instance_id.reset();
        status = "DIRT PATH MODE: DRAG ON OWNED GRASS"; (void)audio.play(SoundEvent::ui_select);
    };
    const auto begin_decoration_mode = [&]() {
        clear_map_modes();
        build_panel_open = false;
        decoration_mode = true;
        selected_instance_id.reset();
        status = "DECORATION: SELECT AN ITEM";
        (void)audio.play(SoundEvent::ui_select);
    };
    const auto open_agriculture_panel = [&]() {
        clear_map_modes();
        build_panel_open = false;
        agriculture_mode = true;
        agriculture_panel_open = true;
        selected_instance_id.reset();
        status = "AGRICULTURE: SELECT SOIL OR TOMATO";
        (void)audio.play(SoundEvent::ui_open_panel);
    };
    const auto select_farming_item = [&](const std::string& id) {
        const bool sell_resource = id.starts_with("sell_resource:") &&
            resource_catalog.find(id.substr(std::string("sell_resource:").size())) != nullptr;
        const bool vehicle_purchase = id.starts_with("purchase_vehicle:") &&
            service_vehicle_catalog.find(id.substr(std::string("purchase_vehicle:").size())) != nullptr;
        if (id != "prepared_soil_01" && id != "harvest_tool" && id != "prepare_soil_tool" && !sell_resource && !vehicle_purchase && crop_catalog.find(id) == nullptr) {
            status = "UNKNOWN FARMING ITEM"; (void)audio.play(SoundEvent::ui_error); return;
        }
        if (sell_resource) {
            const AgriculturalResourceDefinition* resource = resource_catalog.find(id.substr(std::string("sell_resource:").size()));
            const int quantity = farming.inventory_count(resource->id);
            if (quantity <= 0) { status = resource->display_name + ": NO STOCK TO SELL"; (void)audio.play(SoundEvent::ui_error); return; }
            const std::int64_t revenue = static_cast<std::int64_t>(quantity) * resource->base_sell_price;
            if (farming.try_remove_resource(resource->id, quantity)) economy.earn_agricultural_sale(revenue, simulation_clock.date());
            status = resource->display_name + " SOLD: " + std::to_string(quantity) + " | " + format_money(revenue);
            (void)audio.play(SoundEvent::ui_confirm); return;
        }
        clear_map_modes();
        build_panel_open = false;
        agriculture_mode = true;
        agriculture_panel_open = true;
        farming_selection_id = id;
        selected_instance_id.reset();
        status = id == "prepared_soil_01" ? "AGRICULTURE: PLACE PREPARED SOIL" :
            (id == "harvest_tool" ? "AGRICULTURE: DRAG TO HARVEST READY CROPS" :
            (id == "prepare_soil_tool" ? "AGRICULTURE: DRAG AREA TO PREPARE" :
            (vehicle_purchase ? "AGRICULTURE: CLICK EMPTY OWNED TILE FOR TRACTOR HOME" : "AGRICULTURE: PLANT " + crop_catalog.find(id)->display_name)));
        (void)audio.play(SoundEvent::ui_confirm);
    };
    const auto rotate_placement = [&](const bool clockwise) {
        if (const BuildingDefinition* placement = catalog.find(placement_definition_id);
            placement != nullptr && placement->rotatable) {
            placement_rotation = placement->next_supported_rotation(placement_rotation, clockwise);
            status = "BUILD ROTATION: " + std::string(rotation_label(placement_rotation));
            (void)audio.play(SoundEvent::ui_click);
        }
    };
    const auto save_current_city = [&]() {
        const SaveOperationResult result = save_manager.save(save_path, economy, simulation_clock, buildings, roads,
                                                             sidewalks, farming, lands, population, &service_vehicles, &mission_manager,
                                                             &terrain_paint);
        status = result.success ? "SAVE COMPLETE" : "SAVE FAILED: " + result.message;
        (void)audio.play(result.success ? SoundEvent::ui_confirm : SoundEvent::ui_error);
        return result.success;
    };
    const auto load_current_city = [&](const bool keep_paused) {
        const SaveOperationResult result = save_manager.load(save_path, catalog, economy, simulation_clock, buildings, roads,
                                                             sidewalks, farming, lands, population, &service_vehicle_catalog,
                                                             &service_vehicles, &mission_manager, &terrain_paint);
        if (result.success) {
            active_map_doc = ch::MapDocument::load_from_file(initial_city_path.string());
            if (!active_map_doc) active_map_doc = ch::MapDocument::create_empty("City", kMapMax - kMapMin + 1, kMapMax - kMapMin + 1);
            for (const TerrainPaintTile& tile : terrain_paint) {
                if (!active_map_doc || !lands.is_tile_owned(tile.tile_x, tile.tile_y)) continue;
                const std::string path = tile.style == "sand" ? "assets/terrain/sand_isometric_01.png" : "";
                active_map_doc->paint_terrain_at(tile.tile_x, tile.tile_y,
                                                 tile.style == "sand" ? "sand_center" : "grass", path);
            }
            power.rebuild(buildings, catalog);
            status = "LOAD COMPLETE: " + result.message;
            if (mission_manager.check_and_auto_complete_clean_energy(economy, buildings, catalog, population, power)) {
                status = "MISSAO ENERGIA LIMPA CONCLUIDA! Hidreletrica Reativada!";
            }
            selected_instance_id.reset();
            clear_map_modes();
            build_panel_open = false;
            if (keep_paused) {
                simulation_clock.set_speed(SimulationSpeed::paused);
            } else if (simulation_clock.speed() != SimulationSpeed::paused) {
                simulation_clock.set_speed(SimulationSpeed::speed1);
            }
            last_simulation_ticks = SDL_GetTicks();
            simulation_scheduler.reset();
            (void)audio.play(SoundEvent::ui_confirm);
        } else {
            status = "LOAD FAILED: " + result.message;
            (void)audio.play(SoundEvent::ui_error);
        }
        return result.success;
    };
    const auto apply_ui_action = [&](const UiActionEvent& action) {
        switch (action.action) {
            case UiAction::open_build_panel: open_build_panel(); break;
            case UiAction::select_building: begin_build_placement(action.payload); break;
            case UiAction::activate_roads: begin_road_mode(); break;
            case UiAction::activate_sidewalks: begin_sidewalk_mode(); break;
            case UiAction::activate_land: begin_land_mode(); break;
            case UiAction::paint_grass: begin_terrain_paint("grass"); break;
            case UiAction::paint_sand: begin_terrain_paint("sand"); break;
            case UiAction::activate_remove: begin_remove_mode(); break;
            case UiAction::open_agriculture_panel: open_agriculture_panel(); break;
            case UiAction::select_farming_item: select_farming_item(action.payload); break;
            case UiAction::activate_decoration: begin_decoration_mode(); break;
            case UiAction::rotate_left: rotate_placement(false); break;
            case UiAction::rotate_right: rotate_placement(true); break;
            case UiAction::toggle_pause:
                if (active_overlay == UiOverlay::pause) {
                    active_overlay = UiOverlay::none;
                    if (simulation_clock.speed() == SimulationSpeed::paused) simulation_clock.toggle_pause();
                    status = "SIMULATION RESUMED";
                    (void)audio.play(SoundEvent::ui_close_panel);
                } else {
                    if (simulation_clock.speed() != SimulationSpeed::paused) simulation_clock.toggle_pause();
                    active_overlay = UiOverlay::pause;
                    status = "GAME PAUSED";
                    (void)audio.play(SoundEvent::ui_open_panel);
                }
                break;
            case UiAction::resume_game:
                active_overlay = UiOverlay::none;
                if (simulation_clock.speed() == SimulationSpeed::paused) simulation_clock.toggle_pause();
                status = "SIMULATION RESUMED";
                (void)audio.play(SoundEvent::ui_close_panel);
                break;
            case UiAction::open_administration:
                active_overlay = UiOverlay::administration;
                status = "ADMINISTRATION OPEN";
                (void)audio.play(SoundEvent::ui_open_panel);
                break;
            case UiAction::open_reports:
                active_overlay = UiOverlay::reports;
                status = "REPORTS OPEN";
                (void)audio.play(SoundEvent::ui_open_panel);
                break;
            case UiAction::open_settings:
                settings_return_overlay = active_overlay == UiOverlay::pause || active_overlay == UiOverlay::main_menu
                    ? active_overlay : UiOverlay::none;
                active_overlay = UiOverlay::settings;
                status = "SETTINGS OPEN";
                (void)audio.play(SoundEvent::ui_open_panel);
                break;
            case UiAction::open_main_menu:
                if (simulation_clock.speed() != SimulationSpeed::paused) simulation_clock.set_speed(SimulationSpeed::paused);
                startup_main_menu = false;
                active_overlay = UiOverlay::main_menu;
                status = "MAIN MENU OPEN";
                (void)audio.play(SoundEvent::ui_open_panel);
                break;
            case UiAction::start_new_city:
                clear_map_modes();
                build_panel_open = false;
                selected_instance_id.reset();
                startup_main_menu = false;
                active_overlay = UiOverlay::none;
                simulation_clock.set_speed(SimulationSpeed::speed1);
                last_simulation_ticks = SDL_GetTicks();
                simulation_scheduler.reset();
                status = "NEW CITY STARTED";
                (void)audio.play(SoundEvent::ui_confirm);
                break;
            case UiAction::continue_saved_city:
                if (!std::filesystem::exists(save_path)) {
                    status = "NO SAVE AVAILABLE";
                    (void)audio.play(SoundEvent::ui_error);
                    break;
                }
                if (load_current_city(false)) {
                    startup_main_menu = false;
                    active_overlay = UiOverlay::none;
                    simulation_clock.set_speed(SimulationSpeed::speed1);
                    last_simulation_ticks = SDL_GetTicks();
                    simulation_scheduler.reset();
                    status = "CITY CONTINUED";
                }
                break;
            case UiAction::open_save_load:
                if (simulation_clock.speed() != SimulationSpeed::paused) simulation_clock.set_speed(SimulationSpeed::paused);
                save_load_return_overlay = active_overlay == UiOverlay::main_menu ? UiOverlay::main_menu : UiOverlay::pause;
                active_overlay = UiOverlay::save_load;
                status = std::filesystem::exists(save_path) ? "SAVE SLOT READY" : "SAVE SLOT EMPTY";
                (void)audio.play(SoundEvent::ui_open_panel);
                break;
            case UiAction::save_game:
                (void)save_current_city();
                break;
            case UiAction::load_game:
                (void)load_current_city(true);
                break;
            case UiAction::back_to_pause:
                if (simulation_clock.speed() != SimulationSpeed::paused) simulation_clock.set_speed(SimulationSpeed::paused);
                active_overlay = UiOverlay::pause;
                status = "GAME PAUSED";
                (void)audio.play(SoundEvent::ui_back);
                break;
            case UiAction::back_from_save_load:
                if (simulation_clock.speed() != SimulationSpeed::paused) simulation_clock.set_speed(SimulationSpeed::paused);
                active_overlay = save_load_return_overlay;
                status = active_overlay == UiOverlay::main_menu ? "MAIN MENU OPEN" : "GAME PAUSED";
                (void)audio.play(SoundEvent::ui_back);
                break;
            case UiAction::open_quit_confirm:
                if (simulation_clock.speed() != SimulationSpeed::paused) simulation_clock.set_speed(SimulationSpeed::paused);
                quit_return_overlay = active_overlay == UiOverlay::main_menu ? UiOverlay::main_menu : UiOverlay::pause;
                active_overlay = UiOverlay::quit_confirm;
                status = "CONFIRM EXIT";
                (void)audio.play(SoundEvent::ui_open_panel);
                break;
            case UiAction::cancel_quit:
                active_overlay = quit_return_overlay;
                status = active_overlay == UiOverlay::main_menu ? "MAIN MENU OPEN" : "GAME PAUSED";
                (void)audio.play(SoundEvent::ui_back);
                break;
            case UiAction::quit_game:
                status = "EXITING CITY HORIZON";
                (void)audio.play(SoundEvent::ui_confirm);
                running = false;
                break;
            case UiAction::close_modal:
                active_overlay = UiOverlay::none;
                status = "PANEL CLOSED";
                (void)audio.play(SoundEvent::ui_close_panel);
                break;
            case UiAction::settings_cancel:
                active_overlay = settings_return_overlay;
                status = active_overlay == UiOverlay::pause ? "GAME PAUSED" :
                    (active_overlay == UiOverlay::main_menu ? "MAIN MENU OPEN" : "PANEL CLOSED");
                (void)audio.play(SoundEvent::ui_close_panel);
                break;
            case UiAction::settings_reset:
                status = "SETTINGS DEFAULTS READY TO APPLY";
                (void)audio.play(SoundEvent::ui_click);
                break;
            case UiAction::settings_apply: {
                const std::size_t separator = action.payload.find(':');
                if (separator == std::string::npos) {
                    status = "INVALID SETTINGS PAYLOAD";
                    (void)audio.play(SoundEvent::ui_error);
                    break;
                }
                const int master_percent = std::clamp(std::stoi(action.payload.substr(0, separator)), 0, 100);
                const int effects_percent = std::clamp(std::stoi(action.payload.substr(separator + 1)), 0, 100);
                AudioVolumeSettings volumes = audio.volume_settings();
                volumes.master = static_cast<float>(master_percent) / 100.0F;
                volumes.effects = static_cast<float>(effects_percent) / 100.0F;
                audio.set_volume_settings(volumes);
                active_overlay = settings_return_overlay;
                status = active_overlay == UiOverlay::pause ? "SETTINGS APPLIED - GAME PAUSED" :
                    (active_overlay == UiOverlay::main_menu ? "SETTINGS APPLIED - MAIN MENU" : "SETTINGS APPLIED");
                (void)audio.play(SoundEvent::ui_confirm);
                break;
            }
            case UiAction::decrease_service_price:
            case UiAction::increase_service_price: {
                if (!selected_instance_id) {
                    status = "NO BUILDING SELECTED";
                    (void)audio.play(SoundEvent::ui_error);
                    break;
                }
                const BuildingInstance* instance = buildings.find_by_id(*selected_instance_id);
                const BuildingDefinition* definition = instance == nullptr ? nullptr : catalog.find(instance->definition_id);
                if (instance == nullptr || definition == nullptr || definition->default_service_price <= 0) {
                    status = "BUILDING HAS NO CUSTOMER PRICE";
                    (void)audio.play(SoundEvent::ui_error);
                    break;
                }
                const std::int64_t delta = action.action == UiAction::increase_service_price ? 1 : -1;
                if (buildings.set_service_price(instance->instance_id, *definition, instance->service_price + delta)) {
                    const BuildingInstance* updated = buildings.find_by_id(instance->instance_id);
                    economy.rebuild_monthly_summary(buildings, catalog, population, &farming);
                    status = definition->name + ": PRECO AO CLIENTE " +
                        format_money(updated == nullptr ? instance->service_price : updated->service_price);
                    (void)audio.play(SoundEvent::ui_click);
                } else {
                    status = "SERVICE PRICE CHANGE FAILED";
                    (void)audio.play(SoundEvent::ui_error);
                }
                break;
            }
            case UiAction::set_wall_color:
            case UiAction::set_roof_color: {
                if (!selected_instance_id) {
                    status = "NO BUILDING SELECTED";
                    (void)audio.play(SoundEvent::ui_error);
                    break;
                }
                const BuildingInstance* instance = buildings.find_by_id(*selected_instance_id);
                const BuildingDefinition* definition = instance == nullptr ? nullptr : catalog.find(instance->definition_id);
                if (instance == nullptr || definition == nullptr || !definition->supports_color_mask(instance->rotation)) {
                    status = "BUILDING HAS NO COLOR MASK";
                    (void)audio.play(SoundEvent::ui_error);
                    break;
                }
                const std::size_t first = action.payload.find(':');
                const std::size_t second = first == std::string::npos ? std::string::npos : action.payload.find(':', first + 1);
                if (first == std::string::npos || second == std::string::npos) {
                    status = "INVALID COLOR";
                    (void)audio.play(SoundEvent::ui_error);
                    break;
                }
                try {
                    const int r = std::clamp(std::stoi(action.payload.substr(0, first)), 0, 255);
                    const int g = std::clamp(std::stoi(action.payload.substr(first + 1, second - first - 1)), 0, 255);
                    const int b = std::clamp(std::stoi(action.payload.substr(second + 1)), 0, 255);
                    const BuildingColorTint tint{static_cast<std::uint8_t>(r), static_cast<std::uint8_t>(g), static_cast<std::uint8_t>(b)};
                    const bool changed = action.action == UiAction::set_wall_color
                        ? buildings.set_wall_color_customization(instance->instance_id, tint)
                        : buildings.set_roof_color_customization(instance->instance_id, tint);
                    status = changed ? definition->name + (action.action == UiAction::set_wall_color ? ": WALL COLOR" : ": ROOF COLOR")
                                     : "COLOR CHANGE FAILED";
                    (void)audio.play(changed ? SoundEvent::ui_click : SoundEvent::ui_error);
                } catch (...) {
                    status = "INVALID COLOR";
                    (void)audio.play(SoundEvent::ui_error);
                }
                break;
            }
            case UiAction::reset_building_colors:
                if (selected_instance_id && buildings.clear_color_customization(*selected_instance_id)) {
                    status = "ORIGINAL BUILDING COLORS RESTORED";
                    (void)audio.play(SoundEvent::ui_click);
                } else {
                    status = "COLOR RESET FAILED";
                    (void)audio.play(SoundEvent::ui_error);
                }
                break;
            case UiAction::close_selection:
                selected_instance_id.reset();
                status = "INFO PANEL CLOSED";
                (void)audio.play(SoundEvent::ui_close_panel);
                break;
            case UiAction::none: break;
        }
    };
    const auto make_ui_model = [&](const std::pair<int, int>& hovered_tile) {
        GameplayUiModel model;
        const MonthlyEconomySummary& monthly = economy.monthly_summary();
        model.funds = format_money(economy.funds());
        model.date = format_date(simulation_clock.date());
        model.day_month = "DAY " + std::to_string(simulation_clock.date().day) +
                          " - MONTH " + std::to_string(simulation_clock.date().month);
        model.year = "YEAR " + std::to_string(simulation_clock.date().year);
        model.monthly_revenue = format_money(monthly.revenue);
        model.monthly_expenses = format_money(monthly.expenses);
        model.monthly_balance = format_balance(monthly.balance);
        model.population = std::to_string(population.current_population());
        model.residential_capacity = std::to_string(population.residential_capacity());
        model.power_demand = std::to_string(power.power_demand());
        model.power_capacity = std::to_string(power.power_capacity());
        switch (simulation_clock.speed()) {
            case SimulationSpeed::paused: model.speed = "PAUSED"; model.paused = true; break;
            case SimulationSpeed::speed1: model.speed = "RUNNING"; break;
            // v1 saves can contain these legacy speed values. They are never
            // exposed by gameplay UI and are normalized on load below.
            case SimulationSpeed::speed2: model.speed = "RUNNING"; break;
            case SimulationSpeed::speed3: model.speed = "RUNNING"; break;
        }
        model.status = status;
        model.terrain_paint_style = terrain_paint_style;
        model.overlay = active_overlay;
        model.administration_services = "ROAD / POWER / FARMING";
        model.administration_alerts = status.empty() ? "NO ACTIVE ALERTS" : status;
        model.master_volume_percent = static_cast<int>(std::lround(audio.volume_settings().master * 100.0F));
        model.effects_volume_percent = static_cast<int>(std::lround(audio.volume_settings().effects * 100.0F));
        model.save_available = std::filesystem::exists(save_path);
        model.startup_main_menu = startup_main_menu;
        model.build_panel_open = build_panel_open;
        model.farming_panel_open = agriculture_panel_open;
        model.selected_farming_id = farming_selection_id;
        const auto infrastructure = agricultural_infrastructure();
        model.farming_infrastructure = "INFRA: CELEIRO " + std::string(infrastructure.barn ? "[OK]" : "[X]") +
            " | SILO " + (infrastructure.silo ? "[OK]" : "[X]");
        model.farming_stock = "ARMAZENAMENTO GERAL " + std::to_string(farming.general_inventory_used()) + "/" +
            std::to_string(farming.general_storage_capacity());
        if (farming.grain_storage_capacity() > 0) {
            model.farming_stock += " | GRAOS " + std::to_string(farming.grain_inventory()) + "/" +
                std::to_string(farming.grain_storage_capacity());
        }
        if (const FarmTile* farm_tile = farming.tile_at(hovered_tile.first, hovered_tile.second)) {
            if (farm_tile->state == FarmTileState::prepared_soil) {
                model.farming_tile_status = "TERRA PREPARADA";
            } else if (const CropDefinition* crop = crop_catalog.find(farm_tile->crop_id); crop != nullptr) {
                if (farm_tile->state == FarmTileState::ready_to_harvest) {
                    model.farming_tile_status = crop->display_name + ": PRONTO +" + std::to_string(crop->harvest_yield) +
                        " | ESPACO " + std::to_string(farming.available_storage_for(*crop));
                } else {
                    const int elapsed = FarmingSystem::absolute_day(simulation_clock.date()) - farm_tile->planted_day;
                    model.farming_tile_status = crop->display_name + " FASE " + std::to_string(farm_tile->stage + 1) +
                        " | " + std::to_string(std::max(0, crop->growth_days_total - elapsed)) + " DIAS";
                }
            } else if (farm_tile->state == FarmTileState::ready_to_harvest) {
                model.farming_tile_status = "CULTURA: COLHER";
            } else {
                model.farming_tile_status = "CULTURA FASE " + std::to_string(farm_tile->stage + 1);
            }
        } else {
            model.farming_tile_status = "GRAMA";
        }
        if (farming.general_inventory_used() > farming.general_storage_capacity()) {
            model.farming_tile_status = "SOBRE CAPACIDADE";
        }
        model.active_tool = UiTool::none;
        if (decoration_mode) {
            model.active_tool = UiTool::decoration;
        } else if (land_mode || !terrain_paint_style.empty()) {
            model.active_tool = UiTool::land;
        } else if (sidewalk_mode) {
            model.active_tool = UiTool::sidewalks;
        } else if (agriculture_mode) {
            model.active_tool = UiTool::agriculture;
        } else if (road_mode) {
            model.active_tool = road_removal_mode ? UiTool::remove : UiTool::roads;
        } else if (!placement_definition_id.empty() || build_panel_open) {
            model.active_tool = UiTool::buildings;
        }
        if (const BuildingDefinition* placement = catalog.find(placement_definition_id)) {
            model.placement_rotatable = placement->rotatable;
        }
        for (const BuildingDefinition& definition : catalog.definitions()) {
            if (!definition.player_buildable) continue;
            if (definition.category == "agriculture" || !belongs_in_construction_catalog(definition)) continue;
            model.build_items.push_back({definition.id, definition.name, construction_catalog_label(definition),
                                         format_money(definition.build_cost), true,
                                         catalog_thumbnail_path(asset_root, definition),
                                         catalog_footprint_label(definition),
                                         catalog_requirements_label(definition)});
            model.build_items.back().thumbnail_frame_count =
                definition.animation ? std::max(1, definition.animation->frame_count) : 1;
        }
        for (const BuildingDefinition& definition : catalog.definitions()) {
            if (!definition.player_buildable) continue;
            if (definition.category != "decor" || belongs_in_construction_catalog(definition)) continue;
            model.decor_items.push_back({definition.id, definition.name, "DECORACAO",
                                         format_money(definition.build_cost), true,
                                         catalog_thumbnail_path(asset_root, definition),
                                         catalog_footprint_label(definition), catalog_requirements_label(definition)});
        }
        model.farming_items.push_back({"prepared_soil_01", "Terra Preparada", "SOLO", "SEM CUSTO", true,
                                       (asset_root / "assets/farming/prepared_soil/prepared_soil_01.png").string()});
        model.farming_items.push_back({"harvest_tool", "Colher", "FERRAMENTA", "CLIQUE OU ARRASTE", true,
                                       (asset_root / "assets/farming/prepared_soil/prepared_soil_01.png").string()});
        model.farming_items.push_back({"prepare_soil_tool", "Preparar Terra", "FERRAMENTA", "ARRASTE PARA PREPARAR", true,
                                       (asset_root / "assets/farming/prepared_soil/prepared_soil_01.png").string()});
        for (const ServiceVehicleDefinition& vehicle : service_vehicle_catalog.definitions()) {
            int owned = 0;
            std::string vehicle_state = "DISPONIVEL";
            for (const ServiceVehicleInstance& instance : service_vehicles.instances()) {
                if (instance.vehicle_id != vehicle.id || !instance.owned) continue;
                ++owned;
                if (instance.state == ServiceVehicleState::working || instance.state == ServiceVehicleState::moving_to_job) vehicle_state = "TRABALHANDO";
                else if (instance.state == ServiceVehicleState::returning && vehicle_state != "TRABALHANDO") vehicle_state = "RETORNANDO";
            }
            model.farming_items.push_back({"purchase_vehicle:" + vehicle.id, vehicle.display_name, "VEICULO",
                                           format_money(vehicle.purchase_cost) + " | X" + std::to_string(owned) + " " + vehicle_state, true,
                                           (asset_root / vehicle.sprite_south).string()});
        }
        for (const CropDefinition& crop : crop_catalog.definitions()) {
            const bool planting_unlocked = infrastructure.barn && infrastructure.silo;
            model.farming_items.push_back({crop.id, crop.display_name, "CULTURA",
                                           planting_unlocked ? "COLHEITA: " + std::to_string(crop.harvest_yield) : "REQUER CELEIRO E SILO",
                                           planting_unlocked,
                                           (asset_root / crop.thumbnail_path()).string()});
        }
        for (const AgriculturalResourceDefinition& resource : resource_catalog.definitions()) {
            model.farming_items.push_back({"sell_resource:" + resource.id, "Vender " + resource.display_name, "ESTOQUE / VENDA",
                                           std::to_string(farming.inventory_count(resource.id)) + " x " + format_money(resource.base_sell_price) + " | VENDER TUDO", true, ""});
        }
        model.selected_building_id = placement_definition_id;
        if (land_mode) {
            const LandParcel* parcel = lands.parcel_at(hovered_tile.first, hovered_tile.second);
            if (parcel == nullptr) {
                model.land_details = UiLandDetails{"OUTSIDE MAP", "-", "LOCKED"};
            } else if (parcel->owned) {
                model.land_details = UiLandDetails{std::to_string(parcel->id), format_money(parcel->purchase_cost), "OWNED"};
            } else if (!lands.can_purchase_parcel(parcel->id)) {
                model.land_details = UiLandDetails{std::to_string(parcel->id), format_money(parcel->purchase_cost), "LOCKED"};
            } else {
                model.land_details = UiLandDetails{std::to_string(parcel->id), format_money(parcel->purchase_cost), "AVAILABLE"};
            }
        }
        if (selected_instance_id) {
            if (const BuildingInstance* instance = buildings.find_by_id(*selected_instance_id)) {
                if (const BuildingDefinition* definition = catalog.find(instance->definition_id)) {
                    const auto& lvl_def = instance->current_level_definition(*definition);
                    const auto* next_lvl_def = instance->next_level_definition(*definition);
                    const bool is_max = instance->is_max_level(*definition);
                    const std::string level_label = "NIVEL " + std::to_string(instance->current_level) + " / " + std::to_string(definition->levels.size());
                    const std::string upgrade_btn_text = is_max
                        ? "NIVEL MAXIMO"
                        : ("EVOLUIR PARA NIVEL " + std::to_string(instance->current_level + 1) + " - " + format_money(next_lvl_def->upgrade_cost));
                    const bool can_upgrade = !is_max && economy.can_afford(next_lvl_def->upgrade_cost);

                    const std::uint32_t commercial_demand_percent = CityEconomy::commercial_demand_percent(
                        *definition, population.current_population());
                    const bool has_commercial_demand = definition->required_population_for_full_revenue != 0;
                    const std::int64_t commercial_current_revenue = lvl_def.tax_revenue_per_month *
                        static_cast<std::int64_t>(commercial_demand_percent) / 100;
                    const ServicePricingEstimate service_estimate = CityEconomy::service_pricing_estimate(
                        *definition, *instance, population.current_population(), &farming);
                    model.selected_building = UiSelectedBuilding{
                        definition->name,
                        std::string(category_label(definition->category)),
                        format_money(definition->build_cost),
                        format_money(lvl_def.tax_revenue_per_month),
                        format_money(lvl_def.maintenance_per_month),
                        format_balance(lvl_def.tax_revenue_per_month - lvl_def.maintenance_per_month),
                        rotation_label(instance->rotation),
                        building_has_required_edge_access(*definition, instance->rotation, instance->tile_x, instance->tile_y, roads, sidewalks)
                            ? (definition->requires_road_or_path_access ? "ROAD/PATH CONNECTED" : "ROAD CONNECTED")
                            : (definition->requires_road_or_path_access ? "NO ROAD/PATH" : "NO ROAD"),
                        std::to_string(instance->instance_id),
                        has_commercial_demand ? std::to_string(commercial_demand_percent) + "%" : "",
                        (asset_root / definition->texture_path_for(instance->rotation, instance->current_level)).string(),
                        definition->requires_road_or_path_access ? "ROAD OR PATH" :
                            (definition->requires_road_access ? "REQUIRED" : "NOT REQUIRED"),
                        lvl_def.power_consumption == 0 ? "" : std::to_string(lvl_def.power_consumption),
                        definition->power_production == 0 ? "" : "+" + std::to_string(definition->power_production),
                        lvl_def.residential_capacity == 0 ? "" : std::to_string(lvl_def.residential_capacity),
                        lvl_def.residential_capacity == 0 ? "" : format_money(definition->property_tax_per_year),
                        has_commercial_demand ? format_money(commercial_current_revenue) : "",
                        level_label,
                        upgrade_btn_text,
                        can_upgrade,
                        is_max,
                        definition->service_name,
                        definition->default_service_price > 0 ? format_money(instance->service_price) : "",
                        definition->default_service_price > 0
                            ? "MIN " + format_money(definition->minimum_service_price) +
                              "  |  MAX " + format_money(definition->maximum_service_price)
                            : "",
                        definition->default_service_price > 0 ? std::to_string(service_estimate.price_demand_percent) + "%" : "",
                        definition->default_service_price > 0 ? std::to_string(service_estimate.customers_per_month) : "",
                        definition->default_service_price > 0 ? format_money(service_estimate.revenue_per_month) + "/MES" : "",
                        definition->default_service_price > 0
                            ? format_balance(service_estimate.revenue_per_month - lvl_def.maintenance_per_month) + "/MES"
                            : "",
                        definition->default_service_price > 0,
                        definition->default_service_price > 0 && instance->service_price > definition->minimum_service_price,
                        definition->default_service_price > 0 && instance->service_price < definition->maximum_service_price,
                        definition->color_mask.has_value() && definition->color_mask->enabled,
                        instance->wall_color_customized,
                        instance->roof_color_customized,
                        static_cast<int>(instance->wall_tint.r),
                        static_cast<int>(instance->wall_tint.g),
                        static_cast<int>(instance->wall_tint.b),
                        static_cast<int>(instance->roof_tint.r),
                        static_cast<int>(instance->roof_tint.g),
                        static_cast<int>(instance->roof_tint.b),
                    };
                    model.selected_building->thumbnail_frame_count =
                        definition->animation ? std::max(1, definition->animation->frame_count) : 1;
                }
            }
        }
        model.debug_visible = debug_visible;
        if (debug_visible) {
            const LandParcel* parcel = lands.parcel_at(hovered_tile.first, hovered_tile.second);
            model.debug_lines = {
                "TILE: " + std::to_string(hovered_tile.first) + "," + std::to_string(hovered_tile.second),
                "BUILDINGS: " + std::to_string(buildings.instances().size()) + " | ROADS: " + std::to_string(roads.tiles().size()),
                "OCCUPANCY: " + std::string(tile_occupancy_label(buildings, roads, sidewalks, farming, hovered_tile.first, hovered_tile.second)),
                "ROAD: " + std::string(roads.is_drivable(hovered_tile.first, hovered_tile.second) ? "DRIVABLE " : "NO ") +
                    connection_label(roads.connection_mask(hovered_tile.first, hovered_tile.second)),
                "SIDEWALK: " + std::string(sidewalks.is_walkable(hovered_tile.first, hovered_tile.second) ? "WALKABLE " : "NO ") +
                    connection_label(sidewalks.connection_mask(hovered_tile.first, hovered_tile.second)),
                "PARCEL: " + (parcel == nullptr ? std::string("OUTSIDE MAP") : std::to_string(parcel->id) + (parcel->owned ? " OWNED" : " LOCKED")),
                "TILE OWNED: " + std::string(lands.is_tile_owned(hovered_tile.first, hovered_tile.second) ? "YES" : "NO") +
                    " | OWNED PARCELS: " + std::to_string(lands.owned_parcel_count()),
                "POPULATION: " + std::to_string(population.current_population()) + " / " +
                    std::to_string(population.residential_capacity()),
                "ENERGY: " + std::to_string(power.power_demand()) + " / " + std::to_string(power.power_capacity()),
                "F2 NETWORK | F3 START | F4 GOAL | F6 PEDESTRIAN | F7 WALK | F8 LOOK | F11 ACTIVITY | F5 SAVE | F9 LOAD | F10 CALIBRATION",
            };
            if (selected_instance_id) {
                if (const BuildingInstance* instance = buildings.find_by_id(*selected_instance_id)) {
                    if (const BuildingDefinition* definition = catalog.find(instance->definition_id)) {
                        const BuildingFootprint footprint = rotated_footprint(*definition, instance->rotation);
                        const BuildingRotation visual_rotation = camera_visual_rotation(*definition, instance->rotation, camera.rotation);
                        model.debug_lines.push_back("ISO AUDIT: " + std::string(rotation_label(instance->rotation)) +
                                                    " | VISUAL " + rotation_label(visual_rotation) +
                                                    " | CAMERA " + camera_rotation_label(camera.rotation));
                        model.debug_lines.push_back("FOOTPRINT: " + std::to_string(footprint.width) + "x" +
                                                    std::to_string(footprint.height) + " | TILE " +
                                                    std::to_string(instance->tile_x) + "," + std::to_string(instance->tile_y));
                        model.debug_lines.push_back("SPRITE ANCHOR: " + std::to_string(definition->anchor_x_for(visual_rotation)) +
                                                    "," + std::to_string(definition->anchor_y_for(visual_rotation)) +
                                                    " | FRONT " + access_points_label(*definition, instance->rotation));
                        model.debug_lines.push_back("OVERLAY: yellow footprint | cyan anchor | magenta PNG bounds | red X | green Y");
                    }
                }
            }
            const std::vector<MobileEntityRenderData> entities = mobile_render_entities();
            if (!entities.empty()) {
                const MobileEntityRenderData& entity = entities.front();
                model.debug_lines.push_back("MOBILE: " + entity.logical_state + " | " + mobile_direction_label(entity.spatial.direction));
                model.debug_lines.push_back("ANIM: " + entity.animation_set_id + " | " + entity.animation_clip_id +
                                            " | FRAME " + std::to_string(entity.animation_frame_index));
            }
            if (!pedestrians.instances().empty()) {
                const PedestrianInstance& pedestrian = pedestrians.instances().front();
                model.debug_lines.push_back("PEDESTRIAN: " + std::string(pedestrian.state == PedestrianState::walking ? "WALKING" : "IDLE") +
                                            " | " + mobile_direction_label(pedestrian.spatial.direction) + " | TILE " +
                                            std::to_string(pedestrian.spatial.logical_tile_x) + "," +
                                            std::to_string(pedestrian.spatial.logical_tile_y));
            }
            if (!placement_definition_id.empty()) {
                if (const BuildingDefinition* definition = catalog.find(placement_definition_id)) {
                    const BuildingPlacementValidation validation = validate_building_placement(
                        *definition, placement_rotation, hovered_tile.first, hovered_tile.second,
                        buildings, roads, lands, sidewalks, farming, economy, power, active_map_doc ? &*active_map_doc : nullptr);
                    model.debug_lines.push_back("PLACEMENT: " + std::string(validation.valid() ? "VALID" : placement_validation_text(validation)));
                    model.debug_lines.push_back("FRONTAGE: " + std::string(road_access_mode_label(resolved_road_access_mode(*definition))) +
                                                " | " + access_points_label(*definition, placement_rotation));
                    std::string candidates = "ROAD CANDIDATES:";
                    for (const BuildingAccessPoint& access : road_access_candidates(*definition, placement_rotation)) {
                        const TileCoordinate offset = road_access_offset(access.facing);
                        candidates += " " + std::to_string(hovered_tile.first + access.local_x + offset.x) + "," +
                                      std::to_string(hovered_tile.second + access.local_y + offset.y);
                    }
                    if (candidates == "ROAD CANDIDATES:") candidates += " PERIMETER";
                    model.debug_lines.push_back(std::move(candidates));
                }
            }
            const std::string navigation_type = navigation_debug_uses_roads ? "ROAD" : "SIDEWALK";
            if (!navigation_debug_start || !navigation_debug_goal) {
                model.debug_lines.push_back("NAV " + navigation_type + ": F2 TYPE | F3 START | F4 GOAL");
            } else {
                NavigationPathResult navigation_path;
                if (navigation_debug_uses_roads) {
                    navigation_path = find_navigation_path(RoadNavigationNetwork{roads}, *navigation_debug_start, *navigation_debug_goal);
                } else {
                    navigation_path = find_navigation_path(SidewalkNavigationNetwork{sidewalks}, *navigation_debug_start, *navigation_debug_goal);
                }
                model.debug_lines.push_back("NAV " + navigation_type + " " + std::to_string(navigation_debug_start->x) + "," +
                                            std::to_string(navigation_debug_start->y) + " -> " +
                                            std::to_string(navigation_debug_goal->x) + "," + std::to_string(navigation_debug_goal->y) +
                                            (navigation_path.status == NavigationPathStatus::found
                                                ? " | PATH " + std::to_string(navigation_path.tiles.size())
                                                : " | NO PATH"));
            }
        }
        return model;
    };

    while (running) {
        rebuild_agricultural_storage();
        int viewport_width = 0;
        int viewport_height = 0;
        SDL_GetCurrentRenderOutputSize(renderer, &viewport_width, &viewport_height);

        float event_mouse_x = 0.0F;
        float event_mouse_y = 0.0F;
        SDL_GetMouseState(&event_mouse_x, &event_mouse_y);
        const auto event_mouse_tile = land_mode
            ? screen_to_tile(event_mouse_x, event_mouse_y, camera, static_cast<float>(viewport_width), static_cast<float>(viewport_height))
            : nearest_owned_tile(screen_to_tile(event_mouse_x, event_mouse_y, camera,
                                                static_cast<float>(viewport_width), static_cast<float>(viewport_height)), lands);
        gameplay_ui.update_layout(viewport_width, viewport_height, make_ui_model(event_mouse_tile));

        SDL_Event event;
        while (SDL_PollEvent(&event)) {
            if (event.type == SDL_EVENT_QUIT) {
                running = false;
            } else if (event.type == SDL_EVENT_MOUSE_MOTION) {
                if (camera_dragging) {
                    camera.pan_x += event.motion.xrel;
                    camera.pan_y += event.motion.yrel;
                    camera.pan_velocity_x = 0.0F;
                    camera.pan_velocity_y = 0.0F;
                    clamp_camera_to_owned_land(camera, lands, static_cast<float>(viewport_width), static_cast<float>(viewport_height));
                    continue;
                }
                gameplay_ui.handle_mouse_motion(event.motion.x, event.motion.y);
            } else if (event.type == SDL_EVENT_MOUSE_WHEEL) {
                float wheel_mouse_x = 0.0F;
                float wheel_mouse_y = 0.0F;
                SDL_GetMouseState(&wheel_mouse_x, &wheel_mouse_y);
                if (gameplay_ui.handle_mouse_wheel(wheel_mouse_x, wheel_mouse_y, event.wheel.y)) {
                    continue;
                }
                if (!gameplay_ui.consumes_point(wheel_mouse_x, wheel_mouse_y)) {
                    camera.zoom = std::clamp(camera.zoom + event.wheel.y * 0.10F, 0.65F, 1.65F);
                    clamp_camera_to_owned_land(camera, lands, static_cast<float>(viewport_width), static_cast<float>(viewport_height));
                }
            } else if (event.type == SDL_EVENT_MOUSE_BUTTON_DOWN) {
                if (event.button.button == SDL_BUTTON_MIDDLE &&
                    !gameplay_ui.consumes_point(event.button.x, event.button.y)) {
                    camera_dragging = true;
                    camera.pan_velocity_x = 0.0F;
                    camera.pan_velocity_y = 0.0F;
                    continue;
                }
                const UiInputResult ui_input = gameplay_ui.handle_mouse_button_down(
                    event.button.x, event.button.y, event.button.button == SDL_BUTTON_LEFT);
                if (ui_input.consumed) {
                    // A physical click has a stable sound even for controls
                    // (such as category tabs) that do not emit an action.
                    if (event.button.button == SDL_BUTTON_LEFT) (void)audio.play(SoundEvent::ui_click);
                    if (ui_input.action) {
                        apply_ui_action(*ui_input.action);
                    }
                    continue;
                }
                const auto raw_clicked_tile = screen_to_tile(event.button.x, event.button.y, camera,
                                                             static_cast<float>(viewport_width), static_cast<float>(viewport_height));
                const auto clicked_tile = land_mode ? raw_clicked_tile : nearest_owned_tile(raw_clicked_tile, lands);
                if (event.button.button == SDL_BUTTON_RIGHT && land_mode) {
                    land_mode = false;
                    status = "LAND MODE CANCELLED";
                    (void)audio.play(SoundEvent::ui_back);
                } else if (event.button.button == SDL_BUTTON_RIGHT && !terrain_paint_style.empty()) {
                    terrain_paint_style.clear();
                    status = "TERRAIN PAINT CANCELLED";
                    (void)audio.play(SoundEvent::ui_back);
                } else if (event.button.button == SDL_BUTTON_RIGHT && road_mode) {
                    road_dragging = false;
                    road_mode = false;
                    road_removal_mode = false;
                    status = "ROAD MODE CANCELLED";
                    (void)audio.play(SoundEvent::ui_back);
                } else if (event.button.button == SDL_BUTTON_RIGHT && sidewalk_mode) {
                    sidewalk_mode = false;
                    sidewalk_dragging = false;
                    status = "SIDEWALK MODE CANCELLED";
                    (void)audio.play(SoundEvent::ui_back);
                } else if (event.button.button == SDL_BUTTON_RIGHT && agriculture_mode) {
                    agriculture_mode = false;
                    agriculture_panel_open = false;
                    farming_selection_id.clear();
                    harvest_dragging = false;
                    preparation_dragging = false;
                    status = "AGRICULTURE MODE CANCELLED";
                    (void)audio.play(SoundEvent::ui_back);
                } else if (event.button.button == SDL_BUTTON_RIGHT && decoration_mode) {
                    decoration_mode = false;
                    status = "DECORATION MODE CANCELLED";
                    (void)audio.play(SoundEvent::ui_back);
                } else if (event.button.button == SDL_BUTTON_RIGHT && !placement_definition_id.empty()) {
                    placement_definition_id.clear();
                    status = "BUILD MODE CANCELLED";
                    (void)audio.play(SoundEvent::ui_back);
                } else if (event.button.button == SDL_BUTTON_LEFT) {
                    if (!terrain_paint_style.empty()) {
                        const int x = raw_clicked_tile.first, y = raw_clicked_tile.second;
                        const MapTileOccupancy occupancy = inspect_map_tile(buildings, roads, sidewalks, farming, x, y);
                        const auto existing = active_map_doc->get_terrain_at(x, y);
                        const std::string existing_style = existing ? existing->terrain_definition : "grass";
                        const bool paintable = existing_style == "grass" || existing_style == "sand" ||
                            existing_style == "sand_center" || existing_style == "sand_wet";
                        if (!lands.is_tile_owned(x, y) || occupancy.building || occupancy.road ||
                            occupancy.sidewalk || occupancy.farm || !paintable ||
                            (terrain_paint_style == "sand" && paintable_sand == nullptr)) {
                            status = "TERRAIN REQUIRES EMPTY OWNED GRASS OR SAND";
                            (void)audio.play(SoundEvent::ui_error);
                        } else {
                            const std::string path = terrain_paint_style == "sand"
                                ? "assets/terrain/sand_isometric_01.png" : "";
                            active_map_doc->paint_terrain_at(x, y,
                                                             terrain_paint_style == "sand" ? "sand_center" : "grass", path);
                            const auto saved = std::find_if(terrain_paint.begin(), terrain_paint.end(),
                                [x, y](const TerrainPaintTile& tile) { return tile.tile_x == x && tile.tile_y == y; });
                            if (saved == terrain_paint.end()) terrain_paint.push_back({x, y, terrain_paint_style});
                            else saved->style = terrain_paint_style;
                            status = terrain_paint_style == "sand" ? "SAND PAINTED" : "GRASS PAINTED";
                            (void)audio.play(SoundEvent::ui_confirm);
                        }
                    } else if (land_mode) {
                        const LandParcel* parcel = lands.parcel_at(clicked_tile.first, clicked_tile.second);
                        if (parcel == nullptr) {
                            status = "NO PARCEL AT THIS TILE";
                            (void)audio.play(SoundEvent::ui_error);
                        } else if (parcel->owned) {
                            status = "PARCEL ALREADY OWNED";
                            (void)audio.play(SoundEvent::ui_error);
                        } else if (!lands.can_purchase_parcel(parcel->id)) {
                            status = "PARCEL MUST TOUCH OWNED LAND";
                            (void)audio.play(SoundEvent::ui_error);
                        } else if (!economy.can_afford(parcel->purchase_cost)) {
                            status = "NOT ENOUGH FUNDS FOR LAND";
                            (void)audio.play(SoundEvent::ui_error);
                        } else if (lands.purchase_parcel(parcel->id, economy, simulation_clock.date())) {
                            status = "LAND PURCHASED: PARCEL " + std::to_string(parcel->id) + " - " +
                                format_money(parcel->purchase_cost);
                            (void)audio.play(SoundEvent::ui_confirm);
                        } else {
                            status = "LAND PURCHASE FAILED";
                            (void)audio.play(SoundEvent::ui_error);
                        }
                    } else if (road_mode && road_removal_mode) {
                        const BuildingInstance* building = buildings.instance_at(clicked_tile.first, clicked_tile.second);
                        const BuildingDefinition* definition = building == nullptr ? nullptr : catalog.find(building->definition_id);
                        if (building != nullptr && definition != nullptr && buildings.remove_instance(*definition, building->instance_id)) {
                            rebuild_agricultural_storage();
                            population.rebuild_capacity(buildings, catalog);
                            power.rebuild(buildings, catalog);
                            selected_instance_id.reset();
                            status = "BUILDING DEMOLISHED";
                            (void)audio.play(SoundEvent::ui_confirm);
                            if (mission_manager.check_and_auto_complete_clean_energy(economy, buildings, catalog, population, power)) {
                                status = "MISSAO ENERGIA LIMPA CONCLUIDA! Hidreletrica Reativada!";
                            }
                        } else if (sidewalks.remove_tile(clicked_tile.first, clicked_tile.second)) {
                            status = "SIDEWALK REMOVED";
                            (void)audio.play(SoundEvent::ui_confirm);
                        } else if (roads.remove_tile(clicked_tile.first, clicked_tile.second)) {
                            status = "ROAD REMOVED";
                            (void)audio.play(SoundEvent::ui_confirm);
                        } else {
                            status = "NO BUILDING, SIDEWALK OR ROAD ON THIS TILE";
                            (void)audio.play(SoundEvent::ui_error);
                        }
                    } else if (sidewalk_mode) {
                        sidewalk_dragging = true;
                        sidewalk_drag_start = {clicked_tile.first, clicked_tile.second};
                    } else if (agriculture_mode && farming_selection_id == "harvest_tool") {
                        harvest_dragging = true;
                        harvest_drag_start = {clicked_tile.first, clicked_tile.second};
                    } else if (agriculture_mode && farming_selection_id == "prepare_soil_tool") {
                        preparation_dragging = true;
                        preparation_drag_start = {clicked_tile.first, clicked_tile.second};
                    } else if (agriculture_mode && crop_catalog.find(farming_selection_id) != nullptr) {
                        planting_dragging = true;
                        planting_drag_start = {clicked_tile.first, clicked_tile.second};
                    } else if (agriculture_mode) {
                        if (farming_selection_id.starts_with("purchase_vehicle:")) {
                            const std::string vehicle_id = farming_selection_id.substr(std::string("purchase_vehicle:").size());
                            const ServiceVehicleDefinition* vehicle = service_vehicle_catalog.find(vehicle_id);
                            if (vehicle == nullptr) {
                                status = "UNKNOWN FARM VEHICLE";
                            } else if (!lands.is_tile_owned(clicked_tile.first, clicked_tile.second) || !vehicle_traversable(clicked_tile.first, clicked_tile.second)) {
                                status = "TRACTOR HOME REQUIRES EMPTY OWNED TILE";
                            } else if (!economy.try_spend(vehicle->purchase_cost)) {
                                status = "NOT ENOUGH FUNDS FOR TRACTOR";
                            } else if (service_vehicles.add({vehicle->id, static_cast<float>(clicked_tile.first), static_cast<float>(clicked_tile.second),
                                                             static_cast<float>(clicked_tile.first), static_cast<float>(clicked_tile.second),
                                                             static_cast<float>(clicked_tile.first), static_cast<float>(clicked_tile.second)}, service_vehicle_catalog)) {
                                status = vehicle->display_name + " PURCHASED";
                                farming_selection_id.clear();
                                (void)audio.play(SoundEvent::ui_confirm);
                            }
                            continue;
                        }
                        const FarmTile* farm_tile = farming.tile_at(clicked_tile.first, clicked_tile.second);
                        if (farm_tile != nullptr && farm_tile->state == FarmTileState::ready_to_harvest) {
                            const CropDefinition* crop = crop_catalog.find(farm_tile->crop_id);
                            const int harvested = farming.harvest(clicked_tile.first, clicked_tile.second, crop_catalog, simulation_clock.date());
                            status = harvested > 0 ? crop->display_name + " HARVESTED: +" + std::to_string(harvested) :
                                (crop != nullptr && farming.available_storage_for(*crop) < crop->harvest_yield ? "ARMAZENAMENTO INSUFICIENTE" : "HARVEST FAILED");
                            (void)audio.play(harvested > 0 ? SoundEvent::ui_confirm : SoundEvent::ui_error);
                        } else if (!lands.is_tile_owned(clicked_tile.first, clicked_tile.second)) {
                            status = "AGRICULTURE REQUIRES OWNED LAND"; (void)audio.play(SoundEvent::ui_error);
                        } else if (farming_selection_id == "prepared_soil_01") {
                            if (roads.is_road(clicked_tile.first, clicked_tile.second) || sidewalks.is_sidewalk(clicked_tile.first, clicked_tile.second) ||
                                buildings.is_occupied(clicked_tile.first, clicked_tile.second) || farming.is_occupied(clicked_tile.first, clicked_tile.second)) {
                                status = "SOIL BLOCKED BY OCCUPIED TILE"; (void)audio.play(SoundEvent::ui_error);
                            } else if (farming.prepare_soil(clicked_tile.first, clicked_tile.second)) {
                                status = "PREPARED SOIL PLACED"; (void)audio.play(SoundEvent::ui_confirm);
                            }
                        } else if (const CropDefinition* crop = crop_catalog.find(farming_selection_id)) {
                            const auto infrastructure = agricultural_infrastructure();
                            if (!infrastructure.barn && !infrastructure.silo) {
                                status = "CONSTRUA CELEIRO E SILO PARA LIBERAR O PLANTIO";
                                (void)audio.play(SoundEvent::ui_error);
                            } else if (!infrastructure.barn) {
                                status = "CONSTRUA UM CELEIRO PARA INICIAR A AGRICULTURA";
                                (void)audio.play(SoundEvent::ui_error);
                            } else if (!infrastructure.silo) {
                                status = "CONSTRUA UM SILO PARA INICIAR A AGRICULTURA";
                                (void)audio.play(SoundEvent::ui_error);
                            } else if (farming.plant(clicked_tile.first, clicked_tile.second, *crop, simulation_clock.date())) {
                                status = crop->display_name + " PLANTED"; (void)audio.play(SoundEvent::ui_confirm);
                            } else {
                                status = "CROP REQUIRES PREPARED SOIL"; (void)audio.play(SoundEvent::ui_error);
                            }
                        } else {
                            status = "SELECT SOIL OR A CROP"; (void)audio.play(SoundEvent::ui_error);
                        }
                    } else if (road_mode) {
                        road_dragging = true;
                        road_drag_start = {clicked_tile.first, clicked_tile.second};
                    } else if (decoration_mode) {
                        status = "DECORATION: SELECT AN ITEM";
                    } else if (placement_definition_id.empty()) {
                        const BuildingInstance* clicked = buildings.instance_at(clicked_tile.first, clicked_tile.second);
                        if (clicked == nullptr) {
                            selected_instance_id.reset();
                        } else {
                            selected_instance_id = clicked->instance_id;
                            // Selection and its information panel are one action: one feedback sound only.
                            (void)audio.play(SoundEvent::ui_select);
                        }
                        status = clicked == nullptr ? "NO BUILDING ON THIS TILE" : "BUILDING SELECTED";
                    } else if (const BuildingDefinition* placement = catalog.find(placement_definition_id)) {
                        const BuildingPlacementValidation validation = validate_building_placement(
                            *placement, placement_rotation, clicked_tile.first, clicked_tile.second,
                            buildings, roads, lands, sidewalks, farming, economy, power, active_map_doc ? &*active_map_doc : nullptr);
                        if (!validation.valid()) {
                            status = placement_validation_text(validation);
                            (void)audio.play(SoundEvent::ui_error);
                        } else if (const auto instance_id = buildings.place(*placement, clicked_tile.first, clicked_tile.second, placement_rotation)) {
                            (void)economy.spend_for_building(placement->build_cost, simulation_clock.date(), *instance_id);
                            population.rebuild_capacity(buildings, catalog);
                            power.rebuild(buildings, catalog);
                            selected_instance_id = *instance_id;
                            status = placement->name + " BUILT: " + format_money(placement->build_cost) + " SPENT";
                            if (power.power_available() < 0) {
                                status += " | POWER DEFICIT " + std::to_string(-power.power_available());
                            }
                            (void)audio.play(SoundEvent::building_place);
                            if (mission_manager.check_and_auto_complete_clean_energy(economy, buildings, catalog, population, power)) {
                                status = "MISSAO ENERGIA LIMPA CONCLUIDA! Hidreletrica Reativada!";
                            }
                        }
                    }
                }
            } else if (event.type == SDL_EVENT_MOUSE_BUTTON_UP) {
                if (event.button.button == SDL_BUTTON_MIDDLE) {
                    camera_dragging = false;
                    continue;
                }
                const bool ui_consumed = gameplay_ui.consumes_point(event.button.x, event.button.y);
                gameplay_ui.handle_mouse_button_up(event.button.x, event.button.y);
                if (ui_consumed) {
                    // A road drag released over a panel is cancelled instead of
                    // drawing through UI coordinates.
                    road_dragging = false;
                    sidewalk_dragging = false;
                    harvest_dragging = false;
                    preparation_dragging = false;
                    planting_dragging = false;
                    continue;
                }
                if (event.button.button != SDL_BUTTON_LEFT) {
                    continue;
                }
                const auto released_tile = screen_to_tile(event.button.x, event.button.y, camera,
                                                          static_cast<float>(viewport_width), static_cast<float>(viewport_height));
                if (agriculture_mode && harvest_dragging) {
                    int harvested_tiles = 0;
                    int total_yield = 0;
                    bool storage_full = false;
                    const int min_x = std::min(harvest_drag_start.x, released_tile.first);
                    const int max_x = std::max(harvest_drag_start.x, released_tile.first);
                    const int min_y = std::min(harvest_drag_start.y, released_tile.second);
                    const int max_y = std::max(harvest_drag_start.y, released_tile.second);
                    for (int y = min_y; y <= max_y && !storage_full; ++y) {
                        for (int x = min_x; x <= max_x; ++x) {
                            const FarmTile* farm_tile = farming.tile_at(x, y);
                            if (farm_tile == nullptr || farm_tile->state != FarmTileState::ready_to_harvest) {
                                continue;
                            }
                            const CropDefinition* crop = crop_catalog.find(farm_tile->crop_id);
                            if (crop == nullptr) {
                                continue;
                            }
                            if (farming.available_storage_for(*crop) < crop->harvest_yield) {
                                storage_full = true;
                                break;
                            }
                            total_yield += farming.harvest(x, y, crop_catalog, simulation_clock.date());
                            ++harvested_tiles;
                        }
                    }
                    status = storage_full ? "ARMAZENAMENTO INSUFICIENTE" :
                        (harvested_tiles == 0 ? "NO READY CROPS IN SELECTION" : "HARVESTED " + std::to_string(harvested_tiles) + " TILE(S): +" + std::to_string(total_yield));
                    (void)audio.play(harvested_tiles > 0 ? SoundEvent::ui_confirm : SoundEvent::ui_error);
                    harvest_dragging = false;
                    continue;
                }
                if (agriculture_mode && preparation_dragging) {
                    const int min_x = std::min(preparation_drag_start.x, released_tile.first);
                    const int max_x = std::max(preparation_drag_start.x, released_tile.first);
                    const int min_y = std::min(preparation_drag_start.y, released_tile.second);
                    const int max_y = std::max(preparation_drag_start.y, released_tile.second);
                    int prepared_count = 0;
                    for (int y = min_y; y <= max_y; ++y) {
                        for (int x = min_x; x <= max_x; ++x) {
                            if (lands.is_tile_owned(x, y) && !roads.is_road(x, y) && !sidewalks.is_sidewalk(x, y) &&
                                !buildings.is_occupied(x, y) && !farming.is_occupied(x, y)) {
                                if (farming.prepare_soil(x, y)) {
                                    prepared_count++;
                                }
                            }
                        }
                    }
                    if (prepared_count > 0) {
                        status = "TERRA PREPARADA: " + std::to_string(prepared_count) + " TILE(S)";
                        (void)audio.play(SoundEvent::ui_confirm);
                    } else {
                        status = "NO VALID TILES FOR SOIL PREPARATION";
                        (void)audio.play(SoundEvent::ui_error);
                    }
                    preparation_dragging = false;
                    continue;
                }
                if (agriculture_mode && planting_dragging) {
                    const CropDefinition* crop = crop_catalog.find(farming_selection_id);
                    const auto infrastructure = agricultural_infrastructure();
                    if (crop == nullptr) {
                        status = "SELECT A CROP TO PLANT";
                        (void)audio.play(SoundEvent::ui_error);
                    } else if (!infrastructure.barn || !infrastructure.silo) {
                        status = !infrastructure.barn && !infrastructure.silo
                            ? "CONSTRUA CELEIRO E SILO PARA LIBERAR O PLANTIO"
                            : (!infrastructure.barn ? "CONSTRUA UM CELEIRO PARA INICIAR A AGRICULTURA"
                                                    : "CONSTRUA UM SILO PARA INICIAR A AGRICULTURA");
                        (void)audio.play(SoundEvent::ui_error);
                    } else {
                        const int min_x = std::min(planting_drag_start.x, released_tile.first);
                        const int max_x = std::max(planting_drag_start.x, released_tile.first);
                        const int min_y = std::min(planting_drag_start.y, released_tile.second);
                        const int max_y = std::max(planting_drag_start.y, released_tile.second);
                        int planted = 0;
                        int skipped = 0;
                        for (int y = min_y; y <= max_y; ++y) {
                            for (int x = min_x; x <= max_x; ++x) {
                                if (farming.plant(x, y, *crop, simulation_clock.date())) ++planted;
                                else ++skipped;
                            }
                        }
                        status = planted == 0 ? "CROP REQUIRES PREPARED SOIL" :
                            crop->display_name + " PLANTED: " + std::to_string(planted) + " TILE(S)" +
                            (skipped == 0 ? "" : " | " + std::to_string(skipped) + " SKIPPED");
                        (void)audio.play(planted == 0 ? SoundEvent::ui_error : SoundEvent::ui_confirm);
                    }
                    planting_dragging = false;
                    continue;
                }
                if (sidewalk_mode && sidewalk_dragging) {
                    int placed = 0;
                    int blocked = 0;
                    for (const TileCoordinate& tile : roads.line_between(sidewalk_drag_start, {released_tile.first, released_tile.second})) {
                        const SidewalkPlacementFailure failure = sidewalks.validate_placement(tile.x, tile.y, roads, buildings);
                        if (!lands.is_tile_owned(tile.x, tile.y) || failure != SidewalkPlacementFailure::none || farming.is_occupied(tile.x, tile.y)) {
                            ++blocked;
                            continue;
                        }
                        if (sidewalks.place_tile(tile.x, tile.y, "dirt_path")) {
                            ++placed;
                        }
                    }
                    status = placed == 0 ? "DIRT PATH BLOCKED BY ROAD, BUILDING OR TILE" :
                        "DIRT PATH PLACED: " + std::to_string(placed) + " TILE(S)" +
                        (blocked == 0 ? "" : " | " + std::to_string(blocked) + " SKIPPED");
                    (void)audio.play(placed == 0 ? SoundEvent::ui_error : SoundEvent::ui_confirm);
                    sidewalk_dragging = false;
                    continue;
                }
                if (!road_mode || !road_dragging) {
                    continue;
                }
                const std::vector<TileCoordinate> segment = roads.line_between(road_drag_start, {released_tile.first, released_tile.second});
                if (!road_segment_is_on_owned_land(segment, lands)) {
                    status = "ROAD REQUIRES OWNED LAND";
                    (void)audio.play(SoundEvent::ui_error);
                } else if (!road_segment_is_valid(segment, roads, buildings) || std::any_of(segment.begin(), segment.end(), [&farming](const TileCoordinate& tile) {
                    return farming.is_occupied(tile.x, tile.y);
                })) {
                    status = "ROAD BLOCKED BY ROAD, BUILDING OR MAP LIMIT";
                    (void)audio.play(SoundEvent::ui_error);
                } else if (!economy.try_spend(static_cast<std::int64_t>(segment.size()) * kRoadCostPerTile)) {
                    status = "NOT ENOUGH FUNDS FOR ROAD";
                    (void)audio.play(SoundEvent::ui_error);
                } else {
                    const int placed = roads.place_segment(segment);
                    status = placed == 0 ? "ROAD ALREADY EXISTS" : "ROAD PLACED: " + std::to_string(placed) + " TILE(S), " +
                        format_money(static_cast<std::int64_t>(placed) * kRoadCostPerTile) + " SPENT";
                }
                road_dragging = false;
            } else if (event.type == SDL_EVENT_KEY_DOWN && !event.key.repeat) {
                if (active_overlay != UiOverlay::none) {
                    if (event.key.scancode == SDL_SCANCODE_ESCAPE) {
                        if (active_overlay == UiOverlay::pause) {
                            apply_ui_action({UiAction::resume_game, {}});
                        } else if (active_overlay == UiOverlay::save_load) {
                            apply_ui_action({UiAction::back_from_save_load, {}});
                        } else if (active_overlay == UiOverlay::settings) {
                            apply_ui_action({UiAction::settings_cancel, {}});
                        } else if (active_overlay == UiOverlay::main_menu) {
                            apply_ui_action({startup_main_menu ? UiAction::open_quit_confirm : UiAction::back_to_pause, {}});
                        } else if (active_overlay == UiOverlay::quit_confirm) {
                            apply_ui_action({UiAction::cancel_quit, {}});
                        } else {
                            active_overlay = UiOverlay::none;
                            status = "PANEL CLOSED";
                            (void)audio.play(SoundEvent::ui_close_panel);
                        }
                    }
                    // Modal screens own keyboard focus.  Their future widgets
                    // can opt in here without build, camera or debug hotkeys
                    // leaking through to the city below.
                    continue;
                }
                switch (event.key.scancode) {
                    case SDL_SCANCODE_K:
                        if (service_vehicles.cancel_active_task(service_vehicle_catalog, vehicle_traversable)) {
                            status = "FARM TASK CANCELLED: TRACTOR RETURNING";
                            (void)audio.play(SoundEvent::ui_back);
                        }
                        break;
                    case SDL_SCANCODE_ESCAPE:
                        if (!placement_definition_id.empty()) {
                            placement_definition_id.clear();
                            status = "BUILD MODE CANCELLED";
                            (void)audio.play(SoundEvent::ui_back);
                        } else if (build_panel_open) {
                            build_panel_open = false;
                            status = "BUILDINGS PANEL CLOSED";
                            (void)audio.play(SoundEvent::ui_close_panel);
                        } else if (land_mode) {
                            land_mode = false;
                            status = "LAND MODE CANCELLED";
                            (void)audio.play(SoundEvent::ui_back);
                        } else if (!terrain_paint_style.empty()) {
                            terrain_paint_style.clear();
                            status = "TERRAIN PAINT CANCELLED";
                            (void)audio.play(SoundEvent::ui_back);
                        } else if (road_mode) {
                            road_dragging = false;
                            road_mode = false;
                            road_removal_mode = false;
                            status = "ROAD MODE CANCELLED";
                            (void)audio.play(SoundEvent::ui_back);
                        } else if (sidewalk_mode) {
                            sidewalk_dragging = false;
                            sidewalk_mode = false;
                            status = "SIDEWALK MODE CANCELLED";
                            (void)audio.play(SoundEvent::ui_back);
                        } else if (agriculture_mode) {
                            agriculture_mode = false;
                            agriculture_panel_open = false;
                            farming_selection_id.clear();
                            status = "AGRICULTURE MODE CANCELLED";
                            (void)audio.play(SoundEvent::ui_back);
                        } else if (decoration_mode) {
                            decoration_mode = false;
                            status = "DECORATION MODE CANCELLED";
                            (void)audio.play(SoundEvent::ui_back);
                        } else if (!placement_definition_id.empty()) {
                            placement_definition_id.clear();
                            status = "BUILD MODE CANCELLED";
                            (void)audio.play(SoundEvent::ui_back);
                        } else if (selected_instance_id) {
                            selected_instance_id.reset();
                            status = "INFO PANEL CLOSED";
                            (void)audio.play(SoundEvent::ui_close_panel);
                        } else {
                            apply_ui_action({UiAction::toggle_pause, {}});
                        }
                        break;
                    case SDL_SCANCODE_B:
                        open_build_panel();
                        break;
                    case SDL_SCANCODE_V:
                        begin_road_mode();
                        break;
                    case SDL_SCANCODE_R:
                        begin_remove_mode();
                        break;
                    case SDL_SCANCODE_L:
                        begin_land_mode();
                        break;
                    case SDL_SCANCODE_C: begin_sidewalk_mode(); break;
                    case SDL_SCANCODE_G: open_agriculture_panel(); break;
                    case SDL_SCANCODE_Z:
                        rotate_placement(false);
                        break;
                    case SDL_SCANCODE_X:
                        rotate_placement(true);
                        break;
                    case SDL_SCANCODE_SPACE:
                        apply_ui_action({UiAction::toggle_pause, {}});
                        break;
                    case SDL_SCANCODE_F5:
                        (void)save_current_city();
                        break;
                    case SDL_SCANCODE_F9:
                        (void)load_current_city(false);
                        break;
                    case SDL_SCANCODE_F11: {
                        if (!selected_instance_id) {
                            status = "ACTIVITY TEST: SELECT A BUILDING FIRST";
                            break;
                        }
                        const BuildingInstance* selected = buildings.find_by_id(*selected_instance_id);
                        const BuildingDefinition* definition = selected == nullptr ? nullptr : catalog.find(selected->definition_id);
                        const bool overlay = definition != nullptr && definition->activity_overlay && definition->activity_overlay->enabled;
                        const bool attraction = definition != nullptr && definition->animation &&
                            definition->animation->playback == "activity_loop";
                        if (selected == nullptr || (!overlay && !attraction)) {
                            status = "ACTIVITY TEST: SELECT AN ATTRACTION OR OVERLAY BUILDING";
                            break;
                        }
                        const bool was_active = selected->activity_active();
                        if (was_active) {
                            while (true) {
                                const BuildingInstance* current = buildings.find_by_id(*selected_instance_id);
                                if (current == nullptr || !current->activity_active()) break;
                                (void)buildings.end_activity(*selected_instance_id);
                            }
                        } else {
                            (void)buildings.begin_activity(*selected_instance_id);
                        }
                        status = definition->name + std::string(" ACTIVITY TEST: ") + (was_active ? "OFF" : "ON");
                        break;
                    }
                    case SDL_SCANCODE_F10: {
                        // Developer-only, read-only scenario load.  It never overwrites
                        // the player save and exists solely to vet asset geometry before
                        // a new building is accepted into the catalogue.
                        const SaveOperationResult result = save_manager.load(calibration_scenario_path, catalog, economy, simulation_clock,
                                                                            buildings, roads, sidewalks, farming, lands, population,
                                                                            &service_vehicle_catalog, &service_vehicles, &mission_manager);
                        if (result.success) {
                            power.rebuild(buildings, catalog);
                            clear_map_modes();
                            selected_instance_id.reset();
                            simulation_clock.set_speed(SimulationSpeed::paused);
                            last_simulation_ticks = SDL_GetTicks();
                            simulation_scheduler.reset();
                            status = "ISOMETRIC CALIBRATION LOADED - F1 THEN CLICK A BUILDING";
                            (void)audio.play(SoundEvent::ui_confirm);
                        } else {
                            status = "CALIBRATION LOAD FAILED: " + result.message;
                            (void)audio.play(SoundEvent::ui_error);
                        }
                        break;
                    }
                    case SDL_SCANCODE_F1: debug_visible = !debug_visible; break;
                    case SDL_SCANCODE_F2:
                        navigation_debug_uses_roads = !navigation_debug_uses_roads;
                        status = std::string("NAVIGATION DEBUG: ") + (navigation_debug_uses_roads ? "ROAD" : "SIDEWALK");
                        break;
                    case SDL_SCANCODE_F3: {
                        float debug_mouse_x = 0.0F;
                        float debug_mouse_y = 0.0F;
                        SDL_GetMouseState(&debug_mouse_x, &debug_mouse_y);
                        const auto tile = screen_to_tile(debug_mouse_x, debug_mouse_y, camera,
                                                         static_cast<float>(viewport_width), static_cast<float>(viewport_height));
                        const bool navigable = navigation_debug_uses_roads
                            ? roads.is_drivable(tile.first, tile.second)
                            : sidewalks.is_walkable(tile.first, tile.second);
                        if (navigable) {
                            navigation_debug_start = NavigationTile{tile.first, tile.second};
                            status = "NAVIGATION START SET";
                        } else {
                            status = std::string("NAVIGATION START MUST BE ") +
                                     (navigation_debug_uses_roads ? "A ROAD" : "A SIDEWALK");
                        }
                        break;
                    }
                    case SDL_SCANCODE_F4: {
                        float debug_mouse_x = 0.0F;
                        float debug_mouse_y = 0.0F;
                        SDL_GetMouseState(&debug_mouse_x, &debug_mouse_y);
                        const auto tile = screen_to_tile(debug_mouse_x, debug_mouse_y, camera,
                                                         static_cast<float>(viewport_width), static_cast<float>(viewport_height));
                        const bool navigable = navigation_debug_uses_roads
                            ? roads.is_drivable(tile.first, tile.second)
                            : sidewalks.is_walkable(tile.first, tile.second);
                        if (navigable) {
                            navigation_debug_goal = NavigationTile{tile.first, tile.second};
                            status = "NAVIGATION GOAL SET";
                        } else {
                            status = std::string("NAVIGATION GOAL MUST BE ") +
                                     (navigation_debug_uses_roads ? "A ROAD" : "A SIDEWALK");
                        }
                        break;
                    }
                    case SDL_SCANCODE_F6:
                        if (!navigation_debug_start || !navigation_debug_goal) {
                            status = "PEDESTRIAN DEBUG: SET ROAD START (F3) AND GOAL (F4)";
                        } else if (!roads.is_road(navigation_debug_start->x, navigation_debug_start->y) ||
                                   !roads.is_road(navigation_debug_goal->x, navigation_debug_goal->y)) {
                            status = "PEDESTRIAN: START AND GOAL MUST BE ROADS";
                        } else if (pedestrians.send_test_pedestrian(*navigation_debug_start, *navigation_debug_goal,
                                                                     PedestrianLaneNavigationNetwork{roads})) {
                            status = "PEDESTRIAN WALKING ON INTEGRATED ROAD EDGE";
                        } else {
                            status = "PEDESTRIAN: NO ROAD-EDGE PATH";
                        }
                        break;
                    case SDL_SCANCODE_F7:
                        send_mixamo_se_test();
                        break;
                    case SDL_SCANCODE_F8: {
                        const int visual_count = mobile_animations.find_set("visitor_male_01_forge_preview") == nullptr ? 3 :
                            mobile_animations.find_set("visitor_male_01_south_front_candidate") == nullptr ? 4 : 5;
                        pedestrian_visual_index = (pedestrian_visual_index + 1) % visual_count;
                        // Two short walk frames per direction, 220 ms each.
                        // Keep this opt-in candidate slow enough for the feet
                        // to read against world movement.
                        const float preview_speed = pedestrian_visual_index == 4 ? 0.30F : 0.80F;
                        pedestrians.configure_visual_test(pedestrian_visual_preset(preview_speed));
                        status = std::string("PEDESTRIAN LOOK: ") + std::string(pedestrian_visual_label());
                        break;
                    }
                    case SDL_SCANCODE_COMMA:
                        if (debug_visible) {
                            camera.rotation = rotate_camera_counter_clockwise(camera.rotation);
                            status = std::string("DEV CAMERA FACING ") + camera_rotation_label(camera.rotation);
                        }
                        break;
                    case SDL_SCANCODE_PERIOD:
                        if (debug_visible) {
                            camera.rotation = rotate_camera_clockwise(camera.rotation);
                            status = std::string("DEV CAMERA FACING ") + camera_rotation_label(camera.rotation);
                        }
                        break;
                    case SDL_SCANCODE_Q: running = false; break;
                    case SDL_SCANCODE_HOME: camera = {}; break;
                    default: break;
                }
            }
        }

        const Uint64 current_simulation_ticks = SDL_GetTicks();
        const double elapsed_seconds = static_cast<double>(current_simulation_ticks - last_simulation_ticks) / 1000.0;
        last_simulation_ticks = current_simulation_ticks;
        const float frame_seconds = static_cast<float>(elapsed_seconds);
        seagull_seconds += std::min(frame_seconds, 0.050F);
        if (seagull_pass_active) {
            seagull_pass_elapsed += std::min(frame_seconds, 0.050F);
            if (seagull_pass_elapsed >= 10.0F) {
                seagull_pass_active = false;
                // Deterministic, varied pauses: 14, 18, 22, or 26 seconds.
                seagull_next_pass_in = 14.0F + static_cast<float>((seagull_pass_index % 4U) * 4U);
            }
        } else {
            seagull_next_pass_in -= std::min(frame_seconds, 0.050F);
            if (seagull_next_pass_in <= 0.0F) {
                seagull_pass_active = true;
                seagull_pass_elapsed = 0.0F;
                ++seagull_pass_index;
            }
        }
        const bool* keyboard_state = SDL_GetKeyboardState(nullptr);
        float camera_input_x = 0.0F;
        float camera_input_y = 0.0F;
        if (keyboard_state[SDL_SCANCODE_A] || keyboard_state[SDL_SCANCODE_LEFT]) {
            camera_input_x += 1.0F;
        }
        if (keyboard_state[SDL_SCANCODE_D] || keyboard_state[SDL_SCANCODE_RIGHT]) {
            camera_input_x -= 1.0F;
        }
        if (keyboard_state[SDL_SCANCODE_W] || keyboard_state[SDL_SCANCODE_UP]) {
            camera_input_y += 1.0F;
        }
        if (keyboard_state[SDL_SCANCODE_S] || keyboard_state[SDL_SCANCODE_DOWN]) {
            camera_input_y -= 1.0F;
        }

        float pan_speed = kCameraKeyboardPanSpeed;
        float mouse_pan_x = 0.0F;
        float mouse_pan_y = 0.0F;
        SDL_GetMouseState(&mouse_pan_x, &mouse_pan_y);
        if (!camera_dragging && !gameplay_ui.consumes_point(mouse_pan_x, mouse_pan_y)) {
            if (mouse_pan_x < kCameraEdgePanBand) {
                camera_input_x += (kCameraEdgePanBand - mouse_pan_x) / kCameraEdgePanBand;
            } else if (mouse_pan_x > static_cast<float>(viewport_width) - kCameraEdgePanBand) {
                camera_input_x -= (mouse_pan_x - (static_cast<float>(viewport_width) - kCameraEdgePanBand)) / kCameraEdgePanBand;
            }
            if (mouse_pan_y < kCameraEdgePanBand) {
                camera_input_y += (kCameraEdgePanBand - mouse_pan_y) / kCameraEdgePanBand;
            } else if (mouse_pan_y > static_cast<float>(viewport_height) - kCameraEdgePanBand) {
                camera_input_y -= (mouse_pan_y - (static_cast<float>(viewport_height) - kCameraEdgePanBand)) / kCameraEdgePanBand;
            }
            pan_speed = kCameraEdgePanSpeed;
        }
        const float camera_input_length = std::sqrt(camera_input_x * camera_input_x + camera_input_y * camera_input_y);
        if (camera_input_length > 1.0F) {
            camera_input_x /= camera_input_length;
            camera_input_y /= camera_input_length;
        }
        const float camera_delta_seconds = std::min(frame_seconds, 0.050F);
        const float camera_blend = 1.0F - std::exp(-kCameraPanResponsiveness * camera_delta_seconds);
        const float target_velocity_x = camera_input_x * pan_speed;
        const float target_velocity_y = camera_input_y * pan_speed;
        camera.pan_velocity_x += (target_velocity_x - camera.pan_velocity_x) * camera_blend;
        camera.pan_velocity_y += (target_velocity_y - camera.pan_velocity_y) * camera_blend;
        camera.pan_x += camera.pan_velocity_x * camera_delta_seconds;
        camera.pan_y += camera.pan_velocity_y * camera_delta_seconds;
        clamp_camera_to_owned_land(camera, lands, static_cast<float>(viewport_width), static_cast<float>(viewport_height));
        const SimulationAdvance time_advance = simulation_clock.advance_seconds(elapsed_seconds);
        const SimulationScheduleAdvance scheduled = simulation_scheduler.advance_frame(frame_seconds);
        for (std::uint32_t tick = 0; tick < scheduled.mobile_ticks; ++tick) {
            service_vehicles.update_tick(scheduled.mobile_tick_seconds, service_vehicle_catalog, vehicle_traversable);
            pedestrians.update_tick(scheduled.mobile_tick_seconds, PedestrianLaneNavigationNetwork{roads});
        }
        for (const TileCoordinate& completed : service_vehicles.take_completed_tiles()) {
            (void)farming.prepare_soil(completed.x, completed.y);
        }
        service_vehicles.interpolate_visual(frame_seconds);
        service_vehicles.update_animation(frame_seconds, mobile_animations);
        pedestrians.interpolate_visual(frame_seconds);
        pedestrians.update_animation(frame_seconds, mobile_animations);
        if (time_advance.days_advanced > 0) {
            farming.on_day_changed(simulation_clock.date(), crop_catalog);
        }
        for (const GameDate& closing_date : time_advance.closed_months) {
            const std::int32_t net_pop_change = population.on_month_closed(buildings, catalog, &power, &roads);
            economy.on_month_closed(buildings, catalog, population, closing_date, &service_vehicle_catalog, &service_vehicles, &farming);
            status = "MONTH CLOSED: " + format_balance(economy.monthly_summary().balance) + " NET | POP " +
                (net_pop_change >= 0 ? "+" : "") + std::to_string(net_pop_change);
            if (mission_manager.check_and_auto_complete_clean_energy(economy, buildings, catalog, population, power)) {
                status = "MISSAO ENERGIA LIMPA CONCLUIDA! Hidreletrica Reativada!";
                (void)audio.play(SoundEvent::ui_confirm);
            }
            if (mission_manager.check_and_auto_complete_city_water(economy, buildings, catalog, population)) {
                status = "AGUA PARA A CIDADE CONCLUIDA! Estacao Municipal de Captacao Reativada!";
                (void)audio.play(SoundEvent::ui_confirm);
            }
        }

        float mouse_x = 0.0F;
        float mouse_y = 0.0F;
        SDL_GetMouseState(&mouse_x, &mouse_y);
        const auto raw_mouse_tile = screen_to_tile(mouse_x, mouse_y, camera, static_cast<float>(viewport_width), static_cast<float>(viewport_height));
        const auto mouse_tile = land_mode ? raw_mouse_tile : nearest_owned_tile(raw_mouse_tile, lands);
        const BuildingInstance* hovered_instance = buildings.instance_at(mouse_tile.first, mouse_tile.second);
        const BuildingDefinition* placement_definition = placement_definition_id.empty() ? nullptr : catalog.find(placement_definition_id);
        const BuildingPlacementValidation placement_validation = placement_definition == nullptr
            ? BuildingPlacementValidation{}
            : validate_building_placement(*placement_definition, placement_rotation, mouse_tile.first, mouse_tile.second,
                                          buildings, roads, lands, sidewalks, farming, economy, power, active_map_doc ? &*active_map_doc : nullptr);
        const std::vector<TileCoordinate> road_preview = road_mode && !road_removal_mode
            ? roads.line_between(road_dragging ? road_drag_start : TileCoordinate{mouse_tile.first, mouse_tile.second},
                                 {mouse_tile.first, mouse_tile.second})
            : std::vector<TileCoordinate>{};
        const std::vector<TileCoordinate> sidewalk_preview = sidewalk_mode
            ? roads.line_between(sidewalk_dragging ? sidewalk_drag_start : TileCoordinate{mouse_tile.first, mouse_tile.second},
                                 {mouse_tile.first, mouse_tile.second})
            : std::vector<TileCoordinate>{};
        const bool road_preview_on_owned_land = road_mode && !road_removal_mode && road_segment_is_on_owned_land(road_preview, lands);
        const bool road_preview_valid = road_mode && (road_removal_mode
            ? roads.is_road(mouse_tile.first, mouse_tile.second)
            : road_segment_is_valid(road_preview, roads, buildings) &&
              road_preview_on_owned_land &&
              economy.can_afford(static_cast<std::int64_t>(road_preview.size()) * kRoadCostPerTile));
        std::optional<NavigationPathResult> navigation_debug_path;
        if (debug_visible && navigation_debug_start && navigation_debug_goal) {
            if (navigation_debug_uses_roads) {
                navigation_debug_path = find_navigation_path(RoadNavigationNetwork{roads}, *navigation_debug_start, *navigation_debug_goal);
            } else {
                navigation_debug_path = find_navigation_path(SidewalkNavigationNetwork{sidewalks}, *navigation_debug_start, *navigation_debug_goal);
            }
        }
        if (active_map_doc.has_value()) {
            const ch::CameraState cs{camera.pan_x, camera.pan_y, camera.zoom, static_cast<ch::CameraRotation>(camera.rotation)};
            ch::MapRenderer::render_world_terrain_and_water(
                renderer,
                *active_map_doc,
                [&textures, &asset_root](const std::filesystem::path& p) {
                    return textures.find(p.is_absolute() ? p : asset_root / p);
                },
                asset_root,
                cs,
                static_cast<float>(viewport_width),
                static_cast<float>(viewport_height)
            );
        } else {
            render_map(renderer, grass, scenario_terrain_textures, camera, static_cast<float>(viewport_width), static_cast<float>(viewport_height));
        }
        const LandParcel* hovered_parcel = lands.parcel_at(mouse_tile.first, mouse_tile.second);
        render_land_overlays(renderer, lands, hovered_parcel, land_mode, camera,
                             static_cast<float>(viewport_width), static_cast<float>(viewport_height));
        render_roads(renderer, roads, road_visuals, textures, asset_root, camera,
                     static_cast<float>(viewport_width), static_cast<float>(viewport_height));
        render_sidewalks(renderer, sidewalks, textures, asset_root, camera, static_cast<float>(viewport_width), static_cast<float>(viewport_height));
        render_farming(renderer, farming, crop_catalog, textures, asset_root, camera,
                       static_cast<float>(viewport_width), static_cast<float>(viewport_height));

        if (road_mode) {
            const SDL_FColor preview_color = road_preview_valid
                ? (road_removal_mode ? SDL_FColor{0.94F, 0.68F, 0.20F, 0.72F} : SDL_FColor{0.34F, 0.78F, 0.52F, 0.62F})
                : SDL_FColor{0.92F, 0.25F, 0.22F, 0.62F};
            if (road_removal_mode) {
                render_road_tile(renderer, mouse_tile.first, mouse_tile.second, camera, static_cast<float>(viewport_width),
                                 static_cast<float>(viewport_height), preview_color);
            } else {
                for (const TileCoordinate& tile : road_preview) {
                    render_road_tile(renderer, tile.x, tile.y, camera, static_cast<float>(viewport_width),
                                     static_cast<float>(viewport_height), preview_color);
                }
            }
        }
        if (sidewalk_mode) {
            for (const TileCoordinate& tile : sidewalk_preview) {
                const bool valid = lands.is_tile_owned(tile.x, tile.y) &&
                    sidewalks.validate_placement(tile.x, tile.y, roads, buildings) == SidewalkPlacementFailure::none &&
                    !farming.is_occupied(tile.x, tile.y);
                SDL_SetRenderDrawColor(renderer, valid ? 112 : 245, valid ? 232 : 82, 96, SDL_ALPHA_OPAQUE);
                render_tile_outline(renderer, tile.x, tile.y, camera,
                                    static_cast<float>(viewport_width), static_cast<float>(viewport_height));
            }
        }

        if (placement_definition != nullptr) {
            const bool valid_preview = placement_validation.valid();
            render_footprint_outline(renderer, *placement_definition, placement_rotation, mouse_tile.first, mouse_tile.second, camera,
                                     static_cast<float>(viewport_width), static_cast<float>(viewport_height),
                                      valid_preview ? 116 : 255, valid_preview ? 238 : 90, 90);
            if (debug_visible) {
                render_road_access_candidates(renderer, *placement_definition, placement_rotation, mouse_tile.first, mouse_tile.second,
                                              roads, camera, static_cast<float>(viewport_width), static_cast<float>(viewport_height));
            }
        }
        if (agriculture_mode) {
            const auto render_farming_preview = [&](const int x, const int y) {
                const FarmTile* farm_tile = farming.tile_at(x, y);
                bool valid = false;
                if (farming_selection_id == "harvest_tool") {
                    valid = farm_tile != nullptr && farm_tile->state == FarmTileState::ready_to_harvest;
                } else if (farming_selection_id == "prepared_soil_01") {
                    valid = lands.is_tile_owned(x, y) && !roads.is_road(x, y) && !sidewalks.is_sidewalk(x, y) &&
                        !buildings.is_occupied(x, y) && !farming.is_occupied(x, y);
                } else if (crop_catalog.find(farming_selection_id) != nullptr) {
                    valid = farm_tile != nullptr && farm_tile->state == FarmTileState::prepared_soil;
                }
                SDL_SetRenderDrawColor(renderer, valid ? 112 : 245, valid ? 232 : 82, 96, SDL_ALPHA_OPAQUE);
                render_tile_outline(renderer, x, y, camera, static_cast<float>(viewport_width), static_cast<float>(viewport_height));
            };
            const TileCoordinate* drag_start = planting_dragging ? &planting_drag_start :
                (harvest_dragging ? &harvest_drag_start : nullptr);
            if (drag_start != nullptr) {
                const int min_x = std::min(drag_start->x, mouse_tile.first);
                const int max_x = std::max(drag_start->x, mouse_tile.first);
                const int min_y = std::min(drag_start->y, mouse_tile.second);
                const int max_y = std::max(drag_start->y, mouse_tile.second);
                for (int y = min_y; y <= max_y; ++y) {
                    for (int x = min_x; x <= max_x; ++x) render_farming_preview(x, y);
                }
            } else {
                render_farming_preview(mouse_tile.first, mouse_tile.second);
            }
        }

        const std::vector<MobileEntityRenderData> mobile_entities = mobile_render_entities();
        render_world_entities(renderer, buildings, catalog, lands, mobile_entities, mobile_animations, textures,
                              asset_root, camera, static_cast<float>(viewport_width), static_cast<float>(viewport_height));
        if (seagull_pass_active) {
            const OwnedTileBounds bounds = owned_tile_bounds(lands);
            const bool southbound = (seagull_pass_index % 2U) == 0U;
            const float route_progress = seagull_pass_elapsed / 10.0F;
            const float route_x = southbound
                ? static_cast<float>(bounds.min_x) + 0.68F * static_cast<float>(bounds.max_x - bounds.min_x)
                : static_cast<float>(bounds.min_x) + 0.32F * static_cast<float>(bounds.max_x - bounds.min_x);
            const float north_edge = static_cast<float>(bounds.min_y) - 4.0F;
            const float south_edge = static_cast<float>(bounds.max_y) + 4.0F;
            if (southbound) {
                render_seagull_south(renderer, textures, asset_root, seagull_seconds, route_x, north_edge, south_edge,
                                     route_progress, camera, static_cast<float>(viewport_width), static_cast<float>(viewport_height));
            } else {
                render_seagull_north(renderer, textures, asset_root, seagull_seconds, route_x, south_edge, north_edge,
                                     route_progress, camera, static_cast<float>(viewport_width), static_cast<float>(viewport_height));
            }
        }
        if (navigation_debug_path) {
            render_navigation_debug_path(renderer, *navigation_debug_path, camera,
                                         static_cast<float>(viewport_width), static_cast<float>(viewport_height));
        }

        if (placement_definition != nullptr) {
            const BuildingRotation visual_rotation = camera_visual_rotation(*placement_definition, placement_rotation, camera.rotation);
            if (const TextureAsset* preview_texture = textures.find(asset_root / placement_definition->texture_path_for(visual_rotation))) {
                BuildingInstance preview;
                preview.definition_id = placement_definition->id;
                preview.tile_x = mouse_tile.first;
                preview.tile_y = mouse_tile.second;
                preview.rotation = placement_rotation;
                render_building(renderer, *placement_definition, preview, visual_rotation, *preview_texture, camera,
                                static_cast<float>(viewport_width), static_cast<float>(viewport_height), 115);
            }
        }

        if (hovered_instance != nullptr) {
            if (const BuildingDefinition* definition = catalog.find(hovered_instance->definition_id)) {
                render_footprint_outline(renderer, *definition, hovered_instance->rotation, hovered_instance->tile_x, hovered_instance->tile_y, camera,
                                         static_cast<float>(viewport_width), static_cast<float>(viewport_height), 92, 206, 255);
            }
        }
        if (selected_instance_id) {
            if (const BuildingInstance* selected = buildings.find_by_id(*selected_instance_id)) {
                if (const BuildingDefinition* definition = catalog.find(selected->definition_id)) {
                    render_footprint_outline(renderer, *definition, selected->rotation, selected->tile_x, selected->tile_y, camera,
                                             static_cast<float>(viewport_width), static_cast<float>(viewport_height), 255, 208, 92);
                    if (debug_visible) {
                        const BuildingRotation visual_rotation = camera_visual_rotation(*definition, selected->rotation, camera.rotation);
                        if (const TextureAsset* texture = textures.find(asset_root / definition->texture_path_for(visual_rotation, selected->current_level))) {
                            render_building_calibration_debug(renderer, *definition, *selected, visual_rotation, *texture, roads, camera,
                                                              static_cast<float>(viewport_width), static_cast<float>(viewport_height));
                        }
                    }
                }
            }
        }

        gameplay_ui.update_layout(viewport_width, viewport_height, make_ui_model(mouse_tile));
        gameplay_ui.render(renderer);
        SDL_RenderPresent(renderer);
    }

    audio.shutdown();
    gameplay_ui.release_renderer_resources();
    textures.clear();
    SDL_DestroyRenderer(renderer);
    SDL_DestroyWindow(window);
    SDL_Quit();
    return 0;
}
