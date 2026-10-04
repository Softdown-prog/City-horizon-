#include <SDL3/SDL.h>

#include "src/ch_core/contracts.h"
#include "src/ch_core/grid.h"
#include "src/ch_core/projection.h"
#include "src/ch_core/map_document.h"
#include "src/ch_core/terrain_heightfield.h"
#include "src/ch_core/terrain_projection.h"
#include "src/ch_core/terrain_semantics_catalog.h"
#include "src/ch_core/validation.h"
#include "src/ch_render/map_renderer.h"

#include "audio_manager.h"
#include "building_system.h"
#include "coaster_runtime.h"
#include "coaster_sdl_renderer.h"
#include "crosswalk_runtime.h"
#include "economy_system.h"
#include "money_spend_fx.h"
#include "farming_system.h"
#include "land_system.h"
#include "map_tile_occupancy.h"
#include "mission_system.h"
#include "mobile_animation.h"
#include "navigation_network.h"
#include "pedestrian_decision.h"
#include "pedestrian_system.h"
#include "park_fence_runtime.h"
#include "population_system.h"
#include "power_system.h"
#include "ride_runtime_registry.h"
#include "road_system.h"
#include "road_visual_catalog.h"
#include "resource_system.h"
#include "save_manager.h"
#include "simulation_clock.h"
#include "simulation_scheduler.h"
#include "sidewalk_system.h"
#include "tool_cursor.h"
#include "ui_manager.h"
#include "vehicle_system.h"
#include "weather_system.h"

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

