#include "sidewalk_system.h"
#include "building_system.h"

SidewalkManager::SidewalkManager(int map_min, int map_max) : min_(map_min), max_(map_max) {}
bool SidewalkManager::inside(int x, int y) const { return x >= min_ && x <= max_ && y >= min_ && y <= max_; }
int SidewalkManager::key(int x, int y) const { return (y - min_) * (max_ - min_ + 1) + x - min_; }
bool SidewalkManager::is_sidewalk(int x, int y) const { return indices_.contains(key(x, y)); }
bool SidewalkManager::is_walkable(int x, int y) const { return is_sidewalk(x, y); }
bool SidewalkManager::is_crosswalk(int x, int y) const {
    const SidewalkTile* tile = tile_at(x, y);
    return tile != nullptr && is_crosswalk_style(tile->style_id);
}
const SidewalkTile* SidewalkManager::tile_at(int x, int y) const {
    if (!inside(x, y)) return nullptr;
    const auto found = indices_.find(key(x, y));
    return found == indices_.end() ? nullptr : &tiles_[found->second];
}
TileConnectionMask SidewalkManager::connection_mask(int x, int y) const {
    const SidewalkTile* tile = tile_at(x, y);
    return tile == nullptr ? 0 : tile->connections;
}
bool SidewalkManager::is_connected_to(int x, int y, const CardinalDirection direction) const {
    return has_connection(connection_mask(x, y), direction);
}
SidewalkPlacementFailure SidewalkManager::validate_placement(int x, int y, const RoadManager& roads,
                                                              const BuildingManager& buildings,
                                                              const std::string_view style_id) const {
    if (!inside(x,y)) return SidewalkPlacementFailure::outside_map;
    if (is_sidewalk(x,y)) return SidewalkPlacementFailure::sidewalk_occupied;
    const bool crosswalk = is_crosswalk_style(style_id);
    if (crosswalk && !roads.is_road(x, y)) return SidewalkPlacementFailure::road_required;
    if (!crosswalk && roads.is_road(x,y)) return SidewalkPlacementFailure::road_occupied;
    return buildings.is_occupied(x,y) ? SidewalkPlacementFailure::building_occupied : SidewalkPlacementFailure::none;
}
bool SidewalkManager::place_tile(int x, int y, std::string style_id) {
    if (!inside(x,y) || is_sidewalk(x,y)) return false;
    indices_.emplace(key(x,y), tiles_.size()); tiles_.push_back({x,y,std::move(style_id), 0});
    refresh_connections_around(x, y);
    return true;
}
bool SidewalkManager::paint_tile(int x, int y, std::string style_id) {
    if (!inside(x, y)) return false;
    const auto found = indices_.find(key(x, y));
    if (found == indices_.end()) return place_tile(x, y, std::move(style_id));
    SidewalkTile& tile = tiles_[found->second];
    if (tile.style_id == style_id) return false;
    tile.style_id = std::move(style_id);
    refresh_connections_around(x, y);
    return true;
}
bool SidewalkManager::remove_tile(int x, int y) {
    const auto found = indices_.find(key(x, y));
    if (found == indices_.end()) return false;
    const std::size_t index = found->second;
    const std::size_t last = tiles_.size() - 1;
    if (index != last) {
        tiles_[index] = std::move(tiles_[last]);
        indices_[key(tiles_[index].tile_x, tiles_[index].tile_y)] = index;
    }
    tiles_.pop_back();
    indices_.erase(found);
    refresh_connections_around(x, y);
    return true;
}
std::optional<CrosswalkPortal> SidewalkManager::crosswalk_portal(const int x, const int y) const {
    const SidewalkTile* tile = tile_at(x, y);
    if (tile == nullptr) return std::nullopt;
    const auto axis = crosswalk_axis_from_style(tile->style_id);
    if (!axis) return std::nullopt;
    CrosswalkPortal portal;
    portal.axis = *axis;
    portal.road_tile = {x, y};
    portal.conflict_x = static_cast<float>(x);
    portal.conflict_y = static_cast<float>(y);
    if (*axis == CrosswalkAxis::north_south) {
        portal.side_a = {x, y - 1};
        portal.side_b = {x, y + 1};
    } else {
        portal.side_a = {x - 1, y};
        portal.side_b = {x + 1, y};
    }
    return portal;
}
void SidewalkManager::clear() { tiles_.clear(); indices_.clear(); }
const std::vector<SidewalkTile>& SidewalkManager::tiles() const { return tiles_; }
void SidewalkManager::refresh_connections_around(const int x, const int y) {
    refresh_connections(x, y);
    for (const CardinalDirection direction : kCardinalDirections) {
        const TileOffset offset = direction_offset(direction);
        refresh_connections(x + offset.x, y + offset.y);
    }
}
void SidewalkManager::refresh_connections(const int x, const int y) {
    const auto found = indices_.find(key(x, y));
    if (found == indices_.end()) return;
    SidewalkTile& tile = tiles_[found->second];
    if (const auto axis = crosswalk_axis_from_style(tile.style_id)) {
        tile.connections = *axis == CrosswalkAxis::north_south
            ? static_cast<TileConnectionMask>(tile_connection_north | tile_connection_south)
            : static_cast<TileConnectionMask>(tile_connection_east | tile_connection_west);
        return;
    }
    TileConnectionMask mask = 0;
    for (const CardinalDirection direction : kCardinalDirections) {
        const TileOffset offset = direction_offset(direction);
        const SidewalkTile* neighbour = tile_at(x + offset.x, y + offset.y);
        if (neighbour != nullptr && neighbour->style_id == tile.style_id)
            mask = static_cast<TileConnectionMask>(mask | connection_bit(direction));
    }
    tile.connections = mask;
}
