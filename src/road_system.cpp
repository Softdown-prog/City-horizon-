#include "road_system.h"
#include "procedural_road_placement_bridge.h"

#include <algorithm>
#include <bit>
#include <cmath>
#include <iterator>

namespace {

[[nodiscard]] TileCoordinate building_direction_offset(const GridDirection direction) {
    switch (direction) {
        case GridDirection::north: return {0, -1};
        case GridDirection::east: return {1, 0};
        case GridDirection::south: return {0, 1};
        case GridDirection::west: return {-1, 0};
    }
    return {0, 0};
}

[[nodiscard]] float road_distance_3d(const RoadWorldPoint3& a, const RoadWorldPoint3& b) {
    const float dx = b.x - a.x;
    const float dy = b.y - a.y;
    const float dz = b.z - a.z;
    return std::sqrt(dx * dx + dy * dy + dz * dz);
}

}  // namespace

RoadWorldPoint3 RoadMeshBuilder::sample_cubic(const RoadSplineSegment& segment, const float t) {
    const float clamped_t = std::clamp(t, 0.0F, 1.0F);
    const float one_minus_t = 1.0F - clamped_t;
    const float b0 = one_minus_t * one_minus_t * one_minus_t;
    const float b1 = 3.0F * one_minus_t * one_minus_t * clamped_t;
    const float b2 = 3.0F * one_minus_t * clamped_t * clamped_t;
    const float b3 = clamped_t * clamped_t * clamped_t;
    return {
        segment.start.x * b0 + segment.control_a.x * b1 + segment.control_b.x * b2 + segment.end.x * b3,
        segment.start.y * b0 + segment.control_a.y * b1 + segment.control_b.y * b2 + segment.end.y * b3,
        segment.start.z * b0 + segment.control_a.z * b1 + segment.control_b.z * b2 + segment.end.z * b3,
    };
}

RoadWorldPoint3 RoadMeshBuilder::tangent_cubic(const RoadSplineSegment& segment, const float t) {
    const float clamped_t = std::clamp(t, 0.0F, 1.0F);
    const float one_minus_t = 1.0F - clamped_t;
    const float a = 3.0F * one_minus_t * one_minus_t;
    const float b = 6.0F * one_minus_t * clamped_t;
    const float c = 3.0F * clamped_t * clamped_t;
    return {
        a * (segment.control_a.x - segment.start.x) +
            b * (segment.control_b.x - segment.control_a.x) +
            c * (segment.end.x - segment.control_b.x),
        a * (segment.control_a.y - segment.start.y) +
            b * (segment.control_b.y - segment.control_a.y) +
            c * (segment.end.y - segment.control_b.y),
        a * (segment.control_a.z - segment.start.z) +
            b * (segment.control_b.z - segment.control_a.z) +
            c * (segment.end.z - segment.control_b.z),
    };
}

RoadMesh RoadMeshBuilder::build_cubic(const RoadSplineSegment& segment) {
    RoadMesh mesh;
    if (!(segment.width > 0.0F)) return mesh;

    const int subdivisions = std::clamp(segment.subdivisions, 2, 256);
    const float repeat_world_units = std::max(0.01F, segment.texture_repeat_world_units);
    mesh.vertices.reserve(static_cast<std::size_t>(subdivisions + 1) * 2U);
    mesh.indices.reserve(static_cast<std::size_t>(subdivisions) * 6U);

    RoadWorldPoint3 previous_center = sample_cubic(segment, 0.0F);
    float accumulated_length = 0.0F;

    for (int step = 0; step <= subdivisions; ++step) {
        const float t = static_cast<float>(step) / static_cast<float>(subdivisions);
        const RoadWorldPoint3 center = sample_cubic(segment, t);
        if (step > 0) accumulated_length += road_distance_3d(previous_center, center);
        previous_center = center;

        RoadWorldPoint3 tangent = tangent_cubic(segment, t);
        float planar_length = std::sqrt(tangent.x * tangent.x + tangent.y * tangent.y);
        if (planar_length < 0.00001F) {
            tangent.x = segment.end.x - segment.start.x;
            tangent.y = segment.end.y - segment.start.y;
            planar_length = std::sqrt(tangent.x * tangent.x + tangent.y * tangent.y);
        }
        if (planar_length < 0.00001F) {
            tangent.x = 1.0F;
            tangent.y = 0.0F;
            planar_length = 1.0F;
        }

        const float normal_x = -tangent.y / planar_length;
        const float normal_y = tangent.x / planar_length;
        const float half_width = segment.width * 0.5F;
        const float v = accumulated_length / repeat_world_units;

        mesh.vertices.push_back({
            {center.x + normal_x * half_width, center.y + normal_y * half_width, center.z},
            0.0F,
            v,
        });
        mesh.vertices.push_back({
            {center.x - normal_x * half_width, center.y - normal_y * half_width, center.z},
            1.0F,
            v,
        });

        if (step == 0) continue;
        const std::uint32_t current_left = static_cast<std::uint32_t>(step * 2);
        const std::uint32_t current_right = current_left + 1U;
        const std::uint32_t previous_left = current_left - 2U;
        const std::uint32_t previous_right = current_right - 2U;
        mesh.indices.insert(mesh.indices.end(), {
            previous_left, previous_right, current_left,
            previous_right, current_right, current_left,
        });
    }

    return mesh;
}

