#pragma once

#include "road_system.h"

#include <string>
#include <unordered_map>
#include <vector>

class BuildingManager;

struct SidewalkTile {
    int tile_x = 0;
    int tile_y = 0;
    std::string style_id;
    TileConnectionMask connections = 0;
};

enum class SidewalkPlacementFailure { none, outside_map, sidewalk_occupied, road_occupied, building_occupied };

// Decorative grid layer. It intentionally has no road-access, economy, power or population API.
class SidewalkManager {
public:
    SidewalkManager(int map_min, int map_max);
    [[nodiscard]] bool is_sidewalk(int tile_x, int tile_y) const;
    [[nodiscard]] bool is_walkable(int tile_x, int tile_y) const;
    [[nodiscard]] bool is_connected_to(int tile_x, int tile_y, CardinalDirection direction) const;
    [[nodiscard]] const SidewalkTile* tile_at(int tile_x, int tile_y) const;
    [[nodiscard]] TileConnectionMask connection_mask(int tile_x, int tile_y) const;
    [[nodiscard]] SidewalkPlacementFailure validate_placement(int tile_x, int tile_y, const RoadManager& roads,
                                                               const BuildingManager& buildings) const;
    [[nodiscard]] bool place_tile(int tile_x, int tile_y, std::string style_id);
    [[nodiscard]] bool remove_tile(int tile_x, int tile_y);
    void clear();
    [[nodiscard]] const std::vector<SidewalkTile>& tiles() const;
private:
    [[nodiscard]] bool inside(int tile_x, int tile_y) const;
    [[nodiscard]] int key(int tile_x, int tile_y) const;
    void refresh_connections_around(int tile_x, int tile_y);
    void refresh_connections(int tile_x, int tile_y);
    int min_; int max_;
    std::vector<SidewalkTile> tiles_;
    std::unordered_map<int, std::size_t> indices_;
};
