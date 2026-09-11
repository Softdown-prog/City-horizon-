#include "farming_system.h"

#include <algorithm>
#include <cctype>
#include <fstream>
#include <optional>
#include <sstream>

namespace {
std::string read_file(const std::filesystem::path& path) { std::ifstream input(path); std::ostringstream out; out << input.rdbuf(); return out.str(); }
std::optional<std::size_t> value_position(const std::string& json, std::string_view key) {
    const auto found = json.find("\"" + std::string(key) + "\"");
    if (found == std::string::npos) return std::nullopt;
    const auto colon = json.find(':', found); if (colon == std::string::npos) return std::nullopt;
    auto pos = colon + 1; while (pos < json.size() && std::isspace(static_cast<unsigned char>(json[pos]))) ++pos; return pos;
}
std::optional<std::string> string_value(const std::string& json, std::string_view key) {
    const auto pos = value_position(json, key); if (!pos || *pos >= json.size() || json[*pos] != '\"') return std::nullopt;
    const auto end = json.find('\"', *pos + 1); return end == std::string::npos ? std::nullopt : std::optional(json.substr(*pos + 1, end - *pos - 1));
}
std::optional<int> int_value(const std::string& json, std::string_view key) {
    const auto pos = value_position(json, key); if (!pos) return std::nullopt; try { return std::stoi(json.substr(*pos)); } catch (...) { return std::nullopt; }
}
std::optional<float> float_value(const std::string& json, std::string_view key) {
    const auto pos = value_position(json, key); if (!pos) return std::nullopt; try { return std::stof(json.substr(*pos)); } catch (...) { return std::nullopt; }
}
std::optional<bool> bool_value(const std::string& json, std::string_view key) {
    const auto pos = value_position(json, key); if (!pos) return std::nullopt;
    if (json.compare(*pos, 4, "true") == 0) return true; if (json.compare(*pos, 5, "false") == 0) return false; return std::nullopt;
}
std::vector<std::string> string_array(const std::string& json, std::string_view key) {
    std::vector<std::string> values; const auto pos = value_position(json, key); if (!pos) return values;
    const auto end = json.find(']', *pos); if (*pos >= json.size() || json[*pos] != '[' || end == std::string::npos) return values;
    for (std::size_t at = *pos; (at = json.find('\"', at + 1)) != std::string::npos && at < end;) {
        const auto close = json.find('\"', at + 1); if (close == std::string::npos || close > end) break; values.push_back(json.substr(at + 1, close - at - 1)); at = close;
    } return values;
}
}

