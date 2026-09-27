#pragma once

#include "road_system.h"

#include <cstddef>
#include <optional>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

class BuildingManager;

inline constexpr std::string_view kCrosswalkNorthSouthStyle = "crosswalk_ns";
inline constexpr std::string_view kCrosswalkEastWestStyle = "crosswalk_ew";

enum class CrosswalkAxis : std::uint8_t {
    north_south,
    east_west,
};

[[nodiscard]] constexpr bool is_crosswalk_style(const std::string_view style_id) {
    return style_id == kCrosswalkNorthSouthStyle || style_id == kCrosswalkEastWestStyle;
}

[[nodiscard]] constexpr std::optional<CrosswalkAxis> crosswalk_axis_from_style(const std::string_view style_id) {
    if (style_id == kCrosswalkNorthSouthStyle) return CrosswalkAxis::north_south;
    if (style_id == kCrosswalkEastWestStyle) return CrosswalkAxis::east_west;
    return std::nullopt;
}

struct CrosswalkPortal {
    TileCoordinate side_a;
    TileCoordinate road_tile;
    TileCoordinate side_b;
    CrosswalkAxis axis = CrosswalkAxis::north_south;
    // Logical conflict anchor shared by pedestrian decision and road traffic.
    // TrafficVehicleManager uses integer tile centres as its road reference,
    // so the crossing conflict point is exactly the road tile coordinate.
    float conflict_x = 0.0F;
    float conflict_y = 0.0F;
};

struct SidewalkTile {
    int tile_x = 0;
    int tile_y = 0;
    std::string style_id;
    TileConnectionMask connections = 0;
};

enum class SidewalkPlacementFailure {
    none,
    outside_map,
    sidewalk_occupied,
    road_occupied,
    road_required,
    building_occupied,
};

// Pedestrian floor layer. Ordinary floor cells never overlap roads. Crosswalk
// styles are the sole exception: they are flat road decals that also carry a
// CH_CROSSWALK_PORTAL_V1 logical crossing axis and conflict anchor.
class SidewalkManager {
public:
    SidewalkManager(int map_min, int map_max);
    [[nodiscard]] bool is_sidewalk(int tile_x, int tile_y) const;
    [[nodiscard]] bool is_walkable(int tile_x, int tile_y) const;
    [[nodiscard]] bool is_crosswalk(int tile_x, int tile_y) const;
    [[nodiscard]] bool is_connected_to(int tile_x, int tile_y, CardinalDirection direction) const;
    [[nodiscard]] const SidewalkTile* tile_at(int tile_x, int tile_y) const;
    [[nodiscard]] TileConnectionMask connection_mask(int tile_x, int tile_y) const;
    [[nodiscard]] SidewalkPlacementFailure validate_placement(int tile_x, int tile_y, const RoadManager& roads,
                                                               const BuildingManager& buildings,
                                                               std::string_view style_id = {}) const;
    [[nodiscard]] bool place_tile(int tile_x, int tile_y, std::string style_id);
    // Repaint an existing floor/crosswalk cell without removing it. Runtime
    // placement validation remains responsible for road-vs-floor legality.
    [[nodiscard]] bool paint_tile(int tile_x, int tile_y, std::string style_id);
    [[nodiscard]] bool remove_tile(int tile_x, int tile_y);
    [[nodiscard]] std::optional<CrosswalkPortal> crosswalk_portal(int tile_x, int tile_y) const;
    void clear();
    [[nodiscard]] const std::vector<SidewalkTile>& tiles() const;
private:
    [[nodiscard]] bool inside(int tile_x, int tile_y) const;
    [[nodiscard]] int key(int tile_x, int tile_y) const;
    void refresh_connections_around(int tile_x, int tile_y);
    void refresh_connections(int tile_x, int tile_y);
    int min_; int max_;
    std::vector<SidewalkTile> tiles_;
    std::unordered_map<int, std::size_t> indices_;
};
