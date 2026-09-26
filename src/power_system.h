#pragma once

#include <cstdint>

struct BuildingDefinition;
class BuildingCatalog;
class BuildingManager;

// Compatibility shell kept temporarily while older runtime call sites migrate.
// Energy is no longer a gameplay constraint: there is no city-wide capacity,
// demand, deficit, producer contribution, placement gate or mission dependency.
class PowerSystem {
public:
    static constexpr std::uint64_t kBasePowerCapacity = 0;

    void rebuild(const BuildingManager& buildings, const BuildingCatalog& catalog);

    [[nodiscard]] std::uint64_t power_capacity() const;
    [[nodiscard]] std::uint64_t power_demand() const;
    [[nodiscard]] std::int64_t power_available() const;
    [[nodiscard]] bool can_support(const BuildingDefinition& definition) const;
};
