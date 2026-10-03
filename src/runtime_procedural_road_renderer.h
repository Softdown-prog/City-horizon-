#pragma once

#include "src/ch_render/procedural_road_network_renderer.h"
#include "src/road_system.h"
#include "src/runtime_procedural_road_culling.h"

#include <algorithm>
#include <cmath>

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
    const float viewport_height,
    const TerrainHeightField* heightfield = nullptr) {
    if (renderer == nullptr || roads.tiles().empty()) return false;

    const ProceduralRoad2DWorldBounds visible_bounds =
        procedural_road_visible_world_bounds(camera, viewport_width, viewport_height);
    if (!visible_bounds.valid()) return false;

    // Admission checks use RoadManager's O(1) tile lookup over the camera window
    // instead of scanning every road in the city. This keeps the fallback guard
    // proportional to what can actually be visible at the current zoom.
    const int min_tile_x = std::max(
        contracts::kMapMin, static_cast<int>(std::floor(visible_bounds.min_x - 0.75F)));
    const int max_tile_x = std::min(
        contracts::kMapMax, static_cast<int>(std::ceil(visible_bounds.max_x + 0.75F)));
    const int min_tile_y = std::max(
        contracts::kMapMin, static_cast<int>(std::floor(visible_bounds.min_y - 0.75F)));
    const int max_tile_y = std::min(
        contracts::kMapMax, static_cast<int>(std::ceil(visible_bounds.max_y + 0.75F)));

    bool has_visible_road = false;
    for (int tile_y = min_tile_y; tile_y <= max_tile_y; ++tile_y) {
        for (int tile_x = min_tile_x; tile_x <= max_tile_x; ++tile_x) {
            const RoadTile* tile = roads.tile_at(tile_x, tile_y);
            if (tile == nullptr) continue;
            has_visible_road = true;
            // One-tile islands do not have a procedural edge yet. Fall back for
            // the visible layer instead of silently hiding that tile.
            if (tile->connections == 0U) return false;
        }
    }
    if (!has_visible_road) return true;

    const ProceduralRoadPlacementBridge& mirror = roads.procedural_mirror();
    const ProceduralRoadGraph& graph = mirror.graph();
    if (graph.segments().empty()) return false;

    const ProceduralRoadVisibleGroundRenderPlan visible =
        build_visible_procedural_road_ground_render_plan(mirror, visible_bounds);
    const ProceduralRoadGroundRenderPlan& plan = visible.plan;

    // Promotion is all-or-fallback for the camera-visible working set. The
    // mirror's CH_PROCEDURAL_ROAD_SPATIAL_INDEX_V1 selects nearby chunks first;
    // exact culling and tessellation then run only on those candidates.
    const bool complete_ground_plan =
        plan.skipped_elevated_segments == 0U &&
        plan.skipped_mixed_junctions == 0U &&
        visible.considered_segments > 0U &&
        plan.segment_meshes.size() == visible.considered_segments;
    if (!complete_ground_plan) return false;

    if (!render_procedural_road_ground_plan(
            renderer, plan, camera, viewport_width, viewport_height, {}, heightfield)) {
        return false;
    }

    // Markings use the same spatially indexed camera-visible working set as the
    // asphalt surface. Once asphalt has been submitted, a cosmetic line failure
    // must not redraw legacy tiles on top of the procedural road.
    (void)render_visible_procedural_road_center_markings(
        renderer, mirror, camera, viewport_width, viewport_height, visible_bounds, heightfield);
    return true;
}

} // namespace ch
