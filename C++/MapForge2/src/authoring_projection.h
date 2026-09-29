#pragma once

#include "src/ch_core/projection.h"

#include <QPointF>
#include <QSizeF>

#include <algorithm>

namespace ch::studio {

// Canonical projection bridge for MapForge authoring/render-preview tools.
// Ground XY always delegates to CH_CAMERA_V1 through ch::world_to_screen_point.
// Some authoring renderers express vertical dimensions directly in output pixels
// (for example building wall/roof heights and fence posts); those values remain
// pixel-space offsets and are intentionally not converted to world elevation.
//
// Authoring quarter-turns rotate the asset root. Runtime CameraRotation rotates
// the camera, so the equivalent camera turn is the inverse turn (EAST/WEST swap
// direction while SOUTH/NORTH remain unchanged).
inline ch::CameraRotation authoringCameraRotation(int asset_quarter_turns) {
    int turns = asset_quarter_turns % 4;
    if (turns < 0) turns += 4;
    const int camera_turns = (4 - turns) % 4;
    return static_cast<ch::CameraRotation>(camera_turns);
}

inline QPointF projectAuthoringGround(float world_x,
                                      float world_y,
                                      int asset_quarter_turns,
                                      const QSizeF& viewport,
                                      const QPointF& screen_origin,
                                      float zoom = 1.0F) {
    ch::CameraState camera;
    camera.rotation = authoringCameraRotation(asset_quarter_turns);
    camera.zoom = std::max(0.0001F, zoom);
    camera.pan_x = static_cast<float>(screen_origin.x() - viewport.width() * 0.5);
    camera.pan_y = static_cast<float>(screen_origin.y() - viewport.height() * 0.5);

    const ch::ScreenPoint projected = ch::world_to_screen_point(
        world_x,
        world_y,
        camera,
        static_cast<float>(viewport.width()),
        static_cast<float>(viewport.height()));
    return QPointF(projected.x, projected.y);
}

inline QPointF projectAuthoringPixelElevation(float world_x,
                                              float world_y,
                                              float elevation_pixels,
                                              int asset_quarter_turns,
                                              const QSizeF& viewport,
                                              const QPointF& screen_origin,
                                              float zoom = 1.0F) {
    QPointF projected = projectAuthoringGround(
        world_x, world_y, asset_quarter_turns, viewport, screen_origin, zoom);
    projected.ry() -= static_cast<qreal>(elevation_pixels) * static_cast<qreal>(zoom);
    return projected;
}

} // namespace ch::studio
