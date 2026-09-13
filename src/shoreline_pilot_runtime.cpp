#include <SDL3/SDL.h>
#include <filesystem>
#include <iostream>
#include <memory>
#include <unordered_map>
#include <vector>

#include "src/ch_core/map_document.h"
#include "src/ch_core/projection.h"
#include "src/ch_core/semantic_grid.h"
#include "src/ch_core/shoreline_autotile.h"
#include "src/ch_render/map_renderer.h"
#include "src/ch_render/shoreline_catalog.h"

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
    std::uint32_t transparent_pixel = 0;
    asset.texture = SDL_CreateTexture(renderer, SDL_PIXELFORMAT_RGBA32, SDL_TEXTUREACCESS_STATIC, 1, 1);
    if (asset.texture == nullptr ||
        !SDL_UpdateTexture(asset.texture, nullptr, &transparent_pixel, static_cast<int>(sizeof(transparent_pixel)))) {
        destroy_asset(asset);
        return false;
    }
    asset.source_width = 1175.0F;
    asset.source_height = 636.0F;
    SDL_SetTextureBlendMode(asset.texture, SDL_BLENDMODE_BLEND);
    return true;
}

} // namespace

int main(int argc, char** argv) {
    if (argc < 3) {
        std::cerr << "usage: shoreline_pilot_runtime <asset-root> <output-bmp>\n";
        return 2;
    }
    const std::filesystem::path asset_root = argv[1];
    const std::filesystem::path output_path = argv[2];

    // Build synthetic 12x12 pilot scenario JSON string with straight N/E/S/W edges, peninsula, cove, corners
    std::string json = "{\n  \"version\": 1,\n  \"terrain\": [\n";

    // 12x12 grid: x in [-6, 5], y in [-6, 5]
    // Default to water, set specific areas as land to test all features:
    // - Center area [-3..2, -3..2] is Land (Sand)
    // - Peninsula at (3..4, 0..1)
    // - Cove at (-2..-1, -2..-1) as water inside land
    bool first = true;
    for (int y = -6; y <= 5; ++y) {
        for (int x = -6; x <= 5; ++x) {
            bool is_land = (x >= -4 && x <= 2 && y >= -4 && y <= 2);
            // Peninsula
            if (x >= 3 && x <= 4 && y >= -1 && y <= 1) is_land = true;
            // Cove (water inside land)
            if (x >= -2 && x <= -1 && y >= -2 && y <= -1) is_land = false;

            std::string tex = is_land ? "assets/terrain/coast_adjusted/coast_sand_center_01.png"
                                      : "assets/terrain/coast_adjusted/coast_water_deep.png";
            if (!first) json += ",\n";
            first = false;
            json += "    {\"tileX\": " + std::to_string(x) + ", \"tileY\": " + std::to_string(y) + ", \"texture\": \"" + tex + "\"}";
        }
    }
    json += "\n  ],\n  \"buildings\": [],\n  \"roads\": []\n}";

    ch::MapDocument doc(json);

    if (!SDL_Init(SDL_INIT_VIDEO)) {
        std::cerr << "SDL_Init failed: " << SDL_GetError() << '\n';
        return 4;
    }
    SDL_Surface* canvas = SDL_CreateSurface(1400, 900, SDL_PIXELFORMAT_RGBA32);
    SDL_Renderer* renderer = canvas == nullptr ? nullptr : SDL_CreateSoftwareRenderer(canvas);
    if (!canvas || !renderer) {
        std::cerr << "SDL surface/renderer creation failed\n";
        return 5;
    }

    ch::TextureAsset no_grid_base;
    create_no_grid_base(renderer, no_grid_base);

    // Load terrain assets
    std::unordered_map<std::string, ch::TextureAsset> loaded_assets;
    std::unordered_map<std::uint64_t, const ch::TextureAsset*> terrain_textures;

    for (const auto& tile : doc.terrain_tiles()) {
        auto [it, inserted] = loaded_assets.try_emplace(tile.texture);
        if (inserted) {
            load_asset(renderer, asset_root / tile.texture, it->second);
        }
        terrain_textures[ch::tile_key(tile.tile_x, tile.tile_y)] = &it->second;
    }

    // Evaluate Autotiling via SemanticWorldView
    ch::SemanticWorldView world;
    world.map_document = &doc;
    world.map_min = -6;
    world.map_max = 5;

    ch::GridBounds bounds;
    bounds.min_x = -6; bounds.max_x = 5;
    bounds.min_y = -6; bounds.max_y = 5;

    ch::AutotileResult autotile_res = ch::ShorelineAutotiler::evaluate_shoreline(world, bounds);
    std::cout << "Shoreline Autotiler evaluated " << autotile_res.edits.size() << " shoreline tile recipes in pilot scenario.\n";

    // Setup Camera
    ch::CameraState camera;
    camera.zoom = 0.85F;
    camera.pan_x = 0.0F;
    camera.pan_y = 0.0F;

    // 1. Render Base Terrain Map (preserving Water V2)
    ch::MapRenderer::render_map(renderer, &no_grid_base, terrain_textures, camera, 1400.0F, 900.0F);

    // 2. Render Water V2 Opaque Base Fill + Caustics for Water tiles
    ch::TextureAsset caustics_tex;
    load_asset(renderer, asset_root / "assets/terrain/coast_adjusted/water_caustics_01.png", caustics_tex);

    for (const auto& tile : doc.terrain_tiles()) {
        if (tile.texture.find("water") != std::string::npos) {
            ch::MapRenderer::render_tile_fill(renderer, tile.tile_x, tile.tile_y, camera, 1400.0F, 900.0F,
                SDL_FColor{108.0F / 255.0F, 196.0F / 255.0F, 207.0F / 255.0F, 1.0F});
            ch::MapRenderer::render_water_caustics_overlay_tile(renderer, caustics_tex, tile.tile_x, tile.tile_y, camera, 1400.0F, 900.0F);
        }
    }

    // 3. Render Derived Shoreline Piece Compositions
    for (const auto& edit : autotile_res.edits) {
        for (const auto piece : edit.recipe.pieces) {
            std::string piece_path = ch::ShorelineCatalog::get_piece_texture_path(piece, "coast_adjusted");
            auto [it, inserted] = loaded_assets.try_emplace(piece_path);
            if (inserted) {
                load_asset(renderer, asset_root / piece_path, it->second);
            }
            ch::MapRenderer::render_custom_terrain_tile(renderer, it->second, edit.tile.x, edit.tile.y, camera, 1400.0F, 900.0F);
        }
    }

    SDL_RenderPresent(renderer);
    bool saved = SDL_SaveBMP(canvas, output_path.string().c_str());

    std::cout << "Shoreline pilot render saved to " << output_path << (saved ? " [SUCCESS]" : " [FAILED]") << '\n';

    destroy_asset(caustics_tex);
    destroy_asset(no_grid_base);
    for (auto& [path, asset] : loaded_assets) destroy_asset(asset);
    SDL_DestroyRenderer(renderer);
    SDL_DestroySurface(canvas);
    SDL_Quit();

    return saved ? 0 : 8;
}
