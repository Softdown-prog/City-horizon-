#pragma once

#include "procedural_road_placement_bridge.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <utility>
#include <vector>

// CH_PROCEDURAL_ROAD_2D_RENDER_V1
//
// Canonical visual contract for City Horizon roads. Gameplay/save topology stays
// in RoadManager and its procedural mirror, but the active road presentation is
// generated as flat XY geometry. No Z coordinate, bridge support, viaduct or 3D
// road mesh is admitted into this plan.
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

[[nodiscard]] inline float procedural_road_length_2d(const ProceduralRoad2DPoint point) {
    return std::sqrt(point.x * point.x + point.y * point.y);
}

[[nodiscard]] inline std::optional<ProceduralRoadNodeId> procedural_road_other_node_id(
    const ProceduralRoadGraphSegment& segment,
    const ProceduralRoadNodeId node_id) {
    if (segment.start_node == node_id) return segment.end_node;
    if (segment.end_node == node_id) return segment.start_node;
    return std::nullopt;
}

[[nodiscard]] inline std::optional<ProceduralRoad2DPoint> procedural_road_arm_direction_2d(
    const ProceduralRoadGraph& graph,
    const ProceduralRoadNodeId node_id,
    const ProceduralRoadSegmentId segment_id) {
    const ProceduralRoadNode* node = graph.node(node_id);
    const ProceduralRoadGraphSegment* segment = graph.segment(segment_id);
    if (node == nullptr || segment == nullptr) return std::nullopt;
    const auto other_id = procedural_road_other_node_id(*segment, node_id);
    if (!other_id) return std::nullopt;
    const ProceduralRoadNode* other = graph.node(*other_id);
    if (other == nullptr) return std::nullopt;

    ProceduralRoad2DPoint direction{
        other->position.x - node->position.x,
        other->position.y - node->position.y,
    };
    const float length = procedural_road_length_2d(direction);
    if (length < 0.00001F) return std::nullopt;
    direction.x /= length;
    direction.y /= length;
    return direction;
}

[[nodiscard]] inline bool procedural_road_node_is_straight_continuation(
    const ProceduralRoadGraph& graph,
    const ProceduralRoadNodeId node_id) {
    if (graph.degree(node_id) != 2U) return false;
    const std::vector<ProceduralRoadSegmentId> incident = graph.connected_segments(node_id);
    if (incident.size() != 2U) return false;
    const auto first = procedural_road_arm_direction_2d(graph, node_id, incident[0]);
    const auto second = procedural_road_arm_direction_2d(graph, node_id, incident[1]);
    if (!first || !second) return false;
    const float dot = first->x * second->x + first->y * second->y;
    return dot <= -0.985F;
}

