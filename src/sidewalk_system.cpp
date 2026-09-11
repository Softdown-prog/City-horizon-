#include "sidewalk_system.h"
#include "building_system.h"

SidewalkManager::SidewalkManager(int map_min, int map_max) : min_(map_min), max_(map_max) {}
bool SidewalkManager::inside(int x, int y) const { return x >= min_ && x <= max_ && y >= min_ && y <= max_; }
int SidewalkManager::key(int x, int y) const { return (y - min_) * (max_ - min_ + 1) + x - min_; }
bool SidewalkManager::is_sidewalk(int x, int y) const { return indices_.contains(key(x, y)); }
bool SidewalkManager::is_walkable(int x, int y) const { return is_sidewalk(x, y); }
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
SidewalkPlacementFailure SidewalkManager::validate_placement(int x, int y, const RoadManager& roads, const BuildingManager& buildings) const {
    if (!inside(x,y)) return SidewalkPlacementFailure::outside_map;
    if (is_sidewalk(x,y)) return SidewalkPlacementFailure::sidewalk_occupied;
    if (roads.is_road(x,y)) return SidewalkPlacementFailure::road_occupied;
    return buildings.is_occupied(x,y) ? SidewalkPlacementFailure::building_occupied : SidewalkPlacementFailure::none;
}
bool SidewalkManager::place_tile(int x, int y, std::string style_id) {
    if (!inside(x,y) || is_sidewalk(x,y)) return false;
    indices_.emplace(key(x,y), tiles_.size()); tiles_.push_back({x,y,std::move(style_id), 0});
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
    TileConnectionMask mask = 0;
    for (const CardinalDirection direction : kCardinalDirections) {
        const TileOffset offset = direction_offset(direction);
        if (is_sidewalk(x + offset.x, y + offset.y)) mask = static_cast<TileConnectionMask>(mask | connection_bit(direction));
    }
    tiles_[found->second].connections = mask;
}
