#include "src/ch_core/projection.h"

namespace ch {

ScreenPoint world_to_screen_point(const float world_x, const float world_y, const CameraState& camera, const float viewport_w, const float viewport_h) {
    const WorldPoint view = camera_view_point(world_x, world_y, camera.rotation);
    return {
        viewport_w * 0.5F + camera.pan_x + (view.x - view.y) * (contracts::kTileWidth * 0.5F) * camera.zoom,
        viewport_h * 0.5F + camera.pan_y + (view.x + view.y) * (contracts::kTileHeight * 0.5F) * camera.zoom
    };
}

GridCoord screen_to_tile_coord(const float screen_x, const float screen_y, const CameraState& camera, const float viewport_w, const float viewport_h) {
    const float axis_x = (screen_x - viewport_w * 0.5F - camera.pan_x) / (contracts::kTileWidth * 0.5F * camera.zoom);
    const float axis_y = (screen_y - viewport_h * 0.5F - camera.pan_y) / (contracts::kTileHeight * 0.5F * camera.zoom);
    const WorldPoint logical = logical_world_point((axis_y + axis_x) * 0.5F,
                                                   (axis_y - axis_x) * 0.5F,
                                                   camera.rotation);
    return {
        static_cast<int>(std::floor(logical.x)),
        static_cast<int>(std::floor(logical.y))
    };
}

} // namespace ch
