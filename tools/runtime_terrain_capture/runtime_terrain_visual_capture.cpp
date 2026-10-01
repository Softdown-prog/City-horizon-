#include <SDL3/SDL.h>

#include <filesystem>
#include <iostream>
#include <string>
#include <unordered_map>

#include "src/ch_core/map_document.h"
#include "src/runtime_terrain_renderer.h"

namespace {

void destroy_asset(ch::TextureAsset& asset) {
    if (asset.texture != nullptr) SDL_DestroyTexture(asset.texture);
    asset = {};
}

bool load_asset(SDL_Renderer* renderer, const std::filesystem::path& path, ch::TextureAsset& asset) {
    SDL_Surface* image = SDL_LoadPNG(path.string().c_str());
    if (image == nullptr) {
        return false;
    }
    asset.texture = SDL_CreateTextureFromSurface(renderer, image);
    asset.source_width = static_cast<float>(image->w);
    asset.source_height = static_cast<float>(image->h);
    SDL_DestroySurface(image);
    if (asset.texture == nullptr) return false;
    SDL_SetTextureBlendMode(asset.texture, SDL_BLENDMODE_BLEND);
    SDL_SetTextureScaleMode(asset.texture, SDL_SCALEMODE_LINEAR);
    return true;
}

} // namespace

int main(int argc, char** argv) {
    if (argc != 3) {
        std::cerr << "usage: ch_runtime_terrain_visual_capture <repo-root> <output-bmp>\n";
        return 2;
    }

    const std::filesystem::path repo_root = std::filesystem::absolute(argv[1]);
    const std::filesystem::path output_path = argv[2];

    ch::MapDocument document = ch::MapDocument::create_empty("Runtime Terrain Proof", 32, 32);

    // Rounded hill: two raise passes plus a smoothing pass reproduce a player
    // dragging the terrain brush instead of constructing a hard tile plateau.
    document.apply_terrain_brush(12.5F, 12.5F, 5.5F, 0.78F, ch::TerrainBrushMode::raise);
    document.apply_terrain_brush(12.5F, 12.5F, 4.2F, 0.58F, ch::TerrainBrushMode::raise);
    document.apply_terrain_brush(12.5F, 12.5F, 6.0F, 0.55F, ch::TerrainBrushMode::smooth);

    // Rounded basin/depression using the exact same canonical heightfield.
    document.apply_terrain_brush(20.0F, 18.0F, 4.8F, 0.82F, ch::TerrainBrushMode::lower);
    document.apply_terrain_brush(20.0F, 18.0F, 3.5F, 0.48F, ch::TerrainBrushMode::lower);
    document.apply_terrain_brush(20.0F, 18.0F, 5.2F, 0.60F, ch::TerrainBrushMode::smooth);

    // One connected path crosses the hill and then turns through the basin.
    // Flat cells use the approved legacy PNG; sloped cells are forced through
    // CH_PROCEDURAL_TILE_2D_V1 ramp/stair geometry by the runtime renderer.
    for (int x = 5; x <= 23; ++x) {
        document.paint_terrain_at(x, 13, "dirt_path", "");
    }
    for (int y = 13; y <= 23; ++y) {
        document.paint_terrain_at(20, y, "dirt_path", "");
    }

    if (!SDL_Init(SDL_INIT_VIDEO)) {
        std::cerr << "SDL_Init failed: " << SDL_GetError() << '\n';
        return 3;
    }

    constexpr int kWidth = 1280;
    constexpr int kHeight = 800;
    SDL_Surface* canvas = SDL_CreateSurface(kWidth, kHeight, SDL_PIXELFORMAT_RGBA32);
    SDL_Renderer* renderer = canvas == nullptr ? nullptr : SDL_CreateSoftwareRenderer(canvas);
    if (canvas == nullptr || renderer == nullptr) {
        std::cerr << "SDL software renderer creation failed: " << SDL_GetError() << '\n';
        if (renderer != nullptr) SDL_DestroyRenderer(renderer);
        if (canvas != nullptr) SDL_DestroySurface(canvas);
        SDL_Quit();
        return 4;
    }

    std::unordered_map<std::string, ch::TextureAsset> assets;
    const auto find_texture = [&](const std::filesystem::path& requested) -> const ch::TextureAsset* {
        const std::filesystem::path full = requested.is_absolute() ? requested : repo_root / requested;
        const std::string key = full.lexically_normal().generic_string();
        if (const auto it = assets.find(key); it != assets.end()) return &it->second;

        ch::TextureAsset asset;
        if (!load_asset(renderer, full, asset)) {
            return nullptr;
        }
        auto [it, inserted] = assets.emplace(key, asset);
        (void)inserted;
        return &it->second;
    };

    // Fail early if the production grass cannot be loaded; without it a grid
    // fallback could masquerade as a successful terrain proof.
    if (find_texture("assets/terrain/grass_isometric_01.png") == nullptr) {
        std::cerr << "production grass asset could not be loaded\n";
        for (auto& [key, asset] : assets) destroy_asset(asset);
        SDL_DestroyRenderer(renderer);
        SDL_DestroySurface(canvas);
        SDL_Quit();
        return 5;
    }

    ch::CameraState camera{};
    camera.zoom = 0.92F;
    const float center_x = 14.5F;
    const float center_y = 15.0F;
    camera.pan_x = -(center_x - center_y) * 64.0F * camera.zoom;
    camera.pan_y = -(center_x + center_y) * 32.0F * camera.zoom;

    ch::TerrainAwareRuntimeMapRenderer::render_world_terrain_and_water(
        renderer, document, find_texture, repo_root, camera,
        static_cast<float>(kWidth), static_cast<float>(kHeight), 0.0F);

    // A subtle outline around the two brush centers makes the proof easier to
    // inspect without replacing or faking the production terrain rendering.
    SDL_SetRenderDrawBlendMode(renderer, SDL_BLENDMODE_BLEND);
    SDL_SetRenderDrawColor(renderer, 255, 255, 255, 60);
    ch::MapRenderer::render_tile_outline(renderer, 12, 12, camera,
                                         static_cast<float>(kWidth), static_cast<float>(kHeight));
    ch::MapRenderer::render_tile_outline(renderer, 20, 18, camera,
                                         static_cast<float>(kWidth), static_cast<float>(kHeight));

    SDL_RenderPresent(renderer);
    const bool saved = SDL_SaveBMP(canvas, output_path.string().c_str());
    if (!saved) std::cerr << "SDL_SaveBMP failed: " << SDL_GetError() << '\n';

    for (auto& [key, asset] : assets) destroy_asset(asset);
    SDL_DestroyRenderer(renderer);
    SDL_DestroySurface(canvas);
    SDL_Quit();
    return saved ? 0 : 6;
}
