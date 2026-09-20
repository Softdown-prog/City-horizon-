#pragma once

#include "src/ch_core/map_document.h"
#include "src/tile_topology.h"

#include <string_view>

namespace ch {

inline constexpr std::string_view kGroundDirtPathDefinition = "ground_dirt_path";

[[nodiscard]] inline bool is_connectable_ground_surface(const TerrainTileEntry& tile) {
    return tile.terrain_definition == kGroundDirtPathDefinition;
}

[[nodiscard]] inline TileConnectionMask ground_surface_connection_mask(
    const MapDocument& document,
    const int tile_x,
    const int tile_y,
    const std::string_view terrain_definition
) {
    TileConnectionMask mask = 0;

    for (const CardinalDirection direction : kCardinalDirections) {
        const TileOffset offset = direction_offset(direction);
        const auto neighbor = document.get_terrain_at(tile_x + offset.x, tile_y + offset.y);
        if (neighbor.has_value() && neighbor->terrain_definition == terrain_definition) {
            mask |= connection_bit(direction);
        }
    }

    return mask;
}

} // namespace ch
