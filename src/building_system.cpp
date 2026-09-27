#include "building_system.h"
#include "economy_system.h"
#include "ch_core/placement_engine.h"

#include <algorithm>
#include <cctype>
#include <exception>
#include <fstream>
#include <iostream>
#include <limits>
#include <sstream>
#include <string_view>
#include <type_traits>

namespace {

[[nodiscard]] std::string read_file(const std::filesystem::path& path) {
    std::ifstream input(path, std::ios::binary);
    if (!input) return {};
    std::ostringstream contents;
    contents << input.rdbuf();
    return contents.str();
}

[[nodiscard]] std::size_t skip_whitespace(const std::string& text, std::size_t position) {
    while (position < text.size() && std::isspace(static_cast<unsigned char>(text[position])) != 0) ++position;
    return position;
}

[[nodiscard]] std::optional<std::size_t> value_position(const std::string& json, std::string_view key) {
    const std::string quoted_key = std::string("\"") + std::string(key) + "\"";
    const std::size_t key_position = json.find(quoted_key);
    if (key_position == std::string::npos) return std::nullopt;
    const std::size_t colon = json.find(':', key_position + quoted_key.size());
    if (colon == std::string::npos) return std::nullopt;
    return skip_whitespace(json, colon + 1);
}

[[nodiscard]] std::optional<std::string> json_string(const std::string& json, std::string_view key) {
    const auto position = value_position(json, key);
    if (!position || *position >= json.size() || json[*position] != '"') return std::nullopt;
    const std::size_t end = json.find('"', *position + 1);
    if (end == std::string::npos) return std::nullopt;
    return json.substr(*position + 1, end - *position - 1);
}

template <typename Number>
[[nodiscard]] std::optional<Number> json_number(const std::string& json, std::string_view key) {
    const auto position = value_position(json, key);
    if (!position) return std::nullopt;
    std::size_t parsed = 0;
    try {
        if constexpr (std::is_same_v<Number, int>) {
            const int value = std::stoi(json.substr(*position), &parsed);
            return parsed == 0 ? std::nullopt : std::optional<int>(value);
        } else if constexpr (std::is_same_v<Number, std::int64_t>) {
            const std::int64_t value = std::stoll(json.substr(*position), &parsed);
            return parsed == 0 ? std::nullopt : std::optional<std::int64_t>(value);
        } else if constexpr (std::is_same_v<Number, std::uint32_t>) {
            const unsigned long value = std::stoul(json.substr(*position), &parsed);
            if (parsed == 0 || value > std::numeric_limits<std::uint32_t>::max()) return std::nullopt;
            return static_cast<std::uint32_t>(value);
        } else {
            const float value = std::stof(json.substr(*position), &parsed);
            return parsed == 0 ? std::nullopt : std::optional<float>(value);
        }
    } catch (const std::exception&) { return std::nullopt; }
}

[[nodiscard]] std::optional<std::string> json_object(const std::string& json, std::string_view key) {
    const auto position = value_position(json, key);
    if (!position || *position >= json.size() || json[*position] != '{') return std::nullopt;
    int depth = 0;
    for (std::size_t index = *position; index < json.size(); ++index) {
        if (json[index] == '{') ++depth;
        else if (json[index] == '}' && --depth == 0) return json.substr(*position, index - *position + 1);
    }
    return std::nullopt;
}

[[nodiscard]] std::optional<bool> json_bool(const std::string& json, std::string_view key) {
    const auto position = value_position(json, key);
    if (!position) return std::nullopt;
    if (json.compare(*position, 4, "true") == 0) return true;
    if (json.compare(*position, 5, "false") == 0) return false;
    return std::nullopt;
}

[[nodiscard]] std::optional<std::vector<std::string>> json_array_objects(const std::string& json, std::string_view key) {
    const auto position = value_position(json, key);
    if (!position || *position >= json.size() || json[*position] != '[') return std::nullopt;
    std::vector<std::string> objects;
    int array_depth = 0;
    for (std::size_t index = *position; index < json.size(); ++index) {
        if (json[index] == '[') ++array_depth;
        else if (json[index] == ']' && --array_depth == 0) return objects;
        else if (json[index] == '{') {
            const std::size_t start = index;
            int object_depth = 0;
            for (; index < json.size(); ++index) {
                if (json[index] == '{') ++object_depth;
                else if (json[index] == '}' && --object_depth == 0) {
                    objects.push_back(json.substr(start, index - start + 1));
                    break;
                }
            }
            if (object_depth != 0) return std::nullopt;
        }
    }
    return std::nullopt;
}

[[nodiscard]] std::vector<std::string> json_string_array(const std::string& json, std::string_view key) {
    std::vector<std::string> values;
    const auto position = value_position(json, key);
    if (!position || *position >= json.size() || json[*position] != '[') return values;
    const std::size_t end = json.find(']', *position);
    if (end == std::string::npos) return values;
    for (std::size_t cursor = *position; (cursor = json.find('"', cursor + 1)) != std::string::npos && cursor < end;) {
        const std::size_t close = json.find('"', cursor + 1);
        if (close == std::string::npos || close > end) break;
        values.push_back(json.substr(cursor + 1, close - cursor - 1));
        cursor = close;
    }
    return values;
}

[[nodiscard]] std::optional<GridDirection> parse_grid_direction(std::string_view value) {
    if (value == "north") return GridDirection::north;
    if (value == "east") return GridDirection::east;
    if (value == "south") return GridDirection::south;
    if (value == "west") return GridDirection::west;
    return std::nullopt;
}

[[nodiscard]] std::optional<RoadAccessMode> parse_road_access_mode(const std::string_view value) {
    if (value == "any_perimeter") return RoadAccessMode::any_perimeter;
    if (value == "access_points") return RoadAccessMode::access_points;
    if (value == "front_edge") return RoadAccessMode::front_edge;
    return std::nullopt;
}

[[nodiscard]] bool access_point_faces_outward(const BuildingAccessPoint& access_point, const int width, const int height) {
    switch (access_point.facing) {
        case GridDirection::north: return access_point.local_y == 0;
        case GridDirection::east: return access_point.local_x == width - 1;
        case GridDirection::south: return access_point.local_y == height - 1;
        case GridDirection::west: return access_point.local_x == 0;
    }
    return false;
}

[[nodiscard]] std::optional<BuildingDefinition> parse_definition(const std::filesystem::path& path) {
    const std::string json = read_file(path);
    if (json.empty()) return std::nullopt;
    const auto footprint = json_object(json, "footprint");
    if (!footprint) return std::nullopt;

    BuildingDefinition definition;
    definition.id = json_string(json, "id").value_or("");
    definition.name = json_string(json, "name").value_or(definition.id);
    definition.category = json_string(json, "category").value_or("other");
    definition.texture_path = json_string(json, "texture").value_or("");
    definition.requires_road_access = json_bool(json, "requiresRoadAccess").value_or(false);
    definition.requires_road_or_path_access = json_bool(json, "requiresRoadOrPathAccess").value_or(false);
    definition.requires_ticket_booth = json_bool(json, "requiresTicketBooth").value_or(false);
    definition.is_park_ticket_booth = json_bool(json, "isParkTicketBooth").value_or(false);
    definition.grass_only = json_bool(json, "grassOnly").value_or(false);
    definition.footprint_width = json_number<int>(*footprint, "width").value_or(0);
    definition.footprint_height = json_number<int>(*footprint, "height").value_or(0);
    if (const auto occupancy = json_object(json, "occupancyFootprint")) {
        definition.occupancy_footprint_width = json_number<int>(*occupancy, "width").value_or(0);
        definition.occupancy_footprint_height = json_number<int>(*occupancy, "height").value_or(0);
        definition.occupancy_footprint_offset_x = json_number<int>(*occupancy, "offsetX").value_or(0);
        definition.occupancy_footprint_offset_y = json_number<int>(*occupancy, "offsetY").value_or(0);
        if (definition.occupancy_footprint_width <= 0 || definition.occupancy_footprint_height <= 0 ||
            definition.occupancy_footprint_offset_x < 0 || definition.occupancy_footprint_offset_y < 0 ||
            definition.occupancy_footprint_offset_x + definition.occupancy_footprint_width > definition.footprint_width ||
            definition.occupancy_footprint_offset_y + definition.occupancy_footprint_height > definition.footprint_height) return std::nullopt;
    }
    definition.build_cost = json_number<std::int64_t>(json, "buildCost").value_or(0);
    definition.maintenance_per_month = json_number<std::int64_t>(json, "maintenancePerMonth").value_or(0);
    definition.tax_revenue_per_month = json_number<std::int64_t>(json, "taxRevenuePerMonth").value_or(0);
    definition.property_tax_per_year = json_number<std::int64_t>(json, "propertyTaxPerYear").value_or(0);
    definition.required_population_for_full_revenue = json_number<std::uint32_t>(json, "requiredPopulationForFullRevenue").value_or(0);
    definition.service_name = json_string(json, "serviceName").value_or("");

    if (const auto pricing = json_object(json, "servicePricingContract")) {
        const auto contract = json_string(*pricing, "contract").value_or("");
        const auto currency = json_string(*pricing, "currency").value_or("");
        const auto storage_unit = json_string(*pricing, "storageUnit").value_or("");
        const auto initial = json_number<std::int64_t>(*pricing, "initialPrice");
        const auto minimum = json_number<std::int64_t>(*pricing, "minimumPrice");
        const auto maximum = json_number<std::int64_t>(*pricing, "maximumPrice");
        const auto step = json_number<std::int64_t>(*pricing, "priceStep");
        if (contract != "CH_SERVICE_PRICE_V1" || currency != "USD" || storage_unit != "cent" ||
            !initial || !minimum || !maximum || !step || *initial <= 0 || *minimum <= 0 ||
            *maximum < *minimum || *step <= 0 || *initial < *minimum || *initial > *maximum ||
            ((*initial - *minimum) % *step) != 0 || ((*maximum - *minimum) % *step) != 0) return std::nullopt;
        definition.default_service_price = ch::ServicePrice{*initial, 100, *step};
        definition.minimum_service_price = ch::ServicePrice{*minimum, 100, *step};
        definition.maximum_service_price = ch::ServicePrice{*maximum, 100, *step};
    } else {
        const std::int64_t default_price = json_number<std::int64_t>(json, "defaultServicePrice").value_or(0);
        const std::int64_t minimum_price = json_number<std::int64_t>(json, "minimumServicePrice").value_or(default_price > 0 ? 1 : 0);
        const std::int64_t maximum_price = json_number<std::int64_t>(json, "maximumServicePrice").value_or(default_price);
        definition.default_service_price = ch::ServicePrice{default_price, 1, 1};
        definition.minimum_service_price = ch::ServicePrice{minimum_price, 1, 1};
        definition.maximum_service_price = ch::ServicePrice{maximum_price, 1, 1};
    }

    definition.base_service_customers_per_month = json_number<std::uint32_t>(json, "baseServiceCustomersPerMonth").value_or(0);
    definition.service_population_for_full_demand = json_number<std::uint32_t>(json, "servicePopulationForFullDemand").value_or(0);
    if (const auto effect = json_object(json, "needsEffect")) {
        definition.needs_effect.hunger = std::clamp(json_number<float>(*effect, "hunger").value_or(0.0F), 0.0F, 100.0F);
        definition.needs_effect.thirst = std::clamp(json_number<float>(*effect, "thirst").value_or(0.0F), 0.0F, 100.0F);
        definition.needs_effect.fun = std::clamp(json_number<float>(*effect, "fun").value_or(0.0F), 0.0F, 100.0F);
    }
    definition.residential_capacity = json_number<std::uint32_t>(json, "residentialCapacity").value_or(0);
    definition.power_consumption = json_number<std::uint32_t>(json, "powerConsumption").value_or(0);
    definition.power_production = json_number<std::uint32_t>(json, "powerProduction").value_or(0);
    definition.generation_capacity = json_number<std::uint32_t>(json, "generationCapacity").value_or(0);
    definition.water_intake_capacity = json_number<std::uint32_t>(json, "waterIntakeCapacity").value_or(0);
    definition.preplaced = json_bool(json, "preplaced").value_or(false);
    definition.player_buildable = json_bool(json, "playerBuildable").value_or(true);
    definition.unlock_requirement = json_string(json, "unlockRequirement").value_or("");
    definition.agricultural_storage_capacity = json_number<std::uint32_t>(json, "agriculturalStorageCapacity").value_or(0);
    definition.grain_storage_capacity = json_number<std::uint32_t>(json, "grainStorageCapacity").value_or(0);
    definition.provides_agricultural_storage = json_bool(json, "providesAgriculturalStorage").value_or(false);
    definition.agricultural_infrastructure_role = json_string(json, "agriculturalInfrastructureRole").value_or("");
    definition.accepted_storage_classes = json_string_array(json, "acceptedStorageClasses");
    definition.art_scale = json_number<float>(json, "artScale").value_or(1.0F);
    if (const auto resource_inputs = json_array_objects(json, "resourceInputs")) {
        for (const std::string& serialized_input : *resource_inputs) {
            const auto resource_id = json_string(serialized_input, "resourceId");
            const auto amount = json_number<int>(serialized_input, "amountPerMonth");
            const auto bonus = json_number<std::int64_t>(serialized_input, "localSupplyBonus");
            if (!resource_id || resource_id->empty() || !amount || !bonus || *amount <= 0 || *bonus < 0) return std::nullopt;
            definition.resource_inputs.push_back({*resource_id, *amount, *bonus});
        }
    }

    if (const auto initial_placement = json_object(json, "initialPlacement")) {
        const auto tile_x = json_number<int>(*initial_placement, "tileX");
        const auto tile_y = json_number<int>(*initial_placement, "tileY");
        const auto rotation = json_number<int>(*initial_placement, "rotation");
        if (!tile_x || !tile_y || !rotation || *rotation < 0 || *rotation > 3) return std::nullopt;
        definition.initial_placement = {*tile_x, *tile_y, static_cast<BuildingRotation>(*rotation)};
    }

    if (const auto anchor = json_object(json, "anchor")) {
        definition.anchor_x = json_number<float>(*anchor, "x").value_or(0.5F);
        definition.anchor_y = json_number<float>(*anchor, "y").value_or(1.0F);
    }
    if (const auto anim = json_object(json, "animation")) {
        const int frame_count = json_number<int>(*anim, "frameCount").value_or(1);
        if (frame_count > 1) {
            BuildingAnimationDefinition parsed_animation;
            parsed_animation.frame_count = frame_count;
            parsed_animation.frame_duration_ms = std::max(1, json_number<int>(*anim, "frameDurationMs").value_or(120));
            parsed_animation.layout = json_string(*anim, "layout").value_or("horizontal");
            parsed_animation.playback = json_string(*anim, "playback").value_or("loop");
            if (parsed_animation.playback != "loop" && parsed_animation.playback != "ambient_once" && parsed_animation.playback != "activity_loop") return std::nullopt;
            parsed_animation.idle_frame = std::clamp(json_number<int>(*anim, "idleFrame").value_or(0), 0, frame_count - 1);
            parsed_animation.action_start_frame = std::clamp(json_number<int>(*anim, "actionStartFrame").value_or(1), 0, frame_count - 1);
            const int available_action_frames = frame_count - parsed_animation.action_start_frame;
            parsed_animation.action_frame_count = std::clamp(json_number<int>(*anim, "actionFrameCount").value_or(available_action_frames), 0, available_action_frames);
            parsed_animation.idle_hold_ms = std::max(0, json_number<int>(*anim, "idleHoldMs").value_or(0));
            definition.animation = parsed_animation;
        }
    }
    definition.sprite_anchor_x.fill(definition.anchor_x);
    definition.sprite_anchor_y.fill(definition.anchor_y);

    if (const auto sprite_anchors = json_object(json, "spriteAnchors")) {
        for (std::size_t index = 0; index < definition.sprite_anchor_x.size(); ++index) {
            if (const auto sprite_anchor = json_object(*sprite_anchors, std::to_string(index))) {
                definition.sprite_anchor_x[index] = json_number<float>(*sprite_anchor, "x").value_or(definition.anchor_x);
                definition.sprite_anchor_y[index] = json_number<float>(*sprite_anchor, "y").value_or(definition.anchor_y);
            }
        }
    }

    const auto sprites = json_object(json, "sprites");
    definition.rotatable = json_bool(json, "rotatable").value_or(sprites.has_value());
    if (sprites) {
        for (std::size_t index = 0; index < definition.sprite_paths.size(); ++index) {
            definition.sprite_paths[index] = json_string(*sprites, std::to_string(index)).value_or("");
            definition.available_rotations[index] = !definition.sprite_paths[index].empty();
        }
        if (!definition.available_rotations[0]) return std::nullopt;
        if (definition.texture_path.empty()) definition.texture_path = definition.sprite_paths[0];
    } else {
        definition.rotatable = false;
        definition.sprite_paths.fill(definition.texture_path);
        definition.available_rotations.fill(true);
    }

    if (definition.id.empty() || definition.footprint_width <= 0 || definition.footprint_height <= 0 || definition.texture_path.empty()) return std::nullopt;

    if (const auto road_access_mode = json_string(json, "roadAccessMode")) {
        const auto parsed = parse_road_access_mode(*road_access_mode);
        if (!parsed) return std::nullopt;
        definition.road_access_mode = *parsed;
        definition.road_access_mode_explicit = true;
    }
    if (const auto front_edge = json_string(json, "frontEdge")) {
        definition.front_edge = parse_grid_direction(*front_edge);
        if (!definition.front_edge) return std::nullopt;
    }
    if (const auto access_points = json_array_objects(json, "accessPoints")) {
        for (const std::string& object : *access_points) {
            const auto x = json_number<int>(object, "x");
            const auto y = json_number<int>(object, "y");
            const auto facing = json_string(object, "facing");
            if (!x || !y || !facing) return std::nullopt;
            const auto direction = parse_grid_direction(*facing);
            if (!direction) return std::nullopt;
            BuildingAccessPoint point{*x, *y, *direction};
            if (*x < 0 || *x >= definition.footprint_width || *y < 0 || *y >= definition.footprint_height ||
                !access_point_faces_outward(point, definition.footprint_width, definition.footprint_height)) return std::nullopt;
            definition.access_points.push_back(point);
        }
    }

    if (const auto color_mask = json_object(json, "colorMask")) {
        BuildingColorMaskDefinition parsed;
        parsed.enabled = json_bool(*color_mask, "enabled").value_or(false);
        if (const auto mask_sprites = json_object(*color_mask, "sprites")) {
            for (std::size_t index = 0; index < parsed.sprite_paths.size(); ++index) parsed.sprite_paths[index] = json_string(*mask_sprites, std::to_string(index)).value_or("");
        }
        definition.color_mask = parsed;
    }

    if (const auto activity_overlay = json_object(json, "activityOverlay")) {
        BuildingActivityOverlayDefinition parsed;
        parsed.enabled = json_bool(*activity_overlay, "enabled").value_or(false);
        if (const auto overlay_sprites = json_object(*activity_overlay, "sprites")) {
            for (std::size_t index = 0; index < parsed.sprite_paths.size(); ++index) parsed.sprite_paths[index] = json_string(*overlay_sprites, std::to_string(index)).value_or("");
        }
        if (const auto anim = json_object(*activity_overlay, "animation")) {
            BuildingAnimationDefinition a;
            a.frame_count = std::max(1, json_number<int>(*anim, "frameCount").value_or(1));
            a.frame_duration_ms = std::max(1, json_number<int>(*anim, "frameDurationMs").value_or(120));
            a.layout = json_string(*anim, "layout").value_or("horizontal");
            a.playback = json_string(*anim, "playback").value_or("loop");
            a.idle_frame = std::max(0, json_number<int>(*anim, "idleFrame").value_or(0));
            a.action_start_frame = std::max(0, json_number<int>(*anim, "actionStartFrame").value_or(0));
            a.action_frame_count = std::max(0, json_number<int>(*anim, "actionFrameCount").value_or(a.frame_count));
            parsed.animation = a;
        }
        definition.activity_overlay = parsed;
    }

    if (const auto levels = json_array_objects(json, "levels")) {
        for (const std::string& object : *levels) {
            BuildingLevelDefinition level;
            level.level = json_number<int>(object, "level").value_or(1);
            level.upgrade_cost = json_number<std::int64_t>(object, "upgradeCost").value_or(0);
            level.residential_capacity = json_number<std::uint32_t>(object, "residentialCapacity").value_or(definition.residential_capacity);
            level.power_consumption = json_number<std::uint32_t>(object, "powerConsumption").value_or(definition.power_consumption);
            level.maintenance_per_month = json_number<std::int64_t>(object, "maintenancePerMonth").value_or(definition.maintenance_per_month);
            level.tax_revenue_per_month = json_number<std::int64_t>(object, "taxRevenuePerMonth").value_or(definition.tax_revenue_per_month);
            level.sprite_paths = definition.sprite_paths;
            level.sprite_anchor_x = definition.sprite_anchor_x;
            level.sprite_anchor_y = definition.sprite_anchor_y;
            if (const auto level_sprites = json_object(object, "sprites")) {
                for (std::size_t index = 0; index < level.sprite_paths.size(); ++index) level.sprite_paths[index] = json_string(*level_sprites, std::to_string(index)).value_or(level.sprite_paths[index]);
            }
            definition.levels.push_back(level);
        }
    }
    if (definition.levels.empty()) {
        BuildingLevelDefinition base;
        base.level = 1;
        base.residential_capacity = definition.residential_capacity;
        base.power_consumption = definition.power_consumption;
        base.maintenance_per_month = definition.maintenance_per_month;
        base.tax_revenue_per_month = definition.tax_revenue_per_month;
        base.sprite_paths = definition.sprite_paths;
        base.sprite_anchor_x = definition.sprite_anchor_x;
        base.sprite_anchor_y = definition.sprite_anchor_y;
        definition.levels.push_back(base);
    }
    std::sort(definition.levels.begin(), definition.levels.end(), [](const auto& a, const auto& b) { return a.level < b.level; });
    return definition;
}

} // namespace

