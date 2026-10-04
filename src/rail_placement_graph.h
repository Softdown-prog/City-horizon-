#pragma once

#include "rail_path_builder.h"

#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <optional>
#include <vector>

inline constexpr const char* kChRailPlacementGraphContract = "CH_RAIL_PLACEMENT_GRAPH_V3";

using RailPlacementNodeId = std::uint32_t;
using RailPlacementEdgeId = std::uint32_t;
using RailPlacementPieceId = std::uint32_t;
inline constexpr RailPlacementNodeId kInvalidRailPlacementNodeId = std::numeric_limits<RailPlacementNodeId>::max();
inline constexpr RailPlacementEdgeId kInvalidRailPlacementEdgeId = std::numeric_limits<RailPlacementEdgeId>::max();
inline constexpr RailPlacementPieceId kInvalidRailPlacementPieceId = std::numeric_limits<RailPlacementPieceId>::max();

enum class RailPlacementEdgeKind {
    straight,
    curve,
    turnout_through,
    turnout_diverging,
    crossing_primary,
    crossing_secondary,
};

struct RailPlacementNode {
    RailPlacementNodeId id = kInvalidRailPlacementNodeId;
    RailWorldPoint3 position{};
    float heading_radians = 0.0F;
    // V3 keeps vector indices stable. Nodes become inactive when no live edge
    // references them, preventing deleted geometry from leaving invisible snap
    // magnets behind while preserving IDs for save/load and later pieces.
    bool active = true;
};

struct RailPlacementEdge {
    RailPlacementEdgeId id = kInvalidRailPlacementEdgeId;
    RailPlacementNodeId from = kInvalidRailPlacementNodeId;
    RailPlacementNodeId to = kInvalidRailPlacementNodeId;
    RailPlacementEdgeKind kind = RailPlacementEdgeKind::straight;
    RailSplineSegment segment{};
    // Multiple graph edges may belong to one logical track piece. Straight and
    // curve edges own their group; turnout/crossing route edges share a group.
    RailPlacementPieceId piece_group = kInvalidRailPlacementPieceId;
    // Middle-of-network demolition never erases this record. The tombstone
    // preserves every later ID and makes persisted references deterministic.
    bool active = true;
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

struct RailPlacementCrossingResult {
    RailPlacementNodeId primary_node = kInvalidRailPlacementNodeId;
    RailPlacementNodeId secondary_entry_node = kInvalidRailPlacementNodeId;
    RailPlacementNodeId secondary_exit_node = kInvalidRailPlacementNodeId;
    RailPlacementEdgeId primary_edge = kInvalidRailPlacementEdgeId;
    RailPlacementEdgeId secondary_edge = kInvalidRailPlacementEdgeId;

