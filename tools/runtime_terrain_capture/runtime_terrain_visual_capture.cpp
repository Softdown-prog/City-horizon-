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

    // Deliberately strong, still-canonical relief. Repeated brush passes are
    // exactly what a player can do and make the shape readable in a screenshot
    // without introducing any debug/fake terrain geometry.
    document.apply_terrain_brush(11.5F, 12.0F, 5.0F, 1.35F, ch::TerrainBrushMode::raise);
    document.apply_terrain_brush(11.5F, 12.0F, 4.2F, 1.35F, ch::TerrainBrushMode::raise);
    document.apply_terrain_brush(11.5F, 12.0F, 3.4F, 0.90F, ch::TerrainBrushMode::raise);
    document.apply_terrain_brush(11.5F, 12.0F, 5.5F, 0.22F, ch::TerrainBrushMode::smooth);

    document.apply_terrain_brush(20.5F, 18.5F, 4.7F, 1.35F, ch::TerrainBrushMode::lower);
    document.apply_terrain_brush(20.5F, 18.5F, 3.9F, 1.35F, ch::TerrainBrushMode::lower);
    document.apply_terrain_brush(20.5F, 18.5F, 3.1F, 0.90F, ch::TerrainBrushMode::lower);
    document.apply_terrain_brush(20.5F, 18.5F, 5.2F, 0.22F, ch::TerrainBrushMode::smooth);

    // Refuse to create a visual artifact unless the canonical heightfield has
    // a clearly elevated hill and clearly lowered basin. This guards against
    // a visually flat screenshot being accepted merely because rendering ran.
    const float hill_height = document.terrain_heightfield().sample(11.5F, 12.0F);
    const float basin_height = document.terrain_heightfield().sample(20.5F, 18.5F);
    std::cout << "terrain proof samples: hill=" << hill_height
              << " basin=" << basin_height << '\n';
    if (hill_height <= 2.0F || basin_height >= -2.0F) {
        std::cerr << "canonical terrain relief did not produce strong hill/basin samples\n";
        return 7;
    }

    // Dirt path: one connected route crosses the hill and then turns through
    // the basin. This exercises the production CH_PATH_SLOPE_SPRITE_V1 selector.
    for (int x = 5; x <= 23; ++x) {
        document.paint_terrain_at(x, 13, std::string(ch::kGroundDirtPathDefinition), "");
    }
    for (int y = 13; y <= 23; ++y) {
        document.paint_terrain_at(20, y, std::string(ch::kGroundDirtPathDefinition), "");
    }

    // Sand path: use the second ground-path material family on the same canonical
    // hill. Keeping it on a straight row makes at least one slope cell eligible
    // for the same baked-sprite selection recipe while preserving its own texture.
    for (int x = 5; x <= 18; ++x) {
        document.paint_terrain_at(x, 12, std::string(ch::kGroundSandPathDefinition), "");
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
    camera.zoom = 1.02F;
    const float center_x = 15.0F;
    const float center_y = 15.2F;
    camera.pan_x = -(center_x - center_y) * 64.0F * camera.zoom;
    camera.pan_y = -(center_x + center_y) * 32.0F * camera.zoom;

    ch::TerrainAwareRuntimeMapRenderer::render_world_terrain_and_water(
        renderer, document, find_texture, repo_root, camera,
        static_cast<float>(kWidth), static_cast<float>(kHeight), 0.0F);

    // A screenshot alone is not enough: prove the production renderer actually
    // requested baked slope PNGs from BOTH material libraries instead of falling
    // back to the legacy flat sprite or the old free-form path painter.
    bool loaded_dirt_slope = false;
    bool loaded_sand_slope = false;
    for (const auto& [key, asset] : assets) {
        (void)asset;
        if (key.find("/assets/terrain/paths/dirt_01/slopes/") != std::string::npos) {
            loaded_dirt_slope = true;
        }
        if (key.find("/assets/terrain/paths/sand_01/slopes/") != std::string::npos) {
            loaded_sand_slope = true;
        }
    }
    std::cout << "baked slope assets used: dirt=" << loaded_dirt_slope
              << " sand=" << loaded_sand_slope << '\n';
    if (!loaded_dirt_slope || !loaded_sand_slope) {
        std::cerr << "runtime did not select baked slope sprites for both ground-path materials\n";
        for (auto& [key, asset] : assets) destroy_asset(asset);
        SDL_DestroyRenderer(renderer);
        SDL_DestroySurface(canvas);
        SDL_Quit();
        return 8;
    }

    SDL_RenderPresent(renderer);
    const bool saved = SDL_SaveBMP(canvas, output_path.string().c_str());
    if (!saved) std::cerr << "SDL_SaveBMP failed: " << SDL_GetError() << '\n';

    for (auto& [key, asset] : assets) destroy_asset(asset);
    SDL_DestroyRenderer(renderer);
    SDL_DestroySurface(canvas);
    SDL_Quit();
    return saved ? 0 : 6;
}
