#pragma once

#include "src/ch_render/procedural_road_network_renderer.h"
#include "src/road_system.h"

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

    const ProceduralRoadPlacementBridge& mirror = roads.procedural_mirror();
    const ProceduralRoadGraph& graph = mirror.graph();
    if (graph.segments().empty()) return false;

    const ProceduralRoadGroundRenderPlan plan =
        build_procedural_road_ground_render_plan(mirror);

    // Promotion is all-or-fallback. Do not mix the procedural surface with the
    // old tile renderer when a graph segment was rejected by the flat-ground
    // contract. Isolated one-tile roads likewise stay on the legacy fallback
    // until the procedural contract grows an explicit end-cap/island primitive.
    const bool complete_ground_plan =
        plan.skipped_elevated_segments == 0U &&
        plan.skipped_mixed_junctions == 0U &&
        plan.segment_meshes.size() == graph.segments().size() &&
        !plan.segment_meshes.empty();
    if (!complete_ground_plan) return false;

    if (!render_procedural_road_ground_plan(
            renderer, plan, camera, viewport_width, viewport_height)) {
        return false;
    }

    // Markings are presentation polish. Once the asphalt surface has been
    // submitted successfully, never redraw legacy tiles on top merely because
    // one optional SDL line submission failed.
    (void)render_procedural_road_center_markings(
        renderer, graph, camera, viewport_width, viewport_height);
    return true;
}

} // namespace ch
