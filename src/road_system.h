#pragma once

#include "building_system.h"
#include "tile_topology.h"

#include <algorithm>
#include <cstdint>
#include <optional>
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

// CH_PROCEDURAL_ROAD_GRAPH_V1
//
// Graph topology sits beside the legacy RoadManager until the procedural-road
// visual and editor gates pass. Nodes are shared anchors in world space. Segment
// handles are stored relative to their endpoint nodes, so moving a junction
// keeps every incident road attached while preserving the authored curve shape.
// ID 0 is reserved as invalid; generated IDs are stable for the lifetime of the
// graph and are never derived from vector indices.
using ProceduralRoadNodeId = std::uint64_t;
using ProceduralRoadSegmentId = std::uint64_t;
inline constexpr ProceduralRoadNodeId kInvalidProceduralRoadNodeId = 0;
inline constexpr ProceduralRoadSegmentId kInvalidProceduralRoadSegmentId = 0;

struct ProceduralRoadNode {
    ProceduralRoadNodeId id = kInvalidProceduralRoadNodeId;
    RoadWorldPoint3 position{};
};

struct ProceduralRoadGraphSegment {
    ProceduralRoadSegmentId id = kInvalidProceduralRoadSegmentId;
    ProceduralRoadNodeId start_node = kInvalidProceduralRoadNodeId;
    ProceduralRoadNodeId end_node = kInvalidProceduralRoadNodeId;
    RoadWorldPoint3 start_handle{1.0F, 0.0F, 0.0F};
    RoadWorldPoint3 end_handle{-1.0F, 0.0F, 0.0F};
    float width = 0.72F;
    float texture_repeat_world_units = 1.0F;
    int subdivisions = 24;
    std::uint8_t lane_count = 2;
};

class ProceduralRoadGraph {
public:
    [[nodiscard]] ProceduralRoadNodeId add_node(const RoadWorldPoint3 position) {
        const ProceduralRoadNodeId id = next_node_id_++;
        nodes_.push_back({id, position});
        node_indices_.emplace(id, nodes_.size() - 1U);
        return id;
    }

    [[nodiscard]] std::optional<ProceduralRoadSegmentId> add_segment(
        const ProceduralRoadNodeId start_node,
        const ProceduralRoadNodeId end_node,
        const RoadWorldPoint3 start_handle = {1.0F, 0.0F, 0.0F},
        const RoadWorldPoint3 end_handle = {-1.0F, 0.0F, 0.0F},
        const float width = 0.72F,
        const std::uint8_t lane_count = 2) {
        if (start_node == end_node || node(start_node) == nullptr || node(end_node) == nullptr ||
            !(width > 0.0F) || lane_count == 0) {
            return std::nullopt;
        }
        const ProceduralRoadSegmentId id = next_segment_id_++;
        segments_.push_back({id, start_node, end_node, start_handle, end_handle,
                             width, 1.0F, 24, lane_count});
        segment_indices_.emplace(id, segments_.size() - 1U);
        return id;
    }

    [[nodiscard]] const ProceduralRoadNode* node(const ProceduralRoadNodeId id) const {
        const auto found = node_indices_.find(id);
        return found == node_indices_.end() ? nullptr : &nodes_[found->second];
    }

    [[nodiscard]] ProceduralRoadNode* node(const ProceduralRoadNodeId id) {
        const auto found = node_indices_.find(id);
        return found == node_indices_.end() ? nullptr : &nodes_[found->second];
    }

    [[nodiscard]] const ProceduralRoadGraphSegment* segment(const ProceduralRoadSegmentId id) const {
        const auto found = segment_indices_.find(id);
        return found == segment_indices_.end() ? nullptr : &segments_[found->second];
    }

    [[nodiscard]] ProceduralRoadGraphSegment* segment(const ProceduralRoadSegmentId id) {
        const auto found = segment_indices_.find(id);
        return found == segment_indices_.end() ? nullptr : &segments_[found->second];
    }

    [[nodiscard]] bool set_node_position(const ProceduralRoadNodeId id, const RoadWorldPoint3 position) {
        ProceduralRoadNode* target = node(id);
        if (target == nullptr) return false;
        target->position = position;
        return true;
    }

