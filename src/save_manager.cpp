#include "save_manager.h"

#include "building_system.h"
#include "economy_system.h"
#include "farming_system.h"
#include "land_system.h"
#include "mission_system.h"
#include "population_system.h"
#include "road_system.h"
#include "simulation_clock.h"
#include "sidewalk_system.h"
#include "vehicle_system.h"

#include <charconv>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <optional>
#include <sstream>
#include <string_view>
#include <system_error>
#include <vector>
#include <unordered_map>

// Save snapshots restore the fiscal marker with the rest of city state.

namespace {

struct SaveSnapshot {
    std::int64_t funds = 0;
    GameDate date;
    SimulationSpeed speed = SimulationSpeed::speed1;
    std::uint64_t next_building_instance_id = 1;
    std::uint32_t current_population = 0;
    int last_property_tax_year = 0;
    int months_without_power = 0;
    int crisis_recovery_month = 0;
    std::vector<BuildingInstance> buildings;
    std::vector<TileCoordinate> roads;
    std::vector<SidewalkTile> sidewalks;
    std::vector<FarmTile> farming_tiles;
    std::unordered_map<std::string, int> agricultural_inventory;
    std::vector<std::uint32_t> owned_parcel_ids;
    std::vector<ServiceVehicleInstance> vehicles;
    std::vector<std::string> completed_missions;
};

[[nodiscard]] std::string read_file(const std::filesystem::path& path) {
    std::ifstream input(path, std::ios::binary);
    if (!input) {
        return {};
    }
    std::ostringstream content;
    content << input.rdbuf();
    return content.str();
}

[[nodiscard]] std::size_t skip_whitespace(const std::string_view text, std::size_t position) {
    while (position < text.size() && (text[position] == ' ' || text[position] == '\t' ||
                                     text[position] == '\r' || text[position] == '\n')) {
        ++position;
    }
    return position;
}

[[nodiscard]] std::optional<std::size_t> value_position(const std::string_view json, const std::string_view key) {
    const std::string quoted_key = "\"" + std::string(key) + "\"";
    const std::size_t key_position = json.find(quoted_key);
    if (key_position == std::string_view::npos) {
        return std::nullopt;
    }
    const std::size_t colon = json.find(':', key_position + quoted_key.size());
    return colon == std::string_view::npos ? std::nullopt : std::optional(skip_whitespace(json, colon + 1));
}

template <typename Number>
[[nodiscard]] std::optional<Number> json_number(const std::string_view json, const std::string_view key) {
    const auto position = value_position(json, key);
    if (!position || *position >= json.size()) {
        return std::nullopt;
    }
    Number result{};
    const char* first = json.data() + *position;
    const char* last = json.data() + json.size();
    const auto parsed = std::from_chars(first, last, result);
    return parsed.ec == std::errc{} && parsed.ptr != first ? std::optional(result) : std::nullopt;
}

[[nodiscard]] std::optional<std::string> json_string(const std::string_view json, const std::string_view key) {
    const auto position = value_position(json, key);
    if (!position || *position >= json.size() || json[*position] != '\"') {
        return std::nullopt;
    }
    std::string result;
    bool escaped = false;
    for (std::size_t index = *position + 1; index < json.size(); ++index) {
        const char character = json[index];
        if (escaped) {
            switch (character) {
                case '\\': result += '\\'; break;
                case '\"': result += '\"'; break;
                case 'n': result += '\n'; break;
                case 'r': result += '\r'; break;
                case 't': result += '\t'; break;
                default: return std::nullopt;
            }
            escaped = false;
        } else if (character == '\\') {
            escaped = true;
        } else if (character == '\"') {
            return result;
        } else {
            result += character;
        }
    }
    return std::nullopt;
}

[[nodiscard]] std::optional<std::string_view> json_container(const std::string_view json, const std::string_view key,
                                                              const char opening, const char closing) {
    const auto position = value_position(json, key);
    if (!position || *position >= json.size() || json[*position] != opening) {
        return std::nullopt;
    }
    int depth = 0;
    bool in_string = false;
    bool escaped = false;
    for (std::size_t index = *position; index < json.size(); ++index) {
        const char character = json[index];
        if (in_string) {
            if (escaped) {
                escaped = false;
            } else if (character == '\\') {
                escaped = true;
            } else if (character == '\"') {
                in_string = false;
            }
            continue;
        }
        if (character == '\"') {
            in_string = true;
        } else if (character == opening) {
            ++depth;
        } else if (character == closing && --depth == 0) {
            return json.substr(*position, index - *position + 1);
        }
    }
    return std::nullopt;
}

[[nodiscard]] std::optional<std::vector<std::string_view>> json_object_array(const std::string_view json,
                                                                                const std::string_view key) {
    const auto array = json_container(json, key, '[', ']');
    if (!array) {
        return std::nullopt;
    }
    std::vector<std::string_view> result;
    int depth = 0;
    bool in_string = false;
    bool escaped = false;
    std::size_t object_start = 0;
    for (std::size_t index = 1; index + 1 < array->size(); ++index) {
        const char character = (*array)[index];
        if (in_string) {
            if (escaped) escaped = false;
            else if (character == '\\') escaped = true;
            else if (character == '\"') in_string = false;
            continue;
        }
        if (character == '\"') in_string = true;
        else if (character == '{') {
            if (depth++ == 0) object_start = index;
        } else if (character == '}') {
            if (--depth < 0) return std::nullopt;
            if (depth == 0) result.push_back(array->substr(object_start, index - object_start + 1));
        } else if (character != ',' && character != ' ' && character != '\t' && character != '\r' && character != '\n' && depth == 0) {
            return std::nullopt;
        }
    }
    return depth == 0 && !in_string ? std::optional(result) : std::nullopt;
}

template <typename Number>
[[nodiscard]] std::optional<std::vector<Number>> json_number_array(const std::string_view json, const std::string_view key) {
    const auto array = json_container(json, key, '[', ']');
    if (!array) {
        return std::nullopt;
    }
    std::vector<Number> result;
    std::size_t position = 1;
    while (true) {
        position = skip_whitespace(*array, position);
        if (position >= array->size() - 1) {
            return result;
        }
        Number number{};
        const char* first = array->data() + position;
        const char* last = array->data() + array->size() - 1;
        const auto parsed = std::from_chars(first, last, number);
        if (parsed.ec != std::errc{} || parsed.ptr == first) {
            return std::nullopt;
        }
        result.push_back(number);
        position = skip_whitespace(*array, static_cast<std::size_t>(parsed.ptr - array->data()));
        if (position == array->size() - 1) {
            return result;
        }
        if (position > array->size() - 1) {
            return std::nullopt;
        }
        if ((*array)[position] == ',') {
            ++position;
            continue;
        }
        return (*array)[position] == ']' ? std::optional(result) : std::nullopt;
    }
}

[[nodiscard]] std::optional<std::vector<std::string>> json_string_array(const std::string_view json, const std::string_view key) {
    const auto array = json_container(json, key, '[', ']');
    if (!array) {
        return std::nullopt;
    }
    std::vector<std::string> result;
    std::size_t position = 1;
    while (true) {
        position = skip_whitespace(*array, position);
        if (position >= array->size() - 1) {
            return result;
        }
        if ((*array)[position] != '"') {
            return std::nullopt;
        }
        std::string str;
        bool escaped = false;
        std::size_t index = position + 1;
        bool found_quote = false;
        for (; index < array->size() - 1; ++index) {
            const char c = (*array)[index];
            if (escaped) {
                switch (c) {
                    case '\\': str += '\\'; break;
                    case '"': str += '"'; break;
                    case 'n': str += '\n'; break;
                    case 'r': str += '\r'; break;
                    case 't': str += '\t'; break;
                    default: return std::nullopt;
                }
                escaped = false;
            } else if (c == '\\') {
                escaped = true;
            } else if (c == '"') {
                found_quote = true;
                break;
            } else {
                str += c;
            }
        }
        if (!found_quote) {
            return std::nullopt;
        }
        result.push_back(str);
        position = skip_whitespace(*array, index + 1);
        if (position >= array->size() - 1) {
            return result;
        }
        if ((*array)[position] == ',') {
            ++position;
            continue;
        }
        return (*array)[position] == ']' ? std::optional(result) : std::nullopt;
    }
}

[[nodiscard]] bool parse_snapshot(const std::string_view json, SaveSnapshot& snapshot, std::string& error) {
    const auto version = json_number<int>(json, "saveVersion");
    if (!version) {
        error = "saveVersion is missing or invalid";
        return false;
    }
    if (*version < 1 || *version > SaveManager::kSaveVersion) {
        error = "unsupported saveVersion " + std::to_string(*version);
        return false;
    }
    const auto funds = json_number<std::int64_t>(json, "cityFunds");
    const auto next_id = json_number<std::uint64_t>(json, "nextBuildingInstanceId");
    const auto simulation = json_container(json, "simulation", '{', '}');
    if (!funds || !next_id || !simulation) {
        error = "required city state is missing";
        return false;
    }
    const auto day = json_number<int>(*simulation, "day");
    const auto month = json_number<int>(*simulation, "month");
    const auto year = json_number<int>(*simulation, "year");
    const auto speed_value = json_number<int>(*simulation, "speed");
    if (!day || !month || !year || !speed_value || *next_id == 0 || *speed_value < 0 || *speed_value > 3) {
        error = "simulation state is invalid";
        return false;
    }
    snapshot.funds = *funds;
    snapshot.date = {*day, *month, *year};
    snapshot.speed = static_cast<SimulationSpeed>(*speed_value);
    snapshot.next_building_instance_id = *next_id;
    if (*version >= 2) {
        const auto current_population = json_number<std::uint32_t>(json, "currentPopulation");
        if (!current_population) {
            error = "currentPopulation is missing or invalid";
            return false;
        }
        snapshot.current_population = *current_population;
    }
    if (*version >= 3) {
        const auto last_property_tax_year = json_number<int>(json, "lastPropertyTaxYear");
        if (!last_property_tax_year || *last_property_tax_year < 0 || *last_property_tax_year > snapshot.date.year) {
            error = "lastPropertyTaxYear is missing or invalid";
            return false;
        }
        snapshot.last_property_tax_year = *last_property_tax_year;
    } else if (snapshot.date.month > 1) {
        // Legacy saves have no fiscal marker. Treat a year whose January has
        // already passed as settled, avoiding a retroactive duplicate charge.
        snapshot.last_property_tax_year = snapshot.date.year;
    }
    if (*version >= 8) {
        const auto months_no_power = json_number<int>(json, "monthsWithoutPower");
        const auto crisis_month = json_number<int>(json, "crisisRecoveryMonth");
        if (months_no_power) snapshot.months_without_power = std::max(0, *months_no_power);
        if (crisis_month) snapshot.crisis_recovery_month = std::max(0, *crisis_month);
    }

    const auto saved_buildings = json_object_array(json, "buildings");
    const auto saved_roads = json_object_array(json, "roads");
    const auto saved_sidewalks = *version >= 4 ? json_object_array(json, "sidewalks") : std::optional<std::vector<std::string_view>>{{}};
    const auto saved_farming_tiles = *version >= 5 ? json_object_array(json, "farmingTiles") : std::optional<std::vector<std::string_view>>{{}};
    const auto saved_inventory = *version >= 5 ? json_object_array(json, "agriculturalInventory") : std::optional<std::vector<std::string_view>>{{}};
    const auto saved_vehicles = *version >= 7 ? json_object_array(json, "serviceVehicles") : std::optional<std::vector<std::string_view>>{{}};
    const auto saved_missions = json_string_array(json, "completedMissions");
    if (saved_missions) {
        for (const std::string& m : *saved_missions) {
            snapshot.completed_missions.push_back(m);
        }
    }
    const auto owned_parcels = json_number_array<std::uint32_t>(json, "ownedParcelIds");
    if (!saved_buildings) {
        error = "buildings array is invalid";
        return false;
    }
    if (!saved_roads || !saved_sidewalks || !saved_farming_tiles || !saved_inventory || !saved_vehicles) {
        error = "roads array is invalid";
        return false;
    }
    if (!owned_parcels) {
        error = "ownedParcelIds array is invalid";
        return false;
    }
    for (const std::string_view building : *saved_buildings) {
        const auto instance_id = json_number<std::uint64_t>(building, "instanceId");
        const auto definition_id = json_string(building, "definitionId");
        const auto tile_x = json_number<int>(building, "tileX");
        const auto tile_y = json_number<int>(building, "tileY");
        const auto rotation = json_number<int>(building, "rotation");
        const auto level = json_number<int>(building, "level");
        const auto service_price = json_number<std::int64_t>(building, "servicePrice");
        const auto wall_color_customized = json_bool(building, "wallColorCustomized");
        const auto roof_color_customized = json_bool(building, "roofColorCustomized");
        const auto wall_tint_r = json_number<int>(building, "wallTintR");
        const auto wall_tint_g = json_number<int>(building, "wallTintG");
        const auto wall_tint_b = json_number<int>(building, "wallTintB");
        const auto roof_tint_r = json_number<int>(building, "roofTintR");
        const auto roof_tint_g = json_number<int>(building, "roofTintG");
        const auto roof_tint_b = json_number<int>(building, "roofTintB");
        const int current_level = level.has_value() ? std::max(1, *level) : 1;
        if (!instance_id || !definition_id || !tile_x || !tile_y || !rotation || *instance_id == 0 ||
            *rotation < 0 || *rotation > 3) {
            error = "building entry is invalid";
            return false;
        }
        BuildingInstance saved;
        saved.instance_id = *instance_id;
        saved.definition_id = *definition_id;
        saved.tile_x = *tile_x;
        saved.tile_y = *tile_y;
        saved.rotation = static_cast<BuildingRotation>(*rotation);
        saved.current_level = current_level;
        saved.service_price = (*version >= 9 && service_price.has_value()) ? std::max<std::int64_t>(0, *service_price) : 0;
        const auto valid_channel = [](const std::optional<int>& r, const std::optional<int>& g, const std::optional<int>& b) {
            return r && g && b && *r >= 0 && *r <= 255 && *g >= 0 && *g <= 255 && *b >= 0 && *b <= 255;
        };
        if (*version >= 10) {
            saved.wall_color_customized = wall_color_customized.value_or(false);
            saved.roof_color_customized = roof_color_customized.value_or(false);
            if ((saved.wall_color_customized && !valid_channel(wall_tint_r, wall_tint_g, wall_tint_b)) ||
                (saved.roof_color_customized && !valid_channel(roof_tint_r, roof_tint_g, roof_tint_b))) {
                error = "building color customization is invalid";
                return false;
            }
            if (saved.wall_color_customized) {
                saved.wall_tint = {static_cast<std::uint8_t>(*wall_tint_r), static_cast<std::uint8_t>(*wall_tint_g),
                                   static_cast<std::uint8_t>(*wall_tint_b)};
            }
            if (saved.roof_color_customized) {
                saved.roof_tint = {static_cast<std::uint8_t>(*roof_tint_r), static_cast<std::uint8_t>(*roof_tint_g),
                                   static_cast<std::uint8_t>(*roof_tint_b)};
            }
        } else {
            const bool has_legacy_tint = wall_tint_r || wall_tint_g || wall_tint_b || roof_tint_r || roof_tint_g || roof_tint_b;
            if (has_legacy_tint) {
                if (!valid_channel(wall_tint_r, wall_tint_g, wall_tint_b) || !valid_channel(roof_tint_r, roof_tint_g, roof_tint_b)) {
                    error = "building color customization is invalid";
                    return false;
                }
                saved.wall_color_customized = true;
                saved.roof_color_customized = true;
                saved.wall_tint = {static_cast<std::uint8_t>(*wall_tint_r), static_cast<std::uint8_t>(*wall_tint_g),
                                   static_cast<std::uint8_t>(*wall_tint_b)};
                saved.roof_tint = {static_cast<std::uint8_t>(*roof_tint_r), static_cast<std::uint8_t>(*roof_tint_g),
                                   static_cast<std::uint8_t>(*roof_tint_b)};
            }
        }
        snapshot.buildings.push_back(std::move(saved));
    }
    for (const std::string_view road : *saved_roads) {
        const auto tile_x = json_number<int>(road, "tileX");
        const auto tile_y = json_number<int>(road, "tileY");
        if (!tile_x || !tile_y) {
            error = "road entry is invalid";
            return false;
        }
        snapshot.roads.push_back({*tile_x, *tile_y});
    }
    for (const std::string_view sidewalk : *saved_sidewalks) {
        const auto tile_x = json_number<int>(sidewalk, "tileX"); const auto tile_y = json_number<int>(sidewalk, "tileY");
        const auto style = json_string(sidewalk, "styleId");
        if (!tile_x || !tile_y || !style || style->empty()) { error = "sidewalk entry is invalid"; return false; }
        snapshot.sidewalks.push_back({*tile_x, *tile_y, *style});
    }
    for (const std::string_view farm : *saved_farming_tiles) {
        const auto tile_x = json_number<int>(farm, "tileX"); const auto tile_y = json_number<int>(farm, "tileY");
        const auto state = json_number<int>(farm, "state"); const auto crop = json_string(farm, "cropId");
        const auto planted_day = json_number<int>(farm, "plantedDay"); const auto stage = json_number<int>(farm, "stage");
        const auto harvest_cycles = *version >= 6 ? json_number<int>(farm, "harvestCycleCount") : std::optional<int>{0};
        if (!tile_x || !tile_y || !state || !crop || !planted_day || !stage || !harvest_cycles || *state < 0 || *state > 2 || *stage < 0 || *harvest_cycles < 0) {
            error = "farming entry is invalid"; return false;
        }
        snapshot.farming_tiles.push_back({*tile_x, *tile_y, static_cast<FarmTileState>(*state), *crop, *planted_day, *stage, *harvest_cycles});
    }
    for (const std::string_view item : *saved_inventory) {
        const auto crop = json_string(item, "cropId"); const auto quantity = json_number<int>(item, "quantity");
        if (!crop || crop->empty() || !quantity || *quantity < 0) { error = "agricultural inventory entry is invalid"; return false; }
        snapshot.agricultural_inventory[*crop] = *quantity;
    }
    for (const std::string_view item : *saved_vehicles) {
        const auto vehicle_id = json_string(item, "vehicleId"); const auto x = json_number<int>(item, "tileX"); const auto y = json_number<int>(item, "tileY");
        const auto home_x = json_number<int>(item, "homeTileX"); const auto home_y = json_number<int>(item, "homeTileY");
        const auto direction = json_number<int>(item, "direction"); const auto state = json_number<int>(item, "state");
        if (!vehicle_id || vehicle_id->empty() || !x || !y || !home_x || !home_y || !direction || !state || *direction < 0 || *direction > 3 || *state < 0 || *state > 3) { error = "service vehicle entry is invalid"; return false; }
        ServiceVehicleInstance vehicle; vehicle.vehicle_id = *vehicle_id; vehicle.map_x = static_cast<float>(*x); vehicle.map_y = static_cast<float>(*y);
        vehicle.origin_x = static_cast<float>(*home_x); vehicle.origin_y = static_cast<float>(*home_y); vehicle.direction = static_cast<VehicleDirection>(*direction); vehicle.state = ServiceVehicleState::idle; vehicle.owned = true;
        snapshot.vehicles.push_back(std::move(vehicle));
    }
    snapshot.owned_parcel_ids = *owned_parcels;
    return true;
}

[[nodiscard]] std::string escape_json(const std::string_view value) {
    std::string escaped;
    escaped.reserve(value.size());
    for (const char character : value) {
        switch (character) {
            case '\\': escaped += "\\\\"; break;
            case '\"': escaped += "\\\""; break;
            case '\n': escaped += "\\n"; break;
            case '\r': escaped += "\\r"; break;
            case '\t': escaped += "\\t"; break;
            default: escaped += character; break;
        }
    }
    return escaped;
}

[[nodiscard]] std::filesystem::path user_data_directory() {
    if (const char* local_app_data = std::getenv("LOCALAPPDATA"); local_app_data != nullptr && *local_app_data != '\0') {
        return std::filesystem::path(local_app_data) / "CityBuilder";
    }
    return std::filesystem::temp_directory_path() / "CityBuilder";
}

}  // namespace

