#pragma once

#include "road_system.h"

// Transitional bridge while the legacy RoadVisualType API is retired.
// CH_PATH_TOPOLOGY_V1 is the semantic authority; legacy visual names are mapped
// only at compatibility boundaries and must not define topology themselves.
[[nodiscard]] constexpr TileTopologyKind road_visual_type_topology(const RoadVisualType type) {
    switch (type) {
        case RoadVisualType::isolated: return TileTopologyKind::isolated;
        case RoadVisualType::end: return TileTopologyKind::endpoint;
        case RoadVisualType::straight: return TileTopologyKind::straight;
        case RoadVisualType::curve: return TileTopologyKind::corner;
        case RoadVisualType::tee: return TileTopologyKind::tee;
        case RoadVisualType::intersection: return TileTopologyKind::cross;
    }
    return TileTopologyKind::isolated;
}

[[nodiscard]] inline TileTopologyKind road_topology_kind(
    const RoadManager& roads,
    const int tile_x,
    const int tile_y
) {
    return classify_tile_topology(roads.connection_mask(tile_x, tile_y));
}

[[nodiscard]] inline bool legacy_road_visual_matches_topology(
    const RoadManager& roads,
    const int tile_x,
    const int tile_y
) {
    return road_visual_type_topology(roads.visual_type(tile_x, tile_y)) ==
           road_topology_kind(roads, tile_x, tile_y);
}
