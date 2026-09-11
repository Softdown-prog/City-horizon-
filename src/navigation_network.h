#pragma once

#include "road_system.h"
#include "sidewalk_system.h"

#include <vector>

struct NavigationTile {
    int x = 0;
    int y = 0;

    [[nodiscard]] constexpr bool operator==(const NavigationTile&) const = default;
};

// Minimal live graph interface. It is intentionally entity-agnostic: a future
// enclosure or water network only needs to answer the same tile questions.
class NavigationNetwork {
public:
    virtual ~NavigationNetwork() = default;
    [[nodiscard]] virtual bool is_navigable(NavigationTile tile) const = 0;
    [[nodiscard]] virtual bool is_connected(NavigationTile tile, CardinalDirection direction) const = 0;

    [[nodiscard]] bool can_move(NavigationTile from, CardinalDirection direction) const;
};

class RoadNavigationNetwork final : public NavigationNetwork {
public:
    explicit RoadNavigationNetwork(const RoadManager& roads) : roads_(roads) {}
    [[nodiscard]] bool is_navigable(NavigationTile tile) const override;
    [[nodiscard]] bool is_connected(NavigationTile tile, CardinalDirection direction) const override;
private:
    const RoadManager& roads_;
};

class SidewalkNavigationNetwork final : public NavigationNetwork {
public:
    explicit SidewalkNavigationNetwork(const SidewalkManager& sidewalks) : sidewalks_(sidewalks) {}
    [[nodiscard]] bool is_navigable(NavigationTile tile) const override;
    [[nodiscard]] bool is_connected(NavigationTile tile, CardinalDirection direction) const override;
private:
    const SidewalkManager& sidewalks_;
};

enum class NavigationPathStatus { found, no_path };

struct NavigationPathResult {
    NavigationPathStatus status = NavigationPathStatus::no_path;
    std::vector<NavigationTile> tiles;
};

// Uniform-cost BFS. A network edge is one tile, so A* would not add useful
// behavior at the current map size.
[[nodiscard]] NavigationPathResult find_navigation_path(const NavigationNetwork& network,
                                                        NavigationTile start, NavigationTile goal);
