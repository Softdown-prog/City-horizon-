#pragma once

#include "building_system.h"

#include <cstdint>

// Aggregate, deterministic population model. It deliberately has no residents
// as entities: homes only contribute capacity and occupants are assigned in
// stable building-instance order for economic accounting.
class PopulationSystem {
public:
    static constexpr std::uint32_t kResidentsPerMonth = 1;

    [[nodiscard]] std::uint32_t current_population() const;
    [[nodiscard]] std::uint32_t residential_capacity() const;

    // Recompute derived capacity after a catalogue or building set changes.
    void rebuild_capacity(const BuildingManager& buildings, const BuildingCatalog& catalog);
    // Advances a single deterministic monthly population step and returns how
    // many residents arrived. Population is clamped if capacity was reduced.
    [[nodiscard]] std::uint32_t advance_month(const BuildingManager& buildings, const BuildingCatalog& catalog);
    [[nodiscard]] std::uint32_t on_month_closed(const BuildingManager& buildings, const BuildingCatalog& catalog);
    // Save/load boundary. Capacity is always rebuilt from buildings rather than
    // stored, while persisted population is safely clamped to that capacity.
    void restore_current_population(std::uint32_t population, const BuildingManager& buildings,
                                    const BuildingCatalog& catalog);
    // Number of currently assigned occupants for a particular residence.
    [[nodiscard]] std::uint32_t residents_for(const BuildingInstance& instance,
                                               const BuildingManager& buildings,
                                               const BuildingCatalog& catalog) const;

private:
    std::uint32_t current_population_ = 0;
    std::uint32_t residential_capacity_ = 0;
};
