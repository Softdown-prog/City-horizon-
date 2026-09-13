#include "src/ch_render/map_renderer.h"
#include "src/ch_render/semantic_renderer.h"
#include <algorithm>
#include <cmath>
#include <iomanip>
#include <sstream>

namespace ch {

namespace {

constexpr float kTileWidth = static_cast<float>(contracts::kTileWidth);
constexpr float kGrassOpaqueLeft = 53.0F;
constexpr float kGrassOpaqueTop = 23.0F;
constexpr float kGrassOpaqueWidth = 1175.0F;

constexpr float kFarmOpaqueLeft = 16.0F;
constexpr float kFarmOpaqueTop = 151.0F;
constexpr float kFarmOpaqueWidth = 1220.0F;

constexpr TileCoordinate road_access_offset(const GridDirection direction) {
    switch (direction) {
        case GridDirection::north: return {0, -1};
        case GridDirection::east: return {1, 0};
        case GridDirection::south: return {0, 1};
        case GridDirection::west: return {-1, 0};
    }
    return {};
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
        const int frame_count = std::max(1, definition.animation->frame_count);
        const int duration_ms = std::max(1, definition.animation->frame_duration_ms);
        const int frame_index = static_cast<int>((SDL_GetTicks() / duration_ms) % frame_count);
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
    for (const FarmTile& tile : farming.tiles()) {
        const WorldPoint visual_top = tile_visual_top_world(tile.tile_x, tile.tile_y, camera.rotation);
        const ScreenPoint top = world_to_screen_point(visual_top.x, visual_top.y, camera, viewport_width, viewport_height);
        const CropDefinition* crop = tile.state == FarmTileState::prepared_soil ? nullptr : crops.find(tile.crop_id);
        const bool legacy_composite = crop != nullptr && !crop->has_stage_overlays();

        if (!legacy_composite) {
            if (const TextureAsset* soil = find_texture(root / "assets/farming/prepared_soil/prepared_soil_01.png")) {
                const float scale = (kTileWidth / kFarmOpaqueWidth) * camera.zoom;
                const SDL_FRect destination = {top.x - kTileWidth * camera.zoom * 0.5F - kFarmOpaqueLeft * scale,
                                               top.y - kFarmOpaqueTop * scale,
                                               soil->source_width * scale, soil->source_height * scale};
                SDL_RenderTexture(renderer, soil->texture, nullptr, &destination);
            }
        }
        if (crop == nullptr || tile.stage < 0 || tile.stage >= crop->stage_count()) continue;
        const TextureAsset* sprite = find_texture(root / crop->active_stage_sprites()[static_cast<std::size_t>(tile.stage)]);
        if (sprite == nullptr) continue;
        if (legacy_composite) {
            const float scale = (kTileWidth / kFarmOpaqueWidth) * camera.zoom;
            const SDL_FRect destination = {top.x - kTileWidth * camera.zoom * 0.5F - kFarmOpaqueLeft * scale,
                                           top.y - kFarmOpaqueTop * scale,
                                           sprite->source_width * scale, sprite->source_height * scale};
            SDL_RenderTexture(renderer, sprite->texture, nullptr, &destination);
        } else {
            const float canvas_width = crop->overlay_canvas_width > 0 ? static_cast<float>(crop->overlay_canvas_width) : static_cast<float>(sprite->source_width);
            const float canvas_height = crop->overlay_canvas_height > 0 ? static_cast<float>(crop->overlay_canvas_height) : static_cast<float>(sprite->source_height);
            const float scale = (kTileWidth / canvas_width) * camera.zoom * crop->overlay_scale;
            const SDL_FRect destination = {top.x - crop->overlay_anchor_x * canvas_width * scale,
                                           top.y - crop->overlay_anchor_y * canvas_height * scale,
                                           sprite->source_width * scale, sprite->source_height * scale};
            SDL_RenderTexture(renderer, sprite->texture, nullptr, &destination);
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

    return true;
}

void MapForgeNativeViewport::resize(int physical_width, int physical_height) {
    physical_width_ = physical_width;
    physical_height_ = physical_height;
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
}

void MapForgeNativeViewport::render_frame() {
    if (renderer_ == nullptr) return;
    int w = physical_width_;
    int h = physical_height_;
    SDL_GetRenderOutputSize(renderer_, &w, &h);
    const float vw = static_cast<float>(w);
    const float vh = static_cast<float>(h);

    const TextureAsset* grass = find_texture("assets/terrain/grass_isometric_01.png");
    std::unordered_map<std::uint64_t, const TextureAsset*> scenario_textures;
    if (current_document_.has_value()) {
        for (const auto& t : current_document_->terrain_tiles()) {
            if (!t.texture.empty()) {
                if (const TextureAsset* tex = find_texture(t.texture)) {
                    scenario_textures[tile_key(t.tile_x, t.tile_y)] = tex;
                }
            }
        }
    }

    // View mode: 0 = ART, 1 = LOGIC, 2 = ART_AND_LOGIC
    if (view_mode_ == 0 || view_mode_ == 2) {
        MapRenderer::render_map(renderer_, grass, scenario_textures, camera_, vw, vh);

        if (current_document_.has_value()) {
            for (const auto& r : current_document_->roads()) {
                if (const TextureAsset* tex = find_texture("assets/roads/straight_01.png")) {
                    MapRenderer::render_road_sprite(renderer_, *tex, r.tile_x, r.tile_y, camera_, vw, vh);
                }
            }
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
}

} // namespace ch
