#include "building_system.h"
#include "economy_system.h"
#include "farming_system.h"
#include "land_system.h"
#include "mission_system.h"
#include "population_system.h"
#include "power_system.h"
#include "road_system.h"
#include "save_manager.h"
#include "sidewalk_system.h"
#include "simulation_clock.h"

#include <filesystem>
#include <iostream>
#include <vector>

namespace {

constexpr int kMapMin = -24;
constexpr int kMapMax = 23;

bool require(const bool condition, const char* description) {
    if (!condition) std::cerr << "FAILED: " << description << '\n';
    return condition;
}

}  // namespace

int main(const int argc, char** argv) {
    if (!require(argc == 2, "definitions directory argument")) return 1;

    BuildingCatalog catalog;
    if (!require(catalog.load_from_directory(argv[1]), "building catalog loads")) return 1;
    const BuildingDefinition* bakery = catalog.find("bakery_01");
    if (!require(bakery != nullptr, "bakery definition exists")) return 1;

    BuildingManager buildings(kMapMin, kMapMax);
    RoadManager roads(kMapMin, kMapMax);
    SidewalkManager sidewalks(kMapMin, kMapMax);
    FarmingSystem farming(kMapMin, kMapMax);
    LandManager lands(kMapMin, kMapMax);
    CityEconomy economy;
    PopulationSystem population;
    SimulationClock clock;
    MissionManager missions;

    const auto building_id = buildings.place(*bakery, 0, 0, BuildingRotation::r0);
    if (!require(building_id.has_value(), "building placement succeeds") ||
        !require(roads.place_tile(5, 5) && roads.place_tile(6, 5), "road state prepared") ||
        !require(sidewalks.place_tile(5, 6, "dirt_path"), "sidewalk state prepared") ||
        !require(clock.restore_state({12, 5, 2}, SimulationSpeed::paused), "clock state prepared")) {
        return 1;
    }
    (void)economy.spend_for_building(bakery->build_cost, {1, 1, 1}, *building_id);

    std::vector<TerrainPaintTile> terrain_paint = {{-2, -3, "sand"}, {-1, -3, "grass"}};
    const std::filesystem::path root = std::filesystem::temp_directory_path() / "city_builder_save_manager_test";
    const std::filesystem::path save_file = root / "round_trip.json";
    std::filesystem::create_directories(root);

    SaveManager saves;
    if (!require(saves.save(save_file, economy, clock, buildings, roads, sidewalks, farming,
                            lands, population, nullptr, &missions, &terrain_paint).success,
                 "city saves with retired mission compatibility object")) {
        return 1;
    }

    BuildingManager loaded_buildings(kMapMin, kMapMax);
    RoadManager loaded_roads(kMapMin, kMapMax);
    SidewalkManager loaded_sidewalks(kMapMin, kMapMax);
    FarmingSystem loaded_farming(kMapMin, kMapMax);
    LandManager loaded_lands(kMapMin, kMapMax);
    CityEconomy loaded_economy;
    PopulationSystem loaded_population;
    SimulationClock loaded_clock;
    MissionManager loaded_missions;
    std::vector<TerrainPaintTile> loaded_terrain_paint;

    const SaveOperationResult loaded = saves.load(save_file, catalog, loaded_economy, loaded_clock,
                                                   loaded_buildings, loaded_roads, loaded_sidewalks,
                                                   loaded_farming, loaded_lands, loaded_population,
                                                   nullptr, nullptr, &loaded_missions, &loaded_terrain_paint);
    if (!require(loaded.success, "saved city loads") ||
        !require(loaded_buildings.instances().size() == 1, "building round trips") ||
        !require(loaded_buildings.find_by_id(*building_id) != nullptr, "building id round trips") ||
        !require(loaded_roads.tiles().size() == 2, "roads round trip") ||
        !require(loaded_sidewalks.tiles().size() == 1, "sidewalk round trips") ||
        !require(loaded_terrain_paint.size() == 2 && loaded_terrain_paint[0].style == "sand" &&
                     loaded_terrain_paint[1].style == "grass", "terrain paint round trips") ||
        !require(loaded_clock.date().day == 12 && loaded_clock.date().month == 5 && loaded_clock.date().year == 2 &&
                     loaded_clock.speed() == SimulationSpeed::paused, "clock round trips") ||
        !require(loaded_missions.definitions().empty() && loaded_missions.completed_mission_ids().empty(),
                 "legacy mission save data is ignored")) {
        return 1;
    }

    PowerSystem power;
    power.rebuild(loaded_buildings, catalog);
    if (!require(power.power_capacity() == 0 && power.power_demand() == 0 &&
                     power.power_available() == 0 && power.can_support(*bakery),
                 "energy remains disabled after load")) {
        return 1;
    }

    std::error_code ignored;
    std::filesystem::remove_all(root, ignored);
    std::cout << "save manager tests passed with missions and energy disabled\n";
    return 0;
}
