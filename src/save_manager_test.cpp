#include "building_system.h"
#include "economy_system.h"
#include "farming_system.h"
#include "land_system.h"
#include "mission_system.h"
#include "population_system.h"
#include "power_system.h"
#include "road_system.h"
#include "save_manager.h"
#include "simulation_clock.h"
#include "sidewalk_system.h"

#include <algorithm>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

namespace {

constexpr int kMapMin = -24;
constexpr int kMapMax = 23;

bool require(const bool condition, const std::string& message) {
    if (!condition) {
        std::cerr << "FAILED: " << message << '\n';
    }
    return condition;
}

bool write_text(const std::filesystem::path& path, const std::string& text) {
    std::ofstream output(path, std::ios::binary | std::ios::trunc);
    output << text;
    return static_cast<bool>(output);
}

std::size_t property_tax_transaction_count(const CityEconomy& economy) {
    return static_cast<std::size_t>(std::count_if(economy.ledger().begin(), economy.ledger().end(),
        [](const EconomyTransaction& transaction) {
            return transaction.type == EconomyTransactionType::property_tax;
        }));
}

}  // namespace

int main(const int argc, char** argv) {
    if (argc != 2) {
        std::cerr << "usage: save_manager_test <building-definition-directory>\n";
        return 2;
    }
    const std::filesystem::path definitions = argv[1];
    const std::filesystem::path test_directory = std::filesystem::temp_directory_path() / "city_builder_save_manager_test";
    const std::filesystem::path save_file = test_directory / "round_trip.json";
    const std::filesystem::path invalid_file = test_directory / "invalid.json";
    const std::filesystem::path unsupported_file = test_directory / "unsupported.json";
    const std::filesystem::path missing_definition_file = test_directory / "missing_definition.json";
    const std::filesystem::path legacy_roadless_file = test_directory / "legacy_roadless.json";
    std::filesystem::create_directories(test_directory);

    BuildingCatalog catalog;
    if (!require(catalog.load_from_directory(definitions), "building catalog loads")) {
        return 1;
    }
    const BuildingDefinition* cafe = catalog.find("cafe_01");
    const BuildingDefinition* mini_market = catalog.find("mini_market_01");
    const BuildingDefinition* house = catalog.find("house_suburban_01");
    const BuildingDefinition* ferris = catalog.find("ferris_wheel_01");
    const BuildingDefinition* ticket_booth = catalog.find("park_ticket_booth_01");
    if (!require(cafe != nullptr, "cafe definition exists") ||
        !require(mini_market != nullptr, "mini market definition exists") ||
        !require(house != nullptr, "house definition exists") ||
        !require(ferris != nullptr && ferris->animation && ferris->animation->playback == "activity_loop",
                 "ferris wheel uses activity gated animation") ||
        !require(ticket_booth != nullptr && ticket_booth->player_buildable && ticket_booth->rotatable &&
                 ticket_booth->footprint_width == 2 && ticket_booth->footprint_height == 2 &&
                 ticket_booth->requires_road_or_path_access && !ticket_booth->animation &&
                 ticket_booth->category == "city_park" &&
                 ticket_booth->texture_path_for(BuildingRotation::r0).find("ticket_booth_south.png") != std::string::npos &&
                 ticket_booth->texture_path_for(BuildingRotation::r90).find("ticket_booth_west.png") != std::string::npos &&
                 ticket_booth->texture_path_for(BuildingRotation::r180).find("ticket_booth_north.png") != std::string::npos &&
                 ticket_booth->texture_path_for(BuildingRotation::r270).find("ticket_booth_east.png") != std::string::npos,
                 "park ticket booth loads with four directions and path access")) {
        return 1;
    }

    BuildingManager buildings(kMapMin, kMapMax);
    RoadManager roads(kMapMin, kMapMax);
    SidewalkManager sidewalks(kMapMin, kMapMax);
    FarmingSystem farming(kMapMin, kMapMax);
    LandManager lands(kMapMin, kMapMax);
    CityEconomy economy;
    PopulationSystem population;
    SimulationClock clock;
    const LandParcel* initial_parcel = lands.parcel_at(0, 0);
    const LandParcel* east_parcel = lands.parcel_at(16, 0);
    if (!require(initial_parcel != nullptr && east_parcel != nullptr, "test parcels exist")) {
        return 1;
    }

    const auto first_id = buildings.place(*cafe, 0, 0, BuildingRotation::r0);
    const auto second_id = buildings.place(*mini_market, 4, 0, BuildingRotation::r90);
    const auto third_id = buildings.place(*mini_market, 0, 4, BuildingRotation::r180);
    const auto house_id = buildings.place(*house, 4, 4, BuildingRotation::r0);
    if (!require(first_id.has_value() && second_id.has_value() && third_id.has_value() && house_id.has_value(),
                 "one cafe, two rotated mini markets, and one rotated house are placed") ||
        !require(economy.spend_for_building(cafe->build_cost, {1, 1, 1}, *first_id) &&
                 economy.spend_for_building(mini_market->build_cost, {1, 1, 1}, *second_id) &&
                 economy.spend_for_building(mini_market->build_cost, {1, 1, 1}, *third_id) &&
                 economy.spend_for_building(house->build_cost, {1, 1, 1}, *house_id),
                 "building costs are applied before saving") ||
        !require(lands.purchase_parcel(east_parcel->id, economy, {1, 1, 1}), "an adjacent parcel is purchased") ||
        !require(roads.place_tile(10, 10) && roads.place_tile(11, 10) && roads.place_tile(11, 11) && sidewalks.place_tile(9, 10, "concrete_01"), "roads and sidewalks are placed")) {
        return 1;
    }
    if (!require(clock.restore_state({12, 5, 2}, SimulationSpeed::paused), "clock state is prepared") ||
        !require(economy.funds() == 35'700, "expected pre-save funds")) {
        return 1;
    }
    population.restore_current_population(3, buildings, catalog);
    if (!require(population.current_population() == 3 && population.residential_capacity() == 4,
                 "population state is prepared before saving")) {
        return 1;
    }
    economy.process_month(buildings, catalog, population, {30, 1, 2});
    if (!require(economy.monthly_summary().revenue == 339 && economy.monthly_summary().expenses == 240 &&
                     economy.monthly_summary().balance == 99 && economy.funds() == 35'799 &&
                     economy.last_property_tax_year() == 2,
                 "fiscal property tax is collected before saving")) {
        return 1;
    }

    MissionManager missions;
    missions.register_mission("clean_energy", "Energia Limpa");
    missions.complete_mission("clean_energy");

    SaveManager saves;
    std::vector<TerrainPaintTile> terrain_paint = {{-2, -3, "sand"}, {-1, -3, "grass"}};
    if (!require(saves.save(save_file, economy, clock, buildings, roads, sidewalks, farming, lands, population,
                            nullptr, &missions, &terrain_paint).success, "small city saves")) {
        return 1;
    }
    terrain_paint.clear();

    // Destroy every runtime state before loading, proving the load is a true reconstruction.
    buildings.clear();
    roads.clear();
    sidewalks.clear();
    farming.clear();
    (void)lands.restore_owned_parcels({});
    economy.restore_funds(1);
    (void)clock.restore_state({1, 1, 1}, SimulationSpeed::speed1);
    PopulationSystem loaded_population;
    MissionManager loaded_missions;
    loaded_missions.register_mission("clean_energy", "Energia Limpa");
    const SaveOperationResult loaded = saves.load(save_file, catalog, economy, clock, buildings, roads, sidewalks, farming, lands,
                                                   loaded_population, nullptr, nullptr, &loaded_missions, &terrain_paint);
    if (!require(loaded.success, "saved city loads") ||
        !require(terrain_paint.size() == 2 && terrain_paint[0].style == "sand" && terrain_paint[1].style == "grass",
                 "painted terrain round trip") ||
        !require(economy.funds() == 35'799 && economy.last_property_tax_year() == 2, "funds and fiscal marker round trip") ||
        !require(clock.date().day == 12 && clock.date().month == 5 && clock.date().year == 2 &&
                 clock.speed() == SimulationSpeed::paused, "clock round trip") ||
        !require(buildings.instances().size() == 4, "all buildings round trip") ||
        !require(buildings.find_by_id(*first_id) != nullptr && buildings.find_by_id(*second_id) != nullptr &&
                 buildings.find_by_id(*third_id) != nullptr && buildings.find_by_id(*house_id) != nullptr,
                 "building ids round trip") ||
        !require(buildings.find_by_id(*second_id)->rotation == BuildingRotation::r0 &&
                 buildings.find_by_id(*third_id)->rotation == BuildingRotation::r0 &&
                 buildings.find_by_id(*house_id)->rotation == BuildingRotation::r0,
                 "building rotations round trip") ||
        !require(buildings.instance_at(4, 0) != nullptr, "building occupancy is rebuilt") ||
        !require(roads.tiles().size() == 3 && roads.connection_mask(11, 10) == static_cast<std::uint8_t>(road_west | road_south),
                 "road tiles and connectivity are rebuilt") ||
        !require(sidewalks.tiles().size() == 1, "sidewalk data round trips") ||
        !require(lands.is_tile_owned(16, 0) && lands.owned_parcel_count() == 2, "purchased parcels round trip") ||
        !require(loaded_missions.is_completed("clean_energy"), "completed missions round trip")) {
        return 1;
    }
    if (!require(loaded_population.current_population() == 3 && loaded_population.residential_capacity() == 4,
                 "population round trips without duplication")) {
        return 1;
    }
    PowerSystem loaded_power;
    loaded_power.rebuild(buildings, catalog);
    if (!require(loaded_power.power_capacity() == 1000 && loaded_power.power_demand() == 10 &&
                     loaded_power.power_available() == 990,
                 "power values are rebuilt from loaded buildings without save fields")) {
        return 1;
    }
    const std::int64_t funds_before_duplicate_guard = economy.funds();
    economy.process_month(buildings, catalog, loaded_population, {30, 1, 2});
    if (!require(economy.monthly_summary().revenue == 99 && economy.monthly_summary().expenses == 240 &&
                     economy.monthly_summary().balance == -141 && economy.funds() == funds_before_duplicate_guard - 141 &&
                     property_tax_transaction_count(economy) == 0,
                 "loading in the same fiscal year does not charge IPTU twice")) {
        return 1;
    }
    economy.process_month(buildings, catalog, loaded_population, {30, 1, 3});
    if (!require(economy.monthly_summary().revenue == 339 && economy.monthly_summary().expenses == 240 &&
                     economy.monthly_summary().balance == 99 && economy.last_property_tax_year() == 3 &&
                     property_tax_transaction_count(economy) == 1,
                 "a later fiscal year charges IPTU again after loading")) {
        return 1;
    }
    const auto next_id = buildings.place(*cafe, 8, 0, BuildingRotation::r270);
    if (!require(next_id.has_value() && *next_id == 5, "next building id remains unique after load")) {
        return 1;
    }

    if (!require(!saves.load(test_directory / "missing.json", catalog, economy, clock, buildings, roads, sidewalks, farming, lands, loaded_population).success,
                 "missing save file fails safely") ||
        !require(write_text(invalid_file, "{ not valid json"), "invalid fixture writes") ||
        !require(!saves.load(invalid_file, catalog, economy, clock, buildings, roads, sidewalks, farming, lands, loaded_population).success,
                 "invalid JSON fails safely") ||
        !require(write_text(unsupported_file, "{ \"saveVersion\": 999 }"), "unsupported fixture writes") ||
        !require(!saves.load(unsupported_file, catalog, economy, clock, buildings, roads, sidewalks, farming, lands, loaded_population).success,
                 "unsupported save version fails safely")) {
        return 1;
    }

    const std::string missing_definition_json =
        "{\n"
        "  \"saveVersion\": 1,\n"
        "  \"cityFunds\": 12345,\n"
        "  \"simulation\": { \"day\": 2, \"month\": 1, \"year\": 1, \"speed\": 1 },\n"
        "  \"nextBuildingInstanceId\": 5,\n"
        "  \"buildings\": [{ \"instanceId\": 4, \"definitionId\": \"removed_building\", \"tileX\": 0, \"tileY\": 0, \"rotation\": 0 }],\n"
        "  \"roads\": [],\n"
        "  \"ownedParcelIds\": [" + std::to_string(initial_parcel->id) + "]\n"
        "}\n";
    if (!require(write_text(missing_definition_file, missing_definition_json), "missing-definition fixture writes")) {
        return 1;
    }
    BuildingManager missing_definition_buildings(kMapMin, kMapMax);
    RoadManager missing_definition_roads(kMapMin, kMapMax);
    SidewalkManager missing_definition_sidewalks(kMapMin, kMapMax);
    FarmingSystem missing_definition_farming(kMapMin, kMapMax);
    LandManager missing_definition_lands(kMapMin, kMapMax);
    CityEconomy missing_definition_economy;
    SimulationClock missing_definition_clock;
    PopulationSystem missing_definition_population;
    const SaveOperationResult missing_definition_result = saves.load(missing_definition_file, catalog, missing_definition_economy,
                                                                      missing_definition_clock, missing_definition_buildings,
                                                                      missing_definition_roads, missing_definition_sidewalks, missing_definition_farming, missing_definition_lands,
                                                                      missing_definition_population);
    if (!require(missing_definition_result.success && missing_definition_result.skipped_buildings == 1 &&
                 missing_definition_buildings.instances().empty() && missing_definition_economy.funds() == 12'345,
                 "missing building definition is skipped without corrupting the save")) {
        return 1;
    }

    const std::string legacy_roadless_json =
        "{\n"
        "  \"saveVersion\": 1,\n"
        "  \"cityFunds\": 12345,\n"
        "  \"simulation\": { \"day\": 2, \"month\": 1, \"year\": 1, \"speed\": 1 },\n"
        "  \"nextBuildingInstanceId\": 2,\n"
        "  \"buildings\": [{ \"instanceId\": 1, \"definitionId\": \"cafe_01\", \"tileX\": 0, \"tileY\": 0, \"rotation\": 0 }],\n"
        "  \"roads\": [],\n"
        "  \"ownedParcelIds\": [" + std::to_string(initial_parcel->id) + "]\n"
        "}\n";
    if (!require(write_text(legacy_roadless_file, legacy_roadless_json), "legacy roadless fixture writes")) {
        return 1;
    }
    BuildingManager legacy_buildings(kMapMin, kMapMax);
    RoadManager legacy_roads(kMapMin, kMapMax);
    SidewalkManager legacy_sidewalks(kMapMin, kMapMax);
    FarmingSystem legacy_farming(kMapMin, kMapMax);
    LandManager legacy_lands(kMapMin, kMapMax);
    CityEconomy legacy_economy;
    SimulationClock legacy_clock;
    PopulationSystem legacy_population;
    const SaveOperationResult legacy_result = saves.load(legacy_roadless_file, catalog, legacy_economy, legacy_clock,
                                                          legacy_buildings, legacy_roads, legacy_sidewalks, legacy_farming, legacy_lands, legacy_population);
    if (!require(legacy_result.success && legacy_buildings.instances().size() == 1 && legacy_roads.tiles().empty(),
                 "legacy roadless buildings load without retroactive road-access rejection")) {
        return 1;
    }

    std::error_code ignored;
    std::filesystem::remove_all(test_directory, ignored);
    std::cout << "save manager tests passed\n";
    return 0;
}
