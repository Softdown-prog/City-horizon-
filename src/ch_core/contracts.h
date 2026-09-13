#ifndef CITY_HORIZON_CH_CORE_CONTRACTS_H
#define CITY_HORIZON_CH_CORE_CONTRACTS_H

#include <cstdint>

namespace ch::contracts {

// Locked Canonical Grid Contract (CH_GRID_V1)
inline constexpr int kTileWidth = 128;
inline constexpr int kTileHeight = 64;
inline constexpr double kDiamondRatio = 2.0;
inline constexpr double kHorizontalWorldRotationDeg = 45.0;
inline constexpr double kIsometricInclinationDeg = 35.264;
inline constexpr int kMapMin = -24;
inline constexpr int kMapMax = 23;

// Contract Identifiers
inline constexpr const char* kGridContract = "CH_GRID_V1";
inline constexpr const char* kRenderContract = "CH_RENDER_V1";
inline constexpr const char* kMapContract = "CH_MAP_V1";
inline constexpr const char* kBuildingContract = "CH_BUILDING_V1";
inline constexpr const char* kRoadContract = "CH_ROAD_V1";
inline constexpr const char* kCoastContract = "CH_COAST_V1";

} // namespace ch::contracts

#endif // CITY_HORIZON_CH_CORE_CONTRACTS_H