std::filesystem::path SaveManager::default_save_path() {
    return user_data_directory() / "city_save.json";
}

std::filesystem::path SaveManager::autosave_path() {
    return user_data_directory() / "autosave.json";
}

SaveOperationResult SaveManager::save(const std::filesystem::path& path, const CityEconomy& economy,
                                      const SimulationClock& clock, const BuildingManager& buildings,
                                      const RoadManager& roads, const SidewalkManager& sidewalks, const FarmingSystem& farming,
                                      const LandManager& lands,
                                       const PopulationSystem& population, const ServiceVehicleManager* vehicles,
                                       const MissionManager* missions) const {
    std::error_code error;
    std::filesystem::create_directories(path.parent_path(), error);
    if (error) {
        return {false, "could not create save directory: " + error.message()};
    }
    std::ofstream output(path, std::ios::binary | std::ios::trunc);
    if (!output) {
        return {false, "could not open save file for writing"};
    }

    output << "{\n"
           << "  \"saveVersion\": " << kSaveVersion << ",\n"
           << "  \"cityFunds\": " << economy.funds() << ",\n"
           << "  \"simulation\": { \"day\": " << clock.date().day << ", \"month\": " << clock.date().month
           << ", \"year\": " << clock.date().year << ", \"speed\": " << static_cast<int>(clock.speed()) << " },\n"
           << "  \"nextBuildingInstanceId\": " << buildings.next_instance_id() << ",\n"
           << "  \"currentPopulation\": " << population.current_population() << ",\n"
           << "  \"monthsWithoutPower\": " << population.months_without_power() << ",\n"
           << "  \"crisisRecoveryMonth\": " << population.crisis_recovery_month() << ",\n"
           << "  \"lastPropertyTaxYear\": " << economy.last_property_tax_year() << ",\n"
           << "  \"buildings\": [\n";
    for (std::size_t index = 0; index < buildings.instances().size(); ++index) {
        const BuildingInstance& building = buildings.instances()[index];
        output << "    { \"instanceId\": " << building.instance_id << ", \"definitionId\": \"" << escape_json(building.definition_id)
               << "\", \"tileX\": " << building.tile_x << ", \"tileY\": " << building.tile_y
               << ", \"rotation\": " << static_cast<int>(building.rotation)
               << ", \"level\": " << building.current_level
               << ", \"servicePrice\": " << building.service_price
               << ", \"wallColorCustomized\": " << (building.wall_color_customized ? "true" : "false")
               << ", \"roofColorCustomized\": " << (building.roof_color_customized ? "true" : "false");
        if (building.wall_color_customized) {
            output << ", \"wallTintR\": " << static_cast<int>(building.wall_tint.r)
                   << ", \"wallTintG\": " << static_cast<int>(building.wall_tint.g)
                   << ", \"wallTintB\": " << static_cast<int>(building.wall_tint.b);
        }
        if (building.roof_color_customized) {
            output << ", \"roofTintR\": " << static_cast<int>(building.roof_tint.r)
                   << ", \"roofTintG\": " << static_cast<int>(building.roof_tint.g)
                   << ", \"roofTintB\": " << static_cast<int>(building.roof_tint.b);
        }
        output << " }" << (index + 1U == buildings.instances().size() ? "\n" : ",\n");
    }
    output << "  ],\n  \"roads\": [\n";
    for (std::size_t index = 0; index < roads.tiles().size(); ++index) {
        const RoadTile& road = roads.tiles()[index];
        output << "    { \"tileX\": " << road.tile_x << ", \"tileY\": " << road.tile_y << " }"
               << (index + 1U == roads.tiles().size() ? "\n" : ",\n");
    }
    output << "  ],\n  \"ownedParcelIds\": [";
    bool first = true;
    for (const LandParcel& parcel : lands.parcels()) {
        if (!parcel.owned) continue;
        output << (first ? "" : ", ") << parcel.id;
        first = false;
    }
    output << "],\n  \"sidewalks\": [\n";
    for (std::size_t index = 0; index < sidewalks.tiles().size(); ++index) {
        const SidewalkTile& tile = sidewalks.tiles()[index];
        output << "    { \"tileX\": " << tile.tile_x << ", \"tileY\": " << tile.tile_y << ", \"styleId\": \"" << escape_json(tile.style_id) << "\" }"
               << (index + 1U == sidewalks.tiles().size() ? "\n" : ",\n");
    }
    output << "  ],\n  \"farmingTiles\": [\n";
    for (std::size_t index = 0; index < farming.tiles().size(); ++index) {
        const FarmTile& tile = farming.tiles()[index];
        output << "    { \"tileX\": " << tile.tile_x << ", \"tileY\": " << tile.tile_y
               << ", \"state\": " << static_cast<int>(tile.state) << ", \"cropId\": \"" << escape_json(tile.crop_id)
               << "\", \"plantedDay\": " << tile.planted_day << ", \"stage\": " << tile.stage << ", \"harvestCycleCount\": " << tile.harvest_cycle_count << " }"
               << (index + 1U == farming.tiles().size() ? "\n" : ",\n");
    }
    output << "  ],\n  \"agriculturalInventory\": [\n";
    std::size_t inventory_index = 0;
    for (const auto& [crop_id, quantity] : farming.inventory()) {
        output << "    { \"cropId\": \"" << escape_json(crop_id) << "\", \"quantity\": " << quantity << " }"
               << (++inventory_index == farming.inventory().size() ? "\n" : ",\n");
    }
    output << "  ],\n  \"serviceVehicles\": [\n";
    if (vehicles != nullptr) {
        const auto& instances = vehicles->instances();
        for (std::size_t index = 0; index < instances.size(); ++index) {
            const ServiceVehicleInstance& vehicle = instances[index];
            output << "    { \"vehicleId\": \"" << escape_json(vehicle.vehicle_id) << "\", \"tileX\": " << static_cast<int>(std::lround(vehicle.map_x))
                   << ", \"tileY\": " << static_cast<int>(std::lround(vehicle.map_y)) << ", \"homeTileX\": " << static_cast<int>(std::lround(vehicle.origin_x))
                   << ", \"homeTileY\": " << static_cast<int>(std::lround(vehicle.origin_y)) << ", \"direction\": " << static_cast<int>(vehicle.direction)
                   << ", \"state\": " << static_cast<int>(vehicle.state) << " }" << (index + 1U == instances.size() ? "\n" : ",\n");
        }
    }
    output << "  ],\n  \"completedMissions\": [\n";
    if (missions != nullptr) {
        const auto completed = missions->completed_mission_ids();
        for (std::size_t index = 0; index < completed.size(); ++index) {
            output << "    \"" << escape_json(completed[index]) << "\"" << (index + 1U == completed.size() ? "\n" : ",\n");
        }
    }
    output << "  ]\n}\n";
    if (!output) {
        return {false, "could not finish writing save file"};
    }
    return {true, "saved city to " + path.string()};
}

