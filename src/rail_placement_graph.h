#pragma once

#include "rail_path_builder.h"

#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <optional>
#include <vector>

inline constexpr const char* kChRailPlacementGraphContract = "CH_RAIL_PLACEMENT_GRAPH_V1";

using RailPlacementNodeId = std::uint32_t;
using RailPlacementEdgeId = std::uint32_t;
inline constexpr RailPlacementNodeId kInvalidRailPlacementNodeId = std::numeric_limits<RailPlacementNodeId>::max();
inline constexpr RailPlacementEdgeId kInvalidRailPlacementEdgeId = std::numeric_limits<RailPlacementEdgeId>::max();

enum class RailPlacementEdgeKind {
    straight,
    curve,
    turnout_through,
    turnout_diverging,
};

struct RailPlacementNode {
    RailPlacementNodeId id = kInvalidRailPlacementNodeId;
    RailWorldPoint3 position{};
    float heading_radians = 0.0F;
};

struct RailPlacementEdge {
    RailPlacementEdgeId id = kInvalidRailPlacementEdgeId;
    RailPlacementNodeId from = kInvalidRailPlacementNodeId;
    RailPlacementNodeId to = kInvalidRailPlacementNodeId;
    RailPlacementEdgeKind kind = RailPlacementEdgeKind::straight;
    RailSplineSegment segment{};
};

struct RailPlacementAppendResult {
    RailPlacementNodeId node = kInvalidRailPlacementNodeId;
    RailPlacementEdgeId edge = kInvalidRailPlacementEdgeId;

    [[nodiscard]] bool ok() const {
        return node != kInvalidRailPlacementNodeId && edge != kInvalidRailPlacementEdgeId;
    }
};

struct RailPlacementTurnoutResult {
    RailPlacementNodeId through_node = kInvalidRailPlacementNodeId;
    RailPlacementNodeId diverging_node = kInvalidRailPlacementNodeId;
    RailPlacementEdgeId through_edge = kInvalidRailPlacementEdgeId;
    RailPlacementEdgeId diverging_edge = kInvalidRailPlacementEdgeId;

    [[nodiscard]] bool ok() const {
        return through_node != kInvalidRailPlacementNodeId &&
               diverging_node != kInvalidRailPlacementNodeId &&
               through_edge != kInvalidRailPlacementEdgeId &&
               diverging_edge != kInvalidRailPlacementEdgeId;
    }
};

struct RailPlacementCheckpoint {
    std::size_t node_count = 0U;
    std::size_t edge_count = 0U;
};

// CH_RAIL_PLACEMENT_GRAPH_V1
//
// Transactional staging graph for the editor. It deliberately does not own
// gameplay occupancy or persistence yet. Every edge is fully validated and
// mesh-buildable before it is committed, and rollback truncates only objects
// created after a checkpoint. This keeps failed/cancelled authoring operations
// from leaving orphaned rail geometry behind.
class RailPlacementGraph final {
public:
    explicit RailPlacementGraph(RailProfile profile = {}) : profile_(profile) {}

    [[nodiscard]] std::optional<RailPlacementNodeId> add_root(
        const RailWorldPoint3& position,
        const float heading_radians) {
        if (!finite_point(position) || !std::isfinite(heading_radians) || !inside_world(position)) {
            return std::nullopt;
        }
        if (nodes_.size() >= static_cast<std::size_t>(std::numeric_limits<RailPlacementNodeId>::max())) {
            return std::nullopt;
        }
        const RailPlacementNodeId id = static_cast<RailPlacementNodeId>(nodes_.size());
        nodes_.push_back({id, position, heading_radians});
        return id;
    }

    [[nodiscard]] std::optional<RailPlacementAppendResult> append_straight(
        const RailPlacementNodeId from,
        const float length,
        const int subdivisions = 32) {
        const RailPlacementNode* source = node(from);
        if (source == nullptr) return std::nullopt;
        const RailPathBuildResult authored = RailPathBuilder::straight(
            source->position, source->heading_radians, length, subdivisions, profile_);
        if (!authored.ok() || !mesh_safe(authored.segment)) return std::nullopt;
        return commit_single(from, authored.segment, source->heading_radians, RailPlacementEdgeKind::straight);
    }

    [[nodiscard]] std::optional<RailPlacementAppendResult> append_quarter_curve(
        const RailPlacementNodeId from,
        const float radius,
        const RailTurnDirection direction,
        const int subdivisions = 48) {
        const RailPlacementNode* source = node(from);
        if (source == nullptr) return std::nullopt;
        const RailPathBuildResult authored = RailPathBuilder::quarter_curve(
            source->position, source->heading_radians, radius, direction, subdivisions, profile_);
        if (!authored.ok() || !mesh_safe(authored.segment)) return std::nullopt;
        constexpr float kHalfPi = 1.57079632679489661923F;
        const float exit_heading = source->heading_radians +
            (direction == RailTurnDirection::left ? kHalfPi : -kHalfPi);
        return commit_single(from, authored.segment, exit_heading, RailPlacementEdgeKind::curve);
    }

