#pragma once

#include "src/ch_core/map_document.h"
#include "src/tile_topology.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <string_view>

namespace ch {

// CH_PROCEDURAL_TILE_2D_V1
//
// Logical tiles remain fully 2D and grid based. This contract only describes
// how a connected floor/path tile should be drawn when its neighbours and the
// terrain heightfield demand a richer silhouette (rounded ends/corners) or a
// vertical profile (ramp/stairs). No 3D world object is created.
inline constexpr std::string_view kProceduralTile2DContract = "CH_PROCEDURAL_TILE_2D_V1";

enum class ProceduralTileTopology {
    isolated,
    end,
    straight,
    corner,
    tee,
    cross,
};

enum class ProceduralTileContour {
    island,
    semicircle_cap,
    continuous_outline,
    rounded_corner,
};

enum class ProceduralTileVerticalProfile {
    flat,
    ramp,
    stairs,
};

struct ProceduralTilePolicy {
    // Tiny height noise must not kick a flat sprite into the procedural path.
    float flat_epsilon = 0.08F;

    // A gentle grade stays a continuous 2D ramp. Steeper grades become stairs.
    float stairs_threshold = 0.70F;

    // Target visual rise per generated stair. The renderer may distribute the
    // resulting tread count over more than one connected tile later.
    float target_stair_height = 0.22F;
    int max_stairs_per_tile = 24;
};

struct ProceduralTileRecipe {
    TileConnectionMask logical_connections = 0;
    ProceduralTileTopology topology = ProceduralTileTopology::isolated;
    ProceduralTileContour contour = ProceduralTileContour::island;
    ProceduralTileVerticalProfile vertical_profile = ProceduralTileVerticalProfile::flat;

    // Heights are sampled at the middle of the logical N/E/S/W edges. Keeping
    // them in logical space makes the recipe independent from camera rotation.
    std::array<float, 4> edge_heights{};
    float center_height = 0.0F;
    float min_height = 0.0F;
    float max_height = 0.0F;
    float height_delta = 0.0F;

    CardinalDirection low_edge = CardinalDirection::north;
    CardinalDirection high_edge = CardinalDirection::north;
    int stair_count = 0;

    // Flat legacy tiles can keep their exact approved PNG. Non-flat tiles use
    // the same material/texture as input to the procedural 2D renderer.
    bool legacy_sprite_compatible = true;