    [[nodiscard]] bool ok() const {
        return primary_node != kInvalidRailPlacementNodeId &&
               secondary_entry_node != kInvalidRailPlacementNodeId &&
               secondary_exit_node != kInvalidRailPlacementNodeId &&
               primary_edge != kInvalidRailPlacementEdgeId &&
               secondary_edge != kInvalidRailPlacementEdgeId;
    }
};

struct RailPlacementCheckpoint {
    std::size_t node_count = 0U;
    std::size_t edge_count = 0U;
};

// CH_RAIL_PLACEMENT_GRAPH_V3
//
// Transactional staging graph for the editor. New geometry remains append-only
// so preview rollback is cheap, while committed middle-of-network demolition
// uses tombstones instead of vector erasure. This gives every node, edge and
// logical piece a stable identity suitable for selection and persistence.
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
        nodes_.push_back({id, position, heading_radians, true});
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
        const RailPlacementPieceId piece_group = static_cast<RailPlacementPieceId>(through_edge);
        edges_.push_back({through_edge, from, *through_node, RailPlacementEdgeKind::turnout_through, authored.through, piece_group, true});
        const RailPlacementEdgeId diverging_edge = static_cast<RailPlacementEdgeId>(edges_.size());
        edges_.push_back({diverging_edge, from, *diverging_node, RailPlacementEdgeKind::turnout_diverging, authored.diverging, piece_group, true});
        return RailPlacementTurnoutResult{*through_node, *diverging_node, through_edge, diverging_edge};
    }

    // At-grade diamond crossing. The primary route continues from `from`; the
    // perpendicular route is authored as a second route in the same logical
    // piece and exposes both side nodes for later extension.
    [[nodiscard]] std::optional<RailPlacementCrossingResult> append_crossing(
        const RailPlacementNodeId from,
        const float length,
        const int subdivisions = 32) {
        constexpr float kHalfPi = 1.57079632679489661923F;
        constexpr float kPi = 3.14159265358979323846F;

        const RailPlacementNode* source = node(from);
        if (source == nullptr || !std::isfinite(length) || length <= 0.0F) return std::nullopt;
        const RailPathBuildResult primary = RailPathBuilder::straight(
            source->position, source->heading_radians, length, subdivisions, profile_);
        if (!primary.ok() || !mesh_safe(primary.segment)) return std::nullopt;

        const RailWorldPoint3 center = RailMeshBuilder::sample_cubic(primary.segment, 0.5F);
        const float secondary_heading = source->heading_radians + kHalfPi;
        const float sx = std::cos(secondary_heading);
        const float sy = std::sin(secondary_heading);
        const RailWorldPoint3 secondary_start{
            center.x - sx * (length * 0.5F),
            center.y - sy * (length * 0.5F),
            center.z,
        };
        const RailPathBuildResult secondary = RailPathBuilder::straight(
            secondary_start, secondary_heading, length, subdivisions, profile_);
        if (!secondary.ok() || !mesh_safe(secondary.segment)) return std::nullopt;

        if (nodes_.size() > static_cast<std::size_t>(std::numeric_limits<RailPlacementNodeId>::max()) - 3U ||
            edges_.size() > static_cast<std::size_t>(std::numeric_limits<RailPlacementEdgeId>::max()) - 2U) {
            return std::nullopt;
        }

        const RailPlacementCheckpoint before = checkpoint();
        const auto primary_node = add_root(primary.segment.end, source->heading_radians);
        const auto secondary_entry_node = add_root(secondary.segment.start, secondary_heading + kPi);
        const auto secondary_exit_node = add_root(secondary.segment.end, secondary_heading);
        if (!primary_node || !secondary_entry_node || !secondary_exit_node) {
            const bool rolled_back = rollback(before);
            (void)rolled_back;
            return std::nullopt;
        }

        const RailPlacementEdgeId primary_edge = static_cast<RailPlacementEdgeId>(edges_.size());
        const RailPlacementPieceId piece_group = static_cast<RailPlacementPieceId>(primary_edge);
        edges_.push_back({primary_edge, from, *primary_node, RailPlacementEdgeKind::crossing_primary, primary.segment, piece_group, true});
        const RailPlacementEdgeId secondary_edge = static_cast<RailPlacementEdgeId>(edges_.size());
        edges_.push_back({secondary_edge, *secondary_entry_node, *secondary_exit_node, RailPlacementEdgeKind::crossing_secondary, secondary.segment, piece_group, true});

        return RailPlacementCrossingResult{
            *primary_node,
            *secondary_entry_node,
            *secondary_exit_node,
            primary_edge,
            secondary_edge,
        };
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
        recompute_node_activity();
        return true;
    }

    // Stable committed-piece removal. Every route in the logical group is
    // toggled together; no IDs after the piece move.
    [[nodiscard]] std::size_t remove_piece(const RailPlacementPieceId piece_group) {
        if (piece_group == kInvalidRailPlacementPieceId) return 0U;
        std::size_t changed = 0U;
        for (RailPlacementEdge& edge_value : edges_) {
            if (edge_value.active && edge_value.piece_group == piece_group) {
                edge_value.active = false;
                ++changed;
            }
        }
        if (changed != 0U) recompute_node_activity();
        return changed;
    }

    [[nodiscard]] bool set_piece_active(const RailPlacementPieceId piece_group, const bool active) {
        if (piece_group == kInvalidRailPlacementPieceId) return false;
        bool found = false;
        for (RailPlacementEdge& edge_value : edges_) {
            if (edge_value.piece_group == piece_group) {
                edge_value.active = active;
                found = true;
            }
        }
        if (found) recompute_node_activity();
        return found;
    }

    [[nodiscard]] bool piece_active(const RailPlacementPieceId piece_group) const {
        for (const RailPlacementEdge& edge_value : edges_) {
            if (edge_value.piece_group == piece_group && edge_value.active) return true;
        }
        return false;
    }

    // Save/load boundary. The snapshot is fully validated in temporary storage
    // before replacing live graph state; node activity is derived from live
    // edges so malformed saves cannot resurrect invisible snap points.
    [[nodiscard]] bool restore_snapshot(std::vector<RailPlacementNode> nodes,
                                        std::vector<RailPlacementEdge> edges) {
        if (nodes.size() >= static_cast<std::size_t>(std::numeric_limits<RailPlacementNodeId>::max()) ||
            edges.size() >= static_cast<std::size_t>(std::numeric_limits<RailPlacementEdgeId>::max())) {
            return false;
        }
        for (std::size_t index = 0U; index < nodes.size(); ++index) {
            RailPlacementNode& node_value = nodes[index];
            if (node_value.id != static_cast<RailPlacementNodeId>(index) ||
                !finite_point(node_value.position) || !inside_world(node_value.position) ||
                !std::isfinite(node_value.heading_radians)) {
                return false;
            }
            node_value.active = false;
        }
        for (std::size_t index = 0U; index < edges.size(); ++index) {
            const RailPlacementEdge& edge_value = edges[index];
            if (edge_value.id != static_cast<RailPlacementEdgeId>(index) ||
                edge_value.from >= nodes.size() || edge_value.to >= nodes.size() ||
                edge_value.piece_group == kInvalidRailPlacementPieceId ||
                edge_value.piece_group >= edges.size() || !valid_kind(edge_value.kind) ||
                !mesh_safe(edge_value.segment)) {
                return false;
            }
        }

        nodes_ = std::move(nodes);
        edges_ = std::move(edges);
        recompute_node_activity();
        return true;
    }

    void clear() {
        edges_.clear();
        nodes_.clear();
    }

    [[nodiscard]] const RailPlacementNode* node(const RailPlacementNodeId id) const {
        if (id >= nodes_.size() || !nodes_[id].active) return nullptr;
        return &nodes_[id];
    }

    [[nodiscard]] const RailPlacementEdge* edge(const RailPlacementEdgeId id) const {
        if (id >= edges_.size() || !edges_[id].active) return nullptr;
        return &edges_[id];
    }

    [[nodiscard]] const std::vector<RailPlacementNode>& nodes() const { return nodes_; }
    [[nodiscard]] const std::vector<RailPlacementEdge>& edges() const { return edges_; }
    [[nodiscard]] const RailProfile& profile() const { return profile_; }

private:
    [[nodiscard]] static bool finite_point(const RailWorldPoint3& point) {
        return std::isfinite(point.x) && std::isfinite(point.y) && std::isfinite(point.z);
    }

    [[nodiscard]] static bool valid_kind(const RailPlacementEdgeKind kind) {
        switch (kind) {
            case RailPlacementEdgeKind::straight:
            case RailPlacementEdgeKind::curve:
            case RailPlacementEdgeKind::turnout_through:
            case RailPlacementEdgeKind::turnout_diverging:
            case RailPlacementEdgeKind::crossing_primary:
            case RailPlacementEdgeKind::crossing_secondary:
                return true;
        }
        return false;
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

    void recompute_node_activity() {
        for (RailPlacementNode& node_value : nodes_) node_value.active = false;
        for (const RailPlacementEdge& edge_value : edges_) {
            if (!edge_value.active) continue;
            if (edge_value.from < nodes_.size()) nodes_[edge_value.from].active = true;
            if (edge_value.to < nodes_.size()) nodes_[edge_value.to].active = true;
        }
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
        const RailPlacementPieceId piece_group = static_cast<RailPlacementPieceId>(edge_id);
        edges_.push_back({edge_id, from, *to, kind, segment, piece_group, true});
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