SaveOperationResult SaveManager::load(const std::filesystem::path& path, const BuildingCatalog& catalog,
                                      CityEconomy& economy, SimulationClock& clock, BuildingManager& buildings,
                                      RoadManager& roads, SidewalkManager& sidewalks, FarmingSystem& farming,
                                      LandManager& lands, PopulationSystem& population, const ServiceVehicleCatalog* vehicle_catalog,
                                      ServiceVehicleManager* vehicles, MissionManager* missions) const {
    const std::string serialized = read_file(path);
    if (serialized.empty()) {
        return {false, "save file does not exist or is empty"};
    }
    SaveSnapshot snapshot;
    std::string parse_error;
    if (!parse_snapshot(serialized, snapshot, parse_error)) {
        return {false, "save load failed: " + parse_error};
    }
    SimulationClock validated_clock(clock.seconds_per_game_day());
    if (!validated_clock.restore_state(snapshot.date, snapshot.speed)) {
        return {false, "save load failed: invalid simulation date"};
    }

    SaveOperationResult result;
    result.success = true;
    result.unknown_parcels = lands.restore_owned_parcels(snapshot.owned_parcel_ids);
    economy.restore_funds(snapshot.funds);
    economy.restore_last_property_tax_year(snapshot.last_property_tax_year);
    (void)clock.restore_state(snapshot.date, snapshot.speed);
    buildings.clear();
    roads.clear();
    sidewalks.clear();
    farming.clear();
    if (vehicles != nullptr) vehicles->clear();
    if (missions != nullptr) missions->restore_completed_missions(snapshot.completed_missions);

    for (const BuildingInstance& saved : snapshot.buildings) {
        const BuildingDefinition* definition = catalog.find(saved.definition_id);
        if (definition == nullptr) {
            ++result.skipped_buildings;
            std::cerr << "Save skipped missing building definition: " << saved.definition_id << '\n';
            continue;
        }
        const BuildingFootprint footprint = rotated_footprint(*definition, saved.rotation);
        const bool area_valid = definition->preplaced || lands.is_area_owned(saved.tile_x, saved.tile_y, footprint.width, footprint.height);
        if (!area_valid || !buildings.restore_instance(*definition, saved)) {
            ++result.skipped_buildings;
            std::cerr << "Save skipped invalid building instance " << saved.instance_id << '\n';
        }
    }
    buildings.set_next_instance_id(snapshot.next_building_instance_id);
    if (missions != nullptr) {
        if (missions->is_completed("clean_energy")) {
            buildings.set_operational_by_definition("hydroelectric_01", true);
        }
        if (missions->is_completed("city_water")) {
            buildings.set_operational_by_definition("water_intake_01", true);
        }
    }
    for (const TileCoordinate& saved : snapshot.roads) {
        if (!lands.is_tile_owned(saved.x, saved.y) || buildings.is_occupied(saved.x, saved.y) ||
            !roads.place_tile(saved.x, saved.y)) {
            ++result.skipped_roads;
            std::cerr << "Save skipped invalid road tile: " << saved.x << ',' << saved.y << '\n';
        }
    }
    for (const SidewalkTile& saved : snapshot.sidewalks) {
        if (!lands.is_tile_owned(saved.tile_x, saved.tile_y) ||
            sidewalks.validate_placement(saved.tile_x, saved.tile_y, roads, buildings) != SidewalkPlacementFailure::none ||
            !sidewalks.place_tile(saved.tile_x, saved.tile_y, saved.style_id)) ++result.skipped_sidewalks;
    }
    for (const FarmTile& saved : snapshot.farming_tiles) {
        if (!lands.is_tile_owned(saved.tile_x, saved.tile_y) || roads.is_road(saved.tile_x, saved.tile_y) ||
            sidewalks.is_sidewalk(saved.tile_x, saved.tile_y) || buildings.is_occupied(saved.tile_x, saved.tile_y) ||
            !farming.restore_tile(saved)) {
            ++result.skipped_farming_tiles;
        }
    }
    farming.restore_inventory(std::move(snapshot.agricultural_inventory));
    if (vehicles != nullptr && vehicle_catalog != nullptr) {
        for (ServiceVehicleInstance& saved : snapshot.vehicles) {
            if (vehicle_catalog->find(saved.vehicle_id) != nullptr && lands.is_tile_owned(static_cast<int>(saved.map_x), static_cast<int>(saved.map_y))) {
                (void)vehicles->add(std::move(saved), *vehicle_catalog);
            }
        }
    }
    population.restore_current_population(snapshot.current_population, buildings, catalog, nullptr, nullptr, snapshot.months_without_power, snapshot.crisis_recovery_month);
    economy.rebuild_monthly_summary(buildings, catalog, population, &farming);
    result.message = "loaded " + std::to_string(buildings.instances().size()) + " buildings and " +
        std::to_string(roads.tiles().size()) + " roads and " + std::to_string(sidewalks.tiles().size()) + " sidewalks";
    if (result.skipped_buildings != 0 || result.skipped_roads != 0 || result.skipped_sidewalks != 0 ||
        result.skipped_farming_tiles != 0 || result.unknown_parcels != 0) {
        result.message += " (some invalid entries skipped)";
    }
    return result;
}