const BuildingLevelDefinition& BuildingDefinition::level_definition(const int level) const {
    for (const BuildingLevelDefinition& candidate : levels) if (candidate.level == level) return candidate;
    return levels.front();
}

const std::string& BuildingDefinition::texture_path_for(const BuildingRotation rotation, const int level) const {
    const BuildingLevelDefinition& selected = level_definition(level);
    const auto index = static_cast<std::size_t>(rotation);
    return selected.sprite_paths[index].empty() ? texture_path : selected.sprite_paths[index];
}

const std::string& BuildingDefinition::color_mask_path_for(const BuildingRotation rotation) const {
    static const std::string empty;
    if (!color_mask || !color_mask->enabled) return empty;
    return color_mask->sprite_paths[static_cast<std::size_t>(rotation)];
}

bool BuildingDefinition::supports_color_mask(const BuildingRotation rotation) const {
    return color_mask && color_mask->enabled && !color_mask_path_for(rotation).empty();
}

float BuildingDefinition::anchor_x_for(const BuildingRotation rotation, const int level) const {
    return level_definition(level).sprite_anchor_x[static_cast<std::size_t>(rotation)];
}

float BuildingDefinition::anchor_y_for(const BuildingRotation rotation, const int level) const {
    return level_definition(level).sprite_anchor_y[static_cast<std::size_t>(rotation)];
}

