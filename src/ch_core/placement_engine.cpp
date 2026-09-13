#include "placement_engine.h"
#include <algorithm>

namespace ch {

PlacementResult PlacementEngine::can_place(
    const PlacementRequest& request,
    const SemanticWorldView& world,
    const IAssetCatalogView& catalog
) {
    PlacementResult result;
    result.object_id = request.object_id;
    result.resolved_origin = request.origin;

    // 1. Resolve footprint dimensions
    AssetFootprintInfo fp = catalog.get_footprint(request.object_id);
    int fp_w = (fp.width > 0) ? fp.width : 1;
    int fp_h = (fp.height > 0) ? fp.height : 1;

    // Adjust for rotation (0/180 -> w,h | 90/270 -> h,w)
    int rot = (request.rotation % 4 + 4) % 4;
    int w = (rot == 1 || rot == 3) ? fp_h : fp_w;
    int h = (rot == 1 || rot == 3) ? fp_w : fp_h;

    // 2. Generate affected tiles list
    result.affected_tiles.reserve(static_cast<size_t>(w * h));
    for (int dy = 0; dy < h; ++dy) {
        for (int dx = 0; dx < w; ++dx) {
            result.affected_tiles.push_back(GridCoord(request.origin.x + dx, request.origin.y + dy));
        }
    }

    // 3. Evaluate Bounds Enforcement (CH_PLACE_BOUNDS)
    for (const auto& tile : result.affected_tiles) {
        if (tile.x < world.map_min || tile.x > world.map_max ||
            tile.y < world.map_min || tile.y > world.map_max) {
            if (std::find(result.violations.begin(), result.violations.end(), PlacementViolation::bounds_exceeded) == result.violations.end()) {
                result.violations.push_back(PlacementViolation::bounds_exceeded);
                result.conflicting_tile = tile;
            }
        }
    }

    // 4. Evaluate Terrain Compatibility & Footprint Occupancy
    for (const auto& tile : result.affected_tiles) {
        TileSemanticInfo info = SemanticGrid::inspect_tile_channels(world, tile);

        // Check water compatibility
        if (info.water_state == SemanticState::valid && request.category != PlacementCategory::water_structure) {
            if (std::find(result.violations.begin(), result.violations.end(), PlacementViolation::terrain_incompatible) == result.violations.end()) {
                result.violations.push_back(PlacementViolation::terrain_incompatible);
                result.conflicting_tile = tile;
            }
        }

        // Check footprint / occupancy overlap
        if (info.footprint_state == SemanticState::valid || info.road_state == SemanticState::valid || info.occupancy_state == SemanticState::valid) {
            if (std::find(result.violations.begin(), result.violations.end(), PlacementViolation::occupied) == result.violations.end()) {
                result.violations.push_back(PlacementViolation::occupied);
                result.conflicting_tile = tile;
            }
        }
    }

    // Final state evaluation
    if (result.violations.empty()) {
        result.state = SemanticState::valid;
    } else {
        result.state = SemanticState::invalid;
    }

    return result;
}

} // namespace ch
