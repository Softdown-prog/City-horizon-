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

// Parsing is kept in this translation unit so every target consumes the same
// data-driven BuildingDefinition layout.
[[nodiscard]] std::string read_file(const std::filesystem::path& path) {
    std::ifstream input(path, std::ios::binary);
    if (!input) {
        return {};
    }
    std::ostringstream contents;
    contents << input.rdbuf();
    return contents.str();
}

[[nodiscard]] std::size_t skip_whitespace(const std::string& text, std::size_t position) {
    while (position < text.size() && std::isspace(static_cast<unsigned char>(text[position])) != 0) {
        ++position;
    }
    return position;
}

[[nodiscard]] std::optional<std::size_t> value_position(const std::string& json, std::string_view key) {
    const std::string quoted_key = std::string("\"") + std::string(key) + "\"";
    const std::size_t key_position = json.find(quoted_key);
    if (key_position == std::string::npos) {
        return std::nullopt;
    }
    const std::size_t colon = json.find(':', key_position + quoted_key.size());
    if (colon == std::string::npos) {
        return std::nullopt;
    }
    return skip_whitespace(json, colon + 1);
}

[[nodiscard]] std::optional<std::string> json_string(const std::string& json, std::string_view key) {
    const auto position = value_position(json, key);
    if (!position || *position >= json.size() || json[*position] != '"') {
        return std::nullopt;
    }
    const std::size_t end = json.find('"', *position + 1);
    if (end == std::string::npos) {
        return std::nullopt;
    }
    return json.substr(*position + 1, end - *position - 1);
}

template <typename Number>
[[nodiscard]] std::optional<Number> json_number(const std::string& json, std::string_view key) {
    const auto position = value_position(json, key);
    if (!position) {
        return std::nullopt;
    }
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
            if (parsed == 0 || value > std::numeric_limits<std::uint32_t>::max()) {
                return std::nullopt;
            }
            return static_cast<std::uint32_t>(value);
        } else {
            const float value = std::stof(json.substr(*position), &parsed);
            return parsed == 0 ? std::nullopt : std::optional<float>(value);
        }
    } catch (const std::exception&) {
        return std::nullopt;
    }
}

[[nodiscard]] std::optional<std::string> json_object(const std::string& json, std::string_view key) {
    const auto position = value_position(json, key);
    if (!position || *position >= json.size() || json[*position] != '{') {
        return std::nullopt;
    }
    int depth = 0;
    for (std::size_t index = *position; index < json.size(); ++index) {
        if (json[index] == '{') {
            ++depth;
        } else if (json[index] == '}' && --depth == 0) {
            return json.substr(*position, index - *position + 1);
        }
    }
    return std::nullopt;
}

[[nodiscard]] std::optional<bool> json_bool(const std::string& json, std::string_view key) {
    const auto position = value_position(json, key);
    if (!position) {
        return std::nullopt;
    }
    if (json.compare(*position, 4, "true") == 0) {
        return true;
    }
    if (json.compare(*position, 5, "false") == 0) {
        return false;
    }
    return std::nullopt;
}

