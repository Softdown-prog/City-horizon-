#ifndef CITY_HORIZON_CH_RENDER_MAP_RENDERER_H
#define CITY_HORIZON_CH_RENDER_MAP_RENDERER_H

#include <SDL3/SDL.h>
#include <filesystem>
#include <string>
#include <functional>
#include <unordered_map>
#include <vector>

#include "src/ch_core/contracts.h"
#include "src/ch_core/grid.h"
#include "src/ch_core/projection.h"
#include "src/building_system.h"
#include "src/farming_system.h"
#include "src/land_system.h"
#include "src/road_system.h"
#include "src/road_visual_catalog.h"
#include "src/sidewalk_system.h"

#include <optional>
#include "src/ch_core/map_document.h"

#include "src/ch_render/overlay_catalog.h"
#include "src/ch_render/animated_prop_catalog.h"

namespace ch {

enum class Season { Normal, Spring, Summer, Autumn, Winter };

struct RenderContext {
    Season season = Season::Normal;
    float snow_coverage = 0.0F;      // [0.0 .. 1.0] - Sole driver for snow
    float wetness = 0.0F;            // Reserved
    bool diagnostic_overlay = false; // Visual diagnostic mode for permitted regions
};

struct TextureAsset {
    SDL_Texture* texture = nullptr;
    float source_width = 0.0F;
    float source_height = 0.0F;
};

struct BuildingSpriteGeometry {
    WorldPoint ground_world;
    SDL_FPoint screen_anchor;
    SDL_FRect sprite_bounds;
};

struct RenderGeometryRecord {
    std::string layer;
    std::string asset_id;
    int grid_x = 0;
    int grid_y = 0;
    float screen_x = 0.0F;
    float screen_y = 0.0F;
    float dest_w = 0.0F;
    float dest_h = 0.0F;
    float anchor_x = 0.0F;
    float anchor_y = 0.0F;
    float art_scale = 0.0F;
    float depth_key = 0.0F;
    int footprint_w = 0;
    int footprint_h = 0;
};

struct RenderGeometryDiff {
    bool match = true;
    std::string report;
};

struct RenderGeometrySignature {
    std::vector<RenderGeometryRecord> records;

    [[nodiscard]] std::string compute_hash() const;
};

[[nodiscard]] RenderGeometryDiff compare_signatures(const RenderGeometrySignature& game_sig,
                                                     const RenderGeometrySignature& forge_sig);

class MapRenderer {
public:
    static void render_tile_outline(SDL_Renderer* renderer, int x, int y, const CameraState& camera, float viewport_width, float viewport_height);

    static void render_footprint_outline(SDL_Renderer* renderer, const BuildingDefinition& definition, BuildingRotation rotation,
                                        int tile_x, int tile_y, const CameraState& camera, float viewport_width, float viewport_height,
                                        Uint8 red = 255, Uint8 green = 208, Uint8 blue = 92);

    static void render_tile_fill(SDL_Renderer* renderer, int tile_x, int tile_y, const CameraState& camera,
                                float viewport_width, float viewport_height, SDL_FColor color);

    static void render_road_tile(SDL_Renderer* renderer, int tile_x, int tile_y, const CameraState& camera,
                                float viewport_width, float viewport_height, SDL_FColor color);

    static void render_road_access_candidates(SDL_Renderer* renderer, const BuildingDefinition& definition,
                                              BuildingRotation rotation, int tile_x, int tile_y,
                                              const RoadManager& roads, const CameraState& camera,
                                              float viewport_width, float viewport_height);

    static void render_grass_tile(SDL_Renderer* renderer, const TextureAsset& grass, int x, int y,
                                 const CameraState& camera, float viewport_width, float viewport_height);

    static void render_custom_terrain_tile(SDL_Renderer* renderer, const TextureAsset& texture, int x, int y,
                                           const CameraState& camera, float viewport_width, float viewport_height);

