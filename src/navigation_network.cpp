#include "navigation_network.h"
#include "crosswalk_system.h"

#include <algorithm>
#include <deque>
#include <string>
#include <unordered_map>
#include <unordered_set>

namespace {

[[nodiscard]] std::string tile_key(const NavigationTile tile) {
    return std::to_string(tile.x) + ':' + std::to_string(tile.y);
}

[[nodiscard]] bool is_walkable_floor_style(const SidewalkTile* floor) {
    if (floor == nullptr) return false;
    return floor->style_id == "dirt_path" || floor->style_id == "sand_path" ||
           floor->style_id == "cement_path" || floor->style_id == "concrete_01";
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

bool PedestrianSurfaceNavigationNetwork::is_navigable(const NavigationTile tile) const {
    // Roads belong exclusively to vehicle traffic. Pedestrians only receive a
    // road exception from PedestrianCrosswalkNavigationNetwork.
    if (roads_.is_road(tile.x, tile.y)) return false;
    return is_walkable_floor_style(sidewalks_.tile_at(tile.x, tile.y));
}

bool PedestrianSurfaceNavigationNetwork::is_connected(const NavigationTile tile, const CardinalDirection direction) const {
    const TileOffset offset = direction_offset(direction);
    return is_navigable(tile) && is_navigable({tile.x + offset.x, tile.y + offset.y});
}

bool PedestrianCrosswalkNavigationNetwork::is_navigable(const NavigationTile tile) const {
    if (surfaces_.is_navigable(tile)) return true;
    return roads_.is_road(tile.x, tile.y) && crosswalks_.is_active_portal(tile.x, tile.y, sidewalks_);
}

bool PedestrianCrosswalkNavigationNetwork::is_connected(const NavigationTile tile,
                                                         const CardinalDirection direction) const {
    const TileOffset offset = direction_offset(direction);
    const NavigationTile other{tile.x + offset.x, tile.y + offset.y};

    const bool from_crosswalk = crosswalks_.is_crosswalk(tile.x, tile.y);
    const bool to_crosswalk = crosswalks_.is_crosswalk(other.x, other.y);

    if (!from_crosswalk && !to_crosswalk) {
        return surfaces_.is_connected(tile, direction);
    }

    // Crossing cells may be entered/exited only along the authored portal axis.
    if (from_crosswalk) {
        return crosswalks_.is_active_portal(tile.x, tile.y, sidewalks_) &&
               crosswalks_.allows_direction(tile.x, tile.y, direction) &&
               surfaces_.is_navigable(other);
    }

    return crosswalks_.is_active_portal(other.x, other.y, sidewalks_) &&
           crosswalks_.allows_direction(other.x, other.y, opposite_direction(direction)) &&
           surfaces_.is_navigable(tile);
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

NavigationPathResult find_navigation_path_with_minimum_length(const NavigationNetwork& network,
                                                             const NavigationTile start, const std::size_t minimum_tiles) {
    if (!network.is_navigable(start)) return {};
    if (minimum_tiles <= 1) return {NavigationPathStatus::found, {start}};
    std::deque<NavigationTile> frontier{start};
    std::unordered_set<std::string> visited{tile_key(start)};
    std::unordered_map<std::string, NavigationTile> previous;
    std::unordered_map<std::string, std::size_t> lengths{{tile_key(start), 1}};
    while (!frontier.empty()) {
        const NavigationTile current = frontier.front();
        frontier.pop_front();
        for (const CardinalDirection direction : kCardinalDirections) {
            if (!network.can_move(current, direction)) continue;
            const TileOffset offset = direction_offset(direction);
            const NavigationTile next{current.x + offset.x, current.y + offset.y};
            const std::string key = tile_key(next);
            if (!visited.insert(key).second) continue;
            previous.emplace(key, current);
            const std::size_t length = lengths.at(tile_key(current)) + 1;
            if (length >= minimum_tiles) {
                NavigationPathResult result{NavigationPathStatus::found, {}};
                for (NavigationTile step = next;; step = previous.at(tile_key(step))) {
                    result.tiles.push_back(step);
                    if (step == start) break;
                }
                std::reverse(result.tiles.begin(), result.tiles.end());
                return result;
            }
            lengths.emplace(key, length);
            frontier.push_back(next);
        }
    }
    return {};
}
