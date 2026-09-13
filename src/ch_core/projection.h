#ifndef CITY_HORIZON_CH_CORE_PROJECTION_H
#define CITY_HORIZON_CH_CORE_PROJECTION_H

#include "src/ch_core/contracts.h"
#include "src/ch_core/grid.h"
#include <cmath>

namespace ch {

enum class CameraRotation { r0 = 0, r90 = 1, r180 = 2, r270 = 3 };

struct CameraState {
    float pan_x = 0.0F;
    float pan_y = 0.0F;
    float zoom = 1.0F;
    CameraRotation rotation = CameraRotation::r0;
};

struct WorldPoint {
    float x = 0.0F;
    float y = 0.0F;
};

struct ScreenPoint {
    float x = 0.0F;
    float y = 0.0F;
};

[[nodiscard]] constexpr WorldPoint camera_view_point(const float x, const float y, const CameraRotation rotation) {
    switch (rotation) {
        case CameraRotation::r0: return {x, y};
        case CameraRotation::r90: return {y, -x};
        case CameraRotation::r180: return {-x, -y};
        case CameraRotation::r270: return {-y, x};
    }
    return {x, y};
}

[[nodiscard]] constexpr WorldPoint logical_world_point(const float x, const float y, const CameraRotation rotation) {
    switch (rotation) {
        case CameraRotation::r0: return {x, y};
        case CameraRotation::r90: return {-y, x};
        case CameraRotation::r180: return {-x, -y};
        case CameraRotation::r270: return {y, -x};
    }
    return {x, y};
}

[[nodiscard]] constexpr WorldPoint tile_visual_top_world(const int tile_x, const int tile_y, const CameraRotation rotation) {
    switch (rotation) {
        case CameraRotation::r0: return {static_cast<float>(tile_x), static_cast<float>(tile_y)};
        case CameraRotation::r90: return {static_cast<float>(tile_x + 1), static_cast<float>(tile_y)};
        case CameraRotation::r180: return {static_cast<float>(tile_x + 1), static_cast<float>(tile_y + 1)};
        case CameraRotation::r270: return {static_cast<float>(tile_x), static_cast<float>(tile_y + 1)};
    }
    return {static_cast<float>(tile_x), static_cast<float>(tile_y)};
}

[[nodiscard]] constexpr WorldPoint building_visual_ground_world(const int tile_x, const int tile_y,
                                                                 const int footprint_width, const int footprint_height,
                                                                 const CameraRotation rotation) {
    switch (rotation) {
        case CameraRotation::r0: return {static_cast<float>(tile_x + footprint_width), static_cast<float>(tile_y + footprint_height)};
        case CameraRotation::r90: return {static_cast<float>(tile_x), static_cast<float>(tile_y + footprint_height)};
        case CameraRotation::r180: return {static_cast<float>(tile_x), static_cast<float>(tile_y)};
        case CameraRotation::r270: return {static_cast<float>(tile_x + footprint_width), static_cast<float>(tile_y)};
    }
    return {static_cast<float>(tile_x), static_cast<float>(tile_y)};
}

[[nodiscard]] constexpr float camera_depth_key(const float world_x, const float world_y, const CameraState& camera) {
    const WorldPoint view = camera_view_point(world_x, world_y, camera.rotation);
    return view.x + view.y;
}

[[nodiscard]] ScreenPoint world_to_screen_point(float world_x, float world_y, const CameraState& camera, float viewport_w, float viewport_h);

[[nodiscard]] GridCoord screen_to_tile_coord(float screen_x, float screen_y, const CameraState& camera, float viewport_w, float viewport_h);

} // namespace ch

#endif // CITY_HORIZON_CH_CORE_PROJECTION_H