[[nodiscard]] std::optional<std::vector<std::string>> json_array_objects(const std::string& json, std::string_view key) {
    const auto position = value_position(json, key);
    if (!position || *position >= json.size() || json[*position] != '[') {
        return std::nullopt;
    }
    std::vector<std::string> objects;
    int array_depth = 0;
    for (std::size_t index = *position; index < json.size(); ++index) {
        if (json[index] == '[') {
            ++array_depth;
        } else if (json[index] == ']' && --array_depth == 0) {
            return objects;
        } else if (json[index] == '{') {
            const std::size_t start = index;
            int object_depth = 0;
            for (; index < json.size(); ++index) {
                if (json[index] == '{') {
                    ++object_depth;
                } else if (json[index] == '}' && --object_depth == 0) {
                    objects.push_back(json.substr(start, index - start + 1));
                    break;
                }
            }
            if (object_depth != 0) {
                return std::nullopt;
            }
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
    if (json.empty()) {
        return std::nullopt;
    }

    const auto footprint = json_object(json, "footprint");
    if (!footprint) {
        return std::nullopt;
    }

    BuildingDefinition definition;
    definition.id = json_string(json, "id").value_or("");
    definition.name = json_string(json, "name").value_or(definition.id);
    definition.category = json_string(json, "category").value_or("other");
    definition.texture_path = json_string(json, "texture").value_or("");
    definition.requires_road_access = json_bool(json, "requiresRoadAccess").value_or(false);
    definition.requires_road_or_path_access = json_bool(json, "requiresRoadOrPathAccess").value_or(false);
    definition.grass_only = json_bool(json, "grassOnly").value_or(false);
    definition.footprint_width = json_number<int>(*footprint, "width").value_or(0);
    definition.footprint_height = json_number<int>(*footprint, "height").value_or(0);
    definition.build_cost = json_number<std::int64_t>(json, "buildCost").value_or(0);
    definition.maintenance_per_month = json_number<std::int64_t>(json, "maintenancePerMonth").value_or(0);
    definition.tax_revenue_per_month = json_number<std::int64_t>(json, "taxRevenuePerMonth").value_or(0);
    definition.property_tax_per_year = json_number<std::int64_t>(json, "propertyTaxPerYear").value_or(0);
    definition.required_population_for_full_revenue =
        json_number<std::uint32_t>(json, "requiredPopulationForFullRevenue").value_or(0);
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
            ((*initial - *minimum) % *step) != 0 || ((*maximum - *minimum) % *step) != 0) {
            return std::nullopt;
        }
        definition.default_service_price = ch::ServicePrice{*initial, 100, *step};
        definition.minimum_service_price = ch::ServicePrice{*minimum, 100, *step};
        definition.maximum_service_price = ch::ServicePrice{*maximum, 100, *step};
    } else {
        const std::int64_t default_price = json_number<std::int64_t>(json, "defaultServicePrice").value_or(0);
        const std::int64_t minimum_price = json_number<std::int64_t>(json, "minimumServicePrice").value_or(
            default_price > 0 ? 1 : 0);
        const std::int64_t maximum_price = json_number<std::int64_t>(json, "maximumServicePrice").value_or(default_price);
        definition.default_service_price = ch::ServicePrice{default_price, 1, 1};
        definition.minimum_service_price = ch::ServicePrice{minimum_price, 1, 1};
        definition.maximum_service_price = ch::ServicePrice{maximum_price, 1, 1};
    }

    definition.base_service_customers_per_month =
        json_number<std::uint32_t>(json, "baseServiceCustomersPerMonth").value_or(0);
    definition.service_population_for_full_demand =
        json_number<std::uint32_t>(json, "servicePopulationForFullDemand").value_or(0);
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
        if (!tile_x || !tile_y || !rotation || *rotation < 0 || *rotation > 3) {
            return std::nullopt;
        }
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
            parsed_animation.frame_duration_ms =
                std::max(1, json_number<int>(*anim, "frameDurationMs").value_or(120));
            parsed_animation.layout = json_string(*anim, "layout").value_or("horizontal");
            parsed_animation.playback = json_string(*anim, "playback").value_or("loop");
            if (parsed_animation.playback != "loop" && parsed_animation.playback != "ambient_once" &&
                parsed_animation.playback != "activity_loop") {
                return std::nullopt;
            }
            parsed_animation.idle_frame = std::clamp(
                json_number<int>(*anim, "idleFrame").value_or(0), 0, frame_count - 1);
            parsed_animation.action_start_frame = std::clamp(
                json_number<int>(*anim, "actionStartFrame").value_or(1), 0, frame_count - 1);
            const int available_action_frames = frame_count - parsed_animation.action_start_frame;
            parsed_animation.action_frame_count = std::clamp(
                json_number<int>(*anim, "actionFrameCount").value_or(available_action_frames),
                0, available_action_frames);
            parsed_animation.idle_hold_ms =
                std::max(0, json_number<int>(*anim, "idleHoldMs").value_or(0));
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
        if (!definition.available_rotations[0]) {
            return std::nullopt;
        }
        if (definition.texture_path.empty()) {
            definition.texture_path = definition.sprite_paths[0];
        }
    } else {
        // A legacy definition has one fixed PNG and intentionally ignores rotation.
        definition.rotatable = false;
        definition.sprite_paths.fill(definition.texture_path);
        definition.available_rotations.fill(true);
    }

    if (const auto serialized_mask = json_object(json, "colorMask")) {
        const bool enabled = json_bool(*serialized_mask, "enabled").value_or(false);
        if (enabled) {
            if (json_string(*serialized_mask, "contract").value_or("") != "CH_COLOR_MASK_V1") return std::nullopt;
            const auto channels = json_object(*serialized_mask, "channels");
            const auto mask_sprites = json_object(*serialized_mask, "sprites");
            if (!channels || !mask_sprites || json_string(*channels, "R").value_or("") != "wall" ||
                json_string(*channels, "G").value_or("") != "roof") {
                return std::nullopt;
            }
            BuildingColorMaskDefinition mask;
            mask.enabled = true;
            for (std::size_t index = 0; index < mask.sprite_paths.size(); ++index) {
                mask.sprite_paths[index] = json_string(*mask_sprites, std::to_string(index)).value_or("");
                if (definition.available_rotations[index] && mask.sprite_paths[index].empty()) return std::nullopt;
            }
            definition.color_mask = mask;
        }
    }

    if (const auto serialized_activity = json_object(json, "activityOverlay")) {
        const bool enabled = json_bool(*serialized_activity, "enabled").value_or(true);
        if (enabled) {
            if (json_string(*serialized_activity, "contract").value_or("") !=
                "CH_BUILDING_ACTIVITY_OVERLAY_V1") {
                return std::nullopt;
            }
            const auto activity_sprites = json_object(*serialized_activity, "sprites");
            if (!activity_sprites) return std::nullopt;

            BuildingActivityOverlayDefinition activity;
            activity.enabled = true;
            for (std::size_t index = 0; index < activity.sprite_paths.size(); ++index) {
                activity.sprite_paths[index] =
                    json_string(*activity_sprites, std::to_string(index)).value_or("");
                // Never mirror or synthesize an overlay for an authored orientation.
                if (definition.available_rotations[index] && activity.sprite_paths[index].empty()) {
                    return std::nullopt;
                }
            }

            if (const auto overlay_animation = json_object(*serialized_activity, "animation")) {
                const int frame_count = json_number<int>(*overlay_animation, "frameCount").value_or(1);
                if (frame_count < 1) return std::nullopt;
                if (frame_count > 1) {
                    BuildingAnimationDefinition parsed_animation;
                    parsed_animation.frame_count = frame_count;
                    parsed_animation.frame_duration_ms = std::max(
                        1, json_number<int>(*overlay_animation, "frameDurationMs").value_or(120));
                    parsed_animation.layout =
                        json_string(*overlay_animation, "layout").value_or("horizontal");
                    parsed_animation.playback =
                        json_string(*overlay_animation, "playback").value_or("loop");
                    if (parsed_animation.layout != "horizontal" ||
                        (parsed_animation.playback != "loop" && parsed_animation.playback != "ambient_once")) {
                        return std::nullopt;
                    }
                    parsed_animation.idle_frame = std::clamp(
                        json_number<int>(*overlay_animation, "idleFrame").value_or(0), 0, frame_count - 1);
                    parsed_animation.action_start_frame = std::clamp(
                        json_number<int>(*overlay_animation, "actionStartFrame").value_or(1), 0, frame_count - 1);
                    const int available_action_frames = frame_count - parsed_animation.action_start_frame;
                    parsed_animation.action_frame_count = std::clamp(
                        json_number<int>(*overlay_animation, "actionFrameCount").value_or(available_action_frames),
                        0, available_action_frames);
                    parsed_animation.idle_hold_ms = std::max(
                        0, json_number<int>(*overlay_animation, "idleHoldMs").value_or(0));
                    activity.animation = parsed_animation;
                }
            }
            definition.activity_overlay = activity;
        }
    }

    if (const auto serialized_access_points = json_array_objects(json, "accessPoints")) {
        for (const std::string& serialized_access_point : *serialized_access_points) {
            const auto facing = parse_grid_direction(json_string(serialized_access_point, "facing").value_or(""));
            const auto local_x = json_number<int>(serialized_access_point, "x");
            const auto local_y = json_number<int>(serialized_access_point, "y");
            if (!facing || !local_x || !local_y) {
                return std::nullopt;
            }
            definition.access_points.push_back({*local_x, *local_y, *facing});
        }
    }
    if (const auto serialized_mode = json_string(json, "roadAccessMode")) {
        const auto mode = parse_road_access_mode(*serialized_mode);
        if (!mode) return std::nullopt;
        definition.road_access_mode = *mode;
        definition.road_access_mode_explicit = true;
    }
    if (const auto serialized_front_edge = json_string(json, "frontEdge")) {
        const auto edge = parse_grid_direction(*serialized_front_edge);
        if (!edge) return std::nullopt;
        definition.front_edge = *edge;
    }

    if (definition.id.empty() || definition.name.empty() || definition.texture_path.empty() ||
        definition.footprint_width <= 0 || definition.footprint_height <= 0 || definition.build_cost < 0 ||
        definition.maintenance_per_month < 0 || definition.tax_revenue_per_month < 0 ||
        definition.default_service_price < 0 || definition.minimum_service_price < 0 ||
        definition.maximum_service_price < definition.minimum_service_price ||
        (definition.default_service_price > 0 &&
            (definition.service_name.empty() || definition.default_service_price < definition.minimum_service_price ||
             definition.default_service_price > definition.maximum_service_price)) ||
        definition.art_scale <= 0.0F) {
        return std::nullopt;
    }
    for (const BuildingAccessPoint& access_point : definition.access_points) {
        if (access_point.local_x < 0 || access_point.local_x >= definition.footprint_width ||
            access_point.local_y < 0 || access_point.local_y >= definition.footprint_height ||
            !access_point_faces_outward(access_point, definition.footprint_width, definition.footprint_height)) {
            return std::nullopt;
        }
    }
    if (definition.road_access_mode_explicit && definition.road_access_mode == RoadAccessMode::front_edge &&
        !definition.front_edge) {
        return std::nullopt;
    }
    for (std::size_t index = 0; index < definition.sprite_anchor_x.size(); ++index) {
        if (definition.sprite_anchor_x[index] < 0.0F || definition.sprite_anchor_x[index] > 1.0F ||
            definition.sprite_anchor_y[index] < 0.0F || definition.sprite_anchor_y[index] > 1.0F) {
            return std::nullopt;
        }
    }

    // Parse data-driven levels array if provided.
    if (const auto levels_arr = json_array_objects(json, "levels")) {
        for (const std::string& level_json : *levels_arr) {
            BuildingLevelDefinition lvl;
            lvl.level = json_number<int>(level_json, "level").value_or(static_cast<int>(definition.levels.size()) + 1);
            lvl.upgrade_cost = json_number<std::int64_t>(level_json, "upgradeCost").value_or(0);
            lvl.residential_capacity = json_number<std::uint32_t>(level_json, "residentialCapacity").value_or(definition.residential_capacity);
            lvl.power_consumption = json_number<std::uint32_t>(level_json, "powerConsumption").value_or(definition.power_consumption);
            lvl.maintenance_per_month = json_number<std::int64_t>(level_json, "maintenancePerMonth").value_or(definition.maintenance_per_month);
            lvl.tax_revenue_per_month = json_number<std::int64_t>(level_json, "taxRevenuePerMonth").value_or(definition.tax_revenue_per_month);
            lvl.sprite_paths = definition.sprite_paths;
            lvl.sprite_anchor_x = definition.sprite_anchor_x;
            lvl.sprite_anchor_y = definition.sprite_anchor_y;

            if (const auto single_sprite = json_string(level_json, "sprite")) {
                lvl.sprite_paths.fill(*single_sprite);
            } else if (const auto lvl_sprites = json_object(level_json, "sprites")) {
                for (std::size_t index = 0; index < lvl.sprite_paths.size(); ++index) {
                    if (const auto sprite = json_string(*lvl_sprites, std::to_string(index))) {
                        lvl.sprite_paths[index] = *sprite;
                    }
                }
            }
            if (const auto lvl_anchor = json_object(level_json, "anchor")) {
                const float ax = json_number<float>(*lvl_anchor, "x").value_or(definition.anchor_x);
                const float ay = json_number<float>(*lvl_anchor, "y").value_or(definition.anchor_y);
                lvl.sprite_anchor_x.fill(ax);
                lvl.sprite_anchor_y.fill(ay);
            } else if (const auto lvl_anchors = json_object(level_json, "spriteAnchors")) {
                for (std::size_t index = 0; index < lvl.sprite_anchor_x.size(); ++index) {
                    if (const auto sprite_anchor = json_object(*lvl_anchors, std::to_string(index))) {
                        lvl.sprite_anchor_x[index] = json_number<float>(*sprite_anchor, "x").value_or(definition.anchor_x);
                        lvl.sprite_anchor_y[index] = json_number<float>(*sprite_anchor, "y").value_or(definition.anchor_y);
                    }
                }
            }
            definition.levels.push_back(lvl);
        }
    }

    // Default Level 1 construction for legacy definitions
    if (definition.levels.empty()) {
        BuildingLevelDefinition lvl;
        lvl.level = 1;
        lvl.upgrade_cost = 0;
        lvl.residential_capacity = definition.residential_capacity;
        lvl.power_consumption = definition.power_consumption;
        lvl.maintenance_per_month = definition.maintenance_per_month;
        lvl.tax_revenue_per_month = definition.tax_revenue_per_month;
        lvl.sprite_paths = definition.sprite_paths;
        lvl.sprite_anchor_x = definition.sprite_anchor_x;
        lvl.sprite_anchor_y = definition.sprite_anchor_y;
        definition.levels.push_back(lvl);
    }

    return definition;
}

}  // namespace

