#include "engine_projection_adapter.h"

#include "src/ch_core/contracts.h"

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

QPointF EngineProjectionAdapter::worldToScreen(const float world_x,
                                               const float world_y,
                                               const float world_z,
                                               const ch::CameraState& camera,
                                               const QSizeF& viewport) {
    const ch::ScreenPoint point = ch::world_to_screen_point(
        world_x, world_y, world_z, camera,
        static_cast<float>(viewport.width()),
        static_cast<float>(viewport.height()));
    return QPointF(point.x, point.y);
}

QPointF EngineProjectionAdapter::screenToWorld(const QPointF& screen,
                                               const ch::CameraState& camera,
                                               const QSizeF& viewport) {
    const ch::WorldPoint point = ch::screen_to_world_point(
        static_cast<float>(screen.x()),
        static_cast<float>(screen.y()),
        camera,
        static_cast<float>(viewport.width()),
        static_cast<float>(viewport.height()));
    return QPointF(point.x, point.y);
}

ch::CameraState EngineProjectionAdapter::rotatePreservingScreenPoint(
    const ch::CameraState& camera,
    const ch::CameraRotation next_rotation,
    const QPointF& screen,
    const QSizeF& viewport) {
    const QPointF focus_world = screenToWorld(screen, camera, viewport);

    ch::CameraState rotated = camera;
    rotated.rotation = next_rotation;
    rotated.pan_x = 0.0F;
    rotated.pan_y = 0.0F;

    const QPointF projected = worldToScreen(
        static_cast<float>(focus_world.x()),
        static_cast<float>(focus_world.y()),
        rotated,
        viewport);
    rotated.pan_x = static_cast<float>(screen.x() - projected.x());
    rotated.pan_y = static_cast<float>(screen.y() - projected.y());
    return rotated;
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
        {"canonicalInverseFunction", QString::fromLatin1(kCanonicalInverseFunction)},
        {"gridContract", QString::fromLatin1(ch::contracts::kGridContract)},
        {"cameraContract", QString::fromLatin1(ch::contracts::kCameraContract)},
        {"projectionKind", QStringLiteral("orthographic_dimetric_2_to_1")},
        {"cameraWorldYawDeg", ch::contracts::kCameraWorldYawDeg},
        {"cameraElevationDeg", ch::contracts::kCameraElevationDeg},
        {"groundAxisScreenAngleDeg", ch::contracts::kGroundAxisScreenAngleDeg},
        {"diamondRatio", ch::contracts::kDiamondRatio},
        {"perspective", ch::contracts::kCameraPerspective},
        {"worldElevationPixelsPerUnit", ch::kWorldElevationPixelsPerUnit},
        {"supportsWorldElevation", true},
        {"supportsFourWayRotation", true},
        {"rotationKeepsScreenFocus", true},
        {"formulaDuplicatedInComposer", false},
        {"cameraRotationQuarterTurns", static_cast<int>(camera.rotation)},
        {"cameraZoom", camera.zoom},
        {"cameraPanX", camera.pan_x},
        {"cameraPanY", camera.pan_y},
    };
}

} // namespace ch::studio
