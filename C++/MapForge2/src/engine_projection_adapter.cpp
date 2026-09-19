#include "engine_projection_adapter.h"

namespace ch::studio {

QPointF EngineProjectionAdapter::worldToScreen(const float world_x,
                                               const float world_y,
                                               const ch::CameraState& camera,
                                               const QSizeF& viewport) {
    const ch::ScreenPoint point = ch::world_to_screen_point(
        world_x, world_y, camera,
        static_cast<float>(viewport.width()),
        static_cast<float>(viewport.height()));
    return QPointF(point.x, point.y);
}

QPointF EngineProjectionAdapter::worldDeltaToScreen(const float delta_world_x,
                                                    const float delta_world_y,
                                                    const ch::CameraState& camera) {
    const ch::ScreenPoint origin = ch::world_to_screen_point(
        0.0F, 0.0F, camera, 0.0F, 0.0F);
    const ch::ScreenPoint point = ch::world_to_screen_point(
        delta_world_x, delta_world_y, camera, 0.0F, 0.0F);
    return QPointF(point.x - origin.x, point.y - origin.y);
}

float EngineProjectionAdapter::depthKey(const float world_x,
                                        const float world_y,
                                        const ch::CameraState& camera) {
    return ch::camera_depth_key(world_x, world_y, camera);
}

QJsonObject EngineProjectionAdapter::manifest(const ch::CameraState& camera) {
    return QJsonObject{
        {"version", QString::fromLatin1(kVersion)},
        {"canonicalSourceFile", QString::fromLatin1(kCanonicalSourceFile)},
        {"canonicalFunction", QString::fromLatin1(kCanonicalFunction)},
        {"formulaDuplicatedInComposer", false},
        {"cameraRotationQuarterTurns", static_cast<int>(camera.rotation)},
        {"cameraZoom", camera.zoom},
        {"cameraPanX", camera.pan_x},
        {"cameraPanY", camera.pan_y},
    };
}

} // namespace ch::studio