const BuildingLevelDefinition& BuildingDefinition::level_definition(const int level) const {
    if (levels.empty()) {
        thread_local BuildingLevelDefinition fallback;
        fallback.level = 1;
        fallback.upgrade_cost = 0;
        fallback.residential_capacity = residential_capacity;
        fallback.power_consumption = power_consumption;
        fallback.maintenance_per_month = maintenance_per_month;
        fallback.tax_revenue_per_month = tax_revenue_per_month;
        fallback.sprite_paths = sprite_paths;
        fallback.sprite_anchor_x = sprite_anchor_x;
        fallback.sprite_anchor_y = sprite_anchor_y;
        return fallback;
    }
    const int clamped = std::max(1, std::min(level, static_cast<int>(levels.size())));
    return levels[static_cast<std::size_t>(clamped - 1)];
}

const std::string& BuildingDefinition::texture_path_for(const BuildingRotation rotation, const int level) const {
    const auto& lvl = level_definition(level);
    if (rotatable && supports_rotation(rotation)) {
        return lvl.sprite_paths[static_cast<std::size_t>(rotation)];
    }
    if (level > 1 && !lvl.sprite_paths[0].empty()) {
        return lvl.sprite_paths[0];
    }
    if (!texture_path.empty()) {
        return texture_path;
    }
    return lvl.sprite_paths[0];
}