void render_weather(SDL_Renderer* renderer, const WeatherSystem& weather, const int width, const int height) {
    if (weather.tint_alpha() == 0) return;
    SDL_SetRenderDrawBlendMode(renderer, SDL_BLENDMODE_BLEND);
    SDL_SetRenderDrawColor(renderer, 25, 37, 57, weather.tint_alpha());
    const SDL_FRect viewport{0.0F, 0.0F, static_cast<float>(width), static_cast<float>(height)};
    SDL_RenderFillRect(renderer, &viewport);
    if (weather.is_raining()) {
        SDL_SetRenderDrawColor(renderer, 205, 222, 243, weather.state() == WeatherState::thunderstorm ? 110 : 84);
        const std::size_t count = weather.state() == WeatherState::thunderstorm ? weather.drops().size() : 180U;
        for (std::size_t i = 0; i < count; ++i) {
            const RainDrop& drop = weather.drops()[i];
            SDL_RenderLine(renderer, drop.x + drop.length * 0.18F, drop.y - drop.length,
                           drop.x, drop.y);
        }
    }
    if (weather.flash_alpha() != 0) {
        SDL_SetRenderDrawColor(renderer, 235, 242, 255, weather.flash_alpha());
        SDL_RenderFillRect(renderer, &viewport);
    }
}

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

    // Recolor a chosen actor frame once and cache it for the resident's outfit.
    // Writing the original alpha directly avoids doubled fringe opacity from
    // drawing translucent overlays over an already antialiased sprite.
    [[nodiscard]] const TextureAsset* load_actor_clothing(SDL_Renderer* renderer,
                                                           const std::filesystem::path& frame_path,
                                                           const MobileClothingTint& clothing) {
        const std::string key = frame_path.generic_string() + "#CH_ACTOR_CLOTHING_" +
            std::to_string(clothing.jacket.r) + ":" + std::to_string(clothing.jacket.g) + ":" +
            std::to_string(clothing.jacket.b) + ":" + std::to_string(clothing.pants.r) + ":" +
            std::to_string(clothing.pants.g) + ":" + std::to_string(clothing.pants.b);
        if (const auto existing = textures_.find(key); existing != textures_.end()) return &existing->second;

        const std::filesystem::path mask_path = frame_path.parent_path().parent_path() / "masks" / frame_path.filename();
        SDL_Surface* frame = SDL_LoadPNG(frame_path.string().c_str());
        SDL_Surface* mask = SDL_LoadPNG(mask_path.string().c_str());
        if (frame == nullptr || mask == nullptr || frame->w != mask->w || frame->h != mask->h) {
            if (frame != nullptr) SDL_DestroySurface(frame);
            if (mask != nullptr) SDL_DestroySurface(mask);
            return nullptr; // Preserve the approved frame when a mask is absent.
        }
        SDL_Surface* result = SDL_CreateSurface(frame->w, frame->h, SDL_PIXELFORMAT_RGBA32);
        if (result == nullptr) {
            SDL_DestroySurface(mask);
            SDL_DestroySurface(frame);
            return nullptr;
        }
        for (int y = 0; y < frame->h; ++y) {
            for (int x = 0; x < frame->w; ++x) {
                Uint8 r = 0, g = 0, b = 0, a = 0;
                Uint8 jacket = 0, pants = 0, shade = 0, mask_alpha = 0;
                (void)SDL_ReadSurfacePixel(frame, x, y, &r, &g, &b, &a);
                (void)SDL_ReadSurfacePixel(mask, x, y, &jacket, &pants, &shade, &mask_alpha);
                const MobileClothingColor* tint = mask_alpha == a && jacket == 255 && pants == 0 ? &clothing.jacket :
                    mask_alpha == a && pants == 255 && jacket == 0 ? &clothing.pants : nullptr;
                if (tint != nullptr) {
                    r = static_cast<Uint8>((static_cast<unsigned>(tint->r) * shade + 127U) / 255U);
                    g = static_cast<Uint8>((static_cast<unsigned>(tint->g) * shade + 127U) / 255U);
                    b = static_cast<Uint8>((static_cast<unsigned>(tint->b) * shade + 127U) / 255U);
                }
                (void)SDL_WriteSurfacePixel(result, x, y, r, g, b, a);
            }
        }
        TextureAsset asset;
        asset.texture = SDL_CreateTextureFromSurface(renderer, result);
        asset.source_width = static_cast<float>(result->w);
        asset.source_height = static_cast<float>(result->h);
        SDL_DestroySurface(result);
        SDL_DestroySurface(mask);
        SDL_DestroySurface(frame);
        if (asset.texture == nullptr) return nullptr;
        SDL_SetTextureBlendMode(asset.texture, SDL_BLENDMODE_BLEND);
        SDL_SetTextureScaleMode(asset.texture, SDL_SCALEMODE_LINEAR);
        return &textures_.emplace(key, asset).first->second;
    }

    // Pair a frame-aligned umbrella overlay with its R/shade mask. Cache the
    // composed texture by color, keeping the authored silhouette and alpha.
    [[nodiscard]] const TextureAsset* load_actor_umbrella(SDL_Renderer* renderer,
                                                           const std::filesystem::path& frame_path,
                                                           const MobileClothingColor& fabric) {
        const std::filesystem::path umbrella_root = frame_path.parent_path().parent_path() / "umbrella";
        const std::filesystem::path overlay_path = umbrella_root / "frames" / frame_path.filename();
        const std::string key = overlay_path.generic_string() + "#CH_UMBRELLA_" +
            std::to_string(fabric.r) + ":" + std::to_string(fabric.g) + ":" + std::to_string(fabric.b);
        if (const auto existing = textures_.find(key); existing != textures_.end()) return &existing->second;
        SDL_Surface* overlay = SDL_LoadPNG(overlay_path.string().c_str());
        SDL_Surface* mask = SDL_LoadPNG((umbrella_root / "masks" / frame_path.filename()).string().c_str());
        if (overlay == nullptr || mask == nullptr || overlay->w != mask->w || overlay->h != mask->h) {
            if (overlay != nullptr) SDL_DestroySurface(overlay);
            if (mask != nullptr) SDL_DestroySurface(mask);
            return nullptr;
        }
        SDL_Surface* result = SDL_CreateSurface(overlay->w, overlay->h, SDL_PIXELFORMAT_RGBA32);
        if (result == nullptr) {
            SDL_DestroySurface(mask);
            SDL_DestroySurface(overlay);
            return nullptr;
        }
        for (int y = 0; y < overlay->h; ++y) {
            for (int x = 0; x < overlay->w; ++x) {
                Uint8 r = 0, g = 0, b = 0, a = 0;
                Uint8 selected = 0, unused = 0, shade = 0, mask_alpha = 0;
                (void)SDL_ReadSurfacePixel(overlay, x, y, &r, &g, &b, &a);
                (void)SDL_ReadSurfacePixel(mask, x, y, &selected, &unused, &shade, &mask_alpha);
                if (selected == 255 && mask_alpha == a && a != 0) {
                    r = static_cast<Uint8>((static_cast<unsigned>(fabric.r) * shade + 127U) / 255U);
                    g = static_cast<Uint8>((static_cast<unsigned>(fabric.g) * shade + 127U) / 255U);
                    b = static_cast<Uint8>((static_cast<unsigned>(fabric.b) * shade + 127U) / 255U);
                }
                (void)SDL_WriteSurfacePixel(result, x, y, r, g, b, a);
            }
        }
        TextureAsset asset;
        asset.texture = SDL_CreateTextureFromSurface(renderer, result);
        asset.source_width = static_cast<float>(result->w);
        asset.source_height = static_cast<float>(result->h);
        SDL_DestroySurface(result);
        SDL_DestroySurface(mask);
        SDL_DestroySurface(overlay);
        if (asset.texture == nullptr) return nullptr;
        SDL_SetTextureBlendMode(asset.texture, SDL_BLENDMODE_BLEND);
        SDL_SetTextureScaleMode(asset.texture, SDL_SCALEMODE_LINEAR);
        return &textures_.emplace(key, asset).first->second;
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
    const CameraWorldPoint view_center = camera_view_point(center.x, center.y, camera.rotation);
    camera.pan_x = -(view_center.x - view_center.y) * (kTileWidth * 0.5F) * camera.zoom;
    camera.pan_y = -(view_center.x + view_center.y) * (kTileHeight * 0.5F) * camera.zoom;
}

