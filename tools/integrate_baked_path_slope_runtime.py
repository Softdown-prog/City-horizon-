from pathlib import Path

path = Path("src/runtime_terrain_renderer.h")
text = path.read_text(encoding="utf-8")

replacements = []

replacements.append((
'''struct GroundSurfaceDrawEntry {
    int tile_x = 0;
    int tile_y = 0;
    TileConnectionMask connections = 0;
    ProceduralTileRecipe recipe{};
};''',
'''struct GroundSurfaceDrawEntry {
    int tile_x = 0;
    int tile_y = 0;
    TileConnectionMask connections = 0;
    ProceduralTileRecipe recipe{};
    GroundPathMaterial material = GroundPathMaterial::dirt;
};'''))

anchor = '''inline void render_flat_sprite_at_height(
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
'''
helper = anchor + '''
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
'''
replacements.append((anchor, helper))

replacements.append((
'''// Runtime bridge for CH_TERRAIN_HEIGHTFIELD_V1 + CH_PROCEDURAL_TILE_2D_V1.
// Flat dirt-path cells keep the approved PNGs. Cells whose local height delta
// requires a ramp or stairs are rendered as 2D geometry directly on the same
// canonical heightfield, so sculpting never creates a second terrain system.''',
'''// Runtime bridge for CH_TERRAIN_HEIGHTFIELD_V1 + CH_PATH_SLOPE_SPRITE_V1.
// Flat ground paths keep the approved legacy PNGs. Compatible non-flat straight
// cells select an offline-baked ramp/stair PNG from the same material family.
// The runtime never paints free-form artistic stair geometry.'''))

replacements.append((
'''        const TextureAsset* grass_base = find_texture("assets/terrain/grass_isometric_01.png");
        const TextureAsset* dirt_material =
            find_texture("assets/terrain/paths/dirt_01/dirt_path_15_cross.png");

        std::unordered_map<std::uint64_t, const TextureAsset*> scenario_terrain_textures;
        std::vector<runtime_render_detail::WaterTile> water_tiles;
        std::vector<runtime_terrain_detail::GroundSurfaceDrawEntry> dirt_path_tiles;''',
'''        const TextureAsset* grass_base = find_texture("assets/terrain/grass_isometric_01.png");

        std::unordered_map<std::uint64_t, const TextureAsset*> scenario_terrain_textures;
        std::vector<runtime_render_detail::WaterTile> water_tiles;
        std::vector<runtime_terrain_detail::GroundSurfaceDrawEntry> ground_path_tiles;'''))

replacements.append((
'''                    if (is_connectable_ground_surface(tile)) {
                        const TileConnectionMask connections =
                            ground_surface_connection_mask(document, x, y, tile.terrain_definition);
                        dirt_path_tiles.push_back({
                            x,
                            y,
                            connections,
                            make_procedural_tile_2d_recipe(document, x, y, connections),
                        });
                    }''',
'''                    if (is_connectable_ground_surface(tile)) {
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
                    }'''))

old_render = '''        constexpr SDL_FColor kDirtUnderlay = {0.50F, 0.35F, 0.20F, 1.0F};
        for (const auto& tile : dirt_path_tiles) {
            if (!tile.recipe.legacy_sprite_compatible) continue;
            runtime_terrain_detail::render_deformed_tile_fill(
                renderer, document, tile.tile_x, tile.tile_y, camera,
                viewport_width, viewport_height, kDirtUnderlay);
        }
        for (const auto& tile : dirt_path_tiles) {
            if (!tile.recipe.legacy_sprite_compatible) continue;
            const TileConnectionMask visual_connections =
                runtime_render_detail::camera_visual_connections(tile.connections, camera.rotation);
            if (const TextureAsset* sprite =
                    find_texture(runtime_render_detail::dirt_path_sprite(visual_connections))) {
                runtime_terrain_detail::render_flat_sprite_at_height(
                    renderer, *sprite, document, tile.tile_x, tile.tile_y,
                    camera, viewport_width, viewport_height);
            }
        }

        constexpr SDL_FColor kPathOuter = {
            74.0F / 255.0F, 49.0F / 255.0F, 30.0F / 255.0F, 0.90F};
        constexpr SDL_FColor kPathInner = {
            171.0F / 255.0F, 121.0F / 255.0F, 67.0F / 255.0F, 1.0F};
        const float outer_width = 33.0F * camera.zoom;
        const float inner_width = 27.0F * camera.zoom;

        SDL_SetRenderDrawBlendMode(renderer, SDL_BLENDMODE_BLEND);
        for (const auto& tile : dirt_path_tiles) {
            if (tile.recipe.legacy_sprite_compatible) continue;
            runtime_terrain_detail::render_network_stroke(
                renderer, document, tile, camera, viewport_width, viewport_height,
                outer_width, kPathOuter);
        }
        for (const auto& tile : dirt_path_tiles) {
            if (tile.recipe.legacy_sprite_compatible) continue;
            runtime_terrain_detail::render_network_stroke(
                renderer, document, tile, camera, viewport_width, viewport_height,
                inner_width, kPathInner);
        }
        for (const auto& tile : dirt_path_tiles) {
            if (tile.recipe.legacy_sprite_compatible) continue;
            runtime_terrain_detail::render_network_material(
                renderer, dirt_material, document, tile, camera,
                viewport_width, viewport_height, inner_width * 0.92F);
        }
        for (const auto& tile : dirt_path_tiles) {
            if (tile.recipe.legacy_sprite_compatible) continue;
            runtime_terrain_detail::render_vertical_profile_details(
                renderer, document, tile, camera, viewport_width, viewport_height,
                inner_width);
        }
'''

new_render = '''        constexpr SDL_FColor kDirtUnderlay = {0.50F, 0.35F, 0.20F, 1.0F};
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
'''
replacements.append((old_render, new_render))

for old, new in replacements:
    if old not in text:
        raise SystemExit("runtime integration anchor not found; refusing partial patch")
    text = text.replace(old, new, 1)

if "render_network_stroke(" in new_render or "render_vertical_profile_details(" in new_render:
    raise SystemExit("free-form rendering call unexpectedly survived in replacement block")

path.write_text(text, encoding="utf-8")
print("PASS runtime now selects CH_PATH_SLOPE_SPRITE_V1 baked PNGs")