bool BuildingDefinition::supports_rotation(const BuildingRotation rotation) const {
    return available_rotations[static_cast<std::size_t>(rotation)];
}

BuildingRotation BuildingDefinition::next_supported_rotation(const BuildingRotation rotation, const bool clockwise) const {
    int index = static_cast<int>(rotation);
    for (int attempt = 0; attempt < 4; ++attempt) {
        index = (index + (clockwise ? 1 : 3)) % 4;
        const auto candidate = static_cast<BuildingRotation>(index);
        if (supports_rotation(candidate)) return candidate;
    }
    return rotation;
}

bool BuildingCatalog::load_from_directory(const std::filesystem::path& directory) {
    definitions_.clear();
    if (!std::filesystem::exists(directory)) return false;
    for (const auto& entry : std::filesystem::directory_iterator(directory)) {
        if (!entry.is_regular_file() || entry.path().extension() != ".json") continue;
        const auto parsed = parse_definition(entry.path());
        if (parsed) definitions_.push_back(*parsed);
    }
    return !definitions_.empty();
}

const BuildingDefinition* BuildingCatalog::find(const std::string_view id) const {
    const auto found = std::find_if(definitions_.begin(), definitions_.end(), [id](const BuildingDefinition& definition) { return definition.id == id; });
    return found == definitions_.end() ? nullptr : &*found;
}

