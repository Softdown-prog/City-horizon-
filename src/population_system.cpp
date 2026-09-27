#include "population_system.h"

#include "road_system.h"

#include <algorithm>
#include <limits>

namespace {

[[nodiscard]] bool has_residential_capacity(const BuildingDefinition& definition) {
    return definition.residential_capacity != 0;
}

[[nodiscard]] std::uint32_t saturating_u32(const std::uint64_t value) {
    return static_cast<std::uint32_t>(
        std::min<std::uint64_t>(value, std::numeric_limits<std::uint32_t>::max()));
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

std::uint32_t PopulationSystem::housing_demand() const {
    return housing_demand_;
}

std::uint32_t PopulationSystem::last_month_potential_growth() const {
    return last_month_potential_growth_;
}

std::uint32_t PopulationSystem::last_month_growth() const {
    return last_month_growth_;
}

int PopulationSystem::months_without_power() const {
    return 0;
}

int PopulationSystem::crisis_recovery_month() const {
    return 0;
}

std::uint32_t PopulationSystem::organic_monthly_demand() const {
    // Integer basis-point arithmetic keeps the population simulation stable and
    // deterministic. Round up so a growing city never loses sub-person demand.
    const std::uint64_t proportional =
        (static_cast<std::uint64_t>(current_population_) * kMonthlyGrowthBasisPoints + 9'999ULL) / 10'000ULL;
    return std::max(kStarterMonthlyImmigration, saturating_u32(proportional));
}

std::uint32_t PopulationSystem::housing_demand_cap() const {
    // Demand is useful feedback, not an unbounded debt. At most half the current
    // population (or forty people for a tiny town) can wait in the migration pool.
    return std::max<std::uint32_t>(40U, current_population_ / 2U);
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

    residential_capacity_ = saturating_u32(total);
    powered_residential_capacity_ = saturating_u32(usable_total);
    current_population_ = std::min(current_population_, residential_capacity_);
    housing_demand_ = std::min(housing_demand_, housing_demand_cap());
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

    const std::uint32_t organic_demand = organic_monthly_demand();
    // A portion of previously blocked demand retries each month. The retry budget
    // scales with organic demand, so large cities can absorb a newly built district
    // quickly without allowing an old backlog to fill thousands of homes instantly.
    const std::uint32_t backlog_release_budget = std::max(
        kStarterMonthlyImmigration,
        saturating_u32(static_cast<std::uint64_t>(organic_demand) * 2ULL));
    const std::uint32_t retrying_demand = std::min(housing_demand_, backlog_release_budget);
    const std::uint32_t potential_growth = saturating_u32(
        static_cast<std::uint64_t>(organic_demand) + retrying_demand);

    const std::uint32_t available_slots = powered_residential_capacity_ > current_population_
        ? powered_residential_capacity_ - current_population_
        : 0;
    const std::uint32_t arrived = std::min(potential_growth, available_slots);

    current_population_ += arrived;
    last_month_potential_growth_ = potential_growth;
    last_month_growth_ = arrived;

    // Net waiting demand is old pressure plus this month's new organic interest,
    // minus everybody who actually found a home. Clamp to a deliberate bound.
    const std::uint64_t waiting = static_cast<std::uint64_t>(housing_demand_) + organic_demand;
    housing_demand_ = static_cast<std::uint32_t>(std::min<std::uint64_t>(
        waiting > arrived ? waiting - arrived : 0ULL,
        housing_demand_cap()));

    return static_cast<std::int32_t>(std::min<std::uint32_t>(
        arrived, static_cast<std::uint32_t>(std::numeric_limits<std::int32_t>::max())));
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
    housing_demand_ = 0;
    last_month_potential_growth_ = 0;
    last_month_growth_ = 0;
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
