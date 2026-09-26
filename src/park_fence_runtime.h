#pragma once

#include "fence_placement_controller.h"
#include "fence_system.h"
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
