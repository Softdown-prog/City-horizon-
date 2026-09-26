#include "power_system.h"

void PowerSystem::rebuild(const BuildingManager& buildings, const BuildingCatalog& catalog) {
    (void)buildings;
    (void)catalog;
}

std::uint64_t PowerSystem::power_capacity() const {
    return 0;
}

std::uint64_t PowerSystem::power_demand() const {
    return 0;
}

std::int64_t PowerSystem::power_available() const {
    return 0;
}

bool PowerSystem::can_support(const BuildingDefinition& definition) const {
    (void)definition;
    return true;
}
