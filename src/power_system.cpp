#include "power_system.h"

#include "building_system.h"

#include <limits>

namespace {

void saturating_add(std::uint64_t& total, const std::uint32_t value) {
    if (total > std::numeric_limits<std::uint64_t>::max() - value) {
        total = std::numeric_limits<std::uint64_t>::max();
    } else {
        total += value;
    }
}

}  // namespace

void PowerSystem::rebuild(const BuildingManager& buildings, const BuildingCatalog& catalog) {
    power_capacity_ = kBasePowerCapacity;
    power_demand_ = 0;
    for (const BuildingInstance& instance : buildings.instances()) {
        const BuildingDefinition* definition = catalog.find(instance.definition_id);
        if (definition == nullptr) {
            continue;
        }
        const auto& level_def = instance.current_level_definition(*definition);
        saturating_add(power_capacity_, definition->power_production);
        saturating_add(power_demand_, level_def.power_consumption);
    }
}

std::uint64_t PowerSystem::power_capacity() const {
    return power_capacity_;
}

std::uint64_t PowerSystem::power_demand() const {
    return power_demand_;
}

std::int64_t PowerSystem::power_available() const {
    if (power_capacity_ >= power_demand_) {
        return static_cast<std::int64_t>(power_capacity_ - power_demand_);
    }
    return -static_cast<std::int64_t>(power_demand_ - power_capacity_);
}

bool PowerSystem::can_support(const BuildingDefinition& definition) const {
    if (definition.power_production != 0 || definition.power_consumption == 0) {
        return true;
    }
    return power_demand_ <= power_capacity_ &&
        static_cast<std::uint64_t>(definition.power_consumption) <= power_capacity_ - power_demand_;
}