bool CropCatalog::load_from_directory(const std::filesystem::path& directory) {
    definitions_.clear(); std::error_code error;
    for (const auto& entry : std::filesystem::recursive_directory_iterator(directory, error)) {
        if (error || !entry.is_regular_file() || entry.path().extension() != ".json") continue;
        const std::string json = read_file(entry.path()); CropDefinition crop;
        crop.id = string_value(json, "id").value_or(""); crop.display_name = string_value(json, "displayName").value_or(crop.id);
        crop.stage_overlay_sprites = string_array(json, "stageOverlaySprites");
        crop.legacy_composite_stage_sprites = string_array(json, "legacyCompositeStageSprites");
        // Accept the v1 field as a legacy composite source so older crop JSON
        // files stay valid while artwork is migrated to transparent overlays.
        if (crop.legacy_composite_stage_sprites.empty() && crop.stage_overlay_sprites.empty()) {
            crop.legacy_composite_stage_sprites = string_array(json, "stageSprites");
        }
        crop.overlay_canvas_width = int_value(json, "overlayCanvasWidth").value_or(0);
        crop.overlay_canvas_height = int_value(json, "overlayCanvasHeight").value_or(0);
        crop.overlay_anchor_x = float_value(json, "overlayAnchorX").value_or(0.5F);
        crop.overlay_anchor_y = float_value(json, "overlayAnchorY").value_or(0.5F);
        crop.overlay_scale = float_value(json, "overlayScale").value_or(1.0F);
        crop.growth_days_total = int_value(json, "growthDaysTotal").value_or(0);
        crop.harvest_yield = int_value(json, "harvestYield").value_or(0);
        crop.harvest_resource_id = string_value(json, "harvestResourceId").value_or(crop.id);
        crop.storage_class = string_value(json, "storageClass").value_or("general");
        crop.harvest_behavior = string_value(json, "harvestBehavior").value_or("return_to_prepared_soil");
        crop.regrow_stage = int_value(json, "regrowStage").value_or(0);
        crop.regrow_days = int_value(json, "regrowDays").value_or(0);
        crop.max_harvest_cycles = int_value(json, "maxHarvestCycles").value_or(0);
        crop.returns_to_prepared_soil_after_harvest = bool_value(json, "returnsToPreparedSoilAfterHarvest").value_or(true);
        const int declared_stages = int_value(json, "stageCount").value_or(crop.stage_count());
        const bool valid_overlay_layout = !crop.has_stage_overlays() ||
            (crop.overlay_canvas_width > 0 && crop.overlay_canvas_height > 0 &&
             crop.overlay_anchor_x >= 0.0F && crop.overlay_anchor_x <= 1.0F &&
             crop.overlay_anchor_y >= 0.0F && crop.overlay_anchor_y <= 1.0F &&
             crop.overlay_scale > 0.0F && crop.overlay_scale <= 1.0F);
        if (!crop.id.empty() && crop.stage_count() > 0 && declared_stages == crop.stage_count() &&
            crop.growth_days_total > 0 && crop.harvest_yield > 0 && !crop.harvest_resource_id.empty() &&
            (crop.harvest_behavior == "return_to_prepared_soil" || crop.harvest_behavior == "regrow") && valid_overlay_layout) {
            definitions_.push_back(std::move(crop));
        }
    }
    return !definitions_.empty();
}
const CropDefinition* CropCatalog::find(std::string_view id) const { for (const auto& crop : definitions_) if (crop.id == id) return &crop; return nullptr; }
const std::vector<CropDefinition>& CropCatalog::definitions() const { return definitions_; }

