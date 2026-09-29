#pragma once

#include "road_system.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <deque>
#include <optional>
#include <unordered_map>
#include <vector>

// CH_PROCEDURAL_ROAD_NAV_V1
//
// Continuous navigation contract for elastic roads. This layer is intentionally
// parallel to CH_ROAD_TRAFFIC_V1 while tile traffic remains the runtime fallback.
// Topology comes only from ProceduralRoadGraph nodes/segments; geometric XY
// crossings do not connect unless they share a node, which preserves overpasses.
struct ProceduralRoadLanePoint {
    RoadWorldPoint3 position{};
    ProceduralRoadSegmentId segment_id = kInvalidProceduralRoadSegmentId;
    float segment_t = 0.0F;
};

struct ProceduralRoadRoute {
    std::vector<ProceduralRoadNodeId> nodes;
    std::vector<ProceduralRoadSegmentId> segments;

    [[nodiscard]] bool empty() const { return nodes.empty(); }
};

class ProceduralRoadNavigator {
public:
    [[nodiscard]] static std::optional<ProceduralRoadRoute> find_route(
        const ProceduralRoadGraph& graph,
        const ProceduralRoadNodeId start,
        const ProceduralRoadNodeId goal) {
        if (graph.node(start) == nullptr || graph.node(goal) == nullptr) return std::nullopt;
        if (start == goal) return ProceduralRoadRoute{{start}, {}};

        struct Previous {
            ProceduralRoadNodeId node = kInvalidProceduralRoadNodeId;
            ProceduralRoadSegmentId segment = kInvalidProceduralRoadSegmentId;
        };

        std::deque<ProceduralRoadNodeId> open;
        std::unordered_map<ProceduralRoadNodeId, Previous> previous;
        previous.emplace(start, Previous{});
        open.push_back(start);

        while (!open.empty()) {
            const ProceduralRoadNodeId current = open.front();
            open.pop_front();
            for (const ProceduralRoadSegmentId segment_id : graph.connected_segments(current)) {
                const ProceduralRoadGraphSegment* segment = graph.segment(segment_id);
                if (segment == nullptr) continue;
                const ProceduralRoadNodeId next = segment->start_node == current
                    ? segment->end_node : segment->start_node;
                if (previous.contains(next)) continue;
                previous.emplace(next, Previous{current, segment_id});
                if (next == goal) {
                    open.clear();
                    break;
                }
                open.push_back(next);
            }
        }

        if (!previous.contains(goal)) return std::nullopt;

        ProceduralRoadRoute route;
        ProceduralRoadNodeId cursor = goal;
        route.nodes.push_back(cursor);
        while (cursor != start) {
            const Previous step = previous.at(cursor);
            route.segments.push_back(step.segment);
            cursor = step.node;
            route.nodes.push_back(cursor);
        }
        std::reverse(route.nodes.begin(), route.nodes.end());
        std::reverse(route.segments.begin(), route.segments.end());
        return route;
    }

    [[nodiscard]] static std::vector<ProceduralRoadLanePoint> sample_right_hand_lane(
        const ProceduralRoadGraph& graph,
        const ProceduralRoadRoute& route,
        const float lane_offset,
        const int samples_per_segment = 24) {
        std::vector<ProceduralRoadLanePoint> result;
        if (route.nodes.size() < 2U || route.segments.size() + 1U != route.nodes.size()) return result;

        const int samples = std::clamp(samples_per_segment, 2, 256);
        for (std::size_t route_index = 0; route_index < route.segments.size(); ++route_index) {
            const ProceduralRoadSegmentId segment_id = route.segments[route_index];
            const ProceduralRoadGraphSegment* graph_segment = graph.segment(segment_id);
            const auto spline_optional = graph.spline_for(segment_id);
            if (graph_segment == nullptr || !spline_optional) return {};

            const bool forward = graph_segment->start_node == route.nodes[route_index] &&
                                 graph_segment->end_node == route.nodes[route_index + 1U];
            const bool reverse = graph_segment->end_node == route.nodes[route_index] &&
                                 graph_segment->start_node == route.nodes[route_index + 1U];
            if (!forward && !reverse) return {};

            const RoadSplineSegment& spline = *spline_optional;
            for (int sample_index = 0; sample_index <= samples; ++sample_index) {
                if (route_index > 0U && sample_index == 0) continue;
                const float route_t = static_cast<float>(sample_index) / static_cast<float>(samples);
                const float spline_t = forward ? route_t : (1.0F - route_t);
                RoadWorldPoint3 center = RoadMeshBuilder::sample_cubic(spline, spline_t);
                RoadWorldPoint3 tangent = RoadMeshBuilder::tangent_cubic(spline, spline_t);
                if (!forward) {
                    tangent.x = -tangent.x;
                    tangent.y = -tangent.y;
                    tangent.z = -tangent.z;
                }

                float planar_length = std::sqrt(tangent.x * tangent.x + tangent.y * tangent.y);
                if (planar_length < 0.00001F) planar_length = 1.0F;
                const float right_x = tangent.y / planar_length;
                const float right_y = -tangent.x / planar_length;
                center.x += right_x * lane_offset;
                center.y += right_y * lane_offset;
                result.push_back({center, segment_id, spline_t});
            }
        }
        return result;
    }
};
