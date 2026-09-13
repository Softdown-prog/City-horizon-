#pragma once

#include "building_system.h"

#include <cstdint>

class PowerSystem;
class RoadManager;

// Aggregate, deterministic population model. It deliberately has no individual
// resident entities: homes contribute capacity and occupants are assigned in
// stable building-instance order for economic accounting.
class PopulationSystem {
public:
    static constexpr std::uint32_t kMaxMonthlyImmigration = 20;

    [[nodiscard]] std::uint32_t current_population() const;
    [[nodiscard]] std::uint32_t residential_capacity() const;
    [[nodiscard]] std::uint32_t powered_residential_capacity() const;
    [[nodiscard]] int months_without_power() const;
    [[nodiscard]] int crisis_recovery_month() const;

    // Recompute derived capacity after a catalogue or building set changes.
    void rebuild_capacity(const BuildingManager& buildings, const BuildingCatalog& catalog,
                          const PowerSystem* power = nullptr, const RoadManager* roads = nullptr);

    // Advances a single deterministic monthly population step and returns net population change.
    // Immigration occurs only once per month at month-close settlement.
    std::int32_t advance_month(const BuildingManager& buildings, const BuildingCatalog& catalog,
                               const PowerSystem* power = nullptr, const RoadManager* roads = nullptr);
    std::int32_t on_month_closed(const BuildingManager& buildings, const BuildingCatalog& catalog,
                                const PowerSystem* power = nullptr, const RoadManager* roads = nullptr);

    // Save/load boundary.
    void restore_current_population(std::uint32_t population, const BuildingManager& buildings,
                                    const BuildingCatalog& catalog, const PowerSystem* power = nullptr,
                                    const RoadManager* roads = nullptr, int months_without_power = 0,
                                    int crisis_recovery_month = 0);

    // Number of currently assigned occupants for a particular residence.
    [[nodiscard]] std::uint32_t residents_for(const BuildingInstance& instance,
                                               const BuildingManager& buildings,
                                               const BuildingCatalog& catalog) const;

private:
    std::uint32_t current_population_ = 0;
    std::uint32_t residential_capacity_ = 0;
    std::uint32_t powered_residential_capacity_ = 0;
    int months_without_power_ = 0;
    int crisis_recovery_month_ = 0;
};