FarmingSystem::FarmingSystem(int map_min, int map_max) : min_(map_min), max_(map_max) {}
bool FarmingSystem::inside(int x, int y) const { return x >= min_ && x <= max_ && y >= min_ && y <= max_; }
int FarmingSystem::key(int x, int y) const { return (y - min_) * (max_ - min_ + 1) + x - min_; }
bool FarmingSystem::is_occupied(int x, int y) const { return indices_.contains(key(x, y)); }
const FarmTile* FarmingSystem::tile_at(int x, int y) const { const auto found=indices_.find(key(x,y)); return found == indices_.end() ? nullptr : &tiles_[found->second]; }
bool FarmingSystem::prepare_soil(int x, int y) { if (!inside(x,y) || is_occupied(x,y)) return false; indices_[key(x,y)]=tiles_.size(); tiles_.push_back({x,y}); return true; }
int FarmingSystem::absolute_day(const GameDate& date) { return (date.year - 1) * 360 + (date.month - 1) * 30 + date.day; }
bool FarmingSystem::plant(int x, int y, const CropDefinition& crop, const GameDate& date) { auto* tile=const_cast<FarmTile*>(tile_at(x,y)); if (!tile || tile->state != FarmTileState::prepared_soil) return false; tile->state=FarmTileState::planted; tile->crop_id=crop.id; tile->planted_day=absolute_day(date); tile->stage=0; tile->harvest_cycle_count=0; return true; }
void FarmingSystem::on_day_changed(const GameDate& date, const CropCatalog& crops) { const int today=absolute_day(date); for (auto& tile:tiles_) { if (tile.state != FarmTileState::planted) continue; const auto* crop=crops.find(tile.crop_id); if (!crop) continue; const int elapsed=std::max(0,today-tile.planted_day); tile.stage=std::min(crop->stage_count()-1, elapsed*crop->stage_count()/crop->growth_days_total); if (elapsed >= crop->growth_days_total) { tile.stage=crop->stage_count()-1; tile.state=FarmTileState::ready_to_harvest; } } }
void FarmingSystem::advance_days(const GameDate& date, const CropCatalog& crops) { on_day_changed(date, crops); }
int FarmingSystem::available_storage_for(const CropDefinition& crop) const { int grain_used = 0; int all_used = 0; for (const auto& [resource, quantity] : inventory_) { all_used += quantity; if (const auto found = resource_storage_classes_.find(resource); found != resource_storage_classes_.end() && found->second == "grain") grain_used += quantity; } const int grain_free = crop.storage_class == "grain" ? std::max(0, grain_storage_capacity_ - grain_used) : 0; const int general_used = all_used - std::min(grain_used, grain_storage_capacity_); return std::max(0, general_storage_capacity_ - general_used) + grain_free; }
void FarmingSystem::set_storage_capacities(const int general_capacity, const int grain_capacity) { general_storage_capacity_ = std::max(0, general_capacity); grain_storage_capacity_ = std::max(0, grain_capacity); }
void FarmingSystem::register_crop_definitions(const CropCatalog& crops) { resource_storage_classes_.clear(); for (const CropDefinition& crop : crops.definitions()) resource_storage_classes_[crop.harvest_resource_id] = crop.storage_class; }
void FarmingSystem::register_resource_storage_classes(const std::unordered_map<std::string, std::string>& storage_classes) { resource_storage_classes_ = storage_classes; }
int FarmingSystem::harvest(int x, int y, const CropCatalog& crops, const GameDate& date) { auto* tile=const_cast<FarmTile*>(tile_at(x,y)); if (!tile || tile->state != FarmTileState::ready_to_harvest) return 0; const auto* crop=crops.find(tile->crop_id); if (!crop || available_storage_for(*crop) < crop->harvest_yield) return 0; inventory_[crop->harvest_resource_id]+=crop->harvest_yield; const int yield=crop->harvest_yield; ++tile->harvest_cycle_count; if (crop->harvest_behavior == "regrow" && (crop->max_harvest_cycles == 0 || tile->harvest_cycle_count < crop->max_harvest_cycles)) { tile->state=FarmTileState::planted; tile->stage=std::clamp(crop->regrow_stage, 0, crop->stage_count()-1); tile->planted_day=absolute_day(date) - (crop->growth_days_total - std::max(1, crop->regrow_days)); } else { tile->state=FarmTileState::prepared_soil; tile->crop_id.clear(); tile->planted_day=0; tile->stage=0; tile->harvest_cycle_count=0; } return yield; }
void FarmingSystem::clear() { tiles_.clear(); indices_.clear(); inventory_.clear(); }
bool FarmingSystem::restore_tile(FarmTile tile) { if (!inside(tile.tile_x,tile.tile_y) || is_occupied(tile.tile_x,tile.tile_y)) return false; indices_[key(tile.tile_x,tile.tile_y)]=tiles_.size(); tiles_.push_back(std::move(tile)); return true; }
void FarmingSystem::restore_inventory(std::unordered_map<std::string,int> inventory) { inventory_=std::move(inventory); }
const std::vector<FarmTile>& FarmingSystem::tiles() const { return tiles_; }
const std::unordered_map<std::string,int>& FarmingSystem::inventory() const { return inventory_; }
int FarmingSystem::inventory_count(std::string_view id) const { const auto found=inventory_.find(std::string(id)); return found==inventory_.end()?0:found->second; }
bool FarmingSystem::try_remove_resource(const std::string_view resource_id, const int quantity) { if (quantity <= 0) return false; const auto found = inventory_.find(std::string(resource_id)); if (found == inventory_.end() || found->second < quantity) return false; found->second -= quantity; if (found->second == 0) inventory_.erase(found); return true; }
int FarmingSystem::general_inventory_used() const { int total = 0; for (const auto& [resource, quantity] : inventory_) total += quantity; return total - std::min(grain_inventory(), grain_storage_capacity_); }
int FarmingSystem::grain_inventory() const { int total = 0; for (const auto& [resource, quantity] : inventory_) { const auto found = resource_storage_classes_.find(resource); if (found != resource_storage_classes_.end() && found->second == "grain") total += quantity; } return total; }