    [[nodiscard]] std::vector<ProceduralRoadSegmentId> connected_segments(const ProceduralRoadNodeId node_id) const {
        std::vector<ProceduralRoadSegmentId> result;
        if (node(node_id) == nullptr) return result;
        for (const ProceduralRoadGraphSegment& item : segments_) {
            if (item.start_node == node_id || item.end_node == node_id) result.push_back(item.id);
        }
        return result;
    }

    [[nodiscard]] std::size_t degree(const ProceduralRoadNodeId node_id) const {
        if (node(node_id) == nullptr) return 0U;
        return static_cast<std::size_t>(std::count_if(
            segments_.begin(), segments_.end(), [node_id](const ProceduralRoadGraphSegment& item) {
                return item.start_node == node_id || item.end_node == node_id;
            }));
    }

    [[nodiscard]] std::optional<RoadSplineSegment> spline_for(const ProceduralRoadSegmentId id) const {
        const ProceduralRoadGraphSegment* item = segment(id);
        if (item == nullptr) return std::nullopt;
        const ProceduralRoadNode* start = node(item->start_node);
        const ProceduralRoadNode* end = node(item->end_node);
        if (start == nullptr || end == nullptr) return std::nullopt;

        RoadSplineSegment spline;
        spline.start = start->position;
        spline.control_a = add(start->position, item->start_handle);
        spline.control_b = add(end->position, item->end_handle);
        spline.end = end->position;
        spline.width = item->width;
        spline.texture_repeat_world_units = item->texture_repeat_world_units;
        spline.subdivisions = item->subdivisions;
        return spline;
    }

    [[nodiscard]] bool remove_segment(const ProceduralRoadSegmentId id) {
        const auto found = segment_indices_.find(id);
        if (found == segment_indices_.end()) return false;
        erase_segment_at(found->second);
        return true;
    }

    [[nodiscard]] bool remove_node(const ProceduralRoadNodeId id) {
        const auto found = node_indices_.find(id);
        if (found == node_indices_.end()) return false;

        for (std::size_t index = segments_.size(); index > 0U; --index) {
            const ProceduralRoadGraphSegment& item = segments_[index - 1U];
            if (item.start_node == id || item.end_node == id) erase_segment_at(index - 1U);
        }

        const std::size_t index = found->second;
        const std::size_t last = nodes_.size() - 1U;
        if (index != last) {
            nodes_[index] = nodes_[last];
            node_indices_[nodes_[index].id] = index;
        }
        nodes_.pop_back();
        node_indices_.erase(id);
        return true;
    }

    void clear() {
        nodes_.clear();
        segments_.clear();
        node_indices_.clear();
        segment_indices_.clear();
        next_node_id_ = 1;
        next_segment_id_ = 1;
    }

    [[nodiscard]] const std::vector<ProceduralRoadNode>& nodes() const { return nodes_; }
    [[nodiscard]] const std::vector<ProceduralRoadGraphSegment>& segments() const { return segments_; }

private:
    [[nodiscard]] static RoadWorldPoint3 add(const RoadWorldPoint3 point, const RoadWorldPoint3 delta) {
        return {point.x + delta.x, point.y + delta.y, point.z + delta.z};
    }

    void erase_segment_at(const std::size_t index) {
        const ProceduralRoadSegmentId removed_id = segments_[index].id;
        const std::size_t last = segments_.size() - 1U;
        if (index != last) {
            segments_[index] = segments_[last];
            segment_indices_[segments_[index].id] = index;
        }
        segments_.pop_back();
        segment_indices_.erase(removed_id);
    }

    ProceduralRoadNodeId next_node_id_ = 1;
    ProceduralRoadSegmentId next_segment_id_ = 1;
    std::vector<ProceduralRoadNode> nodes_;
    std::vector<ProceduralRoadGraphSegment> segments_;
    std::unordered_map<ProceduralRoadNodeId, std::size_t> node_indices_;
    std::unordered_map<ProceduralRoadSegmentId, std::size_t> segment_indices_;
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