void draw_text(SDL_Renderer* renderer, float x, float y, const std::string& text, Uint8 red = 238, Uint8 green = 242, Uint8 blue = 244, Uint8 alpha = SDL_ALPHA_OPAQUE);
void draw_panel(SDL_Renderer* renderer, float x, float y, float width, float height, Uint8 alpha = 210);

void render_loading_screen(SDL_Renderer* renderer, const int viewport_width, const int viewport_height,
                           const float progress, const std::string& stage) {
    SDL_SetRenderDrawColor(renderer, 12, 18, 28, SDL_ALPHA_OPAQUE);
    SDL_RenderClear(renderer);
    const float panel_w = std::min(520.0F, static_cast<float>(viewport_width) * 0.72F);
    const float panel_h = 118.0F;
    const float panel_x = (static_cast<float>(viewport_width) - panel_w) * 0.5F;
    const float panel_y = (static_cast<float>(viewport_height) - panel_h) * 0.5F;
    draw_panel(renderer, panel_x, panel_y, panel_w, panel_h, 235);
    draw_text(renderer, panel_x + 18.0F, panel_y + 18.0F, "CITY HORIZON");
    draw_text(renderer, panel_x + 18.0F, panel_y + 40.0F, stage, 185, 204, 224);
    const SDL_FRect track{panel_x + 18.0F, panel_y + 76.0F, panel_w - 36.0F, 14.0F};
    SDL_SetRenderDrawColor(renderer, 40, 52, 66, SDL_ALPHA_OPAQUE);
    SDL_RenderFillRect(renderer, &track);
    SDL_FRect fill = track;
    fill.w *= std::clamp(progress, 0.0F, 1.0F);
    SDL_SetRenderDrawColor(renderer, 92, 190, 126, SDL_ALPHA_OPAQUE);
    SDL_RenderFillRect(renderer, &fill);
}

