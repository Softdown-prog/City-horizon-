#pragma once

#include "placement_contracts.h"
#include "semantic_grid.h"

namespace ch {

class PlacementEngine {
public:
    // Pure placement evaluation function — ZERO state mutation
    static PlacementResult can_place(
        const PlacementRequest& request,
        const SemanticWorldView& world,
        const IAssetCatalogView& catalog
    );
};

} // namespace ch
