#pragma once

#include "procedural_road_class.h"
#include "procedural_road_lane_connector.h"

#include <algorithm>
#include <cstddef>
#include <optional>
#include <vector>

// CH_PROCEDURAL_ROAD_ROUTE_V1
//
// Produces one continuous right-hand traffic path across a ProceduralRoadRoute.
// Each road segment contributes lane samples and every intermediate graph node
// contributes a lane connector. The output is therefore directly consumable by
// a future vehicle follower without tile-to-tile snapping at junctions.
enum class ProceduralRoadRoutePointKind {
    lane,
    junction_connector,
};

struct ProceduralRoadRoutePoint {
    RoadWorldPoint3 position{};
    ProceduralRoadRoutePointKind kind = ProceduralRoadRoutePointKind::lane;
    ProceduralRoadSegmentId segment_id = kInvalidProceduralRoadSegmentId;
    ProceduralRoadNodeId junction_node = kInvalidProceduralRoadNodeId;
    ProceduralRoadTurnKind turn = ProceduralRoadTurnKind::straight;
    ProceduralRoadClass road_class = ProceduralRoadClass::unspecified;
};

class ProceduralRoadRouteSampler {
public:
    [[nodiscard]] static std::optional<std::vector<ProceduralRoadRoutePoint>> sample_right_hand_route(
        const ProceduralRoadGraph& graph,
        const ProceduralRoadRoute& route,
        const float lane_offset,
        const int samples_per_segment = 24,
        const int samples_per_connector = 12) {
        if (!(lane_offset >= 0.0F) || route.nodes.empty()) return std::nullopt;
        if (route.nodes.size() == 1U) {
            if (graph.node(route.nodes.front()) == nullptr || !route.segments.empty()) return std::nullopt;
            return std::vector<ProceduralRoadRoutePoint>{};
        }
        if (route.segments.size() + 1U != route.nodes.size()) return std::nullopt;

        const int lane_samples = std::clamp(samples_per_segment, 2, 256);
        const int connector_samples = std::clamp(samples_per_connector, 2, 128);
        std::vector<ProceduralRoadRoutePoint> result;

        for (std::size_t index = 0; index < route.segments.size(); ++index) {
            ProceduralRoadRoute one_segment_route;
            one_segment_route.nodes = {route.nodes[index], route.nodes[index + 1U]};
            one_segment_route.segments = {route.segments[index]};
            const auto lane = ProceduralRoadNavigator::sample_right_hand_lane(
                graph, one_segment_route, lane_offset, lane_samples);
            if (lane.empty()) return std::nullopt;

            if (index > 0U) {
                const ProceduralRoadNodeId junction = route.nodes[index];
                const auto connector = ProceduralRoadLaneConnectorBuilder::build(
                    graph, junction, route.segments[index - 1U], route.segments[index], lane_offset);
                if (!connector) return std::nullopt;
                const auto connector_points = ProceduralRoadLaneConnectorBuilder::sample(*connector, connector_samples);
                if (connector_points.size() < 2U) return std::nullopt;

                // The previous lane endpoint equals connector_points.front().
                // Skip it to avoid a zero-length duplicate in vehicle distance
                // accumulation while keeping the connector tangent continuous.
                for (std::size_t connector_index = 1U; connector_index < connector_points.size(); ++connector_index) {
                    result.push_back({
                        connector_points[connector_index].position,
                        ProceduralRoadRoutePointKind::junction_connector,
                        kInvalidProceduralRoadSegmentId,
                        junction,
                        connector->turn,
                    });
                }
            }

            // For every segment after the first, connector.back() equals the
            // lane start. Skip that lane start so each world point is emitted
            // once while preserving the exact lane-to-connector handoff.
            const std::size_t first_lane_index = index == 0U ? 0U : 1U;
            for (std::size_t lane_index = first_lane_index; lane_index < lane.size(); ++lane_index) {
                result.push_back({
                    lane[lane_index].position,
                    ProceduralRoadRoutePointKind::lane,
                    route.segments[index],
                    kInvalidProceduralRoadNodeId,
                    ProceduralRoadTurnKind::straight,
                });
            }
        }

        return result;
    }
};
