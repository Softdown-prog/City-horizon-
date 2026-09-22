from pathlib import Path
import re

path = Path('src/ch_render/map_renderer.cpp')
text = path.read_text(encoding='utf-8')

pattern = re.compile(
    r'''void MapRenderer::render_farming\(SDL_Renderer\* renderer, const FarmingSystem& farming, const CropCatalog& crops,\n'''
    r'''\s*const std::function<const TextureAsset\*\(const std::filesystem::path&\)>& find_texture,\n'''
    r'''\s*const std::filesystem::path& root, const CameraState& camera,\n'''
    r'''\s*const float viewport_width, const float viewport_height\) \{.*?\n\}\n\n'''
    r'''(?=void MapRenderer::render_farming\(SDL_Renderer\* renderer, const FarmingSystem& farming, const CropCatalog& crops,\n'''
    r'''\s*const std::unordered_map<std::string, TextureAsset>& texture_lookup,)''',
    re.S,
)

replacement = r'''void MapRenderer::render_farming(SDL_Renderer* renderer, const FarmingSystem& farming, const CropCatalog& crops,
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

'''

patched, count = pattern.subn(replacement, text, count=1)
if count != 1:
    raise SystemExit(f'Expected exactly one render_farming implementation, replaced {count}')

path.write_text(patched, encoding='utf-8')
