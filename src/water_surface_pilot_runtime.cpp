#include <SDL3/SDL.h>

#include <algorithm>
#include <cstdint>
#include <filesystem>
#include <iostream>
#include <string>
#include <unordered_map>
#include <vector>

#include "src/ch_core/map_document.h"
#include "src/ch_core/projection.h"
#include "src/ch_render/map_renderer.h"

namespace {

void destroy_asset(ch::TextureAsset& asset) {
    if (asset.texture != nullptr) SDL_DestroyTexture(asset.texture);
    asset = {};
}

bool load_asset(SDL_Renderer* renderer, const std::filesystem::path& path, ch::TextureAsset& asset) {
    SDL_Surface* image = SDL_LoadPNG(path.string().c_str());
    if (image == nullptr) {
        std::cerr << "SDL_LoadPNG failed for " << path << ": " << SDL_GetError() << '\n';
        return false;
    }
    asset.texture = SDL_CreateTextureFromSurface(renderer, image);
    asset.source_width = static_cast<float>(image->w);
    asset.source_height = static_cast<float>(image->h);
    SDL_DestroySurface(image);
    if (asset.texture == nullptr) {
        std::cerr << "SDL_CreateTextureFromSurface failed: " << SDL_GetError() << '\n';
        return false;
    }
    SDL_SetTextureBlendMode(asset.texture, SDL_BLENDMODE_BLEND);
    SDL_SetTextureScaleMode(asset.texture, SDL_SCALEMODE_LINEAR);
    return true;
}

bool create_no_grid_base(SDL_Renderer* renderer, ch::TextureAsset& asset) {
    // MapRenderer requires a non-null base terrain texture to avoid its
    // explicit outline fallback.  A fully transparent 1x1 texture retains
    // the production map pass while exposing only the renderer background
    // outside the unchanged 6x6 water pilot.
    std::uint32_t transparent_pixel = 0;
    asset.texture = SDL_CreateTexture(renderer, SDL_PIXELFORMAT_RGBA32, SDL_TEXTUREACCESS_STATIC, 1, 1);
    if (asset.texture == nullptr ||
        !SDL_UpdateTexture(asset.texture, nullptr, &transparent_pixel, static_cast<int>(sizeof(transparent_pixel)))) {
        std::cerr << "unable to create no-grid base: " << SDL_GetError() << '\n';
        destroy_asset(asset);
        return false;
    }
    asset.source_width = 1175.0F;  // Matches the production grass footprint.
    asset.source_height = 636.0F;
    SDL_SetTextureBlendMode(asset.texture, SDL_BLENDMODE_BLEND);
    return true;
}

}  // namespace

