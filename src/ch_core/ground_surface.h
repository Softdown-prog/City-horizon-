#pragma once

#include "src/ch_core/map_document.h"
#include "src/ch_core/path_slope_sprite.h"
#include "src/ch_core/procedural_tile_2d.h"
#include "src/tile_topology.h"

#include <optional>
#include <string_view>

namespace ch {

inline constexpr std::string_view kGroundDirtPathDefinition = "ground_dirt_path";
inline constexpr std::string_view kGroundSandPathDefinition = "ground_sand_path";

enum class GroundPathMaterial {
    dirt,
    sand,
};

[[nodiscard]] inline std::optional<GroundPathMaterial> ground_path_material(
    const std::string_view terrain_definition
) {
    if (terrain_definition == kGroundDirtPathDefinition) return GroundPathMaterial::dirt;
    if (terrain_definition == kGroundSandPathDefinition) return GroundPathMaterial::sand;
    return std::nullopt;
}

[[nodiscard]] inline const PathSlopeSpriteFamily& ground_path_sprite_family(
    const GroundPathMaterial material
) {
    return material == GroundPathMaterial::sand ? kSandPathSlopeFamily : kDirtPathSlopeFamily;
}

[[nodiscard]] inline bool is_connectable_ground_surface(const TerrainTileEntry& tile) {
    return ground_path_material(tile.terrain_definition).has_value();
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

// Canonical bridge between the existing auto-tile neighbourhood rules and the
// vertical sprite-selection recipe. Gameplay stays tile based; the renderer
// receives topology + terrain grade from one source of truth and then selects
// a CH_PATH_SLOPE_SPRITE_V1 baked PNG when a compatible slope exists.
[[nodiscard]] inline ProceduralTileRecipe ground_surface_procedural_recipe(
    const MapDocument& document,
    const int tile_x,
    const int tile_y,
    const std::string_view terrain_definition,
    const ProceduralTilePolicy& policy = {}
) {
    return make_procedural_tile_2d_recipe(
        document,
        tile_x,
        tile_y,
        ground_surface_connection_mask(document, tile_x, tile_y, terrain_definition),
        policy);
}

} // namespace ch
