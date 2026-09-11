#include "vehicle_system.h"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <fstream>
#include <deque>
#include <optional>
#include <sstream>
#include <unordered_map>

namespace {
std::string read_file(const std::filesystem::path& path) { std::ifstream input(path); std::ostringstream out; out << input.rdbuf(); return out.str(); }
std::optional<std::size_t> value_position(const std::string& json, std::string_view key) { const auto found = json.find("\"" + std::string(key) + "\""); if (found == std::string::npos) return std::nullopt; const auto colon = json.find(':', found); if (colon == std::string::npos) return std::nullopt; auto position = colon + 1; while (position < json.size() && std::isspace(static_cast<unsigned char>(json[position]))) ++position; return position; }
std::optional<std::string> string_value(const std::string& json, std::string_view key) { const auto position = value_position(json, key); if (!position || *position >= json.size() || json[*position] != '\"') return std::nullopt; const auto end = json.find('\"', *position + 1); return end == std::string::npos ? std::nullopt : std::optional(json.substr(*position + 1, end - *position - 1)); }
std::optional<int> int_value(const std::string& json, std::string_view key) { const auto position = value_position(json, key); if (!position) return std::nullopt; try { return std::stoi(json.substr(*position)); } catch (...) { return std::nullopt; } }
std::optional<float> float_value(const std::string& json, std::string_view key) { const auto position = value_position(json, key); if (!position) return std::nullopt; try { return std::stof(json.substr(*position)); } catch (...) { return std::nullopt; } }
std::optional<bool> bool_value(const std::string& json, std::string_view key) { const auto position = value_position(json, key); if (!position) return std::nullopt; if (json.compare(*position, 4, "true") == 0) return true; if (json.compare(*position, 5, "false") == 0) return false; return std::nullopt; }
}

const std::string& ServiceVehicleDefinition::sprite_for(const VehicleDirection direction) const { switch (direction) { case VehicleDirection::south: return sprite_south; case VehicleDirection::east: return sprite_east; case VehicleDirection::north: return sprite_north; case VehicleDirection::west: return sprite_west; } return sprite_south; }

