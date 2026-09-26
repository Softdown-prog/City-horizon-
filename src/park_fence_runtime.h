#pragma once

#include "fence_placement_controller.h"
#include "fence_system.h"
#include "navigation_network.h"
#include "src/ch_core/contracts.h"

namespace park_fence_runtime {

[[nodiscard]] inline FenceManager& fences() {
    static FenceManager manager(ch::contracts::kMapMin, ch::contracts::kMapMax);
    return manager;
}

[[nodiscard]] inline FencePlacementController& placement() {
    static FencePlacementController controller(fences());
    return controller;
}

inline void clear() {
    placement().cancel_drag();
    fences().clear();
}

}  // namespace park_fence_runtime

// Drop-in replacement for the current pedestrian road-lane graph. Logical
// roads remain the source of walkable tiles, while Park fences veto crossings
// on their grid edge. Open gates deliberately do not veto the crossing.
class ParkFencePedestrianNavigationNetwork final : public NavigationNetwork {
public:
    explicit ParkFencePedestrianNavigationNetwork(const RoadManager& roads)
        : base_(roads) {}

    [[nodiscard]] bool is_navigable(const NavigationTile tile) const override {
        return base_.is_navigable(tile);
    }

    [[nodiscard]] bool is_connected(const NavigationTile tile,
                                    const CardinalDirection direction) const override {
        return base_.is_connected(tile, direction) &&
               !park_fence_runtime::fences().blocks_tile_crossing(tile.x, tile.y, direction);
    }

private:
    PedestrianLaneNavigationNetwork base_;
};