const std::string& BuildingDefinition::color_mask_path_for(const BuildingRotation rotation) const {
    static const std::string empty;
    if (!supports_color_mask(rotation)) return empty;
    return color_mask->sprite_paths[static_cast<std::size_t>(rotation)];
}

bool BuildingDefinition::supports_color_mask(const BuildingRotation rotation) const {
    return color_mask.has_value() && color_mask->enabled && supports_rotation(rotation) &&
           !color_mask->sprite_paths[static_cast<std::size_t>(rotation)].empty();
}

float BuildingDefinition::anchor_x_for(const BuildingRotation rotation, const int level) const {
    const auto& lvl = level_definition(level);
    return lvl.sprite_anchor_x[static_cast<std::size_t>(rotation)];
}

float BuildingDefinition::anchor_y_for(const BuildingRotation rotation, const int level) const {
    const auto& lvl = level_definition(level);
    return lvl.sprite_anchor_y[static_cast<std::size_t>(rotation)];
}

bool BuildingInstance::is_max_level(const BuildingDefinition& definition) const {
    return current_level >= static_cast<int>(definition.levels.size());
}

const BuildingLevelDefinition& BuildingInstance::current_level_definition(const BuildingDefinition& definition) const {
    return definition.level_definition(current_level);
}

const BuildingLevelDefinition* BuildingInstance::next_level_definition(const BuildingDefinition& definition) const {
    if (is_max_level(definition)) {
        return nullptr;
    }
    return &definition.level_definition(current_level + 1);
}

