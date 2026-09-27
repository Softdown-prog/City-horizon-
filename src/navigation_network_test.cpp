#include "navigation_network.h"

#include <cassert>

namespace {

void assert_path(const NavigationPathResult& result, const NavigationTile start, const NavigationTile goal,
                 const std::size_t expected_length) {
    assert(result.status == NavigationPathStatus::found);
    assert(result.tiles.size() == expected_length);
    assert(result.tiles.front() == start);
    assert(result.tiles.back() == goal);
}

void test_roads() {
    RoadManager roads{-8, 8};
    RoadNavigationNetwork network{roads};

    // A four-way crossing proves straight runs, T branches and reciprocal
    // traversal through the shared center.
    assert(roads.place_tile(0, 0));
    assert(roads.place_tile(-1, 0));
    assert(roads.place_tile(1, 0));
    assert(roads.place_tile(0, -1));
    assert(roads.place_tile(0, 1));
    assert(network.can_move({0, 0}, CardinalDirection::east));
    assert(network.can_move({1, 0}, CardinalDirection::west));
    assert_path(find_navigation_path(network, {-1, 0}, {0, 1}), {-1, 0}, {0, 1}, 3);

    // A separate L validates a curve, rather than merely a crossing.
    assert(roads.place_tile(3, 0));
    assert(roads.place_tile(4, 0));
    assert(roads.place_tile(4, 1));
    assert_path(find_navigation_path(network, {3, 0}, {4, 1}), {3, 0}, {4, 1}, 3);

    assert(roads.place_tile(7, 7));
    assert(find_navigation_path(network, {7, 7}, {0, 0}).status == NavigationPathStatus::no_path);

    // The current live topology is queried for each search: removing the
    // centre immediately makes the former crossing inaccessible.
    assert(roads.remove_tile(0, 0));
    assert(find_navigation_path(network, {-1, 0}, {0, 1}).status == NavigationPathStatus::no_path);
}

void test_pedestrian_lanes_derive_from_roads() {
    RoadManager roads{-8, 8};
    PedestrianLaneNavigationNetwork pedestrians{roads};
    for (int x = 0; x < 6; ++x) assert(roads.place_tile(x, 0));

    // No SidewalkManager data is required: the same N/E/S/W mask that carries
    // vehicles exposes a separate pedestrian-lane graph for the renderer.
    assert(pedestrians.can_move({0, 0}, CardinalDirection::east));
    assert_path(find_navigation_path(pedestrians, {0, 0}, {5, 0}), {0, 0}, {5, 0}, 6);
    assert(roads.remove_tile(3, 0));
    assert(find_navigation_path(pedestrians, {0, 0}, {5, 0}).status == NavigationPathStatus::no_path);
}

void test_sidewalks() {
    RoadManager roads{-8, 8};
    SidewalkManager sidewalks{-8, 8};
    SidewalkNavigationNetwork network{sidewalks};

    assert(sidewalks.place_tile(0, 0, "concrete_01"));
    assert(sidewalks.place_tile(-1, 0, "concrete_01"));
    assert(sidewalks.place_tile(1, 0, "concrete_01"));
    assert(sidewalks.place_tile(0, -1, "concrete_01"));
    assert(sidewalks.place_tile(0, 1, "concrete_01"));
    assert(network.can_move({0, 0}, CardinalDirection::north));
    assert(network.can_move({0, -1}, CardinalDirection::south));
    assert_path(find_navigation_path(network, {-1, 0}, {1, 0}), {-1, 0}, {1, 0}, 3);

    assert(sidewalks.place_tile(3, 0, "concrete_01"));
    assert(sidewalks.place_tile(4, 0, "concrete_01"));
    assert(sidewalks.place_tile(4, 1, "concrete_01"));
    assert_path(find_navigation_path(network, {3, 0}, {4, 1}), {3, 0}, {4, 1}, 3);

    assert(sidewalks.place_tile(7, 7, "concrete_01"));
    assert(find_navigation_path(network, {7, 7}, {0, 0}).status == NavigationPathStatus::no_path);

    assert(sidewalks.remove_tile(0, 0));
    assert(find_navigation_path(network, {-1, 0}, {1, 0}).status == NavigationPathStatus::no_path);
}

void test_pedestrian_surface_route() {
    RoadManager roads{-8, 8};
    SidewalkManager sidewalks{-8, 8};
    assert(sidewalks.place_tile(0, 0, "cement_path"));
    assert(sidewalks.place_tile(1, 0, "sand_path"));
    assert(sidewalks.place_tile(2, 0, "dirt_path"));
    assert(roads.place_tile(3, 0));
    assert(roads.place_tile(3, 1));
    assert(sidewalks.place_tile(2, 1, "grass"));
    PedestrianSurfaceNavigationNetwork network{roads, sidewalks};
    assert_path(find_navigation_path(network, {0, 0}, {3, 1}), {0, 0}, {3, 1}, 5);
    assert(network.can_move({1, 0}, CardinalDirection::east));
    assert(!network.is_navigable({2, 1})); // grass is not a route
    assert(!network.can_move({2, 0}, CardinalDirection::south));
    assert(sidewalks.remove_tile(1, 0));
    assert(find_navigation_path(network, {0, 0}, {3, 1}).status == NavigationPathStatus::no_path);
}

void test_patrol_follows_corner_without_grass() {
    RoadManager roads{-8, 8};
    SidewalkManager sidewalks{-8, 8};
    for (const NavigationTile tile : {NavigationTile{0, 0}, {1, 0}, {2, 0}, {2, 1}, {2, 2}, {3, 2}}) {
        assert(sidewalks.place_tile(tile.x, tile.y, "sand_path"));
    }
    PedestrianSurfaceNavigationNetwork network{roads, sidewalks};
    const auto route = find_navigation_path_with_minimum_length(network, {0, 0}, 6);
    assert_path(route, {0, 0}, {3, 2}, 6);
    assert(find_navigation_path_with_minimum_length(network, {0, 0}, 7).status == NavigationPathStatus::no_path);
    assert(!network.is_navigable({3, 1}));
}

} // namespace

int main() {
    test_roads();
    test_pedestrian_lanes_derive_from_roads();
    test_sidewalks();
    test_pedestrian_surface_route();
    test_patrol_follows_corner_without_grass();
}
