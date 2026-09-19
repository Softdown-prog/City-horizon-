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
#include "src/building_system.h"

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

} // namespace

int main(int argc, char** argv) {
    if (argc < 3) {
        std::cerr << "usage: shoreline_pilot_runtime <asset-root> <output-bmp> [scenario-json]\n";
        return 2;
    }
    const std::filesystem::path asset_root = argv[1];
    const std::filesystem::path output_path = argv[2];
    std::filesystem::path scenario_path = asset_root / "assets" / "scenarios" / "initial_city.json";
    if (argc >= 4) {
        scenario_path = argv[3];
    }

    auto doc_opt = ch::MapDocument::load_from_file(scenario_path.string());
    if (!doc_opt.has_value()) {
        std::cerr << "Failed to load map document: " << scenario_path << '\n';
        return 3;
    }
    ch::MapDocument doc = *doc_opt;

    if (!SDL_Init(SDL_INIT_VIDEO)) {
        std::cerr << "SDL_Init failed: " << SDL_GetError() << '\n';
        return 4;
    }
    SDL_Surface* canvas = SDL_CreateSurface(1280, 720, SDL_PIXELFORMAT_RGBA32);
    SDL_Renderer* renderer = canvas == nullptr ? nullptr : SDL_CreateSoftwareRenderer(canvas);
    if (!canvas || !renderer) {
        std::cerr << "SDL surface/renderer creation failed\n";
        return 5;
    }

    std::unordered_map<std::string, ch::TextureAsset> loaded_assets;

    // Setup Camera
    ch::CameraState camera;
    camera.zoom = 0.85F;
    camera.pan_x = 0.0F;
    camera.pan_y = 0.0F;
    camera.rotation = ch::CameraRotation::r0;

    const float vw = 1280.0F;
    const float vh = 720.0F;

    // Render World Terrain and Water via Shared Canonical Pipeline
    ch::MapRenderer::render_world_terrain_and_water(
        renderer,
        doc,
        [&loaded_assets, renderer, &asset_root](const std::filesystem::path& p) -> const ch::TextureAsset* {
            auto [it, inserted] = loaded_assets.try_emplace(p.string());
            if (inserted) {
                if (!load_asset(renderer, asset_root / p, it->second)) {
                    return nullptr;
                }
            }
            return &it->second;
        },
        asset_root,
        camera,
        vw,
        vh
    );

    for (const auto& r : doc.roads()) {
        std::string road_path = "assets/roads/straight_01.png";
        auto [it, inserted] = loaded_assets.try_emplace(road_path);
        if (inserted) {
            load_asset(renderer, asset_root / road_path, it->second);
        }
        if (it->second.texture != nullptr) {
            ch::MapRenderer::render_road_sprite(renderer, it->second, r.tile_x, r.tile_y, camera, vw, vh);
        }
    }

    for (const auto& b : doc.buildings()) {
        std::filesystem::path sprite_path = "assets/buildings/" + b.definition_id + "_lvl1.png";
        if (!std::filesystem::exists(asset_root / sprite_path)) {
            sprite_path = "assets/buildings/" + b.definition_id + ".png";
        }
        auto [it, inserted] = loaded_assets.try_emplace(sprite_path.string());
        if (inserted) {
            load_asset(renderer, asset_root / sprite_path, it->second);
        }
        if (it->second.texture != nullptr) {
            BuildingDefinition def;
            def.id = b.definition_id;
            def.footprint_width = 1;
            def.footprint_height = 1;

            BuildingInstance inst;
            inst.tile_x = b.tile_x;
            inst.tile_y = b.tile_y;

            ch::BuildingSpriteGeometry geom = ch::MapRenderer::building_sprite_geometry(def, inst, BuildingRotation::r0, it->second.source_width, it->second.source_height, camera, vw, vh);
            SDL_RenderTexture(renderer, it->second.texture, nullptr, &geom.sprite_bounds);
        }
    }

    SDL_RenderPresent(renderer);
    bool saved = SDL_SaveBMP(canvas, output_path.string().c_str());

    std::cout << "Water V2 runtime render saved to " << output_path << (saved ? " [SUCCESS]" : " [FAILED]") << '\n';

    for (auto& [path, asset] : loaded_assets) destroy_asset(asset);
    SDL_DestroyRenderer(renderer);
    SDL_DestroySurface(canvas);
    SDL_Quit();

    return saved ? 0 : 8;
}