bool BuildingInstance::try_upgrade(const BuildingDefinition& definition, CityEconomy& economy, const GameDate& date) {
    const BuildingLevelDefinition* next = next_level_definition(definition);
    if (next == nullptr) {
        return false;
    }
    if (!economy.can_afford(next->upgrade_cost)) {
        return false;
    }
    if (!economy.spend_for_building(next->upgrade_cost, date, instance_id)) {
        return false;
    }
    current_level++;
    return true;
}

bool BuildingDefinition::supports_rotation(const BuildingRotation rotation) const {
    return !rotatable || available_rotations[static_cast<std::size_t>(rotation)];
}

BuildingRotation BuildingDefinition::next_supported_rotation(const BuildingRotation rotation, const bool clockwise) const {
    if (!rotatable) {
        return BuildingRotation::r0;
    }
    BuildingRotation candidate = rotation;
    for (int turn = 0; turn < 4; ++turn) {
        candidate = clockwise ? rotate_clockwise(candidate) : rotate_counter_clockwise(candidate);
        if (supports_rotation(candidate)) {
            return candidate;
        }
    }
    return BuildingRotation::r0;
}

BuildingRotation rotate_clockwise(const BuildingRotation rotation) {
    return static_cast<BuildingRotation>((static_cast<std::uint8_t>(rotation) + 1U) % 4U);
}

BuildingRotation rotate_counter_clockwise(const BuildingRotation rotation) {
    return static_cast<BuildingRotation>((static_cast<std::uint8_t>(rotation) + 3U) % 4U);
}

const char* rotation_label(const BuildingRotation rotation) {
    switch (rotation) {
        case BuildingRotation::r0: return "R0";
        case BuildingRotation::r90: return "R90";
        case BuildingRotation::r180: return "R180";
        case BuildingRotation::r270: return "R270";
    }
    return "R0";
}

BuildingFootprint rotated_footprint(const BuildingDefinition& definition, const BuildingRotation rotation) {
    if (!definition.rotatable) {
        return {definition.footprint_width, definition.footprint_height};
    }
    const bool swap_dimensions = rotation == BuildingRotation::r90 || rotation == BuildingRotation::r270;
    return swap_dimensions
        ? BuildingFootprint{definition.footprint_height, definition.footprint_width}
        : BuildingFootprint{definition.footprint_width, definition.footprint_height};
}

BuildingAccessPoint rotate_access_point(const BuildingDefinition& definition, BuildingAccessPoint access_point,
                                        const BuildingRotation rotation) {
    if (!definition.rotatable) {
        return access_point;
    }
    int width = definition.footprint_width;
    int height = definition.footprint_height;
    for (std::uint8_t turn = 0; turn < static_cast<std::uint8_t>(rotation); ++turn) {
        const int previous_x = access_point.local_x;
        access_point.local_x = height - 1 - access_point.local_y;
        access_point.local_y = previous_x;
        access_point.facing = static_cast<GridDirection>((static_cast<std::uint8_t>(access_point.facing) + 1U) % 4U);
        std::swap(width, height);
    }
    return access_point;
}

std::vector<BuildingAccessPoint> rotated_access_points(const BuildingDefinition& definition,
                                                        const BuildingRotation rotation) {
    std::vector<BuildingAccessPoint> result;
    result.reserve(definition.access_points.size());
    for (const BuildingAccessPoint access_point : definition.access_points) {
        result.push_back(rotate_access_point(definition, access_point, rotation));
    }
    return result;
}

RoadAccessMode resolved_road_access_mode(const BuildingDefinition& definition) {
    if (definition.road_access_mode_explicit) return definition.road_access_mode;
    if (!definition.rotatable) return RoadAccessMode::any_perimeter;
    // Saves and definitions from before front_edge already declared their
    // intended doors through accessPoints. Keep that stricter behaviour.
    return definition.access_points.empty() ? RoadAccessMode::any_perimeter : RoadAccessMode::access_points;
}

