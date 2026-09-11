#include "building_system.h"
#include "economy_system.h"
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
                     power.power_available() == 20,
                 "empty city starts with the configured external capacity") ||
        !require(power.can_support(*house) && power.can_support(*cafe), "consumers fit under base capacity")) {
        return 1;
    }

    if (!require(city.place(*house, 0, 0).has_value() && city.place(*cafe, 3, 0).has_value(),
                 "house and cafe can be added for aggregate demand")) {
        return 1;
    }
    power.rebuild(city, catalog);
    if (!require(power.power_capacity() == 20 && power.power_demand() == 4 && power.power_available() == 16,
                 "power demand sums all active building consumption")) {
        return 1;
    }

    BuildingDefinition oversized_consumer = *cafe;
    oversized_consumer.id = "oversized_consumer";
    oversized_consumer.power_consumption = 17;
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

    BuildingManager overloaded_city(-4, 40);
    for (int x = 0; x < 21; x += 3) {
        if (!require(overloaded_city.place(*cafe, x, 0).has_value(), "overload fixture cafe places")) {
            return 1;
        }
    }
    power.rebuild(overloaded_city, catalog);
    if (!require(power.power_demand() == 21 && power.power_capacity() == 20 && power.power_available() == -1 &&
                     !power.can_support(*house),
                 "consumer placement is blocked once the city exceeds capacity")) {
        return 1;
    }

    const std::filesystem::path generator_definitions =
        std::filesystem::temp_directory_path() / "city_builder_power_system_test";
    std::error_code ignored;
    std::filesystem::remove_all(generator_definitions, ignored);
    std::filesystem::copy(argv[1], generator_definitions, std::filesystem::copy_options::recursive);
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
    if (!require(power.power_capacity() == 30 && power.power_demand() == 21 && power.power_available() == 9 &&
                     power.can_support(*house),
                 "producer capacity is rebuilt from active instances")) {
        std::filesystem::remove_all(generator_definitions, ignored);
        return 1;
    }

    std::filesystem::remove_all(generator_definitions, ignored);

    std::cout << "power system tests passed\n";
    return 0;
}