const std::vector<BuildingDefinition>& BuildingCatalog::definitions() const { return definitions_; }

BuildingRotation rotate_clockwise(const BuildingRotation rotation) { return static_cast<BuildingRotation>((static_cast<int>(rotation) + 1) % 4); }
BuildingRotation rotate_counter_clockwise(const BuildingRotation rotation) { return static_cast<BuildingRotation>((static_cast<int>(rotation) + 3) % 4); }
const char* rotation_label(const BuildingRotation rotation) { switch (rotation) { case BuildingRotation::r0: return "SOUTH"; case BuildingRotation::r90: return "WEST"; case BuildingRotation::r180: return "NORTH"; case BuildingRotation::r270: return "EAST"; } return "SOUTH"; }

BuildingFootprint rotated_footprint(const BuildingDefinition& definition, const BuildingRotation rotation) {
    return rotation == BuildingRotation::r90 || rotation == BuildingRotation::r270
        ? BuildingFootprint{definition.footprint_height, definition.footprint_width}
        : BuildingFootprint{definition.footprint_width, definition.footprint_height};
}

BuildingOccupancyFootprint rotated_occupancy_footprint(const BuildingDefinition& definition, const BuildingRotation rotation) {
    const int width = definition.occupancy_footprint_width > 0 ? definition.occupancy_footprint_width : definition.footprint_width;
    const int height = definition.occupancy_footprint_height > 0 ? definition.occupancy_footprint_height : definition.footprint_height;
    const int ox = definition.occupancy_footprint_width > 0 ? definition.occupancy_footprint_offset_x : 0;
    const int oy = definition.occupancy_footprint_height > 0 ? definition.occupancy_footprint_offset_y : 0;
    switch (rotation) {
        case BuildingRotation::r0: return {ox, oy, width, height};
        case BuildingRotation::r90: return {definition.footprint_height - oy - height, ox, height, width};
        case BuildingRotation::r180: return {definition.footprint_width - ox - width, definition.footprint_height - oy - height, width, height};
        case BuildingRotation::r270: return {oy, definition.footprint_width - ox - width, height, width};
    }
    return {ox, oy, width, height};
}