const char* road_access_mode_label(const RoadAccessMode mode) {
    switch (mode) {
        case RoadAccessMode::any_perimeter: return "ANY PERIMETER";
        case RoadAccessMode::access_points: return "ACCESS POINTS";
        case RoadAccessMode::front_edge: return "FRONT EDGE";
    }
    return "ANY PERIMETER";
}

std::vector<BuildingAccessPoint> front_edge_access_points(const BuildingDefinition& definition,
                                                           const BuildingRotation rotation) {
    if (!definition.front_edge) return {};
    std::vector<BuildingAccessPoint> base_points;
    switch (*definition.front_edge) {
        case GridDirection::north:
            for (int x = 0; x < definition.footprint_width; ++x) base_points.push_back({x, 0, GridDirection::north});
            break;
        case GridDirection::east:
            for (int y = 0; y < definition.footprint_height; ++y) base_points.push_back({definition.footprint_width - 1, y, GridDirection::east});
            break;
        case GridDirection::south:
            for (int x = 0; x < definition.footprint_width; ++x) base_points.push_back({x, definition.footprint_height - 1, GridDirection::south});
            break;
        case GridDirection::west:
            for (int y = 0; y < definition.footprint_height; ++y) base_points.push_back({0, y, GridDirection::west});
            break;
    }

    std::vector<BuildingAccessPoint> result;
    result.reserve(base_points.size());
    for (const BuildingAccessPoint point : base_points) result.push_back(rotate_access_point(definition, point, rotation));
    return result;
}

std::vector<BuildingAccessPoint> road_access_candidates(const BuildingDefinition& definition,
                                                        const BuildingRotation rotation) {
    switch (resolved_road_access_mode(definition)) {
        case RoadAccessMode::front_edge: return front_edge_access_points(definition, rotation);
        case RoadAccessMode::access_points: return rotated_access_points(definition, rotation);
        case RoadAccessMode::any_perimeter: return {};
    }
    return {};
}

bool BuildingCatalog::load_from_directory(const std::filesystem::path& directory) {
    definitions_.clear();
    if (!std::filesystem::is_directory(directory)) {
        std::cerr << "Building definitions directory not found: " << directory << '\n';
        return false;
    }

    for (const auto& entry : std::filesystem::directory_iterator(directory)) {
        if (!entry.is_regular_file() || entry.path().extension() != ".json") {
            continue;
        }
        // This directory also contains non-building catalogs (for example the
        // road visual catalog). They are data, not invalid building definitions.
        if (!json_string(read_file(entry.path()), "id")) {
            continue;
        }
        const auto definition = parse_definition(entry.path());
        if (!definition) {
            std::cerr << "Ignoring invalid building definition: " << entry.path() << '\n';
            continue;
        }
        if (find(definition->id) != nullptr) {
            std::cerr << "Ignoring duplicate building definition id: " << definition->id << '\n';
            continue;
        }
        definitions_.push_back(*definition);
    }
    return !definitions_.empty();
}

const BuildingDefinition* BuildingCatalog::find(std::string_view id) const {
    const auto found = std::find_if(definitions_.begin(), definitions_.end(), [id](const BuildingDefinition& definition) {
        return definition.id == id;
    });
    return found == definitions_.end() ? nullptr : &*found;
}

const std::vector<BuildingDefinition>& BuildingCatalog::definitions() const {
    return definitions_;
}

BuildingManager::BuildingManager(int map_min, int map_max)
    : map_min_(map_min), map_max_(map_max) {}

PlacementFailure BuildingManager::validate(const BuildingDefinition& definition, int tile_x, int tile_y,
                                           const BuildingRotation rotation) const {
    if (!definition.supports_rotation(rotation)) {
        return PlacementFailure::unavailable_rotation;
    }

    ch::PlacementRequest req;
    req.object_id = definition.id;
    req.category = ch::PlacementCategory::building;
    req.origin = ch::GridCoord(tile_x, tile_y);
    req.rotation = static_cast<int>(rotation);

    struct SingleCatalogAdapter : public ch::IAssetCatalogView {
        const BuildingDefinition& def;
        explicit SingleCatalogAdapter(const BuildingDefinition& d) : def(d) {}
        ch::AssetFootprintInfo get_footprint(std::string_view) const override {
            return {def.footprint_width, def.footprint_height, true};
        }
    };

    ch::SemanticWorldView world;
    world.map_min = map_min_;
    world.map_max = map_max_;
    SingleCatalogAdapter adapter(definition);
    ch::PlacementResult res = ch::PlacementEngine::can_place(req, world, adapter);

    if (res.state != ch::SemanticState::valid) {
        for (const auto v : res.violations) {
            if (v == ch::PlacementViolation::bounds_exceeded) return PlacementFailure::outside_map;
            if (v == ch::PlacementViolation::occupied) return PlacementFailure::occupied;
        }
    }

    const BuildingFootprint footprint = rotated_footprint(definition, rotation);
    for (int offset_y = 0; offset_y < footprint.height; ++offset_y) {
        for (int offset_x = 0; offset_x < footprint.width; ++offset_x) {
            const int checked_x = tile_x + offset_x;
            const int checked_y = tile_y + offset_y;
            if (!is_inside_map(checked_x, checked_y)) {
                return PlacementFailure::outside_map;
            }
            if (is_occupied(checked_x, checked_y)) {
                return PlacementFailure::occupied;
            }
        }
    }
    return PlacementFailure::none;
}

