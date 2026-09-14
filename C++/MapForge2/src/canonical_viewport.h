#pragma once

#include "src/ch_core/map_document.h"
#include "src/ch_core/projection.h"
#include "src/ch_render/map_renderer.h"

#include <filesystem>
#include <optional>
#include <string>
#include <unordered_map>

namespace ch::editor {

// Editor-only adapter around the canonical City Horizon renderer.
// Qt owns the native child window, input and event loop. SDL3 owns only the
// rendering context attached to that existing HWND.
class CanonicalViewport final {
public:
    CanonicalViewport() = default;
    ~CanonicalViewport();

    CanonicalViewport(const CanonicalViewport&) = delete;
    CanonicalViewport& operator=(const CanonicalViewport&) = delete;

    bool initialize(void* nativeWindowHandle, int physicalWidth, int physicalHeight,
                    const std::filesystem::path& assetRoot, std::string* error = nullptr);
    void shutdown();

    void resize(int physicalWidth, int physicalHeight);
    void setCamera(const CameraState& camera);
    bool loadDocument(const MapDocument& document);
    void setHover(int tileX, int tileY, int brushSize, bool visible);
    void renderFrame();

    [[nodiscard]] bool isInitialized() const { return window_ != nullptr && renderer_ != nullptr; }

private:
    const TextureAsset* findTexture(const std::filesystem::path& path);
    void clearTextures();
    void renderRoads(float viewportWidth, float viewportHeight);
    void renderBuildings(float viewportWidth, float viewportHeight);
    void renderHover(float viewportWidth, float viewportHeight);

    SDL_Window* window_ = nullptr;
    SDL_Renderer* renderer_ = nullptr;
    CameraState camera_{};
    int physical_width_ = 1;
    int physical_height_ = 1;
    std::filesystem::path asset_root_;
    std::optional<MapDocument> document_;
    std::unordered_map<std::string, TextureAsset> texture_cache_;
    BuildingCatalog building_catalog_;
    RoadVisualCatalog road_visuals_;

    bool hover_visible_ = false;
    int hover_x_ = 0;
    int hover_y_ = 0;
    int hover_brush_size_ = 1;
};

} // namespace ch::editor