    [[nodiscard]] std::optional<RailPlacementTurnoutResult> append_turnout(
        const RailPlacementNodeId from,
        const float radius,
        const float diverging_angle_radians,
        const RailTurnDirection direction,
        const int subdivisions = 48) {
        const RailPlacementNode* source = node(from);
        if (source == nullptr) return std::nullopt;

        const RailTurnoutBuildResult authored = RailPathBuilder::turnout(
            source->position, source->heading_radians, radius, diverging_angle_radians,
            direction, subdivisions, profile_);
        if (!authored.ok() || !mesh_safe(authored.through) || !mesh_safe(authored.diverging)) {
            return std::nullopt;
        }
        if (nodes_.size() > static_cast<std::size_t>(std::numeric_limits<RailPlacementNodeId>::max()) - 2U ||
            edges_.size() > static_cast<std::size_t>(std::numeric_limits<RailPlacementEdgeId>::max()) - 2U) {
            return std::nullopt;
        }

        const RailPlacementCheckpoint before = checkpoint();
        const auto through_node = add_root(authored.through.end, source->heading_radians);
        const auto diverging_node = add_root(authored.diverging.end, authored.diverging_exit_heading_radians);
        if (!through_node || !diverging_node) {
            const bool rolled_back = rollback(before);
            (void)rolled_back;
            return std::nullopt;
        }

        const RailPlacementEdgeId through_edge = static_cast<RailPlacementEdgeId>(edges_.size());
        edges_.push_back({through_edge, from, *through_node, RailPlacementEdgeKind::turnout_through, authored.through});
        const RailPlacementEdgeId diverging_edge = static_cast<RailPlacementEdgeId>(edges_.size());
        edges_.push_back({diverging_edge, from, *diverging_node, RailPlacementEdgeKind::turnout_diverging, authored.diverging});
        return RailPlacementTurnoutResult{*through_node, *diverging_node, through_edge, diverging_edge};
    }

    [[nodiscard]] RailPlacementCheckpoint checkpoint() const {
        return {nodes_.size(), edges_.size()};
    }

    [[nodiscard]] bool rollback(const RailPlacementCheckpoint checkpoint_value) {
        if (checkpoint_value.node_count > nodes_.size() || checkpoint_value.edge_count > edges_.size()) {
            return false;
        }
        edges_.resize(checkpoint_value.edge_count);
        nodes_.resize(checkpoint_value.node_count);
        return true;
    }

    void clear() {
        edges_.clear();
        nodes_.clear();
    }

    [[nodiscard]] const RailPlacementNode* node(const RailPlacementNodeId id) const {
        if (id >= nodes_.size()) return nullptr;
        return &nodes_[id];
    }

    [[nodiscard]] const RailPlacementEdge* edge(const RailPlacementEdgeId id) const {
        if (id >= edges_.size()) return nullptr;
        return &edges_[id];
    }

    [[nodiscard]] const std::vector<RailPlacementNode>& nodes() const { return nodes_; }
    [[nodiscard]] const std::vector<RailPlacementEdge>& edges() const { return edges_; }
    [[nodiscard]] const RailProfile& profile() const { return profile_; }

private:
    [[nodiscard]] static bool finite_point(const RailWorldPoint3& point) {
        return std::isfinite(point.x) && std::isfinite(point.y) && std::isfinite(point.z);
    }

    [[nodiscard]] bool inside_world(const RailWorldPoint3& point) const {
        return std::abs(point.x) <= profile_.max_world_abs &&
               std::abs(point.y) <= profile_.max_world_abs &&
               std::abs(point.z) <= profile_.max_world_abs;
    }

    [[nodiscard]] bool mesh_safe(const RailSplineSegment& segment) const {
        const RailBuildResult built = RailMeshBuilder::build(segment, profile_);
        if (!built.ok()) return false;
        return RailMeshBuilder::validate_mesh(built.geometry.ballast, profile_).ok() &&
               RailMeshBuilder::validate_mesh(built.geometry.sleepers, profile_).ok() &&
               RailMeshBuilder::validate_mesh(built.geometry.left_rail, profile_).ok() &&
               RailMeshBuilder::validate_mesh(built.geometry.right_rail, profile_).ok();
    }

    [[nodiscard]] std::optional<RailPlacementAppendResult> commit_single(
        const RailPlacementNodeId from,
        const RailSplineSegment& segment,
        const float exit_heading,
        const RailPlacementEdgeKind kind) {
        if (edges_.size() >= static_cast<std::size_t>(std::numeric_limits<RailPlacementEdgeId>::max())) {
            return std::nullopt;
        }
        const RailPlacementCheckpoint before = checkpoint();
        const auto to = add_root(segment.end, exit_heading);
        if (!to) return std::nullopt;

        const RailPlacementEdgeId edge_id = static_cast<RailPlacementEdgeId>(edges_.size());
        edges_.push_back({edge_id, from, *to, kind, segment});
        if (edge(edge_id) == nullptr) {
            const bool rolled_back = rollback(before);
            (void)rolled_back;
            return std::nullopt;
        }
        return RailPlacementAppendResult{*to, edge_id};
    }

    RailProfile profile_{};
    std::vector<RailPlacementNode> nodes_;
    std::vector<RailPlacementEdge> edges_;
};
