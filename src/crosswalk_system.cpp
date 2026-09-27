#include "crosswalk_system.h"
#include "sidewalk_system.h"

#include <algorithm>

namespace {
[[nodiscard]] NavigationTile offset_tile(const CrosswalkPortal& portal, const CardinalDirection direction) {
    const TileOffset offset = direction_offset(direction);
    return {portal.tile_x + offset.x, portal.tile_y + offset.y};
}
}

CardinalDirection CrosswalkPortal::side_a_direction() const {
    return axis == CrosswalkAxis::north_south ? CardinalDirection::north : CardinalDirection::west;
}

CardinalDirection CrosswalkPortal::side_b_direction() const {
    return axis == CrosswalkAxis::north_south ? CardinalDirection::south : CardinalDirection::east;
}

CrosswalkManager::CrosswalkManager(const int map_min, const int map_max) : min_(map_min), max_(map_max) {}

int CrosswalkManager::key(const int x, const int y) const {
    const int span = max_ - min_ + 1;
    return (y - min_) * span + (x - min_);
}

bool CrosswalkManager::inside(const int x, const int y) const {
    return x >= min_ && x <= max_ && y >= min_ && y <= max_;
}

bool CrosswalkManager::place(const int tile_x, const int tile_y, const CrosswalkAxis axis, const RoadManager& roads) {
    if (!inside(tile_x, tile_y) || !roads.is_drivable(tile_x, tile_y)) return false;
    const int portal_key = key(tile_x, tile_y);
    if (const auto found = indices_.find(portal_key); found != indices_.end()) {
        portals_[found->second].axis = axis;
        portals_[found->second].pedestrian_occupied = false;
        return true;
    }
    indices_[portal_key] = portals_.size();
    portals_.push_back({tile_x, tile_y, axis, false});
    return true;
}

bool CrosswalkManager::remove(const int tile_x, const int tile_y) {
    const auto found = indices_.find(key(tile_x, tile_y));
    if (found == indices_.end()) return false;
    const std::size_t index = found->second;
    const std::size_t last = portals_.size() - 1;
    if (index != last) {
        portals_[index] = portals_[last];
        indices_[key(portals_[index].tile_x, portals_[index].tile_y)] = index;
    }
    portals_.pop_back();
    indices_.erase(found);
    return true;
}

const CrosswalkPortal* CrosswalkManager::at(const int tile_x, const int tile_y) const {
    const auto found = indices_.find(key(tile_x, tile_y));
    return found == indices_.end() ? nullptr : &portals_[found->second];
}

bool CrosswalkManager::is_crosswalk(const int tile_x, const int tile_y) const {
    return at(tile_x, tile_y) != nullptr;
}

bool CrosswalkManager::allows_direction(const int tile_x, const int tile_y, const CardinalDirection direction) const {
    const CrosswalkPortal* portal = at(tile_x, tile_y);
    if (portal == nullptr) return false;
    return direction == portal->side_a_direction() || direction == portal->side_b_direction();
}

bool CrosswalkManager::is_active_portal(const int tile_x, const int tile_y, const SidewalkManager& sidewalks) const {
    const CrosswalkPortal* portal = at(tile_x, tile_y);
    if (portal == nullptr) return false;
    const NavigationTile a = offset_tile(*portal, portal->side_a_direction());
    const NavigationTile b = offset_tile(*portal, portal->side_b_direction());
    return sidewalks.is_walkable(a.x, a.y) && sidewalks.is_walkable(b.x, b.y);
}

void CrosswalkManager::clear_occupancy() {
    for (CrosswalkPortal& portal : portals_) portal.pedestrian_occupied = false;
}

void CrosswalkManager::set_pedestrian_occupied(const int tile_x, const int tile_y, const bool occupied) {
    const auto found = indices_.find(key(tile_x, tile_y));
    if (found != indices_.end()) portals_[found->second].pedestrian_occupied = occupied;
}

bool CrosswalkManager::pedestrian_occupied(const int tile_x, const int tile_y) const {
    const CrosswalkPortal* portal = at(tile_x, tile_y);
    return portal != nullptr && portal->pedestrian_occupied;
}

std::optional<NavigationTile> CrosswalkManager::side_a_anchor(const CrosswalkPortal& portal) const {
    if (!inside(portal.tile_x, portal.tile_y)) return std::nullopt;
    return offset_tile(portal, portal.side_a_direction());
}

std::optional<NavigationTile> CrosswalkManager::side_b_anchor(const CrosswalkPortal& portal) const {
    if (!inside(portal.tile_x, portal.tile_y)) return std::nullopt;
    return offset_tile(portal, portal.side_b_direction());
}

const std::vector<CrosswalkPortal>& CrosswalkManager::portals() const { return portals_; }

void CrosswalkManager::clear() {
    portals_.clear();
    indices_.clear();
}
