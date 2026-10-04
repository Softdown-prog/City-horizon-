#pragma once

#include "rail_placement_graph.h"
#include "track_graph.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <optional>
#include <string>
#include <utility>
#include <vector>

namespace ch::rail {

inline constexpr const char* kRailPlacementTrackGraphAdapterContract =
    "CH_RAIL_PLACEMENT_TRACK_GRAPH_ADAPTER_V2";

struct RailPlacementTopologyBuildResult {
    ch::track::TrackGraph graph{};
    std::vector<ch::track::PieceInstanceId> edge_piece;
    std::vector<std::size_t> edge_route;
    bool valid = false;
    std::string error;
};

namespace detail {

[[nodiscard]] inline RailPlacementPieceId effective_piece_group(const RailPlacementEdge& edge) {
    return edge.piece_group == kInvalidRailPlacementPieceId
        ? static_cast<RailPlacementPieceId>(edge.id)
        : edge.piece_group;
}

[[nodiscard]] inline ch::track::Point3 point3(const RailWorldPoint3& point) {
    return {point.x, point.y, point.z};
}

[[nodiscard]] inline std::optional<ch::track::PortDescriptor> port_from_segment(
    const std::string& id,
    const RailSplineSegment& segment,
    const bool start) {
    RailWorldPoint3 tangent = RailMeshBuilder::tangent_cubic(segment, start ? 0.0F : 1.0F);
    if (start) {
        tangent.x = -tangent.x;
        tangent.y = -tangent.y;
        tangent.z = -tangent.z;
    }
    const double planar = std::hypot(static_cast<double>(tangent.x), static_cast<double>(tangent.y));
    const double length = std::hypot(planar, static_cast<double>(tangent.z));
    if (!std::isfinite(length) || length <= 1.0e-9) return std::nullopt;

    ch::track::PortDescriptor port;
    port.id = id;
    port.position = point3(start ? segment.start : segment.end);
    port.heading_radians = std::atan2(static_cast<double>(tangent.y), static_cast<double>(tangent.x));
    port.pitch_radians = std::atan2(static_cast<double>(tangent.z), planar);
    return port;
}

[[nodiscard]] inline std::vector<ch::track::CenterlinePoint> sample_centerline(
    const RailSplineSegment& segment) {
    const int subdivisions = std::max(2, segment.subdivisions);
    std::vector<ch::track::CenterlinePoint> points;
    points.reserve(static_cast<std::size_t>(subdivisions) + 1U);
    for (int i = 0; i <= subdivisions; ++i) {
        const float t = static_cast<float>(i) / static_cast<float>(subdivisions);
        points.push_back({point3(RailMeshBuilder::sample_cubic(segment, t))});
    }
    return points;
}

[[nodiscard]] inline ch::track::ClearanceEnvelope clearance_from_profile(const RailProfile& profile) {
    ch::track::ClearanceEnvelope envelope;
    envelope.half_width_m = std::max(0.05, static_cast<double>(profile.ballast_width) * 0.5);
    envelope.height_m = std::max(
        0.10,
        static_cast<double>(profile.ballast_height + profile.sleeper_height + profile.rail_height));
    return envelope;
}

[[nodiscard]] inline std::optional<ch::track::PieceDescriptor> single_descriptor(
    const RailPlacementEdge& edge,
    const RailProfile& profile) {
    const auto in = port_from_segment("in", edge.segment, true);
    const auto out = port_from_segment("out", edge.segment, false);
    if (!in || !out) return std::nullopt;

    ch::track::PieceDescriptor descriptor;
    descriptor.id = "rail.piece." + std::to_string(edge.id);
    descriptor.network = ch::track::NetworkKind::railway;
    descriptor.clearance = clearance_from_profile(profile);
    descriptor.ports = {*in, *out};
    descriptor.routes = {{"main", 0U, 1U, true, sample_centerline(edge.segment)}};
    if (!ch::track::valid_descriptor(descriptor)) return std::nullopt;
    return descriptor;
}

[[nodiscard]] inline std::optional<ch::track::PieceDescriptor> turnout_descriptor(
    const RailPlacementEdge& through,
    const RailPlacementEdge& diverging,
    const RailProfile& profile) {
    if (through.from != diverging.from) return std::nullopt;
    const auto entry = port_from_segment("entry", through.segment, true);
    const auto through_out = port_from_segment("through", through.segment, false);
    const auto diverging_out = port_from_segment("diverging", diverging.segment, false);
    if (!entry || !through_out || !diverging_out) return std::nullopt;

    ch::track::PieceDescriptor descriptor;
    descriptor.id = "rail.turnout." + std::to_string(detail::effective_piece_group(through));
    descriptor.network = ch::track::NetworkKind::railway;
    descriptor.flags |= ch::track::flag_mask(ch::track::PieceFlag::switch_piece);
    descriptor.clearance = clearance_from_profile(profile);
    descriptor.ports = {*entry, *through_out, *diverging_out};
    descriptor.routes = {
        {"through", 0U, 1U, true, sample_centerline(through.segment)},
        {"diverging", 0U, 2U, true, sample_centerline(diverging.segment)},
    };
    if (!ch::track::valid_descriptor(descriptor)) return std::nullopt;
    return descriptor;
}

[[nodiscard]] inline std::optional<ch::track::PieceDescriptor> crossing_descriptor(
    const RailPlacementEdge& primary,
    const RailPlacementEdge& secondary,
    const RailProfile& profile) {
    const auto primary_in = port_from_segment("primary_in", primary.segment, true);
    const auto primary_out = port_from_segment("primary_out", primary.segment, false);
    const auto secondary_in = port_from_segment("secondary_in", secondary.segment, true);
    const auto secondary_out = port_from_segment("secondary_out", secondary.segment, false);
    if (!primary_in || !primary_out || !secondary_in || !secondary_out) return std::nullopt;

    ch::track::PieceDescriptor descriptor;
    descriptor.id = "rail.crossing." + std::to_string(detail::effective_piece_group(primary));
    descriptor.network = ch::track::NetworkKind::railway;
    descriptor.flags |= ch::track::flag_mask(ch::track::PieceFlag::crossing);
    descriptor.clearance = clearance_from_profile(profile);
    descriptor.ports = {*primary_in, *primary_out, *secondary_in, *secondary_out};
    descriptor.routes = {
        {"primary", 0U, 1U, true, sample_centerline(primary.segment)},
        {"secondary", 2U, 3U, true, sample_centerline(secondary.segment)},
    };
    if (!ch::track::valid_descriptor(descriptor)) return std::nullopt;
    return descriptor;
}

}  // namespace detail

// Converts only live placement edges into shared modular topology. Tombstoned
// edge slots remain intentionally unmapped so selected-piece demolition can
// preserve stable IDs without leaking deleted routes back into simulation.
[[nodiscard]] inline RailPlacementTopologyBuildResult build_track_graph(
    const RailPlacementGraph& placement) {
    RailPlacementTopologyBuildResult output;
    output.edge_piece.assign(placement.edges().size(), ch::track::kInvalidPieceInstanceId);
    output.edge_route.assign(placement.edges().size(), 0U);

    std::vector<std::vector<ch::track::PortRef>> ports_by_node(placement.nodes().size());
    std::vector<bool> consumed(placement.edges().size(), false);
    for (std::size_t index = 0U; index < placement.edges().size(); ++index) {
        if (!placement.edges()[index].active) consumed[index] = true;
    }

    const auto register_piece = [&](ch::track::PieceDescriptor descriptor,
                                    const std::vector<RailPlacementNodeId>& port_nodes,
                                    const std::vector<std::pair<RailPlacementEdgeId, std::size_t>>& edge_routes)
        -> bool {
        if (descriptor.ports.size() != port_nodes.size()) return false;
        const auto piece_id = output.graph.add_piece(std::move(descriptor));
        if (!piece_id) return false;
        for (std::size_t port = 0U; port < port_nodes.size(); ++port) {
            if (port_nodes[port] >= ports_by_node.size() || !placement.nodes()[port_nodes[port]].active) return false;
            ports_by_node[port_nodes[port]].push_back({*piece_id, port});
        }
        for (const auto& mapping : edge_routes) {
            if (mapping.first >= output.edge_piece.size()) return false;
            output.edge_piece[mapping.first] = *piece_id;
            output.edge_route[mapping.first] = mapping.second;
        }
        return true;
    };

    for (std::size_t edge_index = 0U; edge_index < placement.edges().size(); ++edge_index) {
        if (consumed[edge_index]) continue;
        const RailPlacementEdge& seed = placement.edges()[edge_index];
        if (!seed.active) continue;
        const RailPlacementPieceId group = detail::effective_piece_group(seed);

        std::vector<const RailPlacementEdge*> grouped;
        for (std::size_t candidate = edge_index; candidate < placement.edges().size(); ++candidate) {
            if (consumed[candidate]) continue;
            const RailPlacementEdge& edge = placement.edges()[candidate];
            if (edge.active && detail::effective_piece_group(edge) == group) {
                consumed[candidate] = true;
                grouped.push_back(&edge);
            }
        }

        bool registered = false;
        if (grouped.size() == 1U) {
            const RailPlacementEdge& edge = *grouped.front();
            if (edge.kind != RailPlacementEdgeKind::straight && edge.kind != RailPlacementEdgeKind::curve) {
                output.error = "incomplete grouped rail piece";
                return output;
            }
            const auto descriptor = detail::single_descriptor(edge, placement.profile());
            if (descriptor) {
                registered = register_piece(
                    *descriptor,
                    {edge.from, edge.to},
                    {{edge.id, 0U}});
            }
        } else if (grouped.size() == 2U) {
            const RailPlacementEdge* through = nullptr;
            const RailPlacementEdge* diverging = nullptr;
            const RailPlacementEdge* primary = nullptr;
            const RailPlacementEdge* secondary = nullptr;
            for (const RailPlacementEdge* edge : grouped) {
                if (edge->kind == RailPlacementEdgeKind::turnout_through) through = edge;
                if (edge->kind == RailPlacementEdgeKind::turnout_diverging) diverging = edge;
                if (edge->kind == RailPlacementEdgeKind::crossing_primary) primary = edge;
                if (edge->kind == RailPlacementEdgeKind::crossing_secondary) secondary = edge;
            }

            if (through != nullptr && diverging != nullptr) {
                const auto descriptor = detail::turnout_descriptor(*through, *diverging, placement.profile());
                if (descriptor) {
                    registered = register_piece(
                        *descriptor,
                        {through->from, through->to, diverging->to},
                        {{through->id, 0U}, {diverging->id, 1U}});
                }
            } else if (primary != nullptr && secondary != nullptr) {
                const auto descriptor = detail::crossing_descriptor(*primary, *secondary, placement.profile());
                if (descriptor) {
                    registered = register_piece(
                        *descriptor,
                        {primary->from, primary->to, secondary->from, secondary->to},
                        {{primary->id, 0U}, {secondary->id, 1U}});
                }
            }
        }

        if (!registered) {
            output.error = "failed to translate grouped rail piece";
            return output;
        }
    }

    const double position_tolerance = std::max(
        1.0e-5, static_cast<double>(placement.profile().connection_tolerance));
    constexpr double kDirectionTolerance = 0.035;
    for (const auto& refs : ports_by_node) {
        if (refs.size() <= 1U) continue;
        if (refs.size() != 2U) {
            output.error = "ambiguous rail placement node has more than two external ports";
            return output;
        }
        if (!output.graph.connect(refs[0], refs[1], position_tolerance, kDirectionTolerance)) {
            output.error = "rail placement node failed shared-topology port validation";
            return output;
        }
    }

    for (const RailPlacementEdge& edge : placement.edges()) {
        if (!edge.active) continue;
        if (edge.id >= output.edge_piece.size() || output.edge_piece[edge.id] == ch::track::kInvalidPieceInstanceId) {
            output.error = "active rail placement edge was not mapped to topology";
            return output;
        }
    }

    output.valid = true;
    return output;
}

}  // namespace ch::rail