void draw_glyph(SDL_Renderer* renderer, float x, float y, const char character, Uint8 red, Uint8 green, Uint8 blue, Uint8 alpha) {
    static const std::unordered_map<char, std::array<std::uint8_t, 7>> font = {
        {'A',{0b01110,0b10001,0b10001,0b11111,0b10001,0b10001,0b10001}},
        {'B',{0b11110,0b10001,0b10001,0b11110,0b10001,0b10001,0b11110}},
        {'C',{0b01111,0b10000,0b10000,0b10000,0b10000,0b10000,0b01111}},
        {'D',{0b11110,0b10001,0b10001,0b10001,0b10001,0b10001,0b11110}},
        {'E',{0b11111,0b10000,0b10000,0b11110,0b10000,0b10000,0b11111}},
        {'F',{0b11111,0b10000,0b10000,0b11110,0b10000,0b10000,0b10000}},
        {'G',{0b01111,0b10000,0b10000,0b10111,0b10001,0b10001,0b01111}},
        {'H',{0b10001,0b10001,0b10001,0b11111,0b10001,0b10001,0b10001}},
        {'I',{0b11111,0b00100,0b00100,0b00100,0b00100,0b00100,0b11111}},
        {'J',{0b00111,0b00010,0b00010,0b00010,0b10010,0b10010,0b01100}},
        {'K',{0b10001,0b10010,0b10100,0b11000,0b10100,0b10010,0b10001}},
        {'L',{0b10000,0b10000,0b10000,0b10000,0b10000,0b10000,0b11111}},
        {'M',{0b10001,0b11011,0b10101,0b10101,0b10001,0b10001,0b10001}},
        {'N',{0b10001,0b11001,0b10101,0b10011,0b10001,0b10001,0b10001}},
        {'O',{0b01110,0b10001,0b10001,0b10001,0b10001,0b10001,0b01110}},
        {'P',{0b11110,0b10001,0b10001,0b11110,0b10000,0b10000,0b10000}},
        {'Q',{0b01110,0b10001,0b10001,0b10001,0b10101,0b10010,0b01101}},
        {'R',{0b11110,0b10001,0b10001,0b11110,0b10100,0b10010,0b10001}},
        {'S',{0b01111,0b10000,0b10000,0b01110,0b00001,0b00001,0b11110}},
        {'T',{0b11111,0b00100,0b00100,0b00100,0b00100,0b00100,0b00100}},
        {'U',{0b10001,0b10001,0b10001,0b10001,0b10001,0b10001,0b01110}},
        {'V',{0b10001,0b10001,0b10001,0b10001,0b10001,0b01010,0b00100}},
        {'W',{0b10001,0b10001,0b10001,0b10101,0b10101,0b11011,0b10001}},
        {'X',{0b10001,0b10001,0b01010,0b00100,0b01010,0b10001,0b10001}},
        {'Y',{0b10001,0b10001,0b01010,0b00100,0b00100,0b00100,0b00100}},
        {'Z',{0b11111,0b00001,0b00010,0b00100,0b01000,0b10000,0b11111}},
        {'0',{0b01110,0b10001,0b10011,0b10101,0b11001,0b10001,0b01110}},
        {'1',{0b00100,0b01100,0b00100,0b00100,0b00100,0b00100,0b01110}},
        {'2',{0b01110,0b10001,0b00001,0b00010,0b00100,0b01000,0b11111}},
        {'3',{0b11110,0b00001,0b00001,0b01110,0b00001,0b00001,0b11110}},
        {'4',{0b00010,0b00110,0b01010,0b10010,0b11111,0b00010,0b00010}},
        {'5',{0b11111,0b10000,0b10000,0b11110,0b00001,0b00001,0b11110}},
        {'6',{0b01110,0b10000,0b10000,0b11110,0b10001,0b10001,0b01110}},
        {'7',{0b11111,0b00001,0b00010,0b00100,0b01000,0b01000,0b01000}},
        {'8',{0b01110,0b10001,0b10001,0b01110,0b10001,0b10001,0b01110}},
        {'9',{0b01110,0b10001,0b10001,0b01111,0b00001,0b00001,0b01110}},
        {'-',{0,0,0,0b11111,0,0,0}}, {'+',{0,0b00100,0b00100,0b11111,0b00100,0b00100,0}},
        {'/',{0b00001,0b00010,0b00100,0b01000,0b10000,0,0}},
        {'.',{0,0,0,0,0,0b00100,0b00100}}, {':',{0,0b00100,0b00100,0,0b00100,0b00100,0}},
        {',',{0,0,0,0,0,0b00100,0b01000}}, {'(',{0b00010,0b00100,0b01000,0b01000,0b01000,0b00100,0b00010}},
        {')',{0b01000,0b00100,0b00010,0b00010,0b00010,0b00100,0b01000}},
        {'|',{0b00100,0b00100,0b00100,0b00100,0b00100,0b00100,0b00100}}, {' ',{0,0,0,0,0,0,0}}
    };
    const char glyph = static_cast<char>(std::toupper(static_cast<unsigned char>(character)));
    const auto found = font.find(glyph);
    if (found == font.end()) return;
    SDL_SetRenderDrawColor(renderer, red, green, blue, alpha);
    constexpr float scale = 2.0F;
    for (int row = 0; row < 7; ++row) {
        for (int column = 0; column < 5; ++column) {
            if ((found->second[row] & (1U << (4 - column))) == 0) continue;
            const SDL_FRect pixel = {x + column * scale, y + row * scale, scale, scale};
            SDL_RenderFillRect(renderer, &pixel);
        }
    }
}

