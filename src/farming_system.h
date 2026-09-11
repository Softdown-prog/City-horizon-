#pragma once

#include "simulation_clock.h"

#include <cstdint>
#include <filesystem>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

struct CropDefinition {
    std::string id;
    std::string display_name;
    // Preferred artwork: plant-only transparent sprites rendered over the
    // shared PreparedSoil layer. Every frame of a crop must share this canvas
    // and anchor so growth never shifts the plant on its tile.
    std::vector<std::string> stage_overlay_sprites;
    int overlay_canvas_width = 0;
    int overlay_canvas_height = 0;
    float overlay_anchor_x = 0.5F;
    float overlay_anchor_y = 0.5F;
    // Art-only scale relative to one logical field tile.  It provides a
    // visible soil margin between crops without changing tile ownership.
    float overlay_scale = 1.0F;
    // Temporary bridge for the original full-tile crop art. It is kept in one
    // data-driven fallback path only, never treated as the normal crop format.
    std::vector<std::string> legacy_composite_stage_sprites;
    int growth_days_total = 0;
    int harvest_yield = 0;
    std::string harvest_resource_id;
    std::string storage_class;
    std::string harvest_behavior = "return_to_prepared_soil";
    int regrow_stage = 0;
    int regrow_days = 0;
    int max_harvest_cycles = 0;
    bool returns_to_prepared_soil_after_harvest = true;
    [[nodiscard]] bool has_stage_overlays() const { return !stage_overlay_sprites.empty(); }
    [[nodiscard]] const std::vector<std::string>& active_stage_sprites() const {
        return has_stage_overlays() ? stage_overlay_sprites : legacy_composite_stage_sprites;
    }
    [[nodiscard]] int stage_count() const { return static_cast<int>(active_stage_sprites().size()); }
    [[nodiscard]] const std::string& thumbnail_path() const { return active_stage_sprites().front(); }
};

class CropCatalog {
public:
    bool load_from_directory(const std::filesystem::path& directory);
    [[nodiscard]] const CropDefinition* find(std::string_view id) const;
    [[nodiscard]] const std::vector<CropDefinition>& definitions() const;
private:
    std::vector<CropDefinition> definitions_;
};

enum class FarmTileState : std::uint8_t { prepared_soil, planted, ready_to_harvest };

struct FarmTile {
    int tile_x = 0;
    int tile_y = 0;
    FarmTileState state = FarmTileState::prepared_soil;
    std::string crop_id;
    int planted_day = 0;
    int stage = 0;
    int harvest_cycle_count = 0;
};

class FarmingSystem {
public:
    FarmingSystem(int map_min, int map_max);
    [[nodiscard]] bool is_occupied(int tile_x, int tile_y) const;
    [[nodiscard]] const FarmTile* tile_at(int tile_x, int tile_y) const;
    [[nodiscard]] bool prepare_soil(int tile_x, int tile_y);
    [[nodiscard]] bool plant(int tile_x, int tile_y, const CropDefinition& crop, const GameDate& date);
    [[nodiscard]] int harvest(int tile_x, int tile_y, const CropCatalog& crops, const GameDate& date);
    void set_storage_capacities(int general_capacity, int grain_capacity);
    void register_crop_definitions(const CropCatalog& crops);
    void register_resource_storage_classes(const std::unordered_map<std::string, std::string>& storage_classes);
    [[nodiscard]] int available_storage_for(const CropDefinition& crop) const;
    [[nodiscard]] int general_storage_capacity() const { return general_storage_capacity_; }
    [[nodiscard]] int grain_storage_capacity() const { return grain_storage_capacity_; }
    void on_day_changed(const GameDate& date, const CropCatalog& crops);
    // Retained for callers saved against the early agriculture API.
    void advance_days(const GameDate& date, const CropCatalog& crops);
    void clear();
    [[nodiscard]] bool restore_tile(FarmTile tile);
    void restore_inventory(std::unordered_map<std::string, int> inventory);
    [[nodiscard]] const std::vector<FarmTile>& tiles() const;
    [[nodiscard]] const std::unordered_map<std::string, int>& inventory() const;
    [[nodiscard]] int inventory_count(std::string_view crop_id) const;
    [[nodiscard]] bool try_remove_resource(std::string_view resource_id, int quantity);
    [[nodiscard]] int general_inventory_used() const;
    [[nodiscard]] int grain_inventory() const;
    [[nodiscard]] static int absolute_day(const GameDate& date);
private:
    [[nodiscard]] bool inside(int x, int y) const;
    [[nodiscard]] int key(int x, int y) const;
    int min_;
    int max_;
    std::vector<FarmTile> tiles_;
    std::unordered_map<int, std::size_t> indices_;
    std::unordered_map<std::string, int> inventory_;
    int general_storage_capacity_ = 20;
    int grain_storage_capacity_ = 0;
    std::unordered_map<std::string, std::string> resource_storage_classes_;
};