    // Water is physically covered by the opaque base.  This method applies a
    // detail texture with UVs derived from world coordinates, so a shared
    // logical edge samples the same detail coordinates on both adjacent cells.
    static void render_water_caustics_overlay_tile(SDL_Renderer* renderer, const TextureAsset& overlay, int x, int y,
                                                   const CameraState& camera, float viewport_width, float viewport_height,
                                                   float world_period = 16.0F);

    static void render_map(SDL_Renderer* renderer, const TextureAsset* grass,
                           const std::unordered_map<std::uint64_t, const TextureAsset*>& scenario_terrain_textures,
                           const CameraState& camera, float viewport_width, float viewport_height);

    // Canonical shared world terrain, water V2, caustics, and shoreline autotile renderer.
    static void render_world_terrain_and_water(SDL_Renderer* renderer, const MapDocument& document,
                                               const std::function<const TextureAsset*(const std::filesystem::path&)>& find_texture,
                                               const std::filesystem::path& asset_root, const CameraState& camera,
                                               float viewport_width, float viewport_height, float render_time = 0.0F);

    static void render_road_sprite(SDL_Renderer* renderer, const TextureAsset& texture, int tile_x, int tile_y,
                                  const CameraState& camera, float viewport_width, float viewport_height);

    static void render_roads(SDL_Renderer* renderer, const RoadManager& roads, const RoadVisualCatalog& visuals,
                            const std::function<const TextureAsset*(const std::filesystem::path&)>& find_texture,
                            const std::filesystem::path& asset_root, const CameraState& camera,
                            float viewport_width, float viewport_height);

    static void render_sidewalks(SDL_Renderer* renderer, const SidewalkManager& sidewalks,
                                const std::function<const TextureAsset*(const std::filesystem::path&)>& find_texture,
                                const std::filesystem::path& asset_root, const CameraState& camera,
                                float viewport_width, float viewport_height);

    static BuildingSpriteGeometry building_sprite_geometry(const BuildingDefinition& definition,
                                                          const BuildingInstance& instance,
                                                          BuildingRotation visual_rotation,
                                                          float source_width, float source_height,
                                                          const CameraState& camera,
                                                          float viewport_width, float viewport_height);

    static void render_building(SDL_Renderer* renderer, const BuildingDefinition& definition, const BuildingInstance& instance,
                                BuildingRotation visual_rotation, SDL_Texture* texture, float source_width, float source_height,
                                const CameraState& camera, float viewport_width, float viewport_height,
                                Uint8 alpha = 255, Uint8 red = 255, Uint8 green = 255, Uint8 blue = 255);

    static void render_buildings(SDL_Renderer* renderer, const BuildingManager& manager, const BuildingCatalog& catalog,
                                const LandManager& lands,
                                const std::function<const TextureAsset*(const std::filesystem::path&)>& find_texture,
                                const std::filesystem::path& asset_root,
                                const CameraState& camera, float viewport_width, float viewport_height);

    static void render_land_overlays(SDL_Renderer* renderer, const LandManager& lands, const LandParcel* hovered_parcel,
                                     bool land_mode, const CameraState& camera, float viewport_width, float viewport_height);

    static void render_farming(SDL_Renderer* renderer, const FarmingSystem& farming, const CropCatalog& crops,
                               const std::function<const TextureAsset*(const std::filesystem::path&)>& find_texture,
                               const std::filesystem::path& root, const CameraState& camera,
                               float viewport_width, float viewport_height);

    static void render_farming(SDL_Renderer* renderer, const FarmingSystem& farming, const CropCatalog& crops,
                               const std::unordered_map<std::string, TextureAsset>& texture_lookup,
                               const std::filesystem::path& root, const CameraState& camera,
                               float viewport_width, float viewport_height);

    static RenderGeometrySignature compute_geometry_signature(const BuildingManager& manager, const BuildingCatalog& catalog,
                                                              const CameraState& camera, float viewport_width, float viewport_height);

    static RenderGeometrySignature compute_geometry_signature(const MapDocument& document, const BuildingCatalog& catalog,
                                                              const CameraState& camera, float viewport_width, float viewport_height);
};

class MapForgeNativeViewport {
public:
    MapForgeNativeViewport() = default;
    ~MapForgeNativeViewport();