void draw_text(SDL_Renderer* renderer, float x, float y, const std::string& text, Uint8 red, Uint8 green, Uint8 blue, Uint8 alpha) {
    float cursor = x;
    for (const char character : text) {
        draw_glyph(renderer, cursor, y, character, red, green, blue, alpha);
        cursor += 12.0F;
    }
}

void draw_panel(SDL_Renderer* renderer, float x, float y, float width, float height, Uint8 alpha) {
    SDL_SetRenderDrawBlendMode(renderer, SDL_BLENDMODE_BLEND);
    SDL_SetRenderDrawColor(renderer, 12, 18, 28, alpha);
    const SDL_FRect panel = {x, y, width, height};
    SDL_RenderFillRect(renderer, &panel);
    SDL_SetRenderDrawColor(renderer, 68, 82, 98, alpha);
    SDL_RenderRect(renderer, &panel);
}

[[nodiscard]] ch::MapRenderer::VisibleTileBounds visible_tile_bounds(const Camera& camera, const float viewport_width,
                                                                      const float viewport_height, const float padding_tiles = 2.0F) {
    const ch::CameraState cs{camera.pan_x, camera.pan_y, camera.zoom, static_cast<ch::CameraRotation>(camera.rotation)};
    return ch::MapRenderer::visible_tile_bounds(cs, viewport_width, viewport_height, padding_tiles);
}

