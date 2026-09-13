#include "navigation_network.h"

#include <algorithm>
#include <deque>
#include <string>
#include <unordered_map>
#include <unordered_set>

namespace {

[[nodiscard]] std::string tile_key(const NavigationTile tile) {
    return std::to_string(tile.x) + ':' + std::to_string(tile.y);
}

}  // namespace

bool NavigationNetwork::can_move(const NavigationTile from, const CardinalDirection direction) const {
    const TileOffset offset = direction_offset(direction);
    const NavigationTile to{from.x + offset.x, from.y + offset.y};
    return is_navigable(from) && is_navigable(to) && is_connected(from, direction) &&
           is_connected(to, opposite_direction(direction));
}

bool RoadNavigationNetwork::is_navigable(const NavigationTile tile) const {
    return roads_.is_drivable(tile.x, tile.y);
}

bool RoadNavigationNetwork::is_connected(const NavigationTile tile, const CardinalDirection direction) const {
    return roads_.is_connected_to(tile.x, tile.y, direction);
}

bool PedestrianLaneNavigationNetwork::is_navigable(const NavigationTile tile) const {
    return roads_.is_road(tile.x, tile.y);
}

bool PedestrianLaneNavigationNetwork::is_connected(const NavigationTile tile, const CardinalDirection direction) const {
    return roads_.is_connected_to(tile.x, tile.y, direction);
}

bool SidewalkNavigationNetwork::is_navigable(const NavigationTile tile) const {
    return sidewalks_.is_walkable(tile.x, tile.y);
}

bool SidewalkNavigationNetwork::is_connected(const NavigationTile tile, const CardinalDirection direction) const {
    return sidewalks_.is_connected_to(tile.x, tile.y, direction);
}

NavigationPathResult find_navigation_path(const NavigationNetwork& network, const NavigationTile start, const NavigationTile goal) {
    if (!network.is_navigable(start) || !network.is_navigable(goal)) return {};
    if (start == goal) return {NavigationPathStatus::found, {start}};

    std::deque<NavigationTile> frontier;
    std::unordered_set<std::string> visited;
    std::unordered_map<std::string, NavigationTile> previous;
    frontier.push_back(start);
    visited.insert(tile_key(start));

    while (!frontier.empty()) {
        const NavigationTile current = frontier.front();
        frontier.pop_front();
        for (const CardinalDirection direction : kCardinalDirections) {
            if (!network.can_move(current, direction)) continue;
            const TileOffset offset = direction_offset(direction);
            const NavigationTile next{current.x + offset.x, current.y + offset.y};
            const std::string next_key = tile_key(next);
            if (!visited.insert(next_key).second) continue;
            previous.emplace(next_key, current);
            if (next == goal) {
                NavigationPathResult result;
                result.status = NavigationPathStatus::found;
                for (NavigationTile step = goal;; step = previous.at(tile_key(step))) {
                    result.tiles.push_back(step);
                    if (step == start) break;
                }
                std::reverse(result.tiles.begin(), result.tiles.end());
                return result;
            }
            frontier.push_back(next);
        }
    }
    return {};
}
