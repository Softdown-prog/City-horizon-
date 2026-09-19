#ifndef CITY_HORIZON_CH_CORE_CONTRACTS_H
#define CITY_HORIZON_CH_CORE_CONTRACTS_H

#include <cstdint>

namespace ch::contracts {

// Locked Canonical Grid Contract (CH_GRID_V1)
inline constexpr int kTileWidth = 128;
inline constexpr int kTileHeight = 64;
inline constexpr double kDiamondRatio = 2.0;
inline constexpr int kMapMin = -24;
inline constexpr int kMapMax = 23;

// Locked Canonical Camera Contract (CH_CAMERA_V1)
//
// City Horizon targets the classic late-1990s/early-2000s tycoon visual read
// used by games such as Zoo Tycoon 1: orthographic 2:1 dimetric ground,
// 45-degree world yaw, vertical screen-space height, and no perspective.
//
// Important distinction:
// - 35.264 degrees is the elevation commonly associated with mathematically
//   true isometric projection. It does NOT describe a 2:1 diamond.
// - A 2:1 dimetric ground has screen axes at atan(1/2) = 26.565 degrees and
//   corresponds to a 30-degree orthographic camera elevation at 45-degree yaw.
inline constexpr double kCameraWorldYawDeg = 45.0;
inline constexpr double kCameraElevationDeg = 30.0;
inline constexpr double kGroundAxisScreenAngleDeg = 26.56505117707799;
inline constexpr bool kCameraPerspective = false;

// Compatibility aliases. New camera-facing code should use the explicit names
// above so grid geometry is not confused with a true-isometric camera.
inline constexpr double kHorizontalWorldRotationDeg = kCameraWorldYawDeg;
inline constexpr double kIsometricInclinationDeg = kCameraElevationDeg;

// Contract Identifiers
inline constexpr const char* kGridContract = "CH_GRID_V1";
inline constexpr const char* kCameraContract = "CH_CAMERA_V1";
inline constexpr const char* kRenderContract = "CH_RENDER_V1";
inline constexpr const char* kMapContract = "CH_MAP_V1";
inline constexpr const char* kBuildingContract = "CH_BUILDING_V1";
inline constexpr const char* kRoadContract = "CH_ROAD_V1";
inline constexpr const char* kCoastContract = "CH_COAST_V1";

} // namespace ch::contracts

#endif // CITY_HORIZON_CH_CORE_CONTRACTS_H