bool ServiceVehicleCatalog::load_from_directory(const std::filesystem::path& directory) { definitions_.clear(); std::error_code error; for (const auto& entry : std::filesystem::recursive_directory_iterator(directory, error)) { if (error || !entry.is_regular_file() || entry.path().extension() != ".json") continue; const std::string json = read_file(entry.path()); ServiceVehicleDefinition definition; definition.id = string_value(json, "id").value_or(""); definition.display_name = string_value(json, "displayName").value_or(definition.id); definition.category = string_value(json, "category").value_or(""); definition.role = string_value(json, "role").value_or(""); definition.purchase_cost = int_value(json, "purchaseCost").value_or(0); definition.monthly_maintenance = int_value(json, "monthlyMaintenance").value_or(0); definition.move_speed = float_value(json, "moveSpeed").value_or(0.0F); definition.work_speed = float_value(json, "workSpeed").value_or(0.0F); definition.sprite_south = string_value(json, "spriteSouth").value_or(""); definition.sprite_east = string_value(json, "spriteEast").value_or(""); definition.sprite_north = string_value(json, "spriteNorth").value_or(""); definition.sprite_west = string_value(json, "spriteWest").value_or(""); definition.animation_set_id = string_value(json, "animationSet").value_or(definition.id); definition.requires_owned_farm_vehicle = bool_value(json, "requiresOwnedFarmVehicle").value_or(true); definition.work_tool = string_value(json, "workTool").value_or(""); definition.art_scale = float_value(json, "artScale").value_or(0.12F); definition.anchor_x = float_value(json, "anchorX").value_or(0.5F); definition.anchor_y = float_value(json, "anchorY").value_or(0.82F); if (!definition.id.empty() && definition.category == "farming_vehicle" && !definition.role.empty() && definition.move_speed > 0.0F && !definition.sprite_south.empty() && !definition.sprite_east.empty() && !definition.sprite_north.empty() && !definition.sprite_west.empty()) definitions_.push_back(std::move(definition)); } return !definitions_.empty(); }
const ServiceVehicleDefinition* ServiceVehicleCatalog::find(const std::string_view id) const { for (const auto& definition : definitions_) if (definition.id == id) return &definition; return nullptr; }
const std::vector<ServiceVehicleDefinition>& ServiceVehicleCatalog::definitions() const { return definitions_; }
bool ServiceVehicleManager::add(ServiceVehicleInstance instance, const ServiceVehicleCatalog& catalog) { const ServiceVehicleDefinition* definition = catalog.find(instance.vehicle_id); if (definition == nullptr) return false; instance.visual_x = instance.map_x; instance.visual_y = instance.map_y; instance.animation.animation_set_id = definition->animation_set_id; instances_.push_back(std::move(instance)); return true; }
bool ServiceVehicleManager::has_idle_vehicle_for_role(const std::string_view role, const ServiceVehicleCatalog& catalog) const { for (const auto& vehicle : instances_) { const auto* definition = catalog.find(vehicle.vehicle_id); if (vehicle.owned && vehicle.state == ServiceVehicleState::idle && definition != nullptr && definition->role == role) return true; } return false; }
std::string ServiceVehicleManager::tile_key(const int x, const int y) { return std::to_string(x) + ":" + std::to_string(y); }
bool ServiceVehicleManager::is_reserved(const int x, const int y) const { return reserved_tiles_.contains(tile_key(x, y)); }
bool ServiceVehicleManager::has_active_task() const { return !tasks_.empty(); }
std::vector<TileCoordinate> ServiceVehicleManager::find_route(const TileCoordinate& from, const TileCoordinate& to, const TraversableTile& traversable) const {
    if (from.x == to.x && from.y == to.y) return {};
    std::deque<TileCoordinate> frontier; frontier.push_back(from);
    std::unordered_map<std::string, TileCoordinate> previous;
    std::unordered_set<std::string> visited; visited.insert(tile_key(from.x, from.y));
    constexpr int max_search = 4096;
    const int offsets[][2] = {{1,0},{-1,0},{0,1},{0,-1}};
    while (!frontier.empty() && static_cast<int>(visited.size()) < max_search) {
        const auto current = frontier.front(); frontier.pop_front();
        for (const auto& offset : offsets) {
            const TileCoordinate next{current.x + offset[0], current.y + offset[1]};
            const auto key = tile_key(next.x, next.y);
            if (visited.contains(key) || (!traversable(next.x, next.y) && !(next.x == to.x && next.y == to.y))) continue;
            previous.emplace(key, current); visited.insert(key);
            if (next.x == to.x && next.y == to.y) {
                std::vector<TileCoordinate> result; TileCoordinate step = to;
                while (!(step.x == from.x && step.y == from.y)) { result.push_back(step); step = previous.at(tile_key(step.x, step.y)); }
                std::reverse(result.begin(), result.end()); return result;
            }
            frontier.push_back(next);
        }
    }
    return {};
}
bool ServiceVehicleManager::create_task(const std::string_view role, std::vector<TileCoordinate> tiles, const ServiceVehicleCatalog& catalog, const TraversableTile& traversable, std::string* assigned_vehicle_name) {
    if (tiles.empty()) return false;
    auto vehicle_it = std::find_if(instances_.begin(), instances_.end(), [&](const ServiceVehicleInstance& vehicle) { const auto* definition = catalog.find(vehicle.vehicle_id); return vehicle.owned && vehicle.state == ServiceVehicleState::idle && definition != nullptr && definition->role == role; });
    if (vehicle_it == instances_.end()) return false;
    for (const auto& tile : tiles) if (is_reserved(tile.x, tile.y)) return false;
    const TileCoordinate start{static_cast<int>(std::lround(vehicle_it->map_x)), static_cast<int>(std::lround(vehicle_it->map_y))};
    const auto route = find_route(start, tiles.front(), traversable);
    if (!(start.x == tiles.front().x && start.y == tiles.front().y) && route.empty()) return false;
    const std::size_t index = static_cast<std::size_t>(std::distance(instances_.begin(), vehicle_it));
    ServiceVehicleTask task; task.id = "farm_task_" + std::to_string(next_task_number_++); task.required_role = std::string(role); task.vehicle_index = index; task.tiles = std::move(tiles);
    for (const auto& tile : task.tiles) reserved_tiles_.insert(tile_key(tile.x, tile.y));
    vehicle_it->task_id = task.id; vehicle_it->route = route; vehicle_it->route_index = 0; vehicle_it->travel_progress = 0.0F; vehicle_it->work_progress = 0.0F; vehicle_it->state = route.empty() ? ServiceVehicleState::working : ServiceVehicleState::moving_to_job;
    if (assigned_vehicle_name != nullptr) *assigned_vehicle_name = catalog.find(vehicle_it->vehicle_id)->display_name;
    tasks_.push_back(std::move(task)); return true;
}
void ServiceVehicleManager::begin_return(ServiceVehicleInstance& vehicle, const ServiceVehicleCatalog&, const TraversableTile& traversable) {
    const TileCoordinate from{static_cast<int>(std::lround(vehicle.map_x)), static_cast<int>(std::lround(vehicle.map_y))}; const TileCoordinate home{static_cast<int>(std::lround(vehicle.origin_x)), static_cast<int>(std::lround(vehicle.origin_y))};
    vehicle.route = find_route(from, home, traversable); vehicle.route_index = 0; vehicle.travel_progress = 0.0F; vehicle.work_progress = 0.0F; vehicle.state = vehicle.route.empty() ? ServiceVehicleState::idle : ServiceVehicleState::returning; if (vehicle.state == ServiceVehicleState::idle) vehicle.task_id.clear();
}
bool ServiceVehicleManager::cancel_active_task(const ServiceVehicleCatalog& catalog, const TraversableTile& traversable) {
    if (tasks_.empty()) return false;
    const auto task = tasks_.front(); if (task.vehicle_index >= instances_.size()) return false;
    for (const auto& tile : task.tiles) reserved_tiles_.erase(tile_key(tile.x, tile.y));
    tasks_.erase(tasks_.begin()); begin_return(instances_[task.vehicle_index], catalog, traversable); return true;
}
void ServiceVehicleManager::update_tick(const float tick_seconds, const ServiceVehicleCatalog& catalog, const TraversableTile& traversable) {
    for (auto& vehicle : instances_) {
        const auto* definition = catalog.find(vehicle.vehicle_id); if (definition == nullptr) continue;
        if ((vehicle.state == ServiceVehicleState::moving_to_job || vehicle.state == ServiceVehicleState::returning) && vehicle.route_index < vehicle.route.size()) {
            vehicle.travel_progress += tick_seconds * definition->move_speed;
            while (vehicle.travel_progress >= 1.0F && vehicle.route_index < vehicle.route.size()) {
                const auto next = vehicle.route[vehicle.route_index++]; const int dx = next.x - static_cast<int>(std::lround(vehicle.map_x)); const int dy = next.y - static_cast<int>(std::lround(vehicle.map_y));
                if (std::abs(dx) >= std::abs(dy)) vehicle.direction = dx >= 0 ? VehicleDirection::east : VehicleDirection::west; else vehicle.direction = dy >= 0 ? VehicleDirection::south : VehicleDirection::north;
                vehicle.map_x = static_cast<float>(next.x); vehicle.map_y = static_cast<float>(next.y); vehicle.travel_progress -= 1.0F;
            }
            if (vehicle.route_index >= vehicle.route.size()) {
                if (vehicle.state == ServiceVehicleState::returning) { vehicle.state = ServiceVehicleState::idle; vehicle.task_id.clear(); }
                else vehicle.state = ServiceVehicleState::working;
            }
        }
        if (vehicle.state == ServiceVehicleState::working) {
            const auto task_it = std::find_if(tasks_.begin(), tasks_.end(), [&](const ServiceVehicleTask& task) { return task.id == vehicle.task_id; });
            if (task_it == tasks_.end()) { begin_return(vehicle, catalog, traversable); continue; }
            vehicle.work_progress += tick_seconds * definition->work_speed;
            if (vehicle.work_progress >= 1.0F) {
                vehicle.work_progress = 0.0F; const auto completed = task_it->tiles[task_it->next_tile++]; completed_tiles_.push_back(completed); reserved_tiles_.erase(tile_key(completed.x, completed.y));
                if (task_it->next_tile >= task_it->tiles.size()) { tasks_.erase(task_it); begin_return(vehicle, catalog, traversable); }
                else { const auto next = task_it->tiles[task_it->next_tile]; const TileCoordinate from{static_cast<int>(std::lround(vehicle.map_x)), static_cast<int>(std::lround(vehicle.map_y))}; vehicle.route = find_route(from, next, traversable); vehicle.route_index = 0; vehicle.state = vehicle.route.empty() ? ServiceVehicleState::working : ServiceVehicleState::moving_to_job; }
            }
        }
    }
}

