#pragma once

#include "src/ch_core/projection.h"

#include <QJsonObject>
#include <QPointF>
#include <QSizeF>

namespace ch::studio {

class EngineProjectionAdapter final {
public:
    static constexpr const char* kVersion = "engine_projection_adapter_2";
    static constexpr const char* kCanonicalSourceFile = "src/ch_core/projection.cpp";
    static constexpr const char* kCanonicalFunction = "ch::world_to_screen_point";

    static QPointF worldToScreen(float world_x,
                                 float world_y,
                                 const ch::CameraState& camera,
                                 const QSizeF& viewport);

    static QPointF worldDeltaToScreen(float delta_world_x,
                                      float delta_world_y,
                                      const ch::CameraState& camera);

    static float depthKey(float world_x,
                          float world_y,
                          const ch::CameraState& camera);

    static QJsonObject manifest(const ch::CameraState& camera);
};

} // namespace ch::studio
