#pragma once

#include "building_system.h"

#include <cstdint>

class PowerSystem;
class RoadManager;

// Aggregate, deterministic population model. It deliberately has no individual
// resident entities: homes contribute capacity and occupants are assigned in
// stable building-instance order for economic accounting.
//
// Population growth V1 is intentionally simple: authored residential capacity,
// usable residential road access, and (when runtime road topology is supplied)
// one road connection to the map edge are the only gameplay gates. Energy,
// sanitation and jobs are not population-growth requirements in this tranche.
class PopulationSystem {
public:
    // A basic City Horizon house holds five residents, so starter migration can
    // fill one small residence in a single monthly settlement. Once the city is
    // larger, percentage growth naturally overtakes this floor.
    static constexpr std::uint32_t kStarterMonthlyImmigration = 5;
    static constexpr std::uint32_t kMonthlyGrowthBasisPoints = 400; // 4.00%

    [[nodiscard]] std::uint32_t current_population() const;
    [[nodiscard]] std::uint32_t residential_capacity() const;
    [[nodiscard]] std::uint32_t powered_residential_capacity() const;
    [[nodiscard]] std::uint32_t housing_demand() const;
    [[nodiscard]] std::uint32_t last_month_potential_growth() const;
    [[nodiscard]] std::uint32_t last_month_growth() const;
    [[nodiscard]] int months_without_power() const;
    [[nodiscard]] int crisis_recovery_month() const;

    // Recompute derived capacity after a catalogue or building set changes.
    // Capacity is authored per residence, allowing a cottage to hold 5 while a
    // future apartment or tower can declare 20, 25 or more without code changes.
    void rebuild_capacity(const BuildingManager& buildings, const BuildingCatalog& catalog,
                          const PowerSystem* power = nullptr, const RoadManager* roads = nullptr);

    // Advances a single deterministic monthly population step and returns net population change.
    // Immigration occurs only once per month at month-close settlement. Demand grows
    // proportionally with population, then housing capacity clamps actual arrivals.
    std::int32_t advance_month(const BuildingManager& buildings, const BuildingCatalog& catalog,
                               const PowerSystem* power = nullptr, const RoadManager* roads = nullptr);
    std::int32_t on_month_closed(const BuildingManager& buildings, const BuildingCatalog& catalog,
                                 const PowerSystem* power = nullptr, const RoadManager* roads = nullptr);

    // Save/load boundary. Housing demand is deliberately recomputed after load in
    // this first growth tranche; persistent demand can be added later without
    // introducing utility or employment dependencies into population growth.
    void restore_current_population(std::uint32_t population, const BuildingManager& buildings,
                                    const BuildingCatalog& catalog, const PowerSystem* power = nullptr,
                                    const RoadManager* roads = nullptr, int months_without_power = 0,
                                    int crisis_recovery_month = 0);

    // Number of currently assigned occupants for a particular residence.
    [[nodiscard]] std::uint32_t residents_for(const BuildingInstance& instance,
                                               const BuildingManager& buildings,
                                               const BuildingCatalog& catalog) const;

private:
    [[nodiscard]] std::uint32_t organic_monthly_demand() const;
    [[nodiscard]] std::uint32_t housing_demand_cap() const;

    std::uint32_t current_population_ = 0;
    std::uint32_t residential_capacity_ = 0;
    // Legacy name/API retained for save/test compatibility. This now means
    // usable residential capacity; electricity does not gate occupancy.
    std::uint32_t powered_residential_capacity_ = 0;
    std::uint32_t housing_demand_ = 0;
    std::uint32_t last_month_potential_growth_ = 0;
    std::uint32_t last_month_growth_ = 0;
    int months_without_power_ = 0;
    int crisis_recovery_month_ = 0;
};
