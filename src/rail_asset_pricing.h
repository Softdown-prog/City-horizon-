#pragma once

#include <cstdint>

// CH_RAIL_ASSET_PRICING_V1
// Authoritative fixed acquisition prices for rail assets. Track construction
// remains length-based in rail_construction_economy.h. Station construction and
// monthly maintenance remain defined by the building catalog JSON.
namespace ch::rail_pricing {
inline constexpr std::int64_t locomotive_build_cost = 12'000;
inline constexpr std::int64_t wagon_build_cost = 2'500;
inline constexpr std::int64_t turntable_build_cost = 9'000;
inline constexpr std::int64_t station_build_cost_reference = 7'500;
inline constexpr std::int64_t station_monthly_maintenance_reference = 125;

// Reference-only: station actual costs come from
// assets/definitions/rail_terminal_station_01.json.
// The fixed prices above are not debited until placement/purchase hooks use them.
}