RoadManager::RoadManager(const int map_min, const int map_max)
    : map_min_(map_min), map_max_(map_max),
      procedural_mirror_(std::make_unique<ProceduralRoadPlacementBridge>()) {}

RoadManager::~RoadManager() = default;

RoadManager::RoadManager(const RoadManager& other)
    : map_min_(other.map_min_), map_max_(other.map_max_), tiles_(other.tiles_),
      tile_indices_(other.tile_indices_),
      procedural_mirror_(std::make_unique<ProceduralRoadPlacementBridge>()) {
    rebuild_procedural_mirror();
}

RoadManager& RoadManager::operator=(const RoadManager& other) {
    if (this == &other) return *this;
    map_min_ = other.map_min_;
    map_max_ = other.map_max_;
    tiles_ = other.tiles_;
    tile_indices_ = other.tile_indices_;
    if (!procedural_mirror_) procedural_mirror_ = std::make_unique<ProceduralRoadPlacementBridge>();
    rebuild_procedural_mirror();
    return *this;
}

RoadManager::RoadManager(RoadManager&& other) noexcept = default;
RoadManager& RoadManager::operator=(RoadManager&& other) noexcept = default;

bool RoadManager::is_inside_map(const int tile_x, const int tile_y) const {
    return tile_x >= map_min_ && tile_x <= map_max_ && tile_y >= map_min_ && tile_y <= map_max_;
}

bool RoadManager::is_road(const int tile_x, const int tile_y) const {
    return tile_at(tile_x, tile_y) != nullptr;
}

bool RoadManager::is_drivable(const int tile_x, const int tile_y) const {
    return is_road(tile_x, tile_y);
}

bool RoadManager::is_connected_to(const int tile_x, const int tile_y, const CardinalDirection direction) const {
    return has_connection(connection_mask(tile_x, tile_y), direction);
}

const RoadTile* RoadManager::tile_at(const int tile_x, const int tile_y) const {
    if (!is_inside_map(tile_x, tile_y)) {
        return nullptr;
    }
    const auto found = tile_indices_.find(tile_key(tile_x, tile_y));
    return found == tile_indices_.end() ? nullptr : &tiles_[found->second];
}

TileOccupancy RoadManager::occupancy_at(const int tile_x, const int tile_y, const BuildingManager& buildings) const {
    if (buildings.is_occupied(tile_x, tile_y)) {
        return TileOccupancy::building;
    }
    return is_road(tile_x, tile_y) ? TileOccupancy::road : TileOccupancy::empty;
}

RoadPlacementFailure RoadManager::validate_placement(const int tile_x, const int tile_y, const BuildingManager& buildings) const {
    if (!is_inside_map(tile_x, tile_y)) {
        return RoadPlacementFailure::outside_map;
    }
    switch (occupancy_at(tile_x, tile_y, buildings)) {
        case TileOccupancy::empty: return RoadPlacementFailure::none;
        case TileOccupancy::building: return RoadPlacementFailure::building_occupied;
        case TileOccupancy::road: return RoadPlacementFailure::road_occupied;
    }
    return RoadPlacementFailure::outside_map;
}

std::uint8_t RoadManager::connection_mask(const int tile_x, const int tile_y) const {
    const RoadTile* tile = tile_at(tile_x, tile_y);
    return tile == nullptr ? 0 : tile->connections;
}

