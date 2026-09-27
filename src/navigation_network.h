#pragma once

#include "road_system.h"
#include "sidewalk_system.h"

#include <cstddef>
#include <vector>

class CrosswalkManager;

struct NavigationTile {
    int x = 0;
    int y = 0;

    [[nodiscard]] constexpr bool operator==(const NavigationTile&) const = default;
};

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

// Legacy road pedestrian adapter retained for focused compatibility tests only.
class PedestrianLaneNavigationNetwork final : public NavigationNetwork {
public:
    explicit PedestrianLaneNavigationNetwork(const RoadManager& roads) : roads_(roads) {}
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

// CH_PEDESTRIAN_SURFACE_V2: ordinary roads are not pedestrian surfaces.
// Walkable authored floor/path styles form the pedestrian graph. A road may be
// entered only through PedestrianCrosswalkNavigationNetwork below.
class PedestrianSurfaceNavigationNetwork final : public NavigationNetwork {
public:
    PedestrianSurfaceNavigationNetwork(const RoadManager& roads, const SidewalkManager& sidewalks)
        : roads_(roads), sidewalks_(sidewalks) {}
    [[nodiscard]] bool is_navigable(NavigationTile tile) const override;
    [[nodiscard]] bool is_connected(NavigationTile tile, CardinalDirection direction) const override;
private:
    const RoadManager& roads_;
    const SidewalkManager& sidewalks_;
};

// Adds explicit road-crossing portals to the pedestrian graph. Crosswalk road
// cells are traversable only along their authored crossing axis, never along
// the traffic lane. The portal is active only when walkable pedestrian floor
// exists on both sides of the road.
class PedestrianCrosswalkNavigationNetwork final : public NavigationNetwork {
public:
    PedestrianCrosswalkNavigationNetwork(const RoadManager& roads,
                                         const SidewalkManager& sidewalks,
                                         const CrosswalkManager& crosswalks)
        : surfaces_(roads, sidewalks), roads_(roads), sidewalks_(sidewalks), crosswalks_(crosswalks) {}
    [[nodiscard]] bool is_navigable(NavigationTile tile) const override;
    [[nodiscard]] bool is_connected(NavigationTile tile, CardinalDirection direction) const override;
private:
    PedestrianSurfaceNavigationNetwork surfaces_;
    const RoadManager& roads_;
    const SidewalkManager& sidewalks_;
    const CrosswalkManager& crosswalks_;
};

enum class NavigationPathStatus { found, no_path };

struct NavigationPathResult {
    NavigationPathStatus status = NavigationPathStatus::no_path;
    std::vector<NavigationTile> tiles;
};

[[nodiscard]] NavigationPathResult find_navigation_path(const NavigationNetwork& network,
                                                        NavigationTile start, NavigationTile goal);
[[nodiscard]] NavigationPathResult find_navigation_path_with_minimum_length(
    const NavigationNetwork& network, NavigationTile start, std::size_t minimum_tiles);