std::optional<std::uint64_t> BuildingManager::place(const BuildingDefinition& definition, int tile_x, int tile_y,
                                                     const BuildingRotation rotation) {
    if (validate(definition, tile_x, tile_y, rotation) != PlacementFailure::none) {
        return std::nullopt;
    }

    BuildingInstance instance;
    instance.instance_id = next_instance_id_++;
    instance.definition_id = definition.id;
    instance.tile_x = tile_x;
    instance.tile_y = tile_y;
    instance.rotation = definition.rotatable ? rotation : BuildingRotation::r0;
    instance.operational = !definition.preplaced || definition.unlock_requirement.empty();
    instance.service_price = definition.default_service_price;
    instances_.push_back(instance);

    const BuildingFootprint footprint = rotated_footprint(definition, instance.rotation);
    for (int offset_y = 0; offset_y < footprint.height; ++offset_y) {
        for (int offset_x = 0; offset_x < footprint.width; ++offset_x) {
            occupancy_[tile_key(tile_x + offset_x, tile_y + offset_y)] = instance.instance_id;
        }
    }
    return instance.instance_id;
}

bool BuildingManager::remove_instance(const BuildingDefinition& definition, const std::uint64_t instance_id) {
    const auto found = std::find_if(instances_.begin(), instances_.end(), [instance_id](const BuildingInstance& instance) {
        return instance.instance_id == instance_id;
    });
    if (found == instances_.end() || found->definition_id != definition.id) return false;
    const BuildingFootprint footprint = rotated_footprint(definition, found->rotation);
    for (int offset_y = 0; offset_y < footprint.height; ++offset_y) {
        for (int offset_x = 0; offset_x < footprint.width; ++offset_x) {
            occupancy_.erase(tile_key(found->tile_x + offset_x, found->tile_y + offset_y));
        }
    }
    instances_.erase(found);
    return true;
}

bool BuildingManager::restore_instance(const BuildingDefinition& definition, const BuildingInstance& serialized) {
    if (serialized.instance_id == 0 || serialized.definition_id != definition.id ||
        static_cast<std::uint8_t>(serialized.rotation) > static_cast<std::uint8_t>(BuildingRotation::r270) ||
        find_by_id(serialized.instance_id) != nullptr ||
        validate(definition, serialized.tile_x, serialized.tile_y, serialized.rotation) != PlacementFailure::none) {
        return false;
    }

    BuildingInstance instance = serialized;
    // Activity represents visitors currently inside and is intentionally not
    // restored from a save session.
    instance.activity_count = 0;
    if (!definition.rotatable) {
        instance.rotation = BuildingRotation::r0;
    }
    if (definition.default_service_price > 0) {
        const std::int64_t serialized_price = instance.service_price > 0
            ? static_cast<std::int64_t>(instance.service_price)
            : static_cast<std::int64_t>(definition.default_service_price);
        const std::int64_t clamped = std::clamp(
            serialized_price,
            static_cast<std::int64_t>(definition.minimum_service_price),
            static_cast<std::int64_t>(definition.maximum_service_price));
        instance.service_price = definition.default_service_price.with_minor_units(clamped);
    } else {
        instance.service_price = ch::ServicePrice{};
    }
    instances_.push_back(instance);
    const BuildingFootprint footprint = rotated_footprint(definition, instance.rotation);
    for (int offset_y = 0; offset_y < footprint.height; ++offset_y) {
        for (int offset_x = 0; offset_x < footprint.width; ++offset_x) {
            occupancy_[tile_key(instance.tile_x + offset_x, instance.tile_y + offset_y)] = instance.instance_id;
        }
    }
    next_instance_id_ = std::max(next_instance_id_, instance.instance_id + 1U);
    return true;
}

void BuildingManager::clear() {
    instances_.clear();
    occupancy_.clear();
    next_instance_id_ = 1;
}

void BuildingManager::set_next_instance_id(const std::uint64_t next_instance_id) {
    next_instance_id_ = std::max(next_instance_id, next_instance_id_);
}

std::uint64_t BuildingManager::next_instance_id() const {
    return next_instance_id_;
}

const BuildingInstance* BuildingManager::find_by_id(std::uint64_t instance_id) const {
    const auto found = std::find_if(instances_.begin(), instances_.end(), [instance_id](const BuildingInstance& instance) {
        return instance.instance_id == instance_id;
    });
    return found == instances_.end() ? nullptr : &*found;
}

const BuildingInstance* BuildingManager::instance_at(int tile_x, int tile_y) const {
    if (!is_inside_map(tile_x, tile_y)) {
        return nullptr;
    }
    const auto occupied = occupancy_.find(tile_key(tile_x, tile_y));
    return occupied == occupancy_.end() ? nullptr : find_by_id(occupied->second);
}