BuildingAccessPoint rotate_access_point(const BuildingDefinition& definition, const BuildingAccessPoint access_point, const BuildingRotation rotation) {
    BuildingAccessPoint result = access_point;
    for (int turn = 0; turn < static_cast<int>(rotation); ++turn) {
        const int old_x = result.local_x;
        result.local_x = definition.footprint_height - 1 - result.local_y;
        result.local_y = old_x;
        result.facing = static_cast<GridDirection>((static_cast<int>(result.facing) + 1) % 4);
    }
    return result;
}

std::vector<BuildingAccessPoint> rotated_access_points(const BuildingDefinition& definition, const BuildingRotation rotation) {
    std::vector<BuildingAccessPoint> result;
    result.reserve(definition.access_points.size());
    for (const BuildingAccessPoint point : definition.access_points) result.push_back(rotate_access_point(definition, point, rotation));
    return result;
}

RoadAccessMode resolved_road_access_mode(const BuildingDefinition& definition) {
    if (definition.road_access_mode_explicit) return definition.road_access_mode;
    if (!definition.access_points.empty()) return RoadAccessMode::access_points;
    if (definition.front_edge) return RoadAccessMode::front_edge;
    return RoadAccessMode::any_perimeter;
}

const char* road_access_mode_label(const RoadAccessMode mode) { switch (mode) { case RoadAccessMode::any_perimeter: return "any_perimeter"; case RoadAccessMode::access_points: return "access_points"; case RoadAccessMode::front_edge: return "front_edge"; } return "any_perimeter"; }

