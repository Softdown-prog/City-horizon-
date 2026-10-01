#pragma once

#include "src/ch_core/projection.h"
#include "src/ch_render/procedural_road_network_renderer.h"
#include "src/procedural_road_ground_render_plan.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <utility>

// CH_PROCEDURAL_ROAD_2D_CULLING_V1
//
// Runtime-only visibility layer. It trims the camera-visible working set before
// ribbons/junctions are tessellated, while RoadManager and its procedural mirror
// remain the authoritative full-city topology.
struct ProceduralRoad2DWorldBounds {
    float min_x = 0.0F;
    float min_y = 0.0F;
    float max_x = 0.0F;
    float max_y = 0.0F;

    [[nodiscard]] bool valid() const noexcept {
        return std::isfinite(min_x) && std::isfinite(min_y) &&
               std::isfinite(max_x) && std::isfinite(max_y) &&
               min_x <= max_x && min_y <= max_y;
    }

    [[nodiscard]] bool contains(const ProceduralRoad2DPoint point,
                                const float padding = 0.0F) const noexcept {
        if (!valid()) return false;
        return point.x >= min_x - padding && point.x <= max_x + padding &&
               point.y >= min_y - padding && point.y <= max_y + padding;
    }
};

struct ProceduralRoadVisibleGroundRenderPlan {
    ProceduralRoadGroundRenderPlan plan;
    std::size_t considered_segments = 0U;
    std::size_t culled_segments = 0U;
    std::size_t considered_junctions = 0U;
    std::size_t culled_junctions = 0U;
};

[[nodiscard]] inline ProceduralRoad2DWorldBounds procedural_road_visible_world_bounds(
    const ch::CameraState& camera,
    const float viewport_width,
    const float viewport_height,
    const float padding_world = 2.0F) {
    if (viewport_width <= 0.0F || viewport_height <= 0.0F || camera.zoom <= 0.0F) return {};

    const ch::WorldPoint corners[4] = {
        ch::screen_to_world_point(0.0F, 0.0F, camera, viewport_width, viewport_height),
        ch::screen_to_world_point(viewport_width, 0.0F, camera, viewport_width, viewport_height),
        ch::screen_to_world_point(0.0F, viewport_height, camera, viewport_width, viewport_height),
        ch::screen_to_world_point(viewport_width, viewport_height, camera, viewport_width, viewport_height),
    };

    float min_x = corners[0].x;
    float max_x = corners[0].x;
    float min_y = corners[0].y;
    float max_y = corners[0].y;
    for (const ch::WorldPoint corner : corners) {
        min_x = std::min(min_x, corner.x);
        max_x = std::max(max_x, corner.x);
        min_y = std::min(min_y, corner.y);
        max_y = std::max(max_y, corner.y);
    }

    const float padding = std::max(0.0F, padding_world);
    return {min_x - padding, min_y - padding, max_x + padding, max_y + padding};
}

[[nodiscard]] inline bool procedural_road_spline_intersects_world_bounds(
    const RoadSplineSegment& spline,
    const ProceduralRoad2DWorldBounds& bounds,
    const float padding = 0.20F) noexcept {
    if (!bounds.valid()) return true;
    const float extent = std::max(0.0F, spline.width * 0.5F) + std::max(0.0F, padding);
    const float min_x = std::min(std::min(spline.start.x, spline.control_a.x),
                                 std::min(spline.control_b.x, spline.end.x)) - extent;
    const float max_x = std::max(std::max(spline.start.x, spline.control_a.x),
                                 std::max(spline.control_b.x, spline.end.x)) + extent;
    const float min_y = std::min(std::min(spline.start.y, spline.control_a.y),
                                 std::min(spline.control_b.y, spline.end.y)) - extent;
    const float max_y = std::max(std::max(spline.start.y, spline.control_a.y),
                                 std::max(spline.control_b.y, spline.end.y)) + extent;
    return max_x >= bounds.min_x && min_x <= bounds.max_x &&
           max_y >= bounds.min_y && min_y <= bounds.max_y;
}