void ServiceVehicleManager::interpolate_visual(const float frame_seconds) {
    const float interpolation = std::clamp(frame_seconds * 10.0F, 0.0F, 1.0F);
    for (auto& vehicle : instances_) {
        vehicle.visual_x += (vehicle.map_x - vehicle.visual_x) * interpolation;
        vehicle.visual_y += (vehicle.map_y - vehicle.visual_y) * interpolation;
    }
}

std::string_view ServiceVehicleManager::animation_state(const ServiceVehicleState state) {
    switch (state) {
        case ServiceVehicleState::idle: return "idle";
        case ServiceVehicleState::moving_to_job: return "moving";
        case ServiceVehicleState::working: return "working";
        case ServiceVehicleState::returning: return "returning";
    }
    return "idle";
}

void ServiceVehicleManager::update_animation(const float frame_seconds, const MobileAnimationCatalog& animations) {
    for (ServiceVehicleInstance& vehicle : instances_) {
        animations.update_player(vehicle.animation, animation_state(vehicle.state), vehicle.direction, frame_seconds);
    }
}

std::vector<MobileEntityRenderData> ServiceVehicleManager::render_entities(const ServiceVehicleCatalog& catalog,
                                                                            const MobileAnimationCatalog& animations) const {
    std::vector<MobileEntityRenderData> result;
    result.reserve(instances_.size());
    for (const ServiceVehicleInstance& vehicle : instances_) {
        const ServiceVehicleDefinition* definition = catalog.find(vehicle.vehicle_id);
        if (definition == nullptr) continue;
        MobileEntityRenderData entity;
        entity.spatial.logical_world_x = vehicle.map_x;
        entity.spatial.logical_world_y = vehicle.map_y;
        entity.spatial.logical_tile_x = static_cast<int>(std::lround(vehicle.map_x));
        entity.spatial.logical_tile_y = static_cast<int>(std::lround(vehicle.map_y));
        entity.spatial.visual_world_x = vehicle.visual_x;
        entity.spatial.visual_world_y = vehicle.visual_y;
        entity.spatial.direction = vehicle.direction;
        entity.logical_state = std::string(animation_state(vehicle.state));
        if (const std::string* frame = animations.current_frame(vehicle.animation)) entity.sprite_asset = *frame;
        else entity.sprite_asset = definition->sprite_for(vehicle.direction);
        entity.animation_set_id = definition->animation_set_id;
        entity.animation_clip_id = vehicle.animation.clip_id;
        entity.animation_frame_index = vehicle.animation.frame_index;
        entity.art_scale = definition->art_scale;
        entity.sprite_anchor_x = definition->anchor_x;
        entity.sprite_anchor_y = definition->anchor_y;
        result.push_back(std::move(entity));
    }
    return result;
}
std::vector<TileCoordinate> ServiceVehicleManager::take_completed_tiles() { auto result = std::move(completed_tiles_); completed_tiles_.clear(); return result; }
void ServiceVehicleManager::clear() { instances_.clear(); tasks_.clear(); reserved_tiles_.clear(); completed_tiles_.clear(); next_task_number_ = 1; }
const std::vector<ServiceVehicleInstance>& ServiceVehicleManager::instances() const { return instances_; }
