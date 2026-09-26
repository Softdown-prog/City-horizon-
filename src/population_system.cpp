#include "population_system.h"

#include "road_system.h"

#include <algorithm>
#include <limits>

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

std::uint32_t PopulationSystem::powered_residential_capacity() const {
    // Compatibility accessor retained for old save/tests. Energy no longer
    // partitions housing capacity, so this is the usable residential capacity.
    return powered_residential_capacity_;
}

int PopulationSystem::months_without_power() const {
    return 0;
}

int PopulationSystem::crisis_recovery_month() const {
    return 0;
}

void PopulationSystem::rebuild_capacity(const BuildingManager& buildings, const BuildingCatalog& catalog,
                                        const PowerSystem* power, const RoadManager* roads) {
    (void)power;
    std::uint64_t total = 0;
    std::uint64_t usable_total = 0;

    for (const BuildingInstance& instance : buildings.instances()) {
        const BuildingDefinition* definition = catalog.find(instance.definition_id);
        if (definition == nullptr) continue;

        const std::uint32_t capacity = instance.current_level_definition(*definition).residential_capacity;
        total += capacity;
        if (capacity == 0) continue;

        const bool road_ok = roads == nullptr ||
            roads->has_required_road_access(*definition, instance.tile_x, instance.tile_y, instance.rotation);
        if (road_ok) usable_total += capacity;
    }

    residential_capacity_ = static_cast<std::uint32_t>(
        std::min<std::uint64_t>(total, std::numeric_limits<std::uint32_t>::max()));
    powered_residential_capacity_ = static_cast<std::uint32_t>(
        std::min<std::uint64_t>(usable_total, std::numeric_limits<std::uint32_t>::max()));
    current_population_ = std::min(current_population_, residential_capacity_);
    months_without_power_ = 0;
    crisis_recovery_month_ = 0;
}

std::int32_t PopulationSystem::advance_month(const BuildingManager& buildings, const BuildingCatalog& catalog,
                                              const PowerSystem* power, const RoadManager* roads) {
    return on_month_closed(buildings, catalog, power, roads);
}

std::int32_t PopulationSystem::on_month_closed(const BuildingManager& buildings, const BuildingCatalog& catalog,
                                                const PowerSystem* power, const RoadManager* roads) {
    rebuild_capacity(buildings, catalog, power, roads);
    const std::uint32_t available_slots = powered_residential_capacity_ > current_population_
        ? powered_residential_capacity_ - current_population_
        : 0;
    const std::uint32_t arrived = std::min(kMaxMonthlyImmigration, available_slots);
    current_population_ += arrived;
    return static_cast<std::int32_t>(arrived);
}

void PopulationSystem::restore_current_population(const std::uint32_t population,
                                                   const BuildingManager& buildings,
                                                   const BuildingCatalog& catalog,
                                                   const PowerSystem* power,
                                                   const RoadManager* roads,
                                                   const int months_without_power,
                                                   const int crisis_recovery_month) {
    (void)months_without_power;
    (void)crisis_recovery_month;
    current_population_ = population;
    months_without_power_ = 0;
    crisis_recovery_month_ = 0;
    rebuild_capacity(buildings, catalog, power, roads);
}

std::uint32_t PopulationSystem::residents_for(const BuildingInstance& instance,
                                               const BuildingManager& buildings,
                                               const BuildingCatalog& catalog) const {
    std::uint32_t remaining = current_population_;
    for (const BuildingInstance& candidate : buildings.instances()) {
        const BuildingDefinition* definition = catalog.find(candidate.definition_id);
        if (definition == nullptr || !has_residential_capacity(*definition)) continue;
        const std::uint32_t assigned = std::min(remaining, definition->residential_capacity);
        if (candidate.instance_id == instance.instance_id) return assigned;
        remaining -= assigned;
    }
    return 0;
}