    // Curves/tees/crosses on a slope need more than one local strip so each arm
    // can meet the shared terrain edge without a seam.
    bool requires_subdivision = false;
};

[[nodiscard]] constexpr int procedural_edge_index(const CardinalDirection direction) {
    switch (direction) {
        case CardinalDirection::north: return 0;
        case CardinalDirection::east: return 1;
        case CardinalDirection::south: return 2;
        case CardinalDirection::west: return 3;
    }
    return 0;
}

[[nodiscard]] constexpr int procedural_connection_count(const TileConnectionMask mask) {
    int count = 0;
    for (const CardinalDirection direction : kCardinalDirections) {
        if (has_connection(mask, direction)) ++count;
    }
    return count;
}

[[nodiscard]] constexpr ProceduralTileTopology procedural_tile_topology(const TileConnectionMask mask) {
    const int count = procedural_connection_count(mask);
    if (count == 0) return ProceduralTileTopology::isolated;
    if (count == 1) return ProceduralTileTopology::end;
    if (count == 3) return ProceduralTileTopology::tee;
    if (count >= 4) return ProceduralTileTopology::cross;

    const bool north_south = has_connection(mask, CardinalDirection::north) &&
                             has_connection(mask, CardinalDirection::south);
    const bool east_west = has_connection(mask, CardinalDirection::east) &&
                           has_connection(mask, CardinalDirection::west);
    return (north_south || east_west)
        ? ProceduralTileTopology::straight
        : ProceduralTileTopology::corner;
}

[[nodiscard]] constexpr ProceduralTileContour procedural_tile_contour(const ProceduralTileTopology topology) {
    switch (topology) {
        case ProceduralTileTopology::isolated: return ProceduralTileContour::island;
        case ProceduralTileTopology::end: return ProceduralTileContour::semicircle_cap;
        case ProceduralTileTopology::corner: return ProceduralTileContour::rounded_corner;
        case ProceduralTileTopology::straight:
        case ProceduralTileTopology::tee:
        case ProceduralTileTopology::cross:
            return ProceduralTileContour::continuous_outline;
    }
    return ProceduralTileContour::continuous_outline;
}

[[nodiscard]] inline ProceduralTileRecipe make_procedural_tile_2d_recipe(
    const MapDocument& document,
    const int tile_x,
    const int tile_y,
    const TileConnectionMask logical_connections,
    const ProceduralTilePolicy& policy = {}
) {
    ProceduralTileRecipe recipe;
    recipe.logical_connections = logical_connections;
    recipe.topology = procedural_tile_topology(logical_connections);
    recipe.contour = procedural_tile_contour(recipe.topology);

    const auto& heightfield = document.terrain_heightfield();
    recipe.edge_heights[0] = heightfield.sample(static_cast<float>(tile_x) + 0.5F,
                                                static_cast<float>(tile_y));
    recipe.edge_heights[1] = heightfield.sample(static_cast<float>(tile_x) + 1.0F,
                                                static_cast<float>(tile_y) + 0.5F);
    recipe.edge_heights[2] = heightfield.sample(static_cast<float>(tile_x) + 0.5F,
                                                static_cast<float>(tile_y) + 1.0F);
    recipe.edge_heights[3] = heightfield.sample(static_cast<float>(tile_x),
                                                static_cast<float>(tile_y) + 0.5F);
    recipe.center_height = heightfield.sample(static_cast<float>(tile_x) + 0.5F,
                                              static_cast<float>(tile_y) + 0.5F);

    recipe.min_height = recipe.center_height;
    recipe.max_height = recipe.center_height;
    for (const float height : recipe.edge_heights) {
        recipe.min_height = std::min(recipe.min_height, height);
        recipe.max_height = std::max(recipe.max_height, height);
    }
    recipe.height_delta = recipe.max_height - recipe.min_height;

    float low = recipe.edge_heights[0];
    float high = recipe.edge_heights[0];
    for (const CardinalDirection direction : kCardinalDirections) {
        const float value = recipe.edge_heights[procedural_edge_index(direction)];
        if (value < low) {
            low = value;
            recipe.low_edge = direction;
        }
        if (value > high) {
            high = value;
            recipe.high_edge = direction;
        }
    }

    if (recipe.height_delta <= std::max(0.0F, policy.flat_epsilon)) {
        recipe.vertical_profile = ProceduralTileVerticalProfile::flat;
        recipe.legacy_sprite_compatible = true;
        recipe.stair_count = 0;
    } else if (recipe.height_delta <= std::max(policy.flat_epsilon, policy.stairs_threshold)) {
        recipe.vertical_profile = ProceduralTileVerticalProfile::ramp;
        recipe.legacy_sprite_compatible = false;
        recipe.stair_count = 0;
    } else {
        recipe.vertical_profile = ProceduralTileVerticalProfile::stairs;
        recipe.legacy_sprite_compatible = false;
        const float target = std::max(0.01F, policy.target_stair_height);
        recipe.stair_count = std::clamp(
            static_cast<int>(std::ceil(recipe.height_delta / target)),
            2,
            std::max(2, policy.max_stairs_per_tile));
    }

    recipe.requires_subdivision = recipe.vertical_profile != ProceduralTileVerticalProfile::flat &&
        (recipe.topology == ProceduralTileTopology::corner ||
         recipe.topology == ProceduralTileTopology::tee ||
         recipe.topology == ProceduralTileTopology::cross);

    return recipe;
}

} // namespace ch
