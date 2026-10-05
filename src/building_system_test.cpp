#include "building_system.h"
#include "economy_system.h"
#include "gameplay_commands.h"
#include "road_system.h"

#include <iostream>
#include <string>

namespace {

bool require(const bool condition, const char* description) {
    if (!condition) std::cerr << "FAILED: " << description << '\n';
    return condition;
}

}  // namespace

int main(int argc, char** argv) {
    if (!require(argc == 2, "definitions directory argument")) return 1;

    BuildingCatalog catalog;
    if (!require(catalog.load_from_directory(argv[1]), "runtime building catalog loads")) return 1;

    const BuildingDefinition* coffee = catalog.find("coffee_shop_01");
    const BuildingDefinition* bakery = catalog.find("bakery_01");
    const BuildingDefinition* house = catalog.find("residential_popular_house_01");
    const BuildingDefinition* carousel = catalog.find("carousel_city_horizon_01");
    if (!require(coffee != nullptr, "coffee shop definition exists") ||
        !require(bakery != nullptr, "bakery definition exists") ||
        !require(house != nullptr, "popular house definition exists") ||
        !require(carousel != nullptr, "carousel definition exists")) {
        return 1;
    }

    if (!require(coffee->name == "Cafeteria" && coffee->category == "commercial",
                 "coffee shop identity comes from runtime JSON") ||
        !require(coffee->footprint_width == 2 && coffee->footprint_height == 2 && coffee->rotatable,
                 "coffee shop uses the current 2x2 rotatable footprint") ||
        !require(coffee->requires_road_access && resolved_road_access_mode(*coffee) == RoadAccessMode::front_edge,
                 "coffee shop uses the current front-edge road contract") ||
        !require(coffee->supports_rotation(BuildingRotation::r0) &&
                     coffee->supports_rotation(BuildingRotation::r90) &&
                     coffee->supports_rotation(BuildingRotation::r180) &&
                     coffee->supports_rotation(BuildingRotation::r270),
                 "coffee shop exposes all four prerendered rotations") ||
        !require(coffee->default_service_price.minor_units == 300 &&
                     coffee->minimum_service_price.minor_units == 50 &&
                     coffee->maximum_service_price.minor_units == 2000 &&
                     coffee->default_service_price.units_per_dollar == 100,
                 "coffee shop keeps CH_SERVICE_PRICE_V1 pricing")) {
        return 1;
    }

    if (!require(bakery->build_cost == 2500 && bakery->base_service_customers_per_month == 120,
                 "bakery retains its current service economy") ||
        !require(house->category == "residential" && house->footprint_width == 3 && house->footprint_height == 3 &&
                     house->residential_capacity == 5 && house->rotatable,
                 "popular house uses the current 3x3 residential contract") ||
        !require(carousel->category == "city_park" && carousel->player_buildable && carousel->rotatable,
                 "carousel is exposed as a buildable city-park attraction") ||
        !require(carousel->footprint_width == 4 && carousel->footprint_height == 4 && carousel->build_cost == 15000,
                 "carousel keeps the approved 4x4 footprint and provisional build price") ||
        !require(carousel->default_service_price.minor_units == 5 &&
                     carousel->minimum_service_price.minor_units == 1 &&
                     carousel->maximum_service_price.minor_units == 30,
                 "carousel ticket price range loads from runtime JSON") ||
        !require(carousel->animation.has_value() && carousel->animation->frame_count == 48 &&
                     carousel->animation->frame_duration_ms == 100 &&
                     carousel->animation->playback == "activity_loop",
                 "carousel exposes the promoted 48-frame activity animation") ||
        !require(carousel->color_mask.has_value() && carousel->color_mask->enabled,
                 "carousel primary color mask is available to runtime")) {
        return 1;
    }

    const BuildingFootprint rotated = rotated_footprint(*house, BuildingRotation::r90);
    if (!require(rotated.width == 3 && rotated.height == 3, "square residential footprint remains square when rotated")) {
        return 1;
    }

    const auto coffee_access = road_access_candidates(*coffee, BuildingRotation::r0);
    if (!require(!coffee_access.empty(), "coffee shop exposes road-access candidates")) return 1;

    BuildingManager buildings(-16, 16);
    const auto coffee_id = buildings.place(*coffee, 0, 0, BuildingRotation::r0);
    if (!require(coffee_id.has_value(), "coffee shop placement succeeds") ||
        !require(buildings.is_occupied(0, 0) && buildings.is_occupied(1, 1), "placement occupies the full footprint") ||
        !require(buildings.validate(*coffee, 1, 1, BuildingRotation::r0) == PlacementFailure::occupied,
                 "overlapping placement is rejected")) {
        return 1;
    }

    if (!require(buildings.begin_activity(*coffee_id), "activity begins on placed building") ||
        !require(buildings.find_by_id(*coffee_id) != nullptr && buildings.find_by_id(*coffee_id)->activity_active(),
                 "activity state becomes visible") ||
        !require(buildings.end_activity(*coffee_id), "activity ends cleanly")) {
        return 1;
    }

    if (!require(buildings.set_service_price(*coffee_id, *coffee, 325), "service price update is accepted") ||
        !require(buildings.find_by_id(*coffee_id)->service_price.minor_units == 325,
                 "per-instance service price is stored") ||
        !require(buildings.set_service_price(*coffee_id, *coffee, 326), "arbitrary in-range service price is accepted") ||
        !require(buildings.find_by_id(*coffee_id)->service_price.minor_units == 326,
                 "in-range service price is preserved exactly") ||
        !require(buildings.set_service_price(*coffee_id, *coffee, 10), "below-range service price is clamped") ||
        !require(buildings.find_by_id(*coffee_id)->service_price.minor_units == 50,
                 "service price clamps to configured minimum") ||
        !require(buildings.set_service_price(*coffee_id, *coffee, 5000), "above-range service price is clamped") ||
        !require(buildings.find_by_id(*coffee_id)->service_price.minor_units == 2000,
                 "service price clamps to configured maximum")) {
        return 1;
    }

    if (!require(buildings.remove_instance(*coffee, *coffee_id), "placed coffee shop can be removed") ||
        !require(!buildings.is_occupied(0, 0), "removal releases occupied tiles")) {
        return 1;
    }

    const auto house_id = buildings.place(*house, 4, 4, BuildingRotation::r270);
    if (!require(house_id.has_value(), "current residential building places at a rotated orientation") ||
        !require(buildings.find_by_id(*house_id) != nullptr &&
                     buildings.find_by_id(*house_id)->rotation == BuildingRotation::r270,
                 "logical rotation persists on the instance")) {
        return 1;
    }

    // CH_GAME_COMMAND_V1 vertical slice: preview does not spend or mutate;
    // execute consumes the exact previewed cost and produces the road tile.
    RoadManager roads(-16, 16);
    CityEconomy economy(1000);
    const auto tile_owned = [](const int x, const int y) {
        return x >= -16 && x <= 15 && y >= -16 && y <= 15;
    };
    RoadPlacementCommand road_command(roads, buildings, tile_owned, economy, -2, -2);
    const auto preview = ch::GameCommandExecutor::run(road_command, ch::GameCommandMode::preview);
    if (!require(preview.success && !preview.applied, "road command preview succeeds without applying") ||
        !require(preview.cost_units == kRoadCostPerTile && economy.funds() == 1000,
                 "road preview reports cost without spending") ||
        !require(!roads.is_road(-2, -2), "road preview does not mutate road manager")) {
        return 1;
    }
    const auto executed = ch::GameCommandExecutor::run(road_command, ch::GameCommandMode::execute);
    if (!require(executed.success && executed.applied, "road command executes") ||
        !require(roads.is_road(-2, -2), "road command places the requested tile") ||
        !require(economy.funds() == 1000 - kRoadCostPerTile,
                 "road command charges the same cost exposed by preview")) {
        return 1;
    }

    RoadPlacementCommand occupied_command(roads, buildings, tile_owned, economy, -2, -2);
    const auto occupied = ch::GameCommandExecutor::run(occupied_command, ch::GameCommandMode::execute);
    if (!require(!occupied.success && !occupied.applied &&
                     occupied.failure == ch::GameCommandFailure::conflicting_state,
                 "road command rejects an occupied tile before spending") ||
        !require(economy.funds() == 1000 - kRoadCostPerTile,
                 "rejected road command leaves funds unchanged")) {
        return 1;
    }

    RoadPlacementCommand locked_land(roads, buildings, tile_owned, economy, 16, 0);
    const auto locked = ch::GameCommandExecutor::run(locked_land, ch::GameCommandMode::execute);
    if (!require(!locked.success && !locked.applied && locked.failure == ch::GameCommandFailure::blocked,
                 "road command rejects unowned land") ||
        !require(economy.funds() == 1000 - kRoadCostPerTile,
                 "unowned-land rejection leaves funds unchanged")) {
        return 1;
    }

    // Water uses the same semantic terrain command. The approved shallow-water
    // build price is 50 game units; preview must not charge or mutate.
    ch::MapDocument terrain = ch::MapDocument::create_empty("command-test", 32, 32);
    TerrainPaintCommand shallow_water(terrain, tile_owned, economy, -3, -3, "water_shallow",
                                      "assets/terrain/water/water_shallow_world.png", 50);
    const auto water_preview = ch::GameCommandExecutor::run(shallow_water, ch::GameCommandMode::preview);
    if (!require(water_preview.success && !water_preview.applied && water_preview.cost_units == 50,
                 "shallow-water preview exposes approved cost without applying") ||
        !require(economy.funds() == 1000 - kRoadCostPerTile,
                 "shallow-water preview does not spend funds") ||
        !require(!terrain.get_terrain_at(-3, -3).has_value(),
                 "shallow-water preview does not mutate terrain")) {
        return 1;
    }
    const auto water_executed = ch::GameCommandExecutor::run(shallow_water, ch::GameCommandMode::execute);
    const auto painted_water = terrain.get_terrain_at(-3, -3);
    if (!require(water_executed.success && water_executed.applied,
                 "shallow-water command executes") ||
        !require(painted_water.has_value() && painted_water->terrain_definition == "water_shallow",
                 "water command writes semantic terrain definition") ||
        !require(economy.funds() == 1000 - kRoadCostPerTile - 50,
                 "water execution charges the exact previewed cost")) {
        return 1;
    }

    // Building placement and demolition now use the same transactional command
    // boundary. Surround the candidate footprint with roads so this fixture is
    // independent of the definition's particular road-access edge.
    for (int x = 8; x <= 10; ++x) {
        (void)roads.place_tile(x, -9);
        (void)roads.place_tile(x, -5);
    }
    for (int y = -8; y <= -6; ++y) {
        (void)roads.place_tile(7, y);
        (void)roads.place_tile(11, y);
    }
    CityEconomy construction_economy(100'000);
    const std::int64_t construction_funds = construction_economy.funds();
    BuildingPlacementCommand place_house(buildings, roads, tile_owned, construction_economy,
                                         *house, 8, -8, BuildingRotation::r0, GameDate{1, 1, 1});
    const auto building_preview = ch::GameCommandExecutor::run(place_house, ch::GameCommandMode::preview);
    if (!require(building_preview.success && !building_preview.applied,
                 "building command preview succeeds without applying") ||
        !require(building_preview.cost_units == house->build_cost &&
                     construction_economy.funds() == construction_funds,
                 "building preview exposes exact cost without spending") ||
        !require(buildings.instance_at(8, -8) == nullptr,
                 "building preview does not mutate occupancy")) {
        return 1;
    }

    const auto building_executed = ch::GameCommandExecutor::run(place_house, ch::GameCommandMode::execute);
    const BuildingInstance* commanded_house = buildings.instance_at(8, -8);
    if (!require(building_executed.success && building_executed.applied,
                 "building placement command executes") ||
        !require(commanded_house != nullptr && commanded_house->definition_id == house->id,
                 "building command creates the requested definition") ||
        !require(construction_economy.funds() == construction_funds - house->build_cost,
                 "building command charges the exact previewed cost")) {
        return 1;
    }

    const std::uint64_t commanded_house_id = commanded_house->instance_id;
    BuildingDemolitionCommand demolish_house(buildings, *house, commanded_house_id);
    const auto demolition_preview = ch::GameCommandExecutor::run(demolish_house, ch::GameCommandMode::preview);
    if (!require(demolition_preview.success && !demolition_preview.applied,
                 "demolition preview succeeds without mutating") ||
        !require(buildings.find_by_id(commanded_house_id) != nullptr,
                 "demolition preview leaves building present")) {
        return 1;
    }
    const auto demolition_executed = ch::GameCommandExecutor::run(demolish_house, ch::GameCommandMode::execute);
    if (!require(demolition_executed.success && demolition_executed.applied,
                 "demolition command executes") ||
        !require(buildings.find_by_id(commanded_house_id) == nullptr && !buildings.is_occupied(8, -8),
                 "demolition command releases building occupancy")) {
        return 1;
    }

    std::cout << "building system tests passed\n";
    return 0;
}
