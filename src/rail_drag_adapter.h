#pragma once

#include "rail_placement_controller.h"

#include <cmath>
#include <optional>

inline constexpr const char* kChRailDragAdapterContract = "CH_RAIL_DRAG_ADAPTER_V1";

struct RailDragWorldPoint {
    float x = 0.0F;
    float y = 0.0F;
    float z = 0.0F;
};

// CH_RAIL_DRAG_ADAPTER_V1
//
// Pure world-space bridge between MapForge pointer input and the transactional
// rail placement controller. Screen -> world conversion remains owned by the
// canonical CH_CAMERA_V1 projection. This adapter only measures an already
// projected world-space drag and never authors geometry directly.
class RailDragAdapter final {
public:
    explicit RailDragAdapter(RailPlacementController& controller)
        : controller_(controller) {}

    [[nodiscard]] bool begin(
        const RailPlacementNodeId source,
        const RailPlacementMode mode,
        const RailDragWorldPoint& drag_start) {
        if (active_ || !finite_point(drag_start)) return false;
        if (!controller_.begin(source, mode)) return false;

        start_ = drag_start;
        active_ = true;
        return true;
    }

    [[nodiscard]] std::optional<RailPlacementPreview> update(
        const RailDragWorldPoint& drag_current) {
        if (!active_ || !finite_point(drag_current)) return std::nullopt;

        const float dx = drag_current.x - start_.x;
        const float dy = drag_current.y - start_.y;
        const float planar_distance = std::sqrt(dx * dx + dy * dy);
        if (!std::isfinite(planar_distance) || planar_distance <= 0.0F) {
            return std::nullopt;
        }

        return controller_.preview(planar_distance);
    }

    [[nodiscard]] bool confirm() {
        if (!active_) return false;
        const bool committed = controller_.commit();
        if (committed) finish();
        return committed;
    }

    [[nodiscard]] bool cancel() {
        if (!active_) return false;
        const bool cancelled = controller_.cancel();
        finish();
        return cancelled;
    }

    [[nodiscard]] bool active() const { return active_; }
    [[nodiscard]] RailDragWorldPoint start() const { return start_; }

private:
    [[nodiscard]] static bool finite_point(const RailDragWorldPoint& point) {
        return std::isfinite(point.x) &&
               std::isfinite(point.y) &&
               std::isfinite(point.z);
    }

    void finish() {
        active_ = false;
        start_ = {};
    }

    RailPlacementController& controller_;
    RailDragWorldPoint start_{};
    bool active_ = false;
};
