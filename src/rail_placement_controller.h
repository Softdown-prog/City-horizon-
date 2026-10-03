#pragma once

#include "rail_placement_graph.h"

#include <cmath>
#include <optional>

inline constexpr const char* kChRailPlacementControllerContract = "CH_RAIL_PLACEMENT_CONTROLLER_V2";

enum class RailPlacementMode {
    straight,
    curve_left,
    curve_right,
    turnout_left,
    turnout_right,
    crossing,
};

struct RailPlacementPreview {
    RailPlacementMode mode = RailPlacementMode::straight;
    RailPlacementNodeId primary_node = kInvalidRailPlacementNodeId;
    RailPlacementEdgeId primary_edge = kInvalidRailPlacementEdgeId;
    RailPlacementNodeId secondary_node = kInvalidRailPlacementNodeId;
    RailPlacementEdgeId secondary_edge = kInvalidRailPlacementEdgeId;
    RailPlacementNodeId auxiliary_node = kInvalidRailPlacementNodeId;

    [[nodiscard]] bool ok() const {
        return primary_node != kInvalidRailPlacementNodeId &&
               primary_edge != kInvalidRailPlacementEdgeId;
    }

    [[nodiscard]] bool has_secondary_branch() const {
        return secondary_node != kInvalidRailPlacementNodeId &&
               secondary_edge != kInvalidRailPlacementEdgeId;
    }

    [[nodiscard]] bool has_auxiliary_node() const {
        return auxiliary_node != kInvalidRailPlacementNodeId;
    }
};

// CH_RAIL_PLACEMENT_CONTROLLER_V2
//
// Transactional editor controller for mouse/pen drag authoring. It does not
// interpret screen coordinates; the MapForge adapter converts input through
// CH_CAMERA_V1 and provides a world-space metric. Repeated previews replace the
// previous staging geometry. Crossing uses drag length as its diamond span.
class RailPlacementController final {
public:
    explicit RailPlacementController(RailPlacementGraph& graph) : graph_(graph) {}

    [[nodiscard]] bool begin(const RailPlacementNodeId source, const RailPlacementMode mode) {
        if (active_ || graph_.node(source) == nullptr) return false;
        source_ = source;
        mode_ = mode;
        checkpoint_ = graph_.checkpoint();
        preview_.reset();
        active_ = true;
        return true;
    }

    // metric_world:
    //   straight/crossing -> requested length
    //   curve/turnout     -> requested radius
    [[nodiscard]] std::optional<RailPlacementPreview> preview(const float metric_world) {
        if (!active_ || !std::isfinite(metric_world)) return std::nullopt;
        if (!reset_to_checkpoint()) return std::nullopt;

        std::optional<RailPlacementPreview> candidate;
        switch (mode_) {
        case RailPlacementMode::straight: {
            const auto result = graph_.append_straight(source_, metric_world);
            if (result && result->ok()) {
                candidate = RailPlacementPreview{mode_, result->node, result->edge};
            }
            break;
        }
        case RailPlacementMode::curve_left:
        case RailPlacementMode::curve_right: {
            const RailTurnDirection direction = mode_ == RailPlacementMode::curve_left
                ? RailTurnDirection::left : RailTurnDirection::right;
            const auto result = graph_.append_quarter_curve(source_, metric_world, direction);
            if (result && result->ok()) {
                candidate = RailPlacementPreview{mode_, result->node, result->edge};
            }
            break;
        }
        case RailPlacementMode::turnout_left:
        case RailPlacementMode::turnout_right: {
            constexpr float kTurnoutAngleRadians = 0.2617993877991494F; // 15 degrees
            const RailTurnDirection direction = mode_ == RailPlacementMode::turnout_left
                ? RailTurnDirection::left : RailTurnDirection::right;
            const auto result = graph_.append_turnout(
                source_, metric_world, kTurnoutAngleRadians, direction);
            if (result && result->ok()) {
                candidate = RailPlacementPreview{
                    mode_,
                    result->through_node,
                    result->through_edge,
                    result->diverging_node,
                    result->diverging_edge,
                };
            }
            break;
        }
        case RailPlacementMode::crossing: {
            const auto result = graph_.append_crossing(source_, metric_world);
            if (result && result->ok()) {
                candidate = RailPlacementPreview{
                    mode_,
                    result->primary_node,
                    result->primary_edge,
                    result->secondary_exit_node,
                    result->secondary_edge,
                    result->secondary_entry_node,
                };
            }
            break;
        }
        }

        if (!candidate) {
            const bool rolled_back = graph_.rollback(checkpoint_);
            (void)rolled_back;
            preview_.reset();
            return std::nullopt;
        }

        preview_ = candidate;
        return preview_;
    }

    [[nodiscard]] bool commit() {
        if (!active_ || !preview_ || !preview_->ok()) return false;
        finish_operation();
        return true;
    }

    [[nodiscard]] bool cancel() {
        if (!active_) return false;
        const bool rolled_back = graph_.rollback(checkpoint_);
        finish_operation();
        return rolled_back;
    }

    [[nodiscard]] bool active() const { return active_; }
    [[nodiscard]] RailPlacementNodeId source() const { return source_; }
    [[nodiscard]] RailPlacementMode mode() const { return mode_; }
    [[nodiscard]] const std::optional<RailPlacementPreview>& current_preview() const { return preview_; }

private:
    [[nodiscard]] bool reset_to_checkpoint() {
        if (!graph_.rollback(checkpoint_)) {
            preview_.reset();
            return false;
        }
        preview_.reset();
        return true;
    }

    void finish_operation() {
        active_ = false;
        source_ = kInvalidRailPlacementNodeId;
        preview_.reset();
        checkpoint_ = graph_.checkpoint();
    }

    RailPlacementGraph& graph_;
    RailPlacementCheckpoint checkpoint_{};
    RailPlacementNodeId source_ = kInvalidRailPlacementNodeId;
    RailPlacementMode mode_ = RailPlacementMode::straight;
    std::optional<RailPlacementPreview> preview_;
    bool active_ = false;
};
