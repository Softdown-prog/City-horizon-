#pragma once

#include "procedural_road_junction.h"
#include "procedural_road_placement_bridge.h"

#include <cmath>
#include <cstddef>
#include <utility>
#include <vector>

// CH_PROCEDURAL_ROAD_GROUND_RENDER_V1
//
// Safe first integration gate for procedural roads in MapForge/runtime views.
// Only geometry that is entirely on the ground plane is admitted. Elevated
// spans, ramps and mixed-height junctions stay out of the render plan so the
// project can prove elastic roads without coupling the first renderer rollout
// to bridge/viaduct occlusion and support rules.
struct ProceduralRoadGroundRenderPlan {
    std::vector<RoadMesh> segment_meshes;
    std::vector<RoadMesh> junction_meshes;
    std::size_t skipped_elevated_segments = 0U;
    std::size_t skipped_mixed_junctions = 0U;

    [[nodiscard]] bool empty() const {
        return segment_meshes.empty() && junction_meshes.empty();
    }
};

[[nodiscard]] inline bool procedural_road_spline_is_ground_only(
    const RoadSplineSegment& spline,
    const float epsilon = 0.0001F) {
    const auto on_ground = [epsilon](const RoadWorldPoint3 point) {
        return std::isfinite(point.z) && std::abs(point.z) <= epsilon;
    };
    return on_ground(spline.start)
        && on_ground(spline.control_a)
        && on_ground(spline.control_b)
        && on_ground(spline.end);
}

[[nodiscard]] inline ProceduralRoadGroundRenderPlan build_procedural_road_ground_render_plan(
    const ProceduralRoadPlacementBridge& bridge) {
    ProceduralRoadGroundRenderPlan plan;
    const ProceduralRoadGraph& graph = bridge.graph();

    plan.segment_meshes.reserve(graph.segments().size());
    for (const ProceduralRoadGraphSegment& segment : graph.segments()) {
        const auto spline = graph.spline_for(segment.id);
        if (!spline || !procedural_road_spline_is_ground_only(*spline)) {
            ++plan.skipped_elevated_segments;
            continue;
        }
        RoadMesh mesh = RoadMeshBuilder::build_cubic(*spline);
        if (!mesh.empty()) plan.segment_meshes.push_back(std::move(mesh));
    }

    for (const ProceduralRoadNode& node : graph.nodes()) {
        if (!std::isfinite(node.position.z) || std::abs(node.position.z) > 0.0001F || graph.degree(node.id) < 2U) {
            continue;
        }

        bool all_incident_ground = true;
        for (const ProceduralRoadSegmentId segment_id : graph.connected_segments(node.id)) {
            const auto spline = graph.spline_for(segment_id);
            if (!spline || !procedural_road_spline_is_ground_only(*spline)) {
                all_incident_ground = false;
                break;
            }
        }
        if (!all_incident_ground) {
            ++plan.skipped_mixed_junctions;
            continue;
        }

        RoadMesh patch = RoadJunctionBuilder::build_patch(graph, node.id);
        if (!patch.empty()) plan.junction_meshes.push_back(std::move(patch));
    }

    return plan;
}
