#pragma once

#include "building_system.h"
#include "tile_topology.h"

#include <cstdint>
#include <unordered_map>
#include <vector>

struct TileCoordinate {
    int x = 0;
    int y = 0;
};

inline constexpr std::int64_t kRoadCostPerTile = 100;

// A road owns only its logical grid tile. Its final artwork is selected later
// from this connectivity mask; it is never inferred from a PNG bounding box.
using RoadConnection = TileConnectionMask;
inline constexpr RoadConnection road_north = tile_connection_north;
inline constexpr RoadConnection road_east = tile_connection_east;
inline constexpr RoadConnection road_south = tile_connection_south;
inline constexpr RoadConnection road_west = tile_connection_west;

enum class RoadVisualType {
    isolated,
    end,
    straight,
    curve,
    tee,
    intersection,
};

enum class TileOccupancy {
    empty,
    building,
    road,
};

enum class RoadPlacementFailure {
    none,
    outside_map,
    road_occupied,
    building_occupied,
};

struct RoadTile {
    int tile_x = 0;
    int tile_y = 0;
    std::uint8_t connections = 0;
};

class RoadManager {
public:
    RoadManager(int map_min, int map_max);

    [[nodiscard]] bool is_inside_map(int tile_x, int tile_y) const;
    [[nodiscard]] bool is_road(int tile_x, int tile_y) const;
    [[nodiscard]] bool is_drivable(int tile_x, int tile_y) const;
    [[nodiscard]] bool is_connected_to(int tile_x, int tile_y, CardinalDirection direction) const;
    [[nodiscard]] const RoadTile* tile_at(int tile_x, int tile_y) const;
    [[nodiscard]] TileOccupancy occupancy_at(int tile_x, int tile_y, const BuildingManager& buildings) const;
    [[nodiscard]] RoadPlacementFailure validate_placement(int tile_x, int tile_y, const BuildingManager& buildings) const;
    [[nodiscard]] std::uint8_t connection_mask(int tile_x, int tile_y) const;
    [[nodiscard]] RoadVisualType visual_type(int tile_x, int tile_y) const;
    [[nodiscard]] std::vector<TileCoordinate> line_between(TileCoordinate start, TileCoordinate end) const;

    // Building overlap is intentionally validated by the placement layer;
    // RoadManager itself remains a reusable road-only data structure.
    [[nodiscard]] bool place_tile(int tile_x, int tile_y);
    int place_segment(const std::vector<TileCoordinate>& tiles);
    [[nodiscard]] bool remove_tile(int tile_x, int tile_y);
    void clear();
    [[nodiscard]] bool overlaps_building_footprint(const BuildingDefinition& definition, int tile_x, int tile_y,
                                                   BuildingRotation rotation = BuildingRotation::r0) const;
    // Approved urban-edge contract: a building's own artwork contains any visual
    // sidewalk. A road may be directly adjacent to the footprint edge; no grass
    // tile or other logical margin is inserted between them.
    [[nodiscard]] bool has_adjacent_road(const BuildingInstance& instance,
                                         const BuildingDefinition& definition) const;
    // New-construction query. It checks every edge cell of the rotated logical
    // footprint against N/E/S/W road tiles; diagonal contact never qualifies.
    [[nodiscard]] bool has_adjacent_road(const BuildingDefinition& definition, int tile_x, int tile_y,
                                         BuildingRotation rotation = BuildingRotation::r0) const;
    [[nodiscard]] bool has_required_road_access(const BuildingDefinition& definition, int tile_x, int tile_y,
                                                BuildingRotation rotation = BuildingRotation::r0) const;
    // Access-point query for placement, pedestrians, vehicles and service routing.
    // Unlike has_adjacent_road, it considers only declared entrances/exits.
    [[nodiscard]] bool has_road_at_access_point(const BuildingDefinition& definition, int tile_x, int tile_y,
                                                BuildingRotation rotation = BuildingRotation::r0) const;
    [[nodiscard]] bool has_road_at_access_point(const BuildingInstance& instance,
                                                const BuildingDefinition& definition) const;
    [[nodiscard]] const std::vector<RoadTile>& tiles() const;

private:
    [[nodiscard]] int tile_key(int tile_x, int tile_y) const;
    void refresh_connections_around(int tile_x, int tile_y);
    void refresh_connections(int tile_x, int tile_y);

    int map_min_;
    int map_max_;
    std::vector<RoadTile> tiles_;
    std::unordered_map<int, std::size_t> tile_indices_;
};
