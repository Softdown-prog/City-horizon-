#include "road_system.h"

#include <bit>
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

}  // namespace

RoadManager::RoadManager(const int map_min, const int map_max)
    : map_min_(map_min), map_max_(map_max) {}

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

bool RoadManager::place_tile(const int tile_x, const int tile_y) {
    if (!is_inside_map(tile_x, tile_y) || is_road(tile_x, tile_y)) {
        return false;
    }
    tile_indices_.emplace(tile_key(tile_x, tile_y), tiles_.size());
    tiles_.push_back({tile_x, tile_y, 0});
    refresh_connections_around(tile_x, tile_y);
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
    return true;
}

void RoadManager::clear() {
    tiles_.clear();
    tile_indices_.clear();
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
