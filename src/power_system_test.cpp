#include "building_system.h"
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

int main() {
    BuildingManager buildings(-4, 4);
    BuildingCatalog catalog;

    BuildingDefinition legacy_consumer;
    legacy_consumer.id = "legacy_energy_consumer";
    legacy_consumer.power_consumption = 999999;

    BuildingDefinition legacy_producer;
    legacy_producer.id = "legacy_energy_producer";
    legacy_producer.power_production = 999999;

    PowerSystem power;
    power.rebuild(buildings, catalog);

    if (!require(PowerSystem::kBasePowerCapacity == 0, "base power capacity removed") ||
        !require(power.power_capacity() == 0, "power capacity is disabled") ||
        !require(power.power_demand() == 0, "power demand is disabled") ||
        !require(power.power_available() == 0, "power deficit and surplus are disabled") ||
        !require(power.can_support(legacy_consumer), "legacy consumers never block placement") ||
        !require(power.can_support(legacy_producer), "legacy producers never affect placement")) {
        return 1;
    }

    std::cout << "power system disabled\n";
    return 0;
}