    MapForgeNativeViewport(const MapForgeNativeViewport&) = delete;
    MapForgeNativeViewport& operator=(const MapForgeNativeViewport&) = delete;

    bool initialize(void* win32_hwnd, int physical_width, int physical_height, const std::string& asset_root_path);
    bool initialize_offscreen(int physical_width, int physical_height, const std::string& asset_root_path);
    bool save_frame_to_png(const std::string& filepath);
    void resize(int physical_width, int physical_height);
    void set_camera(const CameraState& camera);
    bool load_map_document(const MapDocument& document);
    void set_view_mode(int mode) { view_mode_ = mode; }
    [[nodiscard]] int view_mode() const { return view_mode_; }

    void set_active_channels(uint32_t channel_bitmask) { active_channels_ = channel_bitmask; }
    [[nodiscard]] uint32_t active_channels() const { return active_channels_; }

    void set_channel_opacity(float opacity) { channel_opacity_ = opacity; }
    [[nodiscard]] float channel_opacity() const { return channel_opacity_; }

    void request_frame_capture(const std::string& filepath) { pending_capture_path_ = filepath; }

    void set_render_context(const RenderContext& context) { render_context_ = context; }
    [[nodiscard]] const RenderContext& render_context() const { return render_context_; }

    void set_prop_phase(float phase) { prop_phase_ = phase; }
    [[nodiscard]] float prop_phase() const { return prop_phase_; }

    OverlayCatalog& overlay_catalog() { return overlay_catalog_; }
    [[nodiscard]] const OverlayCatalog& overlay_catalog() const { return overlay_catalog_; }

    AnimatedPropCatalog& animated_prop_catalog() { return animated_prop_catalog_; }
    [[nodiscard]] const AnimatedPropCatalog& animated_prop_catalog() const { return animated_prop_catalog_; }

    void reload_asset_catalogs();
    void set_hover_tile(int tile_x, int tile_y, bool enabled) {
        hover_tile_x_ = tile_x;
        hover_tile_y_ = tile_y;
        hover_enabled_ = enabled;
    }
    void set_hover_brush_radius(int radius) { hover_brush_radius_ = std::max(0, radius); }

    void render_frame();
    [[nodiscard]] RenderGeometrySignature compute_geometry_signature(const BuildingCatalog& catalog) const;
    void shutdown();

    [[nodiscard]] bool is_initialized() const { return window_ != nullptr && renderer_ != nullptr; }

private:
    SDL_Window* window_ = nullptr;
    SDL_Renderer* renderer_ = nullptr;
    SDL_Surface* offscreen_surface_ = nullptr;
    CameraState camera_{};
    RenderContext render_context_{};
    OverlayCatalog overlay_catalog_{};
    AnimatedPropCatalog animated_prop_catalog_{};
    float prop_phase_ = 0.0F;
    int physical_width_ = 800;
    int physical_height_ = 600;
    std::filesystem::path asset_root_;
    std::optional<MapDocument> current_document_;
    std::unordered_map<std::string, TextureAsset> texture_cache_;
    std::unordered_map<std::string, TextureAsset> overlay_texture_cache_;
    int view_mode_ = 0; // 0 = ART, 1 = LOGIC, 2 = ART_AND_LOGIC
    uint32_t active_channels_ = 0x1FFF; // All channels active by default
    float channel_opacity_ = 0.75F;
    std::optional<std::string> pending_capture_path_;

    bool hover_enabled_ = false;
    int hover_tile_x_ = 0;
    int hover_tile_y_ = 0;
    int hover_brush_radius_ = 0;

    const TextureAsset* find_texture(const std::filesystem::path& relative_path);
    const TextureAsset* find_or_create_overlay_texture(const std::string& asset_id, const OverlayDefinition& def, const std::string& overlay_type);
    void clear_textures();
};

} // namespace ch

#endif // CITY_HORIZON_CH_RENDER_MAP_RENDERER_H
