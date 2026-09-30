#pragma once

#include "src/ch_render/procedural_road_renderer.h"
#include "src/procedural_road_ground_render_plan.h"

namespace ch {

// Returns false only when SDL rejects one of the geometry submissions. Callers
// may immediately fall back to the legacy tile/PNG road renderer in that case.
[[nodiscard]] inline bool render_procedural_road_ground_plan(
    SDL_Renderer* renderer,
    const ProceduralRoadGroundRenderPlan& plan,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height,
    const ProceduralRoadRenderStyle& style = {}) {
    for (const RoadMesh& mesh : plan.segment_meshes) {
        if (!render_procedural_road_mesh(renderer, mesh, camera, viewport_width, viewport_height, style)) {
            return false;
        }
    }
    // Junction patches are intentionally drawn after the approach ribbons so
    // they cover sub-pixel seams where independently generated strips meet.
    for (const RoadMesh& patch : plan.junction_meshes) {
        if (!render_procedural_road_mesh(renderer, patch, camera, viewport_width, viewport_height, style)) {
            return false;
        }
    }
    return true;
}

} // namespace ch
