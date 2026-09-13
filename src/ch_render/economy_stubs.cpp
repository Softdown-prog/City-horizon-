#include "src/economy_system.h"

// Stub implementations for CityEconomy methods referenced by BuildingInstance::try_upgrade
// and LandManager::purchase_parcel so ch_render remains decoupled from gameplay simulation.
bool CityEconomy::can_afford(const std::int64_t) const {
    return false;
}

bool CityEconomy::spend_for_building(const std::int64_t, const GameDate&, const std::uint64_t) {
    return false;
}

bool CityEconomy::spend_for_land(const std::int64_t, const GameDate&, const std::uint32_t) {
    return false;
}