bool BuildingManager::is_occupied(int tile_x, int tile_y) const {
    return is_inside_map(tile_x, tile_y) && occupancy_.contains(tile_key(tile_x, tile_y));
}

const std::vector<BuildingInstance>& BuildingManager::instances() const {
    return instances_;
}

bool BuildingManager::set_operational(const std::uint64_t instance_id, const bool operational) {
    const auto found = std::find_if(instances_.begin(), instances_.end(), [instance_id](BuildingInstance& instance) {
        return instance.instance_id == instance_id;
    });
    if (found == instances_.end()) {
        return false;
    }
    found->operational = operational;
    return true;
}

bool BuildingManager::begin_activity(const std::uint64_t instance_id) {
    const auto found = std::find_if(instances_.begin(), instances_.end(), [instance_id](BuildingInstance& instance) {
        return instance.instance_id == instance_id;
    });
    if (found == instances_.end()) return false;
    if (found->activity_count < std::numeric_limits<std::uint32_t>::max()) {
        ++found->activity_count;
    }
    return true;
}

bool BuildingManager::end_activity(const std::uint64_t instance_id) {
    const auto found = std::find_if(instances_.begin(), instances_.end(), [instance_id](BuildingInstance& instance) {
        return instance.instance_id == instance_id;
    });
    if (found == instances_.end() || found->activity_count == 0) return false;
    --found->activity_count;
    return true;
}

bool BuildingManager::set_service_price(const std::uint64_t instance_id, const BuildingDefinition& definition,
                                        const std::int64_t service_price) {
    const std::int64_t minimum = definition.minimum_service_price;
    const std::int64_t maximum = definition.maximum_service_price;
    if (definition.default_service_price <= 0 || maximum < minimum) {
        return false;
    }
    const auto found = std::find_if(instances_.begin(), instances_.end(), [instance_id](BuildingInstance& instance) {
        return instance.instance_id == instance_id;
    });
    if (found == instances_.end() || found->definition_id != definition.id) {
        return false;
    }

    const std::int64_t current = found->service_price;
    const std::int64_t step = std::max<std::int64_t>(1, definition.default_service_price.step_minor_units);
    std::int64_t target = service_price;
    // Existing UI actions request current +/- 1. For minor-unit contracts,
    // translate that intent to the definition's configured click step.
    if (step > 1 && service_price == current + 1) target = current + step;
    else if (step > 1 && service_price == current - 1) target = current - step;

    target = std::clamp(target, minimum, maximum);
    found->service_price = definition.default_service_price.with_minor_units(target);
    return true;
}

bool BuildingManager::set_color_customization(const std::uint64_t instance_id, const BuildingColorTint wall,
                                              const BuildingColorTint roof) {
    const auto found = std::find_if(instances_.begin(), instances_.end(), [instance_id](BuildingInstance& instance) {
        return instance.instance_id == instance_id;
    });
    if (found == instances_.end()) return false;
    found->wall_tint = wall;
    found->roof_tint = roof;
    found->wall_color_customized = true;
    found->roof_color_customized = true;
    return true;
}

bool BuildingManager::set_wall_color_customization(const std::uint64_t instance_id, const BuildingColorTint wall) {
    const auto found = std::find_if(instances_.begin(), instances_.end(), [instance_id](BuildingInstance& instance) {
        return instance.instance_id == instance_id;
    });
    if (found == instances_.end()) return false;
    found->wall_tint = wall;
    found->wall_color_customized = true;
    return true;
}

bool BuildingManager::set_roof_color_customization(const std::uint64_t instance_id, const BuildingColorTint roof) {
    const auto found = std::find_if(instances_.begin(), instances_.end(), [instance_id](BuildingInstance& instance) {
        return instance.instance_id == instance_id;
    });
    if (found == instances_.end()) return false;
    found->roof_tint = roof;
    found->roof_color_customized = true;
    return true;
}

bool BuildingManager::clear_color_customization(const std::uint64_t instance_id) {
    const auto found = std::find_if(instances_.begin(), instances_.end(), [instance_id](BuildingInstance& instance) {
        return instance.instance_id == instance_id;
    });
    if (found == instances_.end()) return false;
    found->wall_color_customized = false;
    found->roof_color_customized = false;
    found->wall_tint = {};
    found->roof_tint = {};
    return true;
}

std::size_t BuildingManager::set_operational_by_definition(const std::string_view definition_id, const bool operational) {
    std::size_t count = 0;
    for (BuildingInstance& instance : instances_) {
        if (instance.definition_id == definition_id) {
            instance.operational = operational;
            count++;
        }
    }
    return count;
}

bool BuildingManager::is_inside_map(int tile_x, int tile_y) const {
    return tile_x >= map_min_ && tile_x <= map_max_ && tile_y >= map_min_ && tile_y <= map_max_;
}

int BuildingManager::tile_key(int tile_x, int tile_y) const {
    const int span = map_max_ - map_min_ + 1;
    return (tile_y - map_min_) * span + (tile_x - map_min_);
}
