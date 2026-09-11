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

} // namespace

int main() {
    test_roads();
    test_sidewalks();
}
