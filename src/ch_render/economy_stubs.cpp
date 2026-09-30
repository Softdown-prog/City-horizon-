#include "src/economy_system.h"

// Stub implementations for CityEconomy methods referenced by rendering/editor
// dependencies. ch_render must remain decoupled from gameplay simulation: these
// methods exist only to satisfy non-gameplay link targets and never authorize a
// real transaction.
bool CityEconomy::can_afford(const std::int64_t) const {
    return false;
}

bool CityEconomy::spend_for_building(const std::int64_t, const GameDate&, const std::uint64_t) {
    return false;
}

bool CityEconomy::spend_for_upgrade(const std::int64_t, const GameDate&, const std::uint64_t) {
    return false;
}

bool CityEconomy::spend_for_land(const std::int64_t, const GameDate&, const std::uint32_t) {
    return false;
}
