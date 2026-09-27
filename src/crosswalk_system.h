#pragma once

#include "navigation_network.h"
#include "road_system.h"

#include <cstdint>
#include <optional>
#include <unordered_map>
#include <vector>

enum class CrosswalkAxis : std::uint8_t {
    north_south,
    east_west,
};

struct CrosswalkPortal {
    int tile_x = 0;
    int tile_y = 0;
    CrosswalkAxis axis = CrosswalkAxis::north_south;
    bool pedestrian_occupied = false;

    [[nodiscard]] CardinalDirection side_a_direction() const;
    [[nodiscard]] CardinalDirection side_b_direction() const;
};

// CH_CROSSWALK_PORTAL_V1
// A crosswalk is the only normal pedestrian portal across a road tile.
// It does not make the whole road walkable: pedestrians may only enter/leave
// along the authored crossing axis. Cars keep ownership of the road tile and
// use pedestrian_occupied as a braking hazard signal.
class CrosswalkManager {
public:
    CrosswalkManager(int map_min, int map_max);

    [[nodiscard]] bool place(int tile_x, int tile_y, CrosswalkAxis axis, const RoadManager& roads);
    [[nodiscard]] bool remove(int tile_x, int tile_y);
    [[nodiscard]] const CrosswalkPortal* at(int tile_x, int tile_y) const;
    [[nodiscard]] bool is_crosswalk(int tile_x, int tile_y) const;
    [[nodiscard]] bool allows_direction(int tile_x, int tile_y, CardinalDirection direction) const;
    [[nodiscard]] bool is_active_portal(int tile_x, int tile_y, const class SidewalkManager& sidewalks) const;

    void clear_occupancy();
    void set_pedestrian_occupied(int tile_x, int tile_y, bool occupied = true);
    [[nodiscard]] bool pedestrian_occupied(int tile_x, int tile_y) const;

    [[nodiscard]] std::optional<NavigationTile> side_a_anchor(const CrosswalkPortal& portal) const;
    [[nodiscard]] std::optional<NavigationTile> side_b_anchor(const CrosswalkPortal& portal) const;
    [[nodiscard]] const std::vector<CrosswalkPortal>& portals() const;
    void clear();

private:
    [[nodiscard]] int key(int x, int y) const;
    [[nodiscard]] bool inside(int x, int y) const;

    int min_ = 0;
    int max_ = 0;
    std::vector<CrosswalkPortal> portals_;
    std::unordered_map<int, std::size_t> indices_;
};