int main(int argc, char** argv) {
    if (argc != 5) {
        std::cerr << "usage: water_surface_pilot_runtime <asset-root> <scenario-json> <solid|linear|nearest|bleed|composite|composite_low_detail|layers_deep|layers_shallow|layers_deep_grid|real_coast> <runtime-bmp>\n";
        return 2;
    }
    const std::filesystem::path asset_root = argv[1];
    const std::filesystem::path pilot_path = argv[2];
    const std::string mode = argv[3];
    const std::filesystem::path output_path = argv[4];
    if (mode != "solid" && mode != "linear" && mode != "nearest" && mode != "bleed" &&
        mode != "composite" && mode != "composite_low_detail" && mode != "layers_deep" &&
        mode != "layers_shallow" && mode != "layers_deep_grid" && mode != "real_coast") {
        std::cerr << "unknown capture mode: " << mode << '\n';
        return 2;
    }
    const auto document = ch::MapDocument::load_from_file(pilot_path.string());
    const bool real_coast_mode = mode == "real_coast";
    if (!document.has_value() || (!real_coast_mode && document->terrain_tiles().size() != 36U)) {
        std::cerr << "pilot document must contain exactly 36 terrain tiles\n";
        return 3;
    }

    if (!SDL_Init(SDL_INIT_VIDEO)) {
        std::cerr << "SDL_Init failed: " << SDL_GetError() << '\n';
        return 4;
    }
    SDL_Surface* canvas = SDL_CreateSurface(1280, 800, SDL_PIXELFORMAT_RGBA32);
    SDL_Renderer* renderer = canvas == nullptr ? nullptr : SDL_CreateSoftwareRenderer(canvas);
    if (canvas == nullptr || renderer == nullptr) {
        std::cerr << "SDL software target creation failed: " << SDL_GetError() << '\n';
        if (renderer != nullptr) SDL_DestroyRenderer(renderer);
        if (canvas != nullptr) SDL_DestroySurface(canvas);
        SDL_Quit();
        return 5;
    }

    ch::TextureAsset no_grid_base;
    ch::TextureAsset water;
    const bool layered_mode = mode == "layers_deep" || mode == "layers_shallow" || mode == "layers_deep_grid" || real_coast_mode;
    const std::filesystem::path water_path = asset_root / "assets/terrain/coast_adjusted/" /
        (layered_mode ? "water_caustics_overlay_01.png" :
         mode == "bleed" ? "water_surface_v2_master_bleed_diagnostic.png" : "water_surface_v2_master.png");
    const bool loaded = create_no_grid_base(renderer, no_grid_base) &&
                        (mode == "solid" || load_asset(renderer, water_path, water));
    if (!loaded) {
        destroy_asset(water);
        destroy_asset(no_grid_base);
        SDL_DestroyRenderer(renderer);
        SDL_DestroySurface(canvas);
        SDL_Quit();
        return 6;
    }

    std::unordered_map<std::uint64_t, const ch::TextureAsset*> terrain;
    std::unordered_map<std::string, ch::TextureAsset> real_coast_assets;
    std::vector<ch::TerrainTileEntry> water_tiles;
    for (const auto& tile : document->terrain_tiles()) {
        if (!real_coast_mode && tile.texture != "assets/terrain/coast_adjusted/water_surface_v2_master.png") {
            std::cerr << "pilot references a non-approved texture: " << tile.texture << '\n';
            destroy_asset(water);
            destroy_asset(no_grid_base);
            SDL_DestroyRenderer(renderer);
            SDL_DestroySurface(canvas);
            SDL_Quit();
            return 7;
        }
        if (real_coast_mode) {
            auto [it, inserted] = real_coast_assets.try_emplace(tile.texture);
            if (inserted && !load_asset(renderer, asset_root / tile.texture, it->second)) {
                std::cerr << "unable to load real-coast terrain: " << tile.texture << '\n';
                return 7;
            }
            terrain[ch::tile_key(tile.tile_x, tile.tile_y)] = &it->second;
            if (tile.texture.find("coast_water_") != std::string::npos || tile.texture.find("ocean_") != std::string::npos) {
                water_tiles.push_back(tile);
            }
        } else {
            terrain[ch::tile_key(tile.tile_x, tile.tile_y)] = &water;
        }
    }

    ch::CameraState camera{};
    camera.zoom = 0.90F;
    if (real_coast_mode && !water_tiles.empty()) {
        float center_x = 0.0F;
        float center_y = 0.0F;
        for (const auto& tile : water_tiles) {
            center_x += static_cast<float>(tile.tile_x) + 0.5F;
            center_y += static_cast<float>(tile.tile_y) + 0.5F;
        }
        center_x /= static_cast<float>(water_tiles.size());
        center_y /= static_cast<float>(water_tiles.size());
        camera.pan_x = -(center_x - center_y) * 64.0F * camera.zoom;
        camera.pan_y = -(center_x + center_y) * 32.0F * camera.zoom;
    }
    if (real_coast_mode) {
        ch::MapRenderer::render_map(renderer, &no_grid_base, terrain, camera, 1280.0F, 800.0F);
        for (const auto& tile : water_tiles) {
            const bool shallow = tile.texture.find("shallow") != std::string::npos;
            ch::MapRenderer::render_tile_fill(renderer, tile.tile_x, tile.tile_y, camera, 1280.0F, 800.0F,
                shallow ? SDL_FColor{115.0F / 255.0F, 200.0F / 255.0F, 210.0F / 255.0F, 1.0F}
                        : SDL_FColor{108.0F / 255.0F, 196.0F / 255.0F, 207.0F / 255.0F, 1.0F});
        }
        for (const auto& tile : water_tiles) {
            ch::MapRenderer::render_water_caustics_overlay_tile(renderer, water, tile.tile_x, tile.tile_y, camera, 1280.0F, 800.0F);
        }
    } else if (mode == "solid" || mode == "composite" || mode == "composite_low_detail" || layered_mode) {
        std::unordered_map<std::uint64_t, const ch::TextureAsset*> empty_terrain;
        ch::MapRenderer::render_map(renderer, &no_grid_base, empty_terrain, camera, 1280.0F, 800.0F);

        // PASS 0: opaque physical coverage.  This is the exact renderer
        // primitive and geometry that passed the solid-color seam test. The
        // colour is the measured opaque-pixel mean of the approved master:
        // RGB(108, 196, 207).  It deliberately has no alpha edge.
        const SDL_FColor base_colour = mode == "layers_shallow"
            ? SDL_FColor{115.0F / 255.0F, 200.0F / 255.0F, 210.0F / 255.0F, 1.0F}
            : SDL_FColor{108.0F / 255.0F, 196.0F / 255.0F, 207.0F / 255.0F, 1.0F};
        for (const auto& tile : document->terrain_tiles()) {
            ch::MapRenderer::render_tile_fill(
                renderer, tile.tile_x, tile.tile_y, camera, 1280.0F, 800.0F,
                base_colour);
        }

        if (layered_mode) {
            SDL_SetTextureScaleMode(water.texture, SDL_SCALEMODE_LINEAR);
            for (const auto& tile : document->terrain_tiles()) {
                ch::MapRenderer::render_water_caustics_overlay_tile(
                    renderer, water, tile.tile_x, tile.tile_y, camera, 1280.0F, 800.0F);
            }
            if (mode == "layers_deep_grid") {
                SDL_SetRenderDrawColor(renderer, 32, 72, 78, 120);
                for (const auto& tile : document->terrain_tiles()) {
                    ch::MapRenderer::render_tile_outline(renderer, tile.tile_x, tile.tile_y, camera, 1280.0F, 800.0F);
                }
            }
        } else if (mode != "solid") {
            // PASS 1: existing approved art remains a visual detail only.
            // Its partial alpha now reveals the opaque base above, never the
            // terrain/background.  This uses MapRenderer's real terrain-tile
            // draw path, not an alternate projection or an overlapped rect.
            SDL_SetTextureScaleMode(water.texture, SDL_SCALEMODE_LINEAR);
            SDL_SetTextureAlphaMod(water.texture, mode == "composite_low_detail" ? 96U : 255U);
            std::vector<ch::TerrainTileEntry> ordered_tiles = document->terrain_tiles();
            std::sort(ordered_tiles.begin(), ordered_tiles.end(), [](const auto& a, const auto& b) {
                const int depth_a = a.tile_x + a.tile_y;
                const int depth_b = b.tile_x + b.tile_y;
                return depth_a == depth_b ? a.tile_x < b.tile_x : depth_a < depth_b;
            });
            for (const auto& tile : ordered_tiles) {
                ch::MapRenderer::render_custom_terrain_tile(
                    renderer, water, tile.tile_x, tile.tile_y, camera, 1280.0F, 800.0F);
            }
        }
    } else {
        SDL_SetTextureScaleMode(water.texture, mode == "nearest" ? SDL_SCALEMODE_NEAREST : SDL_SCALEMODE_LINEAR);
        ch::MapRenderer::render_map(renderer, &no_grid_base, terrain, camera, 1280.0F, 800.0F);
    }
    SDL_RenderPresent(renderer);
    const bool saved = SDL_SaveBMP(canvas, output_path.string().c_str());
    if (!saved) std::cerr << "SDL_SaveBMP failed: " << SDL_GetError() << '\n';

    destroy_asset(water);
    destroy_asset(no_grid_base);
    for (auto& [path, asset] : real_coast_assets) destroy_asset(asset);
    SDL_DestroyRenderer(renderer);
    SDL_DestroySurface(canvas);
    SDL_Quit();
    return saved ? 0 : 8;
}