RoadVisualType RoadManager::visual_type(const int tile_x, const int tile_y) const {
    const std::uint8_t mask = connection_mask(tile_x, tile_y);
    const int neighbors = std::popcount(mask);
    if (neighbors == 0) {
        return RoadVisualType::isolated;
    }
    if (neighbors == 1) {
        return RoadVisualType::end;
    }
    if (neighbors == 2) {
        const bool opposite = mask == static_cast<std::uint8_t>(road_north | road_south) ||
                              mask == static_cast<std::uint8_t>(road_east | road_west);
        return opposite ? RoadVisualType::straight : RoadVisualType::curve;
    }
    if (neighbors == 3) {
        return RoadVisualType::tee;
    }
    return RoadVisualType::intersection;
}

std::vector<TileCoordinate> RoadManager::line_between(TileCoordinate start, const TileCoordinate end) const {
    std::vector<TileCoordinate> result;
    result.push_back(start);
    while (start.x != end.x) {
        start.x += start.x < end.x ? 1 : -1;
        result.push_back(start);
    }
    while (start.y != end.y) {
        start.y += start.y < end.y ? 1 : -1;
        result.push_back(start);
    }
    return result;
}

bool RoadManager::has_world_connection() const {
    // The outside-world road is represented by a logical gateway at the west
    // edge of the starter 32x32 parcel. Requiring an eastward connection means
    // the player must actually extend the road into the city; a lone marker tile
    // can never unlock immigration by accident.
    if (!is_inside_map(kExternalRoadGatewayX, kExternalRoadGatewayY)) return false;
    return is_road(kExternalRoadGatewayX, kExternalRoadGatewayY) &&
           is_connected_to(kExternalRoadGatewayX, kExternalRoadGatewayY,
                           CardinalDirection::east);
}

bool RoadManager::place_tile(const int tile_x, const int tile_y) {
    if (!is_inside_map(tile_x, tile_y) || is_road(tile_x, tile_y)) {
        return false;
    }
    tile_indices_.emplace(tile_key(tile_x, tile_y), tiles_.size());
    tiles_.push_back({tile_x, tile_y, 0});
    refresh_connections_around(tile_x, tile_y);
    mirror_added_tile(tile_x, tile_y);
    return true;
}

int RoadManager::place_segment(const std::vector<TileCoordinate>& tiles) {
    int placed = 0;
    for (const TileCoordinate& tile : tiles) {
        if (place_tile(tile.x, tile.y)) {
            ++placed;
        }
    }
    return placed;
}

bool RoadManager::remove_tile(const int tile_x, const int tile_y) {
    const auto found = tile_indices_.find(tile_key(tile_x, tile_y));
    if (found == tile_indices_.end()) {
        return false;
    }
    const std::size_t index = found->second;
    const std::size_t last = tiles_.size() - 1;
    if (index != last) {
        tiles_[index] = tiles_[last];
        tile_indices_[tile_key(tiles_[index].tile_x, tiles_[index].tile_y)] = index;
    }
    tiles_.pop_back();
    tile_indices_.erase(found);
    refresh_connections_around(tile_x, tile_y);
    rebuild_procedural_mirror();
    return true;
}

void RoadManager::clear() {
    tiles_.clear();
    tile_indices_.clear();
    if (procedural_mirror_) procedural_mirror_->clear();
}

bool RoadManager::overlaps_building_footprint(const BuildingDefinition& definition, const int tile_x, const int tile_y,
                                              const BuildingRotation rotation) const {
    const BuildingFootprint footprint = rotated_footprint(definition, rotation);
    for (int offset_y = 0; offset_y < footprint.height; ++offset_y) {
        for (int offset_x = 0; offset_x < footprint.width; ++offset_x) {
            if (is_road(tile_x + offset_x, tile_y + offset_y)) {
                return true;
            }
        }
    }
    return false;
}

bool RoadManager::has_adjacent_road(const BuildingInstance& instance, const BuildingDefinition& definition) const {
    return has_adjacent_road(definition, instance.tile_x, instance.tile_y, instance.rotation);
}

bool RoadManager::has_adjacent_road(const BuildingDefinition& definition, const int tile_x, const int tile_y,
                                    const BuildingRotation rotation) const {
    const BuildingFootprint footprint = rotated_footprint(definition, rotation);
    for (int offset_y = 0; offset_y < footprint.height; ++offset_y) {
        for (int offset_x = 0; offset_x < footprint.width; ++offset_x) {
            const int footprint_tile_x = tile_x + offset_x;
            const int footprint_tile_y = tile_y + offset_y;
            if (is_road(footprint_tile_x - 1, footprint_tile_y) || is_road(footprint_tile_x + 1, footprint_tile_y) ||
                is_road(footprint_tile_x, footprint_tile_y - 1) || is_road(footprint_tile_x, footprint_tile_y + 1)) {
                return true;
            }
        }
    }
    return false;
}