std::vector<BuildingAccessPoint> front_edge_access_points(const BuildingDefinition& definition, const BuildingRotation rotation) {
    std::vector<BuildingAccessPoint> points;
    if (!definition.front_edge) return points;
    const BuildingFootprint footprint = rotated_footprint(definition, rotation);
    const GridDirection facing = static_cast<GridDirection>((static_cast<int>(*definition.front_edge) + static_cast<int>(rotation)) % 4);
    if (facing == GridDirection::north || facing == GridDirection::south) {
        const int y = facing == GridDirection::north ? 0 : footprint.height - 1;
        for (int x = 0; x < footprint.width; ++x) points.push_back({x, y, facing});
    } else {
        const int x = facing == GridDirection::west ? 0 : footprint.width - 1;
        for (int y = 0; y < footprint.height; ++y) points.push_back({x, y, facing});
    }
    return points;
}

std::vector<BuildingAccessPoint> road_access_candidates(const BuildingDefinition& definition, const BuildingRotation rotation) {
    if (!definition.access_points.empty()) return rotated_access_points(definition, rotation);
    if (definition.front_edge) return front_edge_access_points(definition, rotation);
    return {};
}

BuildingManager::BuildingManager(const int map_min, const int map_max) : map_min_(map_min), map_max_(map_max) {}

