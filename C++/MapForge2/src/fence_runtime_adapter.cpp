#include "fence_runtime_adapter.h"

namespace ch::studio {
namespace {

[[nodiscard]] ParkFenceRotation to_renderer_rotation(const FenceRotation rotation) {
    switch (rotation) {
        case FenceRotation::south: return ParkFenceRotation::South;
        case FenceRotation::east: return ParkFenceRotation::East;
        case FenceRotation::north: return ParkFenceRotation::North;
        case FenceRotation::west: return ParkFenceRotation::West;
    }
    return ParkFenceRotation::South;
}

[[nodiscard]] ParkFencePiece to_renderer_piece(const FenceVisualType type) {
    switch (type) {
        case FenceVisualType::isolated: return ParkFencePiece::Post;
        case FenceVisualType::end: return ParkFencePiece::End;
        case FenceVisualType::straight: return ParkFencePiece::Straight;
        case FenceVisualType::corner: return ParkFencePiece::Corner;
        case FenceVisualType::tee: return ParkFencePiece::Tee;
        case FenceVisualType::cross: return ParkFencePiece::Cross;
        case FenceVisualType::gate: return ParkFencePiece::Gate;
    }
    return ParkFencePiece::Post;
}

} // namespace

FenceRenderSelection FenceRuntimeAdapter::select(const FenceVisualState& state) {
    return {to_renderer_piece(state.type), to_renderer_rotation(state.rotation)};
}

FenceRenderSelection FenceRuntimeAdapter::select(const FenceManager& fences,
                                                  const int vertex_x,
                                                  const int vertex_y) {
    return select(fences.visual_state(vertex_x, vertex_y));
}

} // namespace ch::studio
