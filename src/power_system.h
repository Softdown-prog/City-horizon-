#pragma once

#include <cstdint>

struct BuildingDefinition;
class BuildingCatalog;
class BuildingManager;

// v1 uses one city-wide power pool. It deliberately owns no map connectivity,
// cables, assets, or save data: all of its values are derived from active building instances.
class PowerSystem {
public:
    static constexpr std::uint64_t kBasePowerCapacity = 1000;

    void rebuild(const BuildingManager& buildings, const BuildingCatalog& catalog);

    [[nodiscard]] std::uint64_t power_capacity() const;
    [[nodiscard]] std::uint64_t power_demand() const;
    [[nodiscard]] std::int64_t power_available() const;
    // Producers must always be placeable, including in an already overloaded
    // city, so a future generator can recover that state.
    [[nodiscard]] bool can_support(const BuildingDefinition& definition) const;

private:
    std::uint64_t power_capacity_ = kBasePowerCapacity;
    std::uint64_t power_demand_ = 0;
};
