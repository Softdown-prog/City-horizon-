#pragma once

#include "procedural_road_placement_bridge.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <utility>
#include <vector>

// CH_PROCEDURAL_ROAD_2D_RENDER_V1
//
// Canonical visual contract for City Horizon roads. Gameplay/save topology stays
// in RoadManager and its procedural mirror, but the active road presentation is
// now generated as flat XY geometry. No Z coordinate, bridge support, viaduct or
// 3D road mesh is admitted into this plan.
struct ProceduralRoad2DPoint {
    float x = 0.0F;
    float y = 0.0F;
};

struct ProceduralRoad2DVertex {
    ProceduralRoad2DPoint position{};
    float u = 0.0F;
    float v = 0.0F;
};

struct ProceduralRoad2DMesh {
    std::vector<ProceduralRoad2DVertex> vertices;
    std::vector<std::uint32_t> indices;

    [[nodiscard]] bool empty() const {
        return vertices.empty() || indices.empty();
    }
};

struct ProceduralRoadGroundRenderPlan {
    std::vector<ProceduralRoad2DMesh> segment_meshes;
    std::vector<ProceduralRoad2DMesh> junction_meshes;
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

[[nodiscard]] inline ProceduralRoad2DPoint procedural_road_sample_cubic_2d(
    const RoadSplineSegment& segment, const float t) {
    const float clamped_t = std::clamp(t, 0.0F, 1.0F);
    const float one_minus_t = 1.0F - clamped_t;
    const float b0 = one_minus_t * one_minus_t * one_minus_t;
    const float b1 = 3.0F * one_minus_t * one_minus_t * clamped_t;
    const float b2 = 3.0F * one_minus_t * clamped_t * clamped_t;
    const float b3 = clamped_t * clamped_t * clamped_t;
    return {
        segment.start.x * b0 + segment.control_a.x * b1 + segment.control_b.x * b2 + segment.end.x * b3,
        segment.start.y * b0 + segment.control_a.y * b1 + segment.control_b.y * b2 + segment.end.y * b3,
    };
}

[[nodiscard]] inline ProceduralRoad2DPoint procedural_road_tangent_cubic_2d(
    const RoadSplineSegment& segment, const float t) {
    const float clamped_t = std::clamp(t, 0.0F, 1.0F);
    const float one_minus_t = 1.0F - clamped_t;
    const float a = 3.0F * one_minus_t * one_minus_t;
    const float b = 6.0F * one_minus_t * clamped_t;
    const float c = 3.0F * clamped_t * clamped_t;
    return {
        a * (segment.control_a.x - segment.start.x)
            + b * (segment.control_b.x - segment.control_a.x)
            + c * (segment.end.x - segment.control_b.x),
        a * (segment.control_a.y - segment.start.y)
            + b * (segment.control_b.y - segment.control_a.y)
            + c * (segment.end.y - segment.control_b.y),
    };
}

[[nodiscard]] inline ProceduralRoad2DMesh build_procedural_road_2d_ribbon(
    const RoadSplineSegment& segment) {
    ProceduralRoad2DMesh mesh;
    if (!(segment.width > 0.0F) || !std::isfinite(segment.width)) return mesh;

    const int subdivisions = std::clamp(segment.subdivisions, 2, 256);
    const float repeat_world_units = std::max(0.01F, segment.texture_repeat_world_units);
    mesh.vertices.reserve(static_cast<std::size_t>(subdivisions + 1) * 2U);
    mesh.indices.reserve(static_cast<std::size_t>(subdivisions) * 6U);

    ProceduralRoad2DPoint previous_center = procedural_road_sample_cubic_2d(segment, 0.0F);
    float accumulated_length = 0.0F;

    for (int step = 0; step <= subdivisions; ++step) {
        const float t = static_cast<float>(step) / static_cast<float>(subdivisions);
        const ProceduralRoad2DPoint center = procedural_road_sample_cubic_2d(segment, t);
        if (step > 0) {
            const float dx = center.x - previous_center.x;
            const float dy = center.y - previous_center.y;
            accumulated_length += std::sqrt(dx * dx + dy * dy);
        }
        previous_center = center;

        ProceduralRoad2DPoint tangent = procedural_road_tangent_cubic_2d(segment, t);
        float length = std::sqrt(tangent.x * tangent.x + tangent.y * tangent.y);
        if (length < 0.00001F) {
            tangent = {segment.end.x - segment.start.x, segment.end.y - segment.start.y};
            length = std::sqrt(tangent.x * tangent.x + tangent.y * tangent.y);
        }
        if (length < 0.00001F) {
            tangent = {1.0F, 0.0F};
            length = 1.0F;
        }

        const float normal_x = -tangent.y / length;
        const float normal_y = tangent.x / length;
        const float half_width = segment.width * 0.5F;
        const float v = accumulated_length / repeat_world_units;

        mesh.vertices.push_back({
            {center.x + normal_x * half_width, center.y + normal_y * half_width}, 0.0F, v});
        mesh.vertices.push_back({
            {center.x - normal_x * half_width, center.y - normal_y * half_width}, 1.0F, v});

        if (step == 0) continue;
        const std::uint32_t current_left = static_cast<std::uint32_t>(step * 2);
        const std::uint32_t current_right = current_left + 1U;
        const std::uint32_t previous_left = current_left - 2U;
        const std::uint32_t previous_right = current_right - 2U;
        mesh.indices.insert(mesh.indices.end(), {
            previous_left, previous_right, current_left,
            previous_right, current_right, current_left,
        });
    }

    return mesh;
}

[[nodiscard]] inline ProceduralRoad2DMesh build_procedural_road_2d_junction_patch(
    const ProceduralRoadGraph& graph, const ProceduralRoadNodeId node_id) {
    ProceduralRoad2DMesh mesh;
    const ProceduralRoadNode* node = graph.node(node_id);
    if (node == nullptr || graph.degree(node_id) < 2U) return mesh;

    float radius = 0.0F;
    for (const ProceduralRoadSegmentId segment_id : graph.connected_segments(node_id)) {
        const ProceduralRoadGraphSegment* segment = graph.segment(segment_id);
        if (segment != nullptr) radius = std::max(radius, segment->width * 0.5F);
    }
    if (!(radius > 0.0F)) return mesh;

    // A compact ground-plane fan closes independently generated ribbons without
    // bringing the old 3D junction/mesh pipeline back into the renderer.
    constexpr int kSides = 16;
    constexpr float kTau = 6.2831853071795864769F;
    mesh.vertices.reserve(static_cast<std::size_t>(kSides) + 2U);
    mesh.indices.reserve(static_cast<std::size_t>(kSides) * 3U);
    mesh.vertices.push_back({{node->position.x, node->position.y}, 0.5F, 0.5F});
    for (int side = 0; side <= kSides; ++side) {
        const float angle = kTau * static_cast<float>(side) / static_cast<float>(kSides);
        const float cs = std::cos(angle);
        const float sn = std::sin(angle);
        mesh.vertices.push_back({
            {node->position.x + cs * radius, node->position.y + sn * radius},
            0.5F + 0.5F * cs,
            0.5F + 0.5F * sn,
        });
        if (side > 0) {
            mesh.indices.insert(mesh.indices.end(), {
                0U,
                static_cast<std::uint32_t>(side),
                static_cast<std::uint32_t>(side + 1),
            });
        }
    }
    return mesh;
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
        ProceduralRoad2DMesh mesh = build_procedural_road_2d_ribbon(*spline);
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

        ProceduralRoad2DMesh patch = build_procedural_road_2d_junction_patch(graph, node.id);
        if (!patch.empty()) plan.junction_meshes.push_back(std::move(patch));
    }

    return plan;
}