int BuildingManager::tile_key(const int tile_x, const int tile_y) const {
    const int span = map_max_ - map_min_ + 1;
    return (tile_y - map_min_) * span + (tile_x - map_min_);
}

PlacementFailure BuildingManager::validate(const BuildingDefinition& definition, const int tile_x, const int tile_y, const BuildingRotation rotation) const {
    if (!definition.supports_rotation(rotation)) return PlacementFailure::unavailable_rotation;
    const BuildingOccupancyFootprint footprint = rotated_occupancy_footprint(definition, rotation);
    for (int y = 0; y < footprint.height; ++y) for (int x = 0; x < footprint.width; ++x) {
        const int tx = tile_x + footprint.offset_x + x;
        const int ty = tile_y + footprint.offset_y + y;
        if (tx < map_min_ || tx > map_max_ || ty < map_min_ || ty > map_max_) return PlacementFailure::outside_map;
        if (occupied_tiles_.contains(tile_key(tx, ty))) return PlacementFailure::occupied;
    }
    return PlacementFailure::none;
}

void BuildingManager::occupy_footprint(const BuildingDefinition& definition, const BuildingInstance& instance) {
    const BuildingOccupancyFootprint footprint = rotated_occupancy_footprint(definition, instance.rotation);
    for (int y = 0; y < footprint.height; ++y) for (int x = 0; x < footprint.width; ++x) occupied_tiles_[tile_key(instance.tile_x + footprint.offset_x + x, instance.tile_y + footprint.offset_y + y)] = instance.instance_id;
}

void BuildingManager::release_footprint(const BuildingDefinition& definition, const BuildingInstance& instance) {
    const BuildingOccupancyFootprint footprint = rotated_occupancy_footprint(definition, instance.rotation);
    for (int y = 0; y < footprint.height; ++y) for (int x = 0; x < footprint.width; ++x) occupied_tiles_.erase(tile_key(instance.tile_x + footprint.offset_x + x, instance.tile_y + footprint.offset_y + y));
}

std::optional<std::uint64_t> BuildingManager::place(const BuildingDefinition& definition, const int tile_x, const int tile_y, const BuildingRotation rotation) {
    if (validate(definition, tile_x, tile_y, rotation) != PlacementFailure::none) return std::nullopt;
    BuildingInstance instance;
    instance.instance_id = next_instance_id_++;
    instance.definition_id = definition.id;
    instance.tile_x = tile_x;
    instance.tile_y = tile_y;
    instance.rotation = rotation;
    instance.service_price = definition.default_service_price;
    instances_.push_back(instance);
    occupy_footprint(definition, instances_.back());
    return instance.instance_id;
}

bool BuildingManager::restore_instance(const BuildingDefinition& definition, const BuildingInstance& instance) {
    if (validate(definition, instance.tile_x, instance.tile_y, instance.rotation) != PlacementFailure::none) return false;
    instances_.push_back(instance);
    occupy_footprint(definition, instances_.back());
    next_instance_id_ = std::max(next_instance_id_, instance.instance_id + 1);
    return true;
}

void BuildingManager::clear() { instances_.clear(); occupied_tiles_.clear(); ticket_booth_to_attraction_.clear(); attraction_to_ticket_booth_.clear(); next_instance_id_ = 1; }
void BuildingManager::set_next_instance_id(const std::uint64_t next_instance_id) { next_instance_id_ = std::max<std::uint64_t>(1, next_instance_id); }
std::uint64_t BuildingManager::next_instance_id() const { return next_instance_id_; }

const BuildingInstance* BuildingManager::find_by_id(const std::uint64_t instance_id) const {
    const auto found = std::find_if(instances_.begin(), instances_.end(), [instance_id](const BuildingInstance& instance) { return instance.instance_id == instance_id; });
    return found == instances_.end() ? nullptr : &*found;
}

BuildingInstance* BuildingManager::find_by_id(const std::uint64_t instance_id) {
    const auto found = std::find_if(instances_.begin(), instances_.end(), [instance_id](const BuildingInstance& instance) { return instance.instance_id == instance_id; });
    return found == instances_.end() ? nullptr : &*found;
}

const BuildingInstance* BuildingManager::instance_at(const int tile_x, const int tile_y) const {
    const auto found = occupied_tiles_.find(tile_key(tile_x, tile_y));
    return found == occupied_tiles_.end() ? nullptr : find_by_id(found->second);
}

