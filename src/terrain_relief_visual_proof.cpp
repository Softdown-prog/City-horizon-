#include "src/ch_core/map_document.h"
#include "src/ch_render/map_renderer.h"

#include <SDL3/SDL.h>

#include <filesystem>
#include <iostream>
#include <string>
#include <unordered_map>

namespace {

constexpr int kWidth = 1280;
constexpr int kHeight = 800;

bool save_frame(SDL_Renderer* renderer, const std::filesystem::path& path) {
    if (!SDL_RenderPresent(renderer)) {
        std::cerr << "terrain proof: SDL_RenderPresent failed: " << SDL_GetError() << '\n';
        return false;
    }
    SDL_Surface* pixels = SDL_RenderReadPixels(renderer, nullptr);
    if (pixels == nullptr) {
        std::cerr << "terrain proof: SDL_RenderReadPixels failed: " << SDL_GetError() << '\n';
        return false;
    }
    const bool ok = SDL_SavePNG(pixels, path.string().c_str());
    if (!ok) {
        std::cerr << "terrain proof: SDL_SavePNG failed: " << SDL_GetError() << '\n';
    }
    SDL_DestroySurface(pixels);
    return ok;
}

}  // namespace

int main(int argc, char** argv) {
    const std::filesystem::path output_dir = argc > 1 ? argv[1] : "terrain_relief_proof";
    std::error_code directory_error;
    std::filesystem::create_directories(output_dir, directory_error);
    if (directory_error) {
        std::cerr << "terrain proof: cannot create output directory: "
                  << directory_error.message() << '\n';
        return 1;
    }

    if (!SDL_Init(SDL_INIT_VIDEO)) {
        std::cerr << "terrain proof: SDL_Init failed: " << SDL_GetError() << '\n';
        return 1;
    }

    SDL_Surface* canvas = SDL_CreateSurface(kWidth, kHeight, SDL_PIXELFORMAT_RGBA32);
    if (canvas == nullptr) {
        std::cerr << "terrain proof: SDL_CreateSurface failed: " << SDL_GetError() << '\n';
        SDL_Quit();
        return 1;
    }

    SDL_Renderer* renderer = SDL_CreateSoftwareRenderer(canvas);
    if (renderer == nullptr) {
        std::cerr << "terrain proof: SDL_CreateSoftwareRenderer failed: " << SDL_GetError() << '\n';
        SDL_DestroySurface(canvas);
        SDL_Quit();
        return 1;
    }

    SDL_Surface* grass_surface = SDL_LoadPNG("assets/terrain/grass_isometric_01.png");
    if (grass_surface == nullptr) {
        std::cerr << "terrain proof: grass asset could not be loaded: " << SDL_GetError() << '\n';
        SDL_DestroyRenderer(renderer);
        SDL_DestroySurface(canvas);
        SDL_Quit();
        return 1;
    }

    SDL_Texture* grass_texture = SDL_CreateTextureFromSurface(renderer, grass_surface);
    ch::TextureAsset grass{grass_texture, static_cast<float>(grass_surface->w),
                           static_cast<float>(grass_surface->h)};
    SDL_DestroySurface(grass_surface);
    if (grass.texture == nullptr) {
        std::cerr << "terrain proof: grass texture could not be created: " << SDL_GetError() << '\n';
        SDL_DestroyRenderer(renderer);
        SDL_DestroySurface(canvas);
        SDL_Quit();
        return 1;
    }
    SDL_SetTextureBlendMode(grass.texture, SDL_BLENDMODE_BLEND);
    SDL_SetTextureScaleMode(grass.texture, SDL_SCALEMODE_LINEAR);

    ch::CameraState camera;
    camera.pan_x = 0.0F;
    camera.pan_y = -40.0F;
    camera.zoom = 0.68F;
    camera.rotation = ch::CameraRotation::r0;

    const std::unordered_map<std::uint64_t, const ch::TextureAsset*> no_custom_terrain;
    ch::MapDocument document = ch::MapDocument::create_empty("Terrain Relief Visual Proof", 32, 32);

    ch::MapRenderer::render_map(renderer, &grass, no_custom_terrain, camera,
                                static_cast<float>(kWidth), static_cast<float>(kHeight), &document);
    if (!save_frame(renderer, output_dir / "terrain_relief_flat.png")) {
        SDL_DestroyTexture(grass.texture);
        SDL_DestroyRenderer(renderer);
        SDL_DestroySurface(canvas);
        SDL_Quit();
        return 1;
    }

    // Same canonical gameplay brush contract used by the runtime construction tool.
    for (int pass = 0; pass < 4; ++pass) {
        document.apply_terrain_brush(-3.0F, -2.0F, 3.75F, 0.42F, ch::TerrainBrushMode::raise);
    }
    document.apply_terrain_brush(-3.0F, -2.0F, 4.25F, 0.24F, ch::TerrainBrushMode::smooth);

    for (int pass = 0; pass < 4; ++pass) {
        document.apply_terrain_brush(4.0F, 2.0F, 3.75F, 0.38F, ch::TerrainBrushMode::lower);
    }
    document.apply_terrain_brush(4.0F, 2.0F, 4.25F, 0.24F, ch::TerrainBrushMode::smooth);

    const float hill_height = document.terrain_height_at(-3, -2);
    const float basin_height = document.terrain_height_at(4, 2);
    if (hill_height <= 0.5F || basin_height >= -0.5F) {
        std::cerr << "terrain proof: canonical brush did not create expected relief: hill="
                  << hill_height << " basin=" << basin_height << '\n';
        SDL_DestroyTexture(grass.texture);
        SDL_DestroyRenderer(renderer);
        SDL_DestroySurface(canvas);
        SDL_Quit();
        return 1;
    }

    ch::MapRenderer::render_map(renderer, &grass, no_custom_terrain, camera,
                                static_cast<float>(kWidth), static_cast<float>(kHeight), &document);
    const bool saved = save_frame(renderer, output_dir / "terrain_relief_sculpted.png");

    SDL_DestroyTexture(grass.texture);
    SDL_DestroyRenderer(renderer);
    SDL_DestroySurface(canvas);
    SDL_Quit();

    if (!saved) return 1;
    std::cout << "terrain proof: hill=" << hill_height
              << " basin=" << basin_height << '\n';
    return 0;
}
