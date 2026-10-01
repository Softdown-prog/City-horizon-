#pragma once

#include "src/ch_render/procedural_road_network_renderer.h"
#include "src/road_system.h"
#include "src/runtime_procedural_road_culling.h"

namespace ch {

// CH_PROCEDURAL_ROAD_2D_RUNTIME_V1
//
// Promotion bridge between the authoritative RoadManager topology and the
// production SDL runtime. It deliberately owns presentation only: placement,
// save/load, navigation, traffic and economy remain in RoadManager.
//
// Returning false means the caller must use the legacy tile/PNG presentation.
// This keeps old saves and any unsupported/mixed-height topology visually safe
// while the ground-road path is promoted to procedural 2D.
[[nodiscard]] inline bool try_render_procedural_roads_runtime(
    SDL_Renderer* renderer,
    const RoadManager& roads,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height) {
    if (renderer == nullptr || roads.tiles().empty()) return false;

    const ProceduralRoad2DWorldBounds visible_bounds =
        procedural_road_visible_world_bounds(camera, viewport_width, viewport_height);
    if (!visible_bounds.valid()) return false;

    bool has_visible_road = false;
    for (const RoadTile& tile : roads.tiles()) {
        const ProceduralRoad2DPoint center{
            static_cast<float>(tile.tile_x) + 0.5F,
            static_cast<float>(tile.tile_y) + 0.5F,
        };
        if (!visible_bounds.contains(center, 0.75F)) continue;
        has_visible_road = true;
        // One-tile islands do not have a procedural edge yet. Fall back for the
        // whole visible road layer instead of silently hiding that tile.
        if (tile.connections == 0U) return false;
    }
    if (!has_visible_road) return true;

    const ProceduralRoadPlacementBridge& mirror = roads.procedural_mirror();
    const ProceduralRoadGraph& graph = mirror.graph();
    if (graph.segments().empty()) return false;

    const ProceduralRoadVisibleGroundRenderPlan visible =
        build_visible_procedural_road_ground_render_plan(mirror, visible_bounds);
    const ProceduralRoadGroundRenderPlan& plan = visible.plan;

    // Promotion is all-or-fallback for the camera-visible working set. Roads
    // outside visible_bounds are culled before tessellation and therefore do not
    // make per-frame cost grow with the entire city network.
    const bool complete_ground_plan =
        plan.skipped_elevated_segments == 0U &&
        plan.skipped_mixed_junctions == 0U &&
        visible.considered_segments > 0U &&
        plan.segment_meshes.size() == visible.considered_segments;
    if (!complete_ground_plan) return false;

    if (!render_procedural_road_ground_plan(
            renderer, plan, camera, viewport_width, viewport_height)) {
        return false;
    }

    // Markings use the same camera-visible working set as the asphalt surface.
    // Once asphalt has been submitted, a cosmetic line failure must not redraw
    // the legacy tiles on top of the procedural road.
    (void)render_visible_procedural_road_center_markings(
        renderer, graph, camera, viewport_width, viewport_height, visible_bounds);
    return true;
}

} // namespace ch
