#pragma once

#include "../rail_system.h"
#include "../ch_core/projection.h"

#include <SDL3/SDL_render.h>

class ProceduralRailRenderer final {
public:
    ProceduralRailRenderer() = delete;
    static constexpr const char* kRuntimeContract = "CH_PROCEDURAL_RAIL_RUNTIME_V1";
    static constexpr bool kFailClosedOnInvalidGeometry = true;

    struct Palette {
        SDL_Color ballast{105, 98, 86, 255};
        SDL_Color sleepers{92, 61, 39, 255};
        SDL_Color rails{121, 126, 128, 255};
    };

    // Fail-closed renderer boundary. Geometry is revalidated before any SDL
    // submission and each material group is submitted independently.
    [[nodiscard]] static bool render_geometry(
        SDL_Renderer* renderer,
        const RailGeometry& geometry,
        const RailProfile& profile,
        const ch::CameraState& camera,
        float viewport_width,
        float viewport_height,
        const Palette& palette = {});

    // Convenience path for callers that own only a spline. Invalid rail input
    // never reaches SDL because RailMeshBuilder::build() returns zero geometry.
    [[nodiscard]] static bool render_segment(
        SDL_Renderer* renderer,
        const RailSplineSegment& segment,
        const RailProfile& profile,
        const ch::CameraState& camera,
        float viewport_width,
        float viewport_height,
        const Palette& palette = {});
};
