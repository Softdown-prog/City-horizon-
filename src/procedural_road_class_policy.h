#pragma once

#include "procedural_road_class.h"
#include "procedural_road_traffic.h"

#include <algorithm>
#include <cmath>

// CH_PROCEDURAL_ROAD_CLASS_V1
//
// Derives conservative unsignalized right-of-way from authored segment classes.
// Explicit traffic signals still have higher authority at runtime, and callers
// may replace any generated policy later with a hand-authored STOP/YIELD policy.
class ProceduralRoadClassPolicyBuilder {
public:
    [[nodiscard]] static bool apply_junction_policy(
        const ProceduralRoadGraph& graph,
        const ProceduralRoadClassCatalog& classes,
        const ProceduralRoadNodeId node_id,
        ProceduralRoadTrafficManager& traffic) {
        if (graph.node(node_id) == nullptr || graph.degree(node_id) < 3U) return false;

        int east_west_rank = -1;
        int north_south_rank = -1;
        for (const ProceduralRoadSegmentId segment_id : graph.connected_segments(node_id)) {
            const ProceduralRoadGraphSegment* segment = graph.segment(segment_id);
            const auto spline = graph.spline_for(segment_id);
            if (segment == nullptr || !spline) continue;

            RoadWorldPoint3 outward{};
            if (segment->start_node == node_id) {
                outward = RoadMeshBuilder::tangent_cubic(*spline, 0.0F);
            } else if (segment->end_node == node_id) {
                outward = RoadMeshBuilder::tangent_cubic(*spline, 1.0F);
                outward.x = -outward.x;
                outward.y = -outward.y;
                outward.z = -outward.z;
            } else {
                continue;
            }

            const ProceduralRoadClass road_class = classes.road_class(graph, segment_id);
            const int rank = procedural_road_class_profile(road_class).priority_rank;
            if (std::fabs(outward.x) >= std::fabs(outward.y)) {
                east_west_rank = std::max(east_west_rank, rank);
            } else {
                north_south_rank = std::max(north_south_rank, rank);
            }
        }

        if (east_west_rank < 0 && north_south_rank < 0) return false;

        ProceduralRoadJunctionPriorityPolicy policy;
        policy.node_id = node_id;
        policy.east_west = ProceduralRoadApproachControl::priority;
        policy.north_south = ProceduralRoadApproachControl::priority;

        if (east_west_rank > north_south_rank) {
            policy.east_west = ProceduralRoadApproachControl::priority;
            policy.north_south = ProceduralRoadApproachControl::yield;
        } else if (north_south_rank > east_west_rank) {
            policy.east_west = ProceduralRoadApproachControl::yield;
            policy.north_south = ProceduralRoadApproachControl::priority;
        }

        return traffic.set_junction_priority_policy(policy);
    }

    [[nodiscard]] static std::size_t apply_all_junction_policies(
        const ProceduralRoadGraph& graph,
        const ProceduralRoadClassCatalog& classes,
        ProceduralRoadTrafficManager& traffic) {
        std::size_t applied = 0U;
        for (const ProceduralRoadNode& node : graph.nodes()) {
            if (apply_junction_policy(graph, classes, node.id, traffic)) ++applied;
        }
        return applied;
    }
};
