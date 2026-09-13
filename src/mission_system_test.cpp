#include "building_system.h"
#include "land_system.h"
#include "mission_system.h"
#include "power_system.h"

#include <iostream>

namespace {

bool require(const bool condition, const char* description) {
    if (!condition) {
        std::cerr << "FAILED: " << description << '\n';
    }
    return condition;
}

}  // namespace

int main(const int argc, char** argv) {
    if (!require(argc == 2, "definitions directory argument")) {
        return 1;
    }

    BuildingCatalog catalog;
    if (!require(catalog.load_from_directory(argv[1]), "catalog loads")) {
        return 1;
    }

    // Verify Hydroelectric Dam definition
    const BuildingDefinition* hydro = catalog.find("hydroelectric_01");
    if (!require(hydro != nullptr, "hydroelectric_01 definition exists") ||
        !require(hydro->preplaced == true, "hydroelectric is preplaced") ||
        !require(hydro->player_buildable == false, "hydroelectric is not buildable by player catalog") ||
        !require(hydro->unlock_requirement == "clean_energy", "hydroelectric unlock requirement is clean_energy") ||
        !require(hydro->initial_placement.has_value() && hydro->initial_placement->tile_x == -18 && hydro->initial_placement->tile_y == 12, "hydroelectric initial placement exists in dam area")) {
        return 1;
    }

    // Verify Water Intake Station (water_intake_01) definition
    const BuildingDefinition* water_intake = catalog.find("water_intake_01");
    if (!require(water_intake != nullptr, "water_intake_01 definition exists") ||
        !require(water_intake->preplaced == true, "water intake station is preplaced") ||
        !require(water_intake->player_buildable == false, "water intake station is not buildable in catalog") ||
        !require(water_intake->unlock_requirement == "city_water", "water intake contract is city_water") ||
        !require(water_intake->water_intake_capacity == 0, "water intake capacity starts at 0 (provisional)") ||
        !require(water_intake->initial_placement.has_value() && water_intake->initial_placement->tile_x == -16 && water_intake->initial_placement->tile_y == 18, "water intake initial placement is on dam bank")) {
        return 1;
    }

    // Verify map placement in darkened/locked region
    LandManager lands(-24, 23);
    const int intake_x = water_intake->initial_placement->tile_x;
    const int intake_y = water_intake->initial_placement->tile_y;
    if (!require(!lands.is_tile_owned(intake_x, intake_y), "water intake station is located in darkened/locked map region")) {
        return 1;
    }

    MissionManager missions;
    if (!require(missions.definitions().count("clean_energy") > 0, "clean_energy mission registered by default") ||
        !require(!missions.is_completed("clean_energy"), "clean_energy mission starts locked/incomplete") ||
        !require(!missions.is_completed("city_water"), "water intake contract starts locked/incomplete")) {
        return 1;
    }

    BuildingManager city(-24, 23);
    const auto hydro_instance = city.place(*hydro, hydro->initial_placement->tile_x, hydro->initial_placement->tile_y);
    const auto intake_instance = city.place(*water_intake, intake_x, intake_y);
    if (!require(hydro_instance.has_value() && intake_instance.has_value(), "preplaced infrastructure items place on map")) {
        return 1;
    }

    PowerSystem power;
    power.rebuild(city, catalog);
    if (!require(power.power_capacity() == 1000, "locked hydroelectric contributes 0 power to city capacity (base 1000)")) {
        return 1;
    }

    // Verify clean_energy mission completion
    if (!require(missions.complete_mission("clean_energy"), "completing clean_energy mission succeeds") ||
        !require(missions.is_completed("clean_energy"), "clean_energy is marked completed")) {
        return 1;
    }

    city.set_operational_by_definition("hydroelectric_01", true);
    power.rebuild(city, catalog);
    if (!require(power.power_capacity() == 1000 + hydro->generation_capacity, "unlocked hydroelectric adds generation capacity to base 1000")) {
        return 1;
    }

    // Verify future water intake mission completion contract
    if (!require(missions.definitions().count("city_water") > 0, "city_water mission registered by default") ||
        !require(!missions.is_completed("city_water"), "city_water starts incomplete")) {
        return 1;
    }

    if (!require(missions.complete_mission("city_water"), "completing city_water mission succeeds") ||
        !require(missions.is_completed("city_water"), "city_water is marked completed")) {
        return 1;
    }

    city.set_operational_by_definition("water_intake_01", true);
    const BuildingInstance* intake_inst = city.find_by_id(*intake_instance);
    if (!require(intake_inst != nullptr && intake_inst->operational == true, "water intake station is set operational upon mission completion")) {
        return 1;
    }

    std::cout << "mission system tests passed\n";
    return 0;
}
