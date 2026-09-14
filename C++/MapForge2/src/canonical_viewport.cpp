#include "canonical_viewport.h"

#include "src/ch_core/contracts.h"
#include "src/road_system.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <vector>

namespace ch::editor {
namespace {

BuildingRotation visualRotation(const BuildingDefinition& definition,
                                const BuildingRotation logicalRotation,
                                const CameraRotation cameraRotation) {
    const int value = (static_cast<int>(logicalRotation) - static_cast<int>(cameraRotation) + 4) % 4;
    const auto desired = static_cast<BuildingRotation>(value);
    return definition.supports_rotation(desired) ? desired : logicalRotation;
}

BuildingRotation safeRotation(const int value) {
    const int normalized = ((value % 4) + 4) % 4;
    return static_cast<BuildingRotation>(normalized);
}

} // namespace

CanonicalViewport::~CanonicalViewport() {
    shutdown();
}

bool CanonicalViewport::initialize(void* nativeWindowHandle, const int physicalWidth, const int physicalHeight,
                                   const std::filesystem::path& assetRoot, std::string* error) {
    shutdown();

#if !defined(_WIN32)
    if (error != nullptr) {
        *error = "The canonical embedded viewport pilot currently requires a Win32 Qt child window.";
    }
    (void)nativeWindowHandle;
    (void)physicalWidth;
    (void)physicalHeight;
    (void)assetRoot;
    return false;
#else
    if (nativeWindowHandle == nullptr) {
        if (error != nullptr) *error = "Qt did not provide a native Win32 viewport handle.";
        return false;
    }

    asset_root_ = assetRoot;
    if (!std::filesystem::exists(asset_root_ / "assets")) {
        if (error != nullptr) {
            *error = "Canonical renderer assets were not found next to the Studio executable: "
                   + (asset_root_ / "assets").string();
        }
        return false;
    }

    physical_width_ = std::max(1, physicalWidth);
    physical_height_ = std::max(1, physicalHeight);

    if (!SDL_WasInit(SDL_INIT_VIDEO) && !SDL_Init(SDL_INIT_VIDEO)) {
        if (error != nullptr) *error = std::string("SDL3 video initialization failed: ") + SDL_GetError();
        return false;
    }

    const SDL_PropertiesID properties = SDL_CreateProperties();
    SDL_SetPointerProperty(properties, SDL_PROP_WINDOW_CREATE_WIN32_HWND_POINTER, nativeWindowHandle);
    SDL_SetNumberProperty(properties, SDL_PROP_WINDOW_CREATE_WIDTH_NUMBER, physical_width_);
    SDL_SetNumberProperty(properties, SDL_PROP_WINDOW_CREATE_HEIGHT_NUMBER, physical_height_);
    window_ = SDL_CreateWindowWithProperties(properties);
    SDL_DestroyProperties(properties);

    if (window_ == nullptr) {
        if (error != nullptr) *error = std::string("SDL3 could not wrap the Qt viewport HWND: ") + SDL_GetError();
        return false;
    }

    renderer_ = SDL_CreateRenderer(window_, nullptr);
    if (renderer_ == nullptr) {
        if (error != nullptr) *error = std::string("SDL3 renderer creation failed: ") + SDL_GetError();
        SDL_DestroyWindow(window_);
        window_ = nullptr;
        return false;
    }

    (void)building_catalog_.load_from_directory(asset_root_ / "assets" / "definitions");
    (void)road_visuals_.load_from_file(asset_root_ / "assets" / "definitions" / "road_visual_catalog.json");
    return true;
#endif
}

void CanonicalViewport::shutdown() {
    clearTextures();
    document_.reset();
    hover_visible_ = false;

    if (renderer_ != nullptr) {
        SDL_DestroyRenderer(renderer_);
        renderer_ = nullptr;
    }
    if (window_ != nullptr) {
        // window_ wraps a Qt-owned external HWND. SDL releases its wrapper;
        // ownership/lifetime of the actual child window remains with Qt.
        SDL_DestroyWindow(window_);
        window_ = nullptr;
    }
}

void CanonicalViewport::resize(const int physicalWidth, const int physicalHeight) {
    physical_width_ = std::max(1, physicalWidth);
    physical_height_ = std::max(1, physicalHeight);
}

void CanonicalViewport::setCamera(const CameraState& camera) {
    camera_ = camera;
}

bool CanonicalViewport::loadDocument(const MapDocument& document) {
    document_ = document;
    return true;
}

void CanonicalViewport::setHover(const int tileX, const int tileY, const int brushSize, const bool visible) {
    hover_x_ = tileX;
    hover_y_ = tileY;
    hover_brush_size_ = brushSize <= 1 ? 1 : (brushSize <= 3 ? 3 : 5);
    hover_visible_ = visible;
}

const TextureAsset* CanonicalViewport::findTexture(const std::filesystem::path& path) {
    if (renderer_ == nullptr || path.empty()) return nullptr;

    const std::filesystem::path fullPath = path.is_absolute() ? path : (asset_root_ / path);
    const std::string key = fullPath.lexically_normal().generic_string();
    if (const auto found = texture_cache_.find(key); found != texture_cache_.end()) {
        return &found->second;
    }

    SDL_Surface* surface = SDL_LoadPNG(fullPath.string().c_str());
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

void CanonicalViewport::clearTextures() {
    for (auto& [_, asset] : texture_cache_) {
        if (asset.texture != nullptr) SDL_DestroyTexture(asset.texture);
    }
    texture_cache_.clear();
}

void CanonicalViewport::renderRoads(const float viewportWidth, const float viewportHeight) {
    if (!document_.has_value()) return;

    RoadManager roads(contracts::kMapMin, contracts::kMapMax);
    for (const auto& road : document_->roads()) {
        (void)roads.place_tile(road.tile_x, road.tile_y);
    }

    MapRenderer::render_roads(
        renderer_, roads, road_visuals_,
        [this](const std::filesystem::path& path) { return findTexture(path); },
        {}, camera_, viewportWidth, viewportHeight);
}

void CanonicalViewport::renderBuildings(const float viewportWidth, const float viewportHeight) {
    if (!document_.has_value()) return;

    std::vector<const BuildingInstanceEntry*> entries;
    entries.reserve(document_->buildings().size());
    for (const auto& entry : document_->buildings()) entries.push_back(&entry);

    std::sort(entries.begin(), entries.end(), [this](const BuildingInstanceEntry* left, const BuildingInstanceEntry* right) {
        const BuildingDefinition* leftDefinition = building_catalog_.find(left->definition_id);
        const BuildingDefinition* rightDefinition = building_catalog_.find(right->definition_id);

        const BuildingRotation leftRotation = safeRotation(left->rotation);
        const BuildingRotation rightRotation = safeRotation(right->rotation);
        const BuildingFootprint leftFootprint = leftDefinition == nullptr
            ? BuildingFootprint{}
            : rotated_footprint(*leftDefinition, leftRotation);
        const BuildingFootprint rightFootprint = rightDefinition == nullptr
            ? BuildingFootprint{}
            : rotated_footprint(*rightDefinition, rightRotation);

        const WorldPoint leftGround = building_visual_ground_world(
            left->tile_x, left->tile_y, leftFootprint.width, leftFootprint.height, camera_.rotation);
        const WorldPoint rightGround = building_visual_ground_world(
            right->tile_x, right->tile_y, rightFootprint.width, rightFootprint.height, camera_.rotation);
        const float leftDepth = camera_depth_key(leftGround.x, leftGround.y, camera_);
        const float rightDepth = camera_depth_key(rightGround.x, rightGround.y, camera_);
        return leftDepth == rightDepth ? left->instance_id < right->instance_id : leftDepth < rightDepth;
    });

    for (const BuildingInstanceEntry* entry : entries) {
        const BuildingDefinition* definition = building_catalog_.find(entry->definition_id);
        if (definition == nullptr) continue;

        BuildingInstance instance;
        instance.instance_id = static_cast<std::uint64_t>(entry->instance_id);
        instance.definition_id = entry->definition_id;
        instance.tile_x = entry->tile_x;
        instance.tile_y = entry->tile_y;
        instance.rotation = safeRotation(entry->rotation);
        instance.current_level = 1;

        const BuildingRotation visual = visualRotation(*definition, instance.rotation, camera_.rotation);
        const TextureAsset* texture = findTexture(definition->texture_path_for(visual, instance.current_level));
        if (texture == nullptr) continue;

        MapRenderer::render_building(
            renderer_, *definition, instance, visual,
            texture->texture, texture->source_width, texture->source_height,
            camera_, viewportWidth, viewportHeight);
    }
}

void CanonicalViewport::renderHover(const float viewportWidth, const float viewportHeight) {
    if (!hover_visible_) return;

    const int radius = (hover_brush_size_ - 1) / 2;
    SDL_SetRenderDrawBlendMode(renderer_, SDL_BLENDMODE_BLEND);
    for (int y = hover_y_ - radius; y <= hover_y_ + radius; ++y) {
        for (int x = hover_x_ - radius; x <= hover_x_ + radius; ++x) {
            MapRenderer::render_tile_fill(renderer_, x, y, camera_, viewportWidth, viewportHeight,
                                          SDL_FColor{1.0F, 0.82F, 0.28F, 0.14F});
            SDL_SetRenderDrawColor(renderer_, 255, 210, 72, 255);
            MapRenderer::render_tile_outline(renderer_, x, y, camera_, viewportWidth, viewportHeight);
        }
    }
}

void CanonicalViewport::renderFrame() {
    if (renderer_ == nullptr) return;

    int width = physical_width_;
    int height = physical_height_;
    (void)SDL_GetRenderOutputSize(renderer_, &width, &height);
    const float viewportWidth = static_cast<float>(std::max(1, width));
    const float viewportHeight = static_cast<float>(std::max(1, height));

    const TextureAsset* grass = findTexture("assets/terrain/grass_isometric_01.png");
    std::unordered_map<std::uint64_t, const TextureAsset*> terrainTextures;
    if (document_.has_value()) {
        for (const auto& terrain : document_->terrain_tiles()) {
            if (terrain.texture.empty()) continue;
            if (const TextureAsset* texture = findTexture(terrain.texture)) {
                terrainTextures[tile_key(terrain.tile_x, terrain.tile_y)] = texture;
            }
        }
    }

    MapRenderer::render_map(renderer_, grass, terrainTextures, camera_, viewportWidth, viewportHeight);
    renderRoads(viewportWidth, viewportHeight);
    renderBuildings(viewportWidth, viewportHeight);
    renderHover(viewportWidth, viewportHeight);
    SDL_RenderPresent(renderer_);
}

} // namespace ch::editor