bool RoadManager::has_required_road_access(const BuildingDefinition& definition, const int tile_x, const int tile_y,
                                           const BuildingRotation rotation) const {
    if (!definition.requires_road_access) return true;

    switch (resolved_road_access_mode(definition)) {
        case RoadAccessMode::any_perimeter:
            return has_adjacent_road(definition, tile_x, tile_y, rotation);
        case RoadAccessMode::access_points:
            return has_road_at_access_point(definition, tile_x, tile_y, rotation);
        case RoadAccessMode::front_edge:
            for (const BuildingAccessPoint access_point : front_edge_access_points(definition, rotation)) {
                const TileCoordinate offset = building_direction_offset(access_point.facing);
                if (is_road(tile_x + access_point.local_x + offset.x, tile_y + access_point.local_y + offset.y)) return true;
            }
            return false;
    }
    return false;
}

bool RoadManager::has_road_at_access_point(const BuildingDefinition& definition, const int tile_x, const int tile_y,
                                           const BuildingRotation rotation) const {
    for (const BuildingAccessPoint access_point : rotated_access_points(definition, rotation)) {
        const TileCoordinate offset = building_direction_offset(access_point.facing);
        if (is_road(tile_x + access_point.local_x + offset.x, tile_y + access_point.local_y + offset.y)) {
            return true;
        }
    }
    return false;
}

bool RoadManager::has_road_at_access_point(const BuildingInstance& instance, const BuildingDefinition& definition) const {
    return has_road_at_access_point(definition, instance.tile_x, instance.tile_y, instance.rotation);
}

const std::vector<RoadTile>& RoadManager::tiles() const {
    return tiles_;
}

const ProceduralRoadPlacementBridge& RoadManager::procedural_mirror() const {
    return *procedural_mirror_;
}

int RoadManager::tile_key(const int tile_x, const int tile_y) const {
    const int span = map_max_ - map_min_ + 1;
    return (tile_y - map_min_) * span + (tile_x - map_min_);
}

void RoadManager::refresh_connections_around(const int tile_x, const int tile_y) {
    refresh_connections(tile_x, tile_y);
    for (const CardinalDirection direction : kCardinalDirections) {
        const TileOffset offset = direction_offset(direction);
        refresh_connections(tile_x + offset.x, tile_y + offset.y);
    }
}

void RoadManager::refresh_connections(const int tile_x, const int tile_y) {
    const auto found = tile_indices_.find(tile_key(tile_x, tile_y));
    if (found == tile_indices_.end()) {
        return;
    }
    std::uint8_t mask = 0;
    for (const CardinalDirection direction : kCardinalDirections) {
        const TileOffset offset = direction_offset(direction);
        if (is_road(tile_x + offset.x, tile_y + offset.y)) {
            mask = static_cast<std::uint8_t>(mask | connection_bit(direction));
        }
    }
    tiles_[found->second].connections = mask;
}

void RoadManager::mirror_added_tile(const int tile_x, const int tile_y) {
    if (!procedural_mirror_) procedural_mirror_ = std::make_unique<ProceduralRoadPlacementBridge>();

    const TileCoordinate added{tile_x, tile_y};
    if (!procedural_mirror_->mirror_tile_segment({added}, ProceduralRoadClass::local)) {
        rebuild_procedural_mirror();
        return;
    }

    for (const CardinalDirection direction : kCardinalDirections) {
        const TileOffset offset = direction_offset(direction);
        const TileCoordinate neighbor{tile_x + offset.x, tile_y + offset.y};
        if (!is_road(neighbor.x, neighbor.y)) continue;
        if (!procedural_mirror_->mirror_tile_segment({added, neighbor}, ProceduralRoadClass::local)) {
            rebuild_procedural_mirror();
            return;
        }
    }
}

void RoadManager::rebuild_procedural_mirror() {
    if (!procedural_mirror_) procedural_mirror_ = std::make_unique<ProceduralRoadPlacementBridge>();
    if (!procedural_mirror_->rebuild_from_legacy_tiles(tiles_, ProceduralRoadClass::local, 0.0F)) {
        procedural_mirror_->clear();
    }
}