bool BuildingManager::is_occupied(const int tile_x, const int tile_y) const { return instance_at(tile_x, tile_y) != nullptr; }
const std::vector<BuildingInstance>& BuildingManager::instances() const { return instances_; }

bool BuildingManager::remove_instance(const BuildingDefinition& definition, const std::uint64_t instance_id) {
    const auto found = std::find_if(instances_.begin(), instances_.end(), [instance_id](const BuildingInstance& instance) { return instance.instance_id == instance_id; });
    if (found == instances_.end()) return false;
    release_footprint(definition, *found);
    unlink_ticket_booth(instance_id);
    if (const auto booth = linked_ticket_booth_for_attraction(instance_id)) unlink_ticket_booth(*booth);
    instances_.erase(found);
    return true;
}

bool BuildingManager::begin_activity(const std::uint64_t instance_id) { if (auto* instance = find_by_id(instance_id)) { ++instance->activity_count; return true; } return false; }
bool BuildingManager::end_activity(const std::uint64_t instance_id) { if (auto* instance = find_by_id(instance_id); instance && instance->activity_count > 0) { --instance->activity_count; return true; } return false; }

bool BuildingManager::set_service_price(const std::uint64_t instance_id, const BuildingDefinition& definition, const std::int64_t price) {
    BuildingInstance* instance = find_by_id(instance_id);
    if (!instance || definition.default_service_price.minor_units <= 0) return false;
    const std::int64_t clamped = std::clamp(price, definition.minimum_service_price.minor_units, definition.maximum_service_price.minor_units);
    instance->service_price = definition.default_service_price.with_minor_units(clamped);
    return true;
}

bool BuildingManager::set_wall_color(const std::uint64_t id, const BuildingColorTint tint) { if (auto* i = find_by_id(id)) { i->wall_color_customized = true; i->wall_tint = tint; return true; } return false; }
bool BuildingManager::set_roof_color(const std::uint64_t id, const BuildingColorTint tint) { if (auto* i = find_by_id(id)) { i->roof_color_customized = true; i->roof_tint = tint; return true; } return false; }
bool BuildingManager::clear_wall_color(const std::uint64_t id) { if (auto* i = find_by_id(id)) { i->wall_color_customized = false; i->wall_tint = {}; return true; } return false; }
bool BuildingManager::clear_roof_color(const std::uint64_t id) { if (auto* i = find_by_id(id)) { i->roof_color_customized = false; i->roof_tint = {}; return true; } return false; }

bool BuildingManager::link_ticket_booth(const std::uint64_t booth_instance_id, const std::uint64_t attraction_instance_id) {
    if (!find_by_id(booth_instance_id) || !find_by_id(attraction_instance_id)) return false;
    ticket_booth_to_attraction_[booth_instance_id] = attraction_instance_id;
    attraction_to_ticket_booth_[attraction_instance_id] = booth_instance_id;
    return true;
}

bool BuildingManager::restore_ticket_link(const std::uint64_t booth_instance_id, const std::uint64_t attraction_instance_id) { return link_ticket_booth(booth_instance_id, attraction_instance_id); }

std::optional<std::uint64_t> BuildingManager::linked_attraction_for_ticket_booth(const std::uint64_t booth_instance_id) const {
    const auto found = ticket_booth_to_attraction_.find(booth_instance_id);
    return found == ticket_booth_to_attraction_.end() ? std::nullopt : std::optional<std::uint64_t>(found->second);
}

std::optional<std::uint64_t> BuildingManager::linked_ticket_booth_for_attraction(const std::uint64_t attraction_instance_id) const {
    const auto found = attraction_to_ticket_booth_.find(attraction_instance_id);
    return found == attraction_to_ticket_booth_.end() ? std::nullopt : std::optional<std::uint64_t>(found->second);
}

void BuildingManager::unlink_ticket_booth(const std::uint64_t booth_instance_id) {
    const auto found = ticket_booth_to_attraction_.find(booth_instance_id);
    if (found == ticket_booth_to_attraction_.end()) return;
    attraction_to_ticket_booth_.erase(found->second);
    ticket_booth_to_attraction_.erase(found);
}

bool BuildingInstance::is_max_level(const BuildingDefinition& definition) const { return current_level >= definition.levels.back().level; }
const BuildingLevelDefinition& BuildingInstance::current_level_definition(const BuildingDefinition& definition) const { return definition.level_definition(current_level); }
const BuildingLevelDefinition* BuildingInstance::next_level_definition(const BuildingDefinition& definition) const { for (const auto& level : definition.levels) if (level.level > current_level) return &level; return nullptr; }
bool BuildingInstance::try_upgrade(const BuildingDefinition& definition, CityEconomy& economy, const GameDate& date) { const auto* next = next_level_definition(definition); if (!next || !economy.spend_for_upgrade(next->upgrade_cost, date, instance_id)) return false; current_level = next->level; return true; }