// Returns a visual-only control handle pointing from a degree-2 corner node into
// one of its incident arms. The graph itself stays untouched, so save topology,
// occupancy, navigation and traffic contracts remain deterministic. For a
// corner, the two arm handles become collinear through the node, producing C1
// continuity across the turn instead of a hard tile-center elbow.
[[nodiscard]] inline std::optional<ProceduralRoad2DPoint> procedural_road_visual_corner_handle_2d(
    const ProceduralRoadGraph& graph,
    const ProceduralRoadNodeId node_id,
    const ProceduralRoadSegmentId segment_id) {
    if (graph.degree(node_id) != 2U) return std::nullopt;
    const std::vector<ProceduralRoadSegmentId> incident = graph.connected_segments(node_id);
    if (incident.size() != 2U) return std::nullopt;

    ProceduralRoadSegmentId peer_id = kInvalidProceduralRoadSegmentId;
    if (incident[0] == segment_id) peer_id = incident[1];
    else if (incident[1] == segment_id) peer_id = incident[0];
    else return std::nullopt;

    const ProceduralRoadNode* node = graph.node(node_id);
    const ProceduralRoadGraphSegment* segment = graph.segment(segment_id);
    const ProceduralRoadGraphSegment* peer = graph.segment(peer_id);
    if (node == nullptr || segment == nullptr || peer == nullptr) return std::nullopt;

    const auto segment_other_id = procedural_road_other_node_id(*segment, node_id);
    const auto peer_other_id = procedural_road_other_node_id(*peer, node_id);
    if (!segment_other_id || !peer_other_id) return std::nullopt;
    const ProceduralRoadNode* segment_other = graph.node(*segment_other_id);
    const ProceduralRoadNode* peer_other = graph.node(*peer_other_id);
    if (segment_other == nullptr || peer_other == nullptr) return std::nullopt;

    ProceduralRoad2DPoint segment_arm{
        segment_other->position.x - node->position.x,
        segment_other->position.y - node->position.y,
    };
    ProceduralRoad2DPoint peer_arm{
        peer_other->position.x - node->position.x,
        peer_other->position.y - node->position.y,
    };
    const float segment_length = procedural_road_length_2d(segment_arm);
    const float peer_length = procedural_road_length_2d(peer_arm);
    if (segment_length < 0.00001F || peer_length < 0.00001F) return std::nullopt;

    segment_arm.x /= segment_length;
    segment_arm.y /= segment_length;
    peer_arm.x /= peer_length;
    peer_arm.y /= peer_length;

    const float dot = segment_arm.x * peer_arm.x + segment_arm.y * peer_arm.y;
    if (dot <= -0.985F || dot >= 0.985F) return std::nullopt;

    // The difference of the two unit arm directions is the through-tangent line
    // at the corner. Choosing the sign associated with this arm gives both
    // incident splines the same travel tangent while keeping each control point
    // on its own side of the node.
    ProceduralRoad2DPoint handle_direction{
        segment_arm.x - peer_arm.x,
        segment_arm.y - peer_arm.y,
    };
    const float handle_direction_length = procedural_road_length_2d(handle_direction);
    if (handle_direction_length < 0.00001F) return std::nullopt;
    handle_direction.x /= handle_direction_length;
    handle_direction.y /= handle_direction_length;

    if (handle_direction.x * segment_arm.x + handle_direction.y * segment_arm.y < 0.0F) {
        handle_direction.x = -handle_direction.x;
        handle_direction.y = -handle_direction.y;
    }

    // Slightly less than half one tile spreads a 90-degree turn across both
    // adjacent tiles without overshooting the neighboring node.
    const float handle_length = std::min(segment_length, peer_length) * 0.46F;
    return ProceduralRoad2DPoint{
        handle_direction.x * handle_length,
        handle_direction.y * handle_length,
    };
}

