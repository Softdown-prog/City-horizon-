#include "engine_projection_adapter.h"

#include "src/ch_core/contracts.h"
#include "src/ch_core/projection.h"

#include <QPointF>
#include <QSizeF>

#include <array>
#include <cmath>
#include <iostream>

namespace {

float pointError(const QPointF& left, const QPointF& right) {
    const float dx = static_cast<float>(left.x() - right.x());
    const float dy = static_cast<float>(left.y() - right.y());
    return std::sqrt(dx * dx + dy * dy);
}

float worldError(const QPointF& left, const QPointF& right) {
    return pointError(left, right);
}

QPointF runtimeProjection(const float x, const float y, const float z,
                          const ch::CameraState& camera, const QSizeF& viewport) {
    const ch::ScreenPoint point = ch::world_to_screen_point(
        x, y, z, camera,
        static_cast<float>(viewport.width()),
        static_cast<float>(viewport.height()));
    return QPointF(point.x, point.y);
}

QPointF runtimeInverse(const QPointF& screen, const ch::CameraState& camera,
                       const QSizeF& viewport) {
    const ch::WorldPoint point = ch::screen_to_world_point(
        static_cast<float>(screen.x()),
        static_cast<float>(screen.y()),
        camera,
        static_cast<float>(viewport.width()),
        static_cast<float>(viewport.height()));
    return QPointF(point.x, point.y);
}

} // namespace

int main() {
    constexpr float kScreenTolerance = 0.0001F;
    constexpr float kWorldTolerance = 0.00001F;

    if (ch::contracts::kTileWidth != 128 || ch::contracts::kTileHeight != 64
        || ch::contracts::kCameraWorldYawDeg != 45.0
        || ch::contracts::kCameraElevationDeg != 30.0
        || ch::contracts::kCameraPerspective) {
        std::cerr << "CH_CAMERA_V1 constants drifted\n";
        return 1;
    }

    const QSizeF viewport(731.0, 509.0);
    const QPointF focusScreen(viewport.width() * 0.5 + 37.25,
                              viewport.height() * 0.5 - 21.75);
    const std::array<ch::WorldPoint3, 5> samples = {{
        {-3.25F, 1.75F, 0.0F},
        {0.0F, 0.0F, 0.5F},
        {2.125F, -4.5F, 1.25F},
        {8.0F, 3.0F, 2.0F},
        {-1.5F, -2.75F, 4.0F},
    }};

    for (int turn = 0; turn < 4; ++turn) {
        ch::CameraState camera;
        camera.rotation = static_cast<ch::CameraRotation>(turn);
        camera.zoom = 1.37F;
        camera.pan_x = 23.25F;
        camera.pan_y = -17.75F;

        for (const ch::WorldPoint3& sample : samples) {
            const QPointF runtime = runtimeProjection(sample.x, sample.y, sample.z, camera, viewport);
            const QPointF mapforge = ch::studio::EngineProjectionAdapter::worldToScreen(
                sample.x, sample.y, sample.z, camera, viewport);
            if (pointError(runtime, mapforge) > kScreenTolerance) {
                std::cerr << "XYZ projection parity failed at rotation " << turn << '\n';
                return 2;
            }
        }

        const QPointF runtimeWorld = runtimeInverse(focusScreen, camera, viewport);
        const QPointF mapforgeWorld = ch::studio::EngineProjectionAdapter::screenToWorld(
            focusScreen, camera, viewport);
        if (worldError(runtimeWorld, mapforgeWorld) > kWorldTolerance) {
            std::cerr << "inverse projection parity failed at rotation " << turn << '\n';
            return 3;
        }

        const auto nextRotation = static_cast<ch::CameraRotation>((turn + 1) % 4);
        const ch::CameraState rotated = ch::studio::EngineProjectionAdapter::rotatePreservingScreenPoint(
            camera, nextRotation, focusScreen, viewport);
        const QPointF worldAfterRotation = ch::studio::EngineProjectionAdapter::screenToWorld(
            focusScreen, rotated, viewport);
        if (worldError(mapforgeWorld, worldAfterRotation) > kWorldTolerance) {
            std::cerr << "focus preservation failed from rotation " << turn << '\n';
            return 4;
        }

        const QPointF projectedFocus = ch::studio::EngineProjectionAdapter::worldToScreen(
            static_cast<float>(mapforgeWorld.x()),
            static_cast<float>(mapforgeWorld.y()),
            rotated,
            viewport);
        if (pointError(focusScreen, projectedFocus) > kScreenTolerance) {
            std::cerr << "rotated focus screen position drifted from rotation " << turn << '\n';
            return 5;
        }
    }

    const QJsonObject manifest = ch::studio::EngineProjectionAdapter::manifest(ch::CameraState{});
    if (manifest.value("cameraContract").toString() != QStringLiteral("CH_CAMERA_V1")
        || !manifest.value("supportsWorldElevation").toBool()
        || !manifest.value("supportsFourWayRotation").toBool()
        || !manifest.value("rotationKeepsScreenFocus").toBool()) {
        std::cerr << "MapForge projection manifest does not advertise runtime camera parity\n";
        return 6;
    }

    std::cout << "PASS MAPFORGE_CAMERA_RUNTIME_PARITY_V1\n";
    return 0;
}
