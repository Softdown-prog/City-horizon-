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
    if (!require(coffee != nullptr, "coffee shop definition exists") ||
        !require(bakery != nullptr, "bakery definition exists") ||
        !require(house != nullptr, "popular house definition exists")) {
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
                 "popular house uses the current 3x3 residential contract")) {
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
    RoadPlacementCommand road_command(roads, buildings, economy, -2, -2);
    const auto preview = ch::GameCommandExecutor::run(road_command, ch::GameCommandMode::preview);
    if (!require(preview.success && !preview.applied, "road command preview succeeds without applying") ||
        !require(preview.cost_cents == kRoadCostPerTile && economy.funds() == 1000,
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

    RoadPlacementCommand occupied_command(roads, buildings, economy, -2, -2);
    const auto occupied = ch::GameCommandExecutor::run(occupied_command, ch::GameCommandMode::execute);
    if (!require(!occupied.success && !occupied.applied &&
                     occupied.failure == ch::GameCommandFailure::conflicting_state,
                 "road command rejects an occupied tile before spending") ||
        !require(economy.funds() == 1000 - kRoadCostPerTile,
                 "rejected road command leaves funds unchanged")) {
        return 1;
    }

    std::cout << "building system tests passed\n";
    return 0;
}