void render_diamond_tile(SDL_Renderer* renderer, int tile_x, int tile_y, const Camera& camera, float viewport_width, float viewport_height,
                         Uint8 red, Uint8 green, Uint8 blue, Uint8 alpha = SDL_ALPHA_OPAQUE) {
    const CameraWorldPoint visual = tile_visual_top_world(tile_x, tile_y, camera.rotation);
    const SDL_FPoint top = world_to_screen(visual.x, visual.y, camera, viewport_width, viewport_height);
    const SDL_FPoint right = {top.x + kTileWidth * 0.5F * camera.zoom, top.y + kTileHeight * 0.5F * camera.zoom};
    const SDL_FPoint bottom = {top.x, top.y + kTileHeight * camera.zoom};
    const SDL_FPoint left = {top.x - kTileWidth * 0.5F * camera.zoom, top.y + kTileHeight * 0.5F * camera.zoom};
    SDL_SetRenderDrawBlendMode(renderer, SDL_BLENDMODE_BLEND);
    SDL_SetRenderDrawColor(renderer, red, green, blue, alpha);
    const float height = bottom.y - top.y;
    for (int row = 0; row <= static_cast<int>(height); ++row) {
        const float t = height > 0.0F ? std::abs((row / height) - 0.5F) * 2.0F : 1.0F;
        const float half = kTileWidth * 0.5F * camera.zoom * (1.0F - t);
        SDL_RenderLine(renderer, top.x - half, top.y + row, top.x + half, top.y + row);
    }
}

void render_map(SDL_Renderer* renderer, const TextureAsset* grass,
                const std::unordered_map<std::string, const TextureAsset*>& terrain_textures,
                const Camera& camera, float viewport_width, float viewport_height) {
    for (const auto& [terrain_id, texture] : terrain_textures) {
        (void)terrain_id;
        (void)texture;
    }
    if (grass == nullptr) {
        SDL_SetRenderDrawBlendMode(renderer, SDL_BLENDMODE_BLEND);
        for (int y = kMapMin; y <= kMapMax; ++y) {
            for (int x = kMapMin; x <= kMapMax; ++x) {
                render_diamond_tile(renderer, x, y, camera, viewport_width, viewport_height, 93, 132, 74, SDL_ALPHA_OPAQUE);
            }
        }
        return;
    }
    const ch::CameraState cs{camera.pan_x, camera.pan_y, camera.zoom, static_cast<ch::CameraRotation>(camera.rotation)};
    for (int y = kMapMin; y <= kMapMax; ++y) {
        for (int x = kMapMin; x <= kMapMax; ++x) {
            ch::MapRenderer::render_terrain_tile(renderer, *grass, x, y, cs, viewport_width, viewport_height,
                                                 kGrassOpaqueLeft, kGrassOpaqueTop, kGrassOpaqueWidth, false);
        }
    }
}

void render_land_overlays(SDL_Renderer* renderer, const LandManager& lands, const LandParcel* hovered, bool land_mode,
                          const Camera& camera, float viewport_width, float viewport_height,
                          const ch::MapDocument* document = nullptr) {
    for (const LandParcel& parcel : lands.parcels()) {
        const bool highlighted = land_mode && hovered != nullptr && parcel.id == hovered->id;
        const bool purchasable = lands.can_purchase_parcel(parcel.id);
        if (parcel.owned && !highlighted) continue;
        const Uint8 red = parcel.owned ? 70 : (purchasable ? 215 : 125);
        const Uint8 green = parcel.owned ? 180 : (purchasable ? 184 : 128);
        const Uint8 blue = parcel.owned ? 92 : (purchasable ? 80 : 136);
        const Uint8 alpha = highlighted ? 110 : 52;
        for (int local_y = 0; local_y < parcel.height; ++local_y) {
            for (int local_x = 0; local_x < parcel.width; ++local_x) {
                const int tile_x = parcel.origin_x + local_x;
                const int tile_y = parcel.origin_y + local_y;
                SDL_SetRenderDrawColor(renderer, red, green, blue, alpha);
                if (document != nullptr) {
                    render_heightfield_tile_fill(renderer, tile_x, tile_y, camera, viewport_width, viewport_height,
                                                 SDL_FColor{static_cast<float>(red) / 255.0F,
                                                            static_cast<float>(green) / 255.0F,
                                                            static_cast<float>(blue) / 255.0F,
                                                            static_cast<float>(alpha) / 255.0F}, document);
                } else {
                    render_diamond_tile(renderer, tile_x, tile_y, camera, viewport_width, viewport_height,
                                        red, green, blue, alpha);
                }
            }
        }
    }
}

...TRUNCATED_FOR_BREVITY...