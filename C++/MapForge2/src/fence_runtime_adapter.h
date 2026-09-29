#pragma once

#include "park_fence_renderer.h"
#include "src/fence_system.h"

namespace ch::studio {

struct FenceRenderSelection {
    ParkFencePiece piece = ParkFencePiece::End;
    ParkFenceRotation rotation = ParkFenceRotation::South;
};

// Single bridge between the gameplay/runtime topology contract and the
// MapForge 2D fence renderer. No renderer is allowed to reinterpret the N/E/S/W
// mask independently; the runtime FenceManager remains authoritative.
class FenceRuntimeAdapter final {
public:
    [[nodiscard]] static FenceRenderSelection select(const FenceVisualState& state);
    [[nodiscard]] static FenceRenderSelection select(const FenceManager& fences,
                                                      int vertex_x,
                                                      int vertex_y);
};

} // namespace ch::studio
