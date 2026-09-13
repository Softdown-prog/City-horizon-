#include "population_system.h"

#include "power_system.h"
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
    return powered_residential_capacity_;
}

int PopulationSystem::months_without_power() const {
    return months_without_power_;
}

int PopulationSystem::crisis_recovery_month() const {
    return crisis_recovery_month_;
}

void PopulationSystem::rebuild_capacity(const BuildingManager& buildings, const BuildingCatalog& catalog,
                                        const PowerSystem* power, const RoadManager* roads) {
    std::uint64_t total = 0;
    std::uint64_t powered_total = 0;
    const bool grid_powered = (power == nullptr || power->power_available() >= 0);

    for (const BuildingInstance& instance : buildings.instances()) {
        const BuildingDefinition* definition = catalog.find(instance.definition_id);
        if (definition == nullptr) {
            continue;
        }
        const std::uint32_t capacity = instance.current_level_definition(*definition).residential_capacity;
        total += capacity;

        if (capacity > 0 && grid_powered) {
            const bool road_ok = (roads == nullptr || roads->has_required_road_access(*definition, instance.tile_x, instance.tile_y, instance.rotation));
            if (road_ok) {
                powered_total += capacity;
            }
        }
    }
    residential_capacity_ = static_cast<std::uint32_t>(std::min<std::uint64_t>(total, std::numeric_limits<std::uint32_t>::max()));
    powered_residential_capacity_ = static_cast<std::uint32_t>(std::min<std::uint64_t>(powered_total, std::numeric_limits<std::uint32_t>::max()));
    current_population_ = std::min(current_population_, residential_capacity_);
}

std::int32_t PopulationSystem::advance_month(const BuildingManager& buildings, const BuildingCatalog& catalog,
                                              const PowerSystem* power, const RoadManager* roads) {
    return on_month_closed(buildings, catalog, power, roads);
}

std::int32_t PopulationSystem::on_month_closed(const BuildingManager& buildings, const BuildingCatalog& catalog,
                                                const PowerSystem* power, const RoadManager* roads) {
    rebuild_capacity(buildings, catalog, power, roads);

    const bool grid_powered = (power == nullptr || power->power_available() >= 0);

    if (!grid_powered) {
        months_without_power_++;
        if (months_without_power_ <= 2) {
            // First 2 months without power: existing residents stay, but 0 new immigrants
            return 0;
        }
        // Month 3+ consecutive without power: residents begin abandoning the city
        std::uint32_t unpowered_residences = 0;
        for (const BuildingInstance& instance : buildings.instances()) {
            const BuildingDefinition* definition = catalog.find(instance.definition_id);
            if (definition != nullptr && has_residential_capacity(*definition)) {
                unpowered_residences++;
            }
        }
        // Configurable data-driven abandonment rate (2 per unpowered residence)
        const std::uint32_t abandonment_total = std::max<std::uint32_t>(1, unpowered_residences * 2);
        const std::uint32_t departed = std::min(current_population_, abandonment_total);
        current_population_ -= departed;
        return -static_cast<std::int32_t>(departed);
    }

    // Grid power is operational
    if (months_without_power_ > 0) {
        // Power restored: reset outage counter and initiate recovery ramp
        months_without_power_ = 0;
        crisis_recovery_month_ = 1;
    }

    std::uint32_t monthly_cap = kMaxMonthlyImmigration;
    if (crisis_recovery_month_ == 1) {
        monthly_cap = 5;
    } else if (crisis_recovery_month_ == 2) {
        monthly_cap = 10;
    } else if (crisis_recovery_month_ == 3) {
        monthly_cap = 15;
    }

    if (crisis_recovery_month_ > 0 && crisis_recovery_month_ <= 3) {
        crisis_recovery_month_++;
    } else if (crisis_recovery_month_ > 3) {
        crisis_recovery_month_ = 0; // Recovery complete
    }

    const std::uint32_t available_slots = (powered_residential_capacity_ > current_population_)
                                               ? (powered_residential_capacity_ - current_population_)
                                               : 0;
    const std::uint32_t arrived = std::min(monthly_cap, available_slots);
    current_population_ += arrived;
    return static_cast<std::int32_t>(arrived);
}

void PopulationSystem::restore_current_population(const std::uint32_t population, const BuildingManager& buildings,
                                                   const BuildingCatalog& catalog, const PowerSystem* power,
                                                   const RoadManager* roads, const int months_without_power,
                                                   const int crisis_recovery_month) {
    current_population_ = population;
    months_without_power_ = months_without_power;
    crisis_recovery_month_ = crisis_recovery_month;
    rebuild_capacity(buildings, catalog, power, roads);
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
