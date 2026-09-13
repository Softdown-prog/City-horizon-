#pragma once

#include "src/ch_core/semantic_contracts.h"
#include "src/ch_core/map_document.h"
#include "src/ch_core/projection.h"
#include <SDL3/SDL.h>

namespace ch {

enum class ViewMode : uint8_t {
    art = 0,
    logic = 1,
    art_and_logic = 2
};

class SemanticRenderer {
public:
    static void render_semantic_overlays(
        SDL_Renderer* renderer,
        const MapDocument& document,
        const CameraState& camera,
        float viewport_width,
        float viewport_height,
        SemanticChannel active_channels,
        float channel_opacity
    );
};

} // namespace ch