[[nodiscard]] inline std::optional<RoadSplineSegment> procedural_road_visual_spline_2d(
    const ProceduralRoadGraph& graph,
    const ProceduralRoadSegmentId segment_id) {
    auto spline = graph.spline_for(segment_id);
    const ProceduralRoadGraphSegment* segment = graph.segment(segment_id);
    if (!spline || segment == nullptr) return std::nullopt;

    const auto apply_corner_handle = [&](const ProceduralRoadNodeId node_id, const bool at_start) {
        const auto handle = procedural_road_visual_corner_handle_2d(graph, node_id, segment_id);
        const ProceduralRoadNode* node = graph.node(node_id);
        if (!handle || node == nullptr) return;
        RoadWorldPoint3 control{
            node->position.x + handle->x,
            node->position.y + handle->y,
            node->position.z,
        };
        if (at_start) spline->control_a = control;
        else spline->control_b = control;
    };

    apply_corner_handle(segment->start_node, true);
    apply_corner_handle(segment->end_node, false);
    return spline;
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
        float length = procedural_road_length_2d(tangent);
        if (length < 0.00001F) {
            tangent = {segment.end.x - segment.start.x, segment.end.y - segment.start.y};
            length = procedural_road_length_2d(tangent);
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

// Builds an arm-aware pavement polygon instead of the old circular patch. A
// straight degree-2 continuation needs no patch at all; curves, tees and crosses
// get a compact polygon whose boundary follows the actual incident road widths
// and directions. This keeps intersections from looking like round blobs.
[[nodiscard]] inline ProceduralRoad2DMesh build_procedural_road_2d_junction_patch(
    const ProceduralRoadGraph& graph, const ProceduralRoadNodeId node_id) {
    ProceduralRoad2DMesh mesh;
    const ProceduralRoadNode* node = graph.node(node_id);
    const std::size_t degree = graph.degree(node_id);
    if (node == nullptr || degree < 2U) return mesh;
    if (degree == 2U && procedural_road_node_is_straight_continuation(graph, node_id)) return mesh;

    struct BoundaryPoint {
        ProceduralRoad2DPoint position{};
        float angle = 0.0F;
    };
    std::vector<BoundaryPoint> boundary;
    const std::vector<ProceduralRoadSegmentId> incident = graph.connected_segments(node_id);
    boundary.reserve(incident.size() * 2U);

    float uv_radius = 0.5F;
    for (const ProceduralRoadSegmentId segment_id : incident) {
        const ProceduralRoadGraphSegment* segment = graph.segment(segment_id);
        const auto spline = procedural_road_visual_spline_2d(graph, segment_id);
        if (segment == nullptr || !spline) continue;

        ProceduralRoad2DPoint direction{};
        if (segment->start_node == node_id) {
            direction = {
                spline->control_a.x - node->position.x,
                spline->control_a.y - node->position.y,
            };
        } else if (segment->end_node == node_id) {
            direction = {
                spline->control_b.x - node->position.x,
                spline->control_b.y - node->position.y,
            };
        } else {
            continue;
        }

        float length = procedural_road_length_2d(direction);
        if (length < 0.00001F) {
            const auto fallback = procedural_road_arm_direction_2d(graph, node_id, segment_id);
            if (!fallback) continue;
            direction = *fallback;
            length = 1.0F;
        }
        const float tangent_x = direction.x / length;
        const float tangent_y = direction.y / length;
        const float normal_x = -tangent_y;
        const float normal_y = tangent_x;
        const float half_width = std::max(0.01F, segment->width * 0.5F);
        const float reach_multiplier = degree >= 3U ? 0.55F : 0.32F;
        const float reach = std::max(0.12F, segment->width * reach_multiplier);
        uv_radius = std::max(uv_radius, reach + half_width);

        const float center_x = node->position.x + tangent_x * reach;
        const float center_y = node->position.y + tangent_y * reach;
        const ProceduralRoad2DPoint left{
            center_x + normal_x * half_width,
            center_y + normal_y * half_width,
        };
        const ProceduralRoad2DPoint right{
            center_x - normal_x * half_width,
            center_y - normal_y * half_width,
        };
        boundary.push_back({left, std::atan2(left.y - node->position.y, left.x - node->position.x)});
        boundary.push_back({right, std::atan2(right.y - node->position.y, right.x - node->position.x)});
    }

    if (boundary.size() < 3U) return mesh;
    std::sort(boundary.begin(), boundary.end(), [](const BoundaryPoint& left, const BoundaryPoint& right) {
        return left.angle < right.angle;
    });

    mesh.vertices.reserve(boundary.size() + 1U);
    mesh.indices.reserve(boundary.size() * 3U);
    mesh.vertices.push_back({{node->position.x, node->position.y}, 0.5F, 0.5F});
    for (const BoundaryPoint& point : boundary) {
        const float u = 0.5F + (point.position.x - node->position.x) / (2.0F * uv_radius);
        const float v = 0.5F + (point.position.y - node->position.y) / (2.0F * uv_radius);
        mesh.vertices.push_back({point.position, u, v});
    }

    for (std::size_t index = 0; index < boundary.size(); ++index) {
        const std::uint32_t current = static_cast<std::uint32_t>(index + 1U);
        const std::uint32_t next = static_cast<std::uint32_t>(((index + 1U) % boundary.size()) + 1U);
        mesh.indices.insert(mesh.indices.end(), {0U, current, next});
    }
    return mesh;
}

[[nodiscard]] inline ProceduralRoadGroundRenderPlan build_procedural_road_ground_render_plan(
    const ProceduralRoadPlacementBridge& bridge) {
    ProceduralRoadGroundRenderPlan plan;
    const ProceduralRoadGraph& graph = bridge.graph();

    plan.segment_meshes.reserve(graph.segments().size());
    for (const ProceduralRoadGraphSegment& segment : graph.segments()) {
        const auto spline = procedural_road_visual_spline_2d(graph, segment.id);
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
            const auto spline = procedural_road_visual_spline_2d(graph, segment_id);
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
