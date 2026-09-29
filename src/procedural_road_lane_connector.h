#pragma once

#include "procedural_road_navigation.h"

#include <algorithm>
#include <cmath>
#include <optional>
#include <vector>

// CH_PROCEDURAL_ROAD_JUNCTION_LANES_V1
//
// Continuous in-junction lane connectors for elastic roads. This stays parallel
// to CH_ROAD_TRAFFIC_V1 until the procedural traffic migration is approved.
// A connector is created only between two segments that share an explicit graph
// node, so an overpass crossing in XY never becomes a traffic junction.
enum class ProceduralRoadTurnKind {
    straight,
    right,
    left,
    u_turn,
};

struct ProceduralRoadLaneConnector {
    ProceduralRoadNodeId node_id = kInvalidProceduralRoadNodeId;
    ProceduralRoadSegmentId incoming_segment = kInvalidProceduralRoadSegmentId;
    ProceduralRoadSegmentId outgoing_segment = kInvalidProceduralRoadSegmentId;
    ProceduralRoadTurnKind turn = ProceduralRoadTurnKind::straight;
    RoadSplineSegment spline{};
};

class ProceduralRoadLaneConnectorBuilder {
public:
    [[nodiscard]] static std::optional<ProceduralRoadLaneConnector> build(
        const ProceduralRoadGraph& graph,
        const ProceduralRoadNodeId node_id,
        const ProceduralRoadSegmentId incoming_segment,
        const ProceduralRoadSegmentId outgoing_segment,
        const float lane_offset,
        const float connector_reach = 0.55F) {
        if (incoming_segment == outgoing_segment || !(lane_offset >= 0.0F) || !(connector_reach > 0.0F)) {
            return std::nullopt;
        }
        const ProceduralRoadNode* node = graph.node(node_id);
        const ProceduralRoadGraphSegment* incoming = graph.segment(incoming_segment);
        const ProceduralRoadGraphSegment* outgoing = graph.segment(outgoing_segment);
        const auto incoming_spline = graph.spline_for(incoming_segment);
        const auto outgoing_spline = graph.spline_for(outgoing_segment);
        if (node == nullptr || incoming == nullptr || outgoing == nullptr || !incoming_spline || !outgoing_spline) {
            return std::nullopt;
        }
        if (!touches_node(*incoming, node_id) || !touches_node(*outgoing, node_id)) return std::nullopt;

        const bool incoming_forward = incoming->end_node == node_id;
        const bool outgoing_forward = outgoing->start_node == node_id;

        const RoadWorldPoint3 incoming_center = RoadMeshBuilder::sample_cubic(*incoming_spline, incoming_forward ? 1.0F : 0.0F);
        const RoadWorldPoint3 outgoing_center = RoadMeshBuilder::sample_cubic(*outgoing_spline, outgoing_forward ? 0.0F : 1.0F);
        RoadWorldPoint3 incoming_direction = RoadMeshBuilder::tangent_cubic(*incoming_spline, incoming_forward ? 1.0F : 0.0F);
        RoadWorldPoint3 outgoing_direction = RoadMeshBuilder::tangent_cubic(*outgoing_spline, outgoing_forward ? 0.0F : 1.0F);
        if (!incoming_forward) incoming_direction = negate(incoming_direction);
        if (!outgoing_forward) outgoing_direction = negate(outgoing_direction);
        incoming_direction = normalize_planar(incoming_direction);
        outgoing_direction = normalize_planar(outgoing_direction);

        RoadWorldPoint3 start = offset_right(incoming_center, incoming_direction, lane_offset);
        RoadWorldPoint3 end = offset_right(outgoing_center, outgoing_direction, lane_offset);
        start.z = node->position.z;
        end.z = node->position.z;

        RoadSplineSegment connector;
        connector.start = start;
        connector.end = end;
        connector.control_a = add(start, scale(incoming_direction, connector_reach));
        connector.control_b = add(end, scale(outgoing_direction, -connector_reach));
        connector.control_a.z = node->position.z;
        connector.control_b.z = node->position.z;
        connector.width = std::max(0.08F, std::min(incoming->width, outgoing->width) * 0.42F);
        connector.texture_repeat_world_units = 1.0F;
        connector.subdivisions = 12;

        return ProceduralRoadLaneConnector{
            node_id,
            incoming_segment,
            outgoing_segment,
            classify_turn(incoming_direction, outgoing_direction),
            connector,
        };
    }

    [[nodiscard]] static std::vector<ProceduralRoadLanePoint> sample(
        const ProceduralRoadLaneConnector& connector,
        const int samples = 12) {
        const int count = std::clamp(samples, 2, 128);
        std::vector<ProceduralRoadLanePoint> points;
        points.reserve(static_cast<std::size_t>(count + 1));
        for (int index = 0; index <= count; ++index) {
            const float t = static_cast<float>(index) / static_cast<float>(count);
            points.push_back({RoadMeshBuilder::sample_cubic(connector.spline, t),
                              kInvalidProceduralRoadSegmentId, t});
        }
        return points;
    }

    [[nodiscard]] static ProceduralRoadTurnKind classify_turn(
        const RoadWorldPoint3 incoming_direction,
        const RoadWorldPoint3 outgoing_direction) {
        const RoadWorldPoint3 in = normalize_planar(incoming_direction);
        const RoadWorldPoint3 out = normalize_planar(outgoing_direction);
        const float dot = in.x * out.x + in.y * out.y;
        const float cross = in.x * out.y - in.y * out.x;
        if (dot < -0.70F) return ProceduralRoadTurnKind::u_turn;
        if (std::fabs(cross) < 0.25F && dot > 0.70F) return ProceduralRoadTurnKind::straight;
        // City Horizon world Y grows southward, so positive screen-planar cross
        // for the canonical XY basis corresponds to a right-hand turn here.
        return cross > 0.0F ? ProceduralRoadTurnKind::right : ProceduralRoadTurnKind::left;
    }

private:
    [[nodiscard]] static bool touches_node(const ProceduralRoadGraphSegment& segment,
                                           const ProceduralRoadNodeId node_id) {
        return segment.start_node == node_id || segment.end_node == node_id;
    }

    [[nodiscard]] static RoadWorldPoint3 negate(const RoadWorldPoint3 value) {
        return {-value.x, -value.y, -value.z};
    }

    [[nodiscard]] static RoadWorldPoint3 normalize_planar(RoadWorldPoint3 value) {
        const float length = std::sqrt(value.x * value.x + value.y * value.y);
        if (length < 0.00001F) return {1.0F, 0.0F, 0.0F};
        value.x /= length;
        value.y /= length;
        value.z = 0.0F;
        return value;
    }

    [[nodiscard]] static RoadWorldPoint3 offset_right(const RoadWorldPoint3 point,
                                                      const RoadWorldPoint3 direction,
                                                      const float distance) {
        return {point.x + direction.y * distance,
                point.y - direction.x * distance,
                point.z};
    }

    [[nodiscard]] static RoadWorldPoint3 add(const RoadWorldPoint3 a, const RoadWorldPoint3 b) {
        return {a.x + b.x, a.y + b.y, a.z + b.z};
    }

    [[nodiscard]] static RoadWorldPoint3 scale(const RoadWorldPoint3 value, const float scalar) {
        return {value.x * scalar, value.y * scalar, value.z * scalar};
    }
};
