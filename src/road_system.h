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

// The initial owned parcel is the canonical 32x32 block centered at the origin
// (-16..15). Immigration connects through one authored logical gateway on its
// west edge, so players never need to buy locked outer parcels just to reach the
// world boundary. The gateway itself is not a prebuilt road and occupies no
// construction space until the player deliberately connects to it.
inline constexpr int kExternalRoadGatewayX = -16;
inline constexpr int kExternalRoadGatewayY = 0;

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

// CH_PROCEDURAL_ROAD_MESH_V1
//
// The current gameplay road network remains tile-based. These structures are a
// parallel visual-geometry contract for elastic roads. They deliberately do not
// change occupancy, pathfinding, costs or save data yet. A later migration can
// move gameplay onto a road graph once the visual proof has passed.
struct RoadWorldPoint3 {
    float x = 0.0F;
    float y = 0.0F;
    float z = 0.0F;
};

struct RoadSplineSegment {
    RoadWorldPoint3 start{};
    RoadWorldPoint3 control_a{};
    RoadWorldPoint3 control_b{};
    RoadWorldPoint3 end{};
    float width = 0.72F;
    float texture_repeat_world_units = 1.0F;
    int subdivisions = 24;
};

struct RoadMeshVertex {
    RoadWorldPoint3 position{};
    float u = 0.0F;
    float v = 0.0F;
};

struct RoadMesh {
    std::vector<RoadMeshVertex> vertices;
    std::vector<std::uint32_t> indices;

    [[nodiscard]] bool empty() const { return vertices.empty() || indices.empty(); }
};

class RoadMeshBuilder {
public:
    [[nodiscard]] static RoadWorldPoint3 sample_cubic(const RoadSplineSegment& segment, float t);
    [[nodiscard]] static RoadWorldPoint3 tangent_cubic(const RoadSplineSegment& segment, float t);
    [[nodiscard]] static RoadMesh build_cubic(const RoadSplineSegment& segment);
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

    // Immigration gateway. A road on the west edge of the starter parcel only
    // counts when it continues east into the owned city, preventing an isolated
    // one-tile road from opening immigration accidentally.
    [[nodiscard]] bool has_world_connection() const;

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