[[nodiscard]] inline ProceduralRoadVisibleGroundRenderPlan
build_visible_procedural_road_ground_render_plan(
    const ProceduralRoadPlacementBridge& bridge,
    const ProceduralRoad2DWorldBounds& bounds) {
    ProceduralRoadVisibleGroundRenderPlan visible;
    const ProceduralRoadGraph& graph = bridge.graph();

    visible.plan.segment_meshes.reserve(graph.segments().size());
    for (const ProceduralRoadGraphSegment& segment : graph.segments()) {
        const auto spline = procedural_road_visual_spline_2d(graph, segment.id);
        if (!spline) {
            ++visible.plan.skipped_elevated_segments;
            continue;
        }
        if (!procedural_road_spline_intersects_world_bounds(*spline, bounds)) {
            ++visible.culled_segments;
            continue;
        }
        ++visible.considered_segments;
        if (!procedural_road_spline_is_ground_only(*spline)) {
            ++visible.plan.skipped_elevated_segments;
            continue;
        }
        ProceduralRoad2DMesh mesh = build_procedural_road_2d_ribbon(*spline);
        if (!mesh.empty()) visible.plan.segment_meshes.push_back(std::move(mesh));
    }

    for (const ProceduralRoadNode& node : graph.nodes()) {
        const std::size_t degree = graph.degree(node.id);
        if (degree < 2U) continue;
        if (!bounds.contains({node.position.x, node.position.y}, 1.25F)) {
            ++visible.culled_junctions;
            continue;
        }
        ++visible.considered_junctions;
        if (!std::isfinite(node.position.z) || std::abs(node.position.z) > 0.0001F) {
            ++visible.plan.skipped_mixed_junctions;
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
            ++visible.plan.skipped_mixed_junctions;
            continue;
        }

        ProceduralRoad2DMesh patch = build_procedural_road_2d_junction_patch(graph, node.id);
        if (!patch.empty()) visible.plan.junction_meshes.push_back(std::move(patch));
    }

    return visible;
}

namespace ch {

[[nodiscard]] inline bool render_visible_procedural_road_center_markings(
    SDL_Renderer* renderer,
    const ProceduralRoadGraph& graph,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height,
    const ProceduralRoad2DWorldBounds& bounds) {
    if (renderer == nullptr) return false;

    Uint8 old_r = 0;
    Uint8 old_g = 0;
    Uint8 old_b = 0;
    Uint8 old_a = 0;
    (void)SDL_GetRenderDrawColor(renderer, &old_r, &old_g, &old_b, &old_a);
    (void)SDL_SetRenderDrawColor(renderer, 236, 221, 159, 220);

    constexpr float kJunctionGapT = 0.34F;
    constexpr int kSamples = 24;
    constexpr int kDashSamples = 3;
    constexpr int kGapSamples = 2;
    constexpr int kPatternSamples = kDashSamples + kGapSamples;

    bool ok = true;
    for (const ProceduralRoadGraphSegment& graph_segment : graph.segments()) {
        const auto spline = procedural_road_visual_spline_2d(graph, graph_segment.id);
        if (!spline || !procedural_road_spline_is_ground_only(*spline) ||
            !procedural_road_spline_intersects_world_bounds(*spline, bounds)) {
            continue;
        }

        float begin_t = 0.0F;
        float end_t = 1.0F;
        if (graph.degree(graph_segment.start_node) >= 3U) begin_t = kJunctionGapT;
        if (graph.degree(graph_segment.end_node) >= 3U) end_t = 1.0F - kJunctionGapT;
        if (begin_t >= end_t) continue;

        for (int sample = 0; sample < kSamples; ++sample) {
            if ((sample % kPatternSamples) >= kDashSamples) continue;
            const float alpha_a = static_cast<float>(sample) / static_cast<float>(kSamples);
            const float alpha_b = static_cast<float>(sample + 1) / static_cast<float>(kSamples);
            const float t_a = begin_t + (end_t - begin_t) * alpha_a;
            const float t_b = begin_t + (end_t - begin_t) * alpha_b;
            const ProceduralRoad2DPoint point_a = procedural_road_sample_cubic_2d(*spline, t_a);
            const ProceduralRoad2DPoint point_b = procedural_road_sample_cubic_2d(*spline, t_b);
            const ScreenPoint screen_a = world_to_screen_point(
                point_a.x, point_a.y, camera, viewport_width, viewport_height);
            const ScreenPoint screen_b = world_to_screen_point(
                point_b.x, point_b.y, camera, viewport_width, viewport_height);
            if (!SDL_RenderLine(renderer, screen_a.x, screen_a.y, screen_b.x, screen_b.y)) ok = false;
        }
    }

    (void)SDL_SetRenderDrawColor(renderer, old_r, old_g, old_b, old_a);
    return ok;
}

} // namespace ch
