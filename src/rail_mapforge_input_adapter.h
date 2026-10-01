#pragma once

#include "rail_drag_adapter.h"
#include "src/ch_core/projection.h"

#include <cmath>
#include <optional>

inline constexpr const char* kChRailMapForgeInputContract = "CH_RAIL_MAPFORGE_INPUT_V1";

// CH_RAIL_MAPFORGE_INPUT_V1
//
// Thin, fail-closed boundary between MapForge screen-space pointer events and
// the railway authoring stack. The only screen->world conversion is the shared
// CH_CAMERA_V1 inverse projection. No tile-flooring is used, so rail previews
// stay continuous between tile centres while the rest of MapForge keeps its
// existing tile-selection semantics.
class RailMapForgeInputAdapter final {
public:
    explicit RailMapForgeInputAdapter(RailDragAdapter& drag) : drag_(drag) {}

    [[nodiscard]] bool begin(
        const RailPlacementNodeId source,
        const RailPlacementMode mode,
        const float screen_x,
        const float screen_y,
        const ch::CameraState& camera,
        const float viewport_w,
        const float viewport_h) {
        const auto world = screen_to_world(screen_x, screen_y, camera, viewport_w, viewport_h);
        if (!world) return false;
        return drag_.begin(source, mode, *world);
    }

    [[nodiscard]] std::optional<RailPlacementPreview> update(
        const float screen_x,
        const float screen_y,
        const ch::CameraState& camera,
        const float viewport_w,
        const float viewport_h) {
        const auto world = screen_to_world(screen_x, screen_y, camera, viewport_w, viewport_h);
        if (!world) return std::nullopt;
        return drag_.update(*world);
    }

    [[nodiscard]] bool confirm() { return drag_.confirm(); }
    [[nodiscard]] bool cancel() { return drag_.cancel(); }
    [[nodiscard]] bool active() const { return drag_.active(); }

    [[nodiscard]] static std::optional<RailDragWorldPoint> screen_to_world(
        const float screen_x,
        const float screen_y,
        const ch::CameraState& camera,
        const float viewport_w,
        const float viewport_h) {
        if (!std::isfinite(screen_x) || !std::isfinite(screen_y) ||
            !std::isfinite(viewport_w) || !std::isfinite(viewport_h) ||
            !std::isfinite(camera.pan_x) || !std::isfinite(camera.pan_y) ||
            !std::isfinite(camera.zoom) || viewport_w <= 0.0F ||
            viewport_h <= 0.0F || camera.zoom <= 0.0F) {
            return std::nullopt;
        }

        const ch::WorldPoint world = ch::screen_to_world_point(
            screen_x, screen_y, camera, viewport_w, viewport_h);
        if (!std::isfinite(world.x) || !std::isfinite(world.y)) return std::nullopt;
        return RailDragWorldPoint{world.x, world.y, 0.0F};
    }

private:
    RailDragAdapter& drag_;
};
