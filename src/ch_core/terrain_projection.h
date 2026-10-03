#pragma once

#include "src/ch_core/projection.h"
#include "src/ch_core/terrain_heightfield.h"

namespace ch {

// Visual scale for sculpted terrain. This is intentionally gentler than the
// object/world Z scale so hills remain readable without becoming cliffs.
inline constexpr float kTerrainHeightPixelsPerUnit = 16.0F;

[[nodiscard]] inline ScreenPoint terrain_world_to_screen_point(
    const float world_x, const float world_y, const TerrainHeightField& heightfield,
    const CameraState& camera, const float viewport_width, const float viewport_height) {
    ScreenPoint point = world_to_screen_point(
        world_x, world_y, camera, viewport_width, viewport_height);
    point.y -= heightfield.sample(world_x, world_y) *
               kTerrainHeightPixelsPerUnit * camera.zoom;
    return point;
}

} // namespace ch
