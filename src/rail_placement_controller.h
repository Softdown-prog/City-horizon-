#pragma once

#include "rail_placement_graph.h"

#include <cmath>
#include <optional>

inline constexpr const char* kChRailPlacementControllerContract = "CH_RAIL_PLACEMENT_CONTROLLER_V1";

enum class RailPlacementMode {
    straight,
    curve_left,
    curve_right,
    turnout_left,
    turnout_right,
};

struct RailPlacementPreview {
    RailPlacementMode mode = RailPlacementMode::straight;
    RailPlacementNodeId primary_node = kInvalidRailPlacementNodeId;
    RailPlacementEdgeId primary_edge = kInvalidRailPlacementEdgeId;
    RailPlacementNodeId secondary_node = kInvalidRailPlacementNodeId;
    RailPlacementEdgeId secondary_edge = kInvalidRailPlacementEdgeId;

    [[nodiscard]] bool ok() const {
        return primary_node != kInvalidRailPlacementNodeId &&
               primary_edge != kInvalidRailPlacementEdgeId;
    }

    [[nodiscard]] bool has_secondary_branch() const {
        return secondary_node != kInvalidRailPlacementNodeId &&
               secondary_edge != kInvalidRailPlacementEdgeId;
    }
};

// CH_RAIL_PLACEMENT_CONTROLLER_V1
//
// Transactional editor controller for mouse/pen drag authoring. It does not
// interpret screen coordinates; the MapForge adapter will convert input through
// the canonical projection and provide a world-space drag metric. Every preview
// first rolls the graph back to the operation checkpoint, so repeated mouse-move
// events replace the previous preview instead of accumulating geometry.
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

    // metric_world is deliberately simple in V1:
    //   straight -> requested length
    //   curve/turnout -> requested radius
    // Invalid metrics fail closed and leave the graph exactly at the begin()
    // checkpoint, ready for the next mouse-move event or cancel().
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

    // Commit is only legal after a valid preview. Geometry is already present
    // in the staging graph, so commit merely seals the transaction.
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
