#include "population_system.h"

#include <algorithm>
#include <limits>

// Capacity is derived from the current BuildingDefinition layout on every
// monthly advancement and load reconstruction; fiscal taxes never affect it.
namespace {

[[nodiscard]] bool has_residential_capacity(const BuildingDefinition& definition) {
    return definition.residential_capacity != 0;
}

}  // namespace

std::uint32_t PopulationSystem::current_population() const {
    return current_population_;
}

std::uint32_t PopulationSystem::residential_capacity() const {
    return residential_capacity_;
}

void PopulationSystem::rebuild_capacity(const BuildingManager& buildings, const BuildingCatalog& catalog) {
    std::uint64_t total = 0;
    for (const BuildingInstance& instance : buildings.instances()) {
        const BuildingDefinition* definition = catalog.find(instance.definition_id);
        if (definition != nullptr) {
            total += instance.current_level_definition(*definition).residential_capacity;
        }
    }
    residential_capacity_ = static_cast<std::uint32_t>(std::min<std::uint64_t>(total, std::numeric_limits<std::uint32_t>::max()));
    current_population_ = std::min(current_population_, residential_capacity_);
}

std::uint32_t PopulationSystem::advance_month(const BuildingManager& buildings, const BuildingCatalog& catalog) {
    return on_month_closed(buildings, catalog);
}

std::uint32_t PopulationSystem::on_month_closed(const BuildingManager& buildings, const BuildingCatalog& catalog) {
    rebuild_capacity(buildings, catalog);
    const std::uint32_t available = residential_capacity_ - current_population_;
    const std::uint32_t arrived = std::min(kResidentsPerMonth, available);
    current_population_ += arrived;
    return arrived;
}

void PopulationSystem::restore_current_population(const std::uint32_t population, const BuildingManager& buildings,
                                                   const BuildingCatalog& catalog) {
    current_population_ = population;
    rebuild_capacity(buildings, catalog);
}

std::uint32_t PopulationSystem::residents_for(const BuildingInstance& instance, const BuildingManager& buildings,
                                               const BuildingCatalog& catalog) const {
    std::uint32_t remaining = current_population_;
    for (const BuildingInstance& candidate : buildings.instances()) {
        const BuildingDefinition* definition = catalog.find(candidate.definition_id);
        if (definition == nullptr || !has_residential_capacity(*definition)) {
            continue;
        }
        const std::uint32_t assigned = std::min(remaining, definition->residential_capacity);
        if (candidate.instance_id == instance.instance_id) {
            return assigned;
        }
        remaining -= assigned;
    }
    return 0;
}
