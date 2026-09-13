#include "building_system.h"
#include "economy_system.h"
#include "mission_system.h"
#include "power_system.h"

#include <filesystem>
#include <fstream>
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
    const BuildingDefinition* house = catalog.find("house_suburban_01");
    const BuildingDefinition* cafe = catalog.find("cafe_01");
    if (!require(house != nullptr && cafe != nullptr, "current building definitions exist") ||
        !require(house->power_consumption == 1 && house->power_production == 0, "house consumes one power") ||
        !require(cafe->power_consumption == 3 && cafe->power_production == 0, "cafe consumes three power")) {
        return 1;
    }

    BuildingManager city(-4, 30);
    PowerSystem power;
    power.rebuild(city, catalog);
    if (!require(power.power_capacity() == PowerSystem::kBasePowerCapacity && power.power_demand() == 0 &&
                     power.power_available() == 1000,
                 "empty city starts with the configured external capacity of 1000") ||
        !require(power.can_support(*house) && power.can_support(*cafe), "consumers fit under base capacity")) {
        return 1;
    }

    if (!require(city.place(*house, 0, 0).has_value() && city.place(*cafe, 3, 0).has_value(),
                 "house and cafe can be added for aggregate demand")) {
        return 1;
    }
    power.rebuild(city, catalog);
    if (!require(power.power_capacity() == 1000 && power.power_demand() == 4 && power.power_available() == 996,
                 "power demand sums all active building consumption")) {
        return 1;
    }

    BuildingDefinition oversized_consumer = *cafe;
    oversized_consumer.id = "oversized_consumer";
    oversized_consumer.power_consumption = 997;
    CityEconomy economy;
    const std::size_t buildings_before_rejection = city.instances().size();
    const std::int64_t funds_before_rejection = economy.funds();
    if (power.can_support(oversized_consumer)) {
        const auto id = city.place(oversized_consumer, 6, 0);
        if (id) {
            (void)economy.spend_for_building(oversized_consumer.build_cost, {1, 1, 1}, *id);
        }
    }
    if (!require(city.instances().size() == buildings_before_rejection && economy.funds() == funds_before_rejection,
                 "insufficient power rejects placement before building creation or spending")) {
        return 1;
    }

    const std::filesystem::path generator_definitions =
        std::filesystem::temp_directory_path() / "city_builder_power_system_test";
    std::error_code ignored;
    std::filesystem::remove_all(generator_definitions, ignored);
    std::filesystem::copy(argv[1], generator_definitions, std::filesystem::copy_options::recursive);

    std::ofstream huge_file(generator_definitions / "huge_consumer.json");
    huge_file << R"({
  "id": "huge_consumer",
  "name": "Huge Consumer",
  "category": "residential",
  "texture": "assets/buildings/house_suburban_01.png",
  "footprint": { "width": 1, "height": 1 },
  "buildCost": 0,
  "powerConsumption": 1001
})";
    huge_file.close();

    BuildingCatalog test_catalog;
    if (!require(test_catalog.load_from_directory(generator_definitions), "test catalog loads")) {
        std::filesystem::remove_all(generator_definitions, ignored);
        return 1;
    }
    const BuildingDefinition* huge_consumer_def = test_catalog.find("huge_consumer");
    if (!require(huge_consumer_def != nullptr, "huge consumer definition loads")) {
        std::filesystem::remove_all(generator_definitions, ignored);
        return 1;
    }

    BuildingManager overloaded_city(-4, 40);
    if (!require(overloaded_city.place(*huge_consumer_def, 0, 0).has_value(), "overload fixture consumer places")) {
        std::filesystem::remove_all(generator_definitions, ignored);
        return 1;
    }
    power.rebuild(overloaded_city, test_catalog);
    if (!require(power.power_demand() == 1001 && power.power_capacity() == 1000 && power.power_available() == -1 &&
                     !power.can_support(*cafe),
                 "consumer placement is blocked once the city exceeds capacity")) {
        std::filesystem::remove_all(generator_definitions, ignored);
        return 1;
    }

    std::ofstream generator_file(generator_definitions / "power_generator_test.json");
    generator_file << R"({
  "id": "power_generator_test",
  "name": "Power Generator Test",
  "category": "infrastructure",
  "texture": "assets/buildings/power_generator_test.png",
  "footprint": { "width": 1, "height": 1 },
  "buildCost": 0,
  "powerProduction": 10
})";
    generator_file.close();
    BuildingCatalog generator_catalog;
    const BuildingDefinition* test_generator = nullptr;
    if (generator_catalog.load_from_directory(generator_definitions)) {
        test_generator = generator_catalog.find("power_generator_test");
    }
    if (!require(test_generator != nullptr, "test-only producer definition loads") ||
        !require(power.can_support(*test_generator), "producer remains placeable in an overloaded city") ||
        !require(overloaded_city.place(*test_generator, 24, 0).has_value(), "producer test instance places")) {
        std::filesystem::remove_all(generator_definitions, ignored);
        return 1;
    }
    power.rebuild(overloaded_city, generator_catalog);
    if (!require(power.power_capacity() == 1010 && power.power_demand() == 1001 && power.power_available() == 9 &&
                     power.can_support(*house),
                 "producer capacity is rebuilt from active instances")) {
        std::filesystem::remove_all(generator_definitions, ignored);
        return 1;
    }

    // Test Mission-locked generator output behavior (Hydroelectric Dam pattern)
    std::ofstream hydro_file(generator_definitions / "hydro_test.json");
    hydro_file << R"({
  "id": "hydro_test",
  "name": "Hydro Test",
  "category": "infrastructure",
  "texture": "assets/buildings/hydro.png",
  "footprint": { "width": 4, "height": 4 },
  "buildCost": 0,
  "preplaced": true,
  "playerBuildable": false,
  "unlockRequirement": "clean_energy",
  "generationCapacity": 500
})";
    hydro_file.close();

    BuildingCatalog hydro_catalog;
    if (!require(hydro_catalog.load_from_directory(generator_definitions), "hydro catalog loads")) {
        std::filesystem::remove_all(generator_definitions, ignored);
        return 1;
    }
    const BuildingDefinition* hydro_def = hydro_catalog.find("hydro_test");
    if (!require(hydro_def != nullptr, "hydro test definition exists")) {
        std::filesystem::remove_all(generator_definitions, ignored);
        return 1;
    }

    BuildingManager hydro_city(-4, 40);
    MissionManager missions;
    missions.register_mission("clean_energy", "Energia Limpa");

    const auto hydro_id = hydro_city.place(*hydro_def, 0, 0);
    if (!require(hydro_id.has_value(), "preplaced hydro places")) {
        std::filesystem::remove_all(generator_definitions, ignored);
        return 1;
    }

    // While clean_energy is locked (operational = false), hydro contributes 0 power capacity
    power.rebuild(hydro_city, hydro_catalog);
    if (!require(power.power_capacity() == 1000, "locked hydro provides 0 extra power capacity")) {
        std::filesystem::remove_all(generator_definitions, ignored);
        return 1;
    }

    // Set hydro operational -> hydro becomes operational (+500 power capacity)
    hydro_city.set_operational_by_definition("hydro_test", true);
    power.rebuild(hydro_city, hydro_catalog);
    if (!require(power.power_capacity() == 1500, "unlocked hydro adds 500 generation capacity")) {
        std::filesystem::remove_all(generator_definitions, ignored);
        return 1;
    }

    std::filesystem::remove_all(generator_definitions, ignored);

    std::cout << "power system tests passed\n";
    return 0;
}
