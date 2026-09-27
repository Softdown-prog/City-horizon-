#include "navigation_network.h"
#include "park_fence_runtime.h"

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

    assert(roads.place_tile(0, 0));
    assert(roads.place_tile(-1, 0));
    assert(roads.place_tile(1, 0));
    assert(roads.place_tile(0, -1));
    assert(roads.place_tile(0, 1));
    assert(network.can_move({0, 0}, CardinalDirection::east));
    assert(network.can_move({1, 0}, CardinalDirection::west));
    assert_path(find_navigation_path(network, {-1, 0}, {0, 1}), {-1, 0}, {0, 1}, 3);

    assert(roads.place_tile(3, 0));
    assert(roads.place_tile(4, 0));
    assert(roads.place_tile(4, 1));
    assert_path(find_navigation_path(network, {3, 0}, {4, 1}), {3, 0}, {4, 1}, 3);

    assert(roads.place_tile(7, 7));
    assert(find_navigation_path(network, {7, 7}, {0, 0}).status == NavigationPathStatus::no_path);

    assert(roads.remove_tile(0, 0));
    assert(find_navigation_path(network, {-1, 0}, {0, 1}).status == NavigationPathStatus::no_path);
}

void test_pedestrian_lanes_derive_from_roads() {
    RoadManager roads{-8, 8};
    PedestrianLaneNavigationNetwork pedestrians{roads};
    for (int x = 0; x < 6; ++x) assert(roads.place_tile(x, 0));

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
    assert(!network.is_navigable({2, 1}));
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

void test_fenced_destination_requires_walkable_gate() {
    park_fence_runtime::fences().clear();
    park_fence_runtime::clear_segment_styles();

    RoadManager roads{-8, 8};
    SidewalkManager sidewalks{-8, 8};
    BuildingManager buildings{-8, 8};
    for (int y = 0; y <= 2; ++y) {
        for (int x = 0; x <= 4; ++x) {
            assert(sidewalks.place_tile(x, y, "concrete_01"));
        }
    }

    const std::vector<FenceVertex> perimeter = {
        {2, 0}, {3, 0}, {4, 0}, {4, 1}, {4, 2}, {3, 2}, {2, 2}, {2, 1},
    };
    for (const FenceVertex vertex : perimeter) {
        assert(park_fence_runtime::fences().place_node(vertex.x, vertex.y));
    }

    park_fence_runtime::PedestrianCollisionNavigationNetwork network{roads, sidewalks, buildings};
    const NavigationTile start{0, 1};
    const NavigationTile target{3, 1};
    assert(find_navigation_path(network, start, target).status == NavigationPathStatus::no_path);

    const FenceVertex gate_from{2, 1};
    const FenceVertex gate_to{2, 2};
    assert(park_fence_runtime::fences().set_open_gate(gate_from, gate_to));
    const auto crossing = park_fence_runtime::fences().open_gate_crossing(gate_from, gate_to);
    assert(crossing);
    assert(crossing->first.x == 1 && crossing->first.y == 1);
    assert(crossing->second.x == 2 && crossing->second.y == 1);

    const NavigationPathResult through_gate = find_navigation_path(network, start, target);
    assert(through_gate.status == NavigationPathStatus::found);
    bool used_gate = false;
    for (std::size_t index = 1; index < through_gate.tiles.size(); ++index) {
        if (through_gate.tiles[index - 1] == NavigationTile{1, 1} &&
            through_gate.tiles[index] == NavigationTile{2, 1}) {
            used_gate = true;
            break;
        }
    }
    assert(used_gate);

    assert(sidewalks.remove_tile(2, 1));
    assert(!network.is_connected({1, 1}, CardinalDirection::east));
    assert(find_navigation_path(network, start, target).status == NavigationPathStatus::no_path);

    park_fence_runtime::fences().clear();
}

void test_building_occupancy_blocks_pedestrian_tile() {
    park_fence_runtime::fences().clear();
    RoadManager roads{-8, 8};
    SidewalkManager sidewalks{-8, 8};
    BuildingManager buildings{-8, 8};
    for (int y = 0; y <= 2; ++y) {
        for (int x = 0; x <= 4; ++x) {
            assert(sidewalks.place_tile(x, y, "concrete_01"));
        }
    }

    BuildingDefinition definition;
    definition.id = "collision_test_building";
    definition.footprint_width = 1;
    definition.footprint_height = 1;
    assert(buildings.place(definition, 2, 1));

    park_fence_runtime::PedestrianCollisionNavigationNetwork network{roads, sidewalks, buildings};
    assert(!network.is_navigable({2, 1}));
    const NavigationPathResult route = find_navigation_path(network, {0, 1}, {4, 1});
    assert(route.status == NavigationPathStatus::found);
    for (const NavigationTile tile : route.tiles) assert(!(tile == NavigationTile{2, 1}));
}

} // namespace

int main() {
    test_roads();
    test_pedestrian_lanes_derive_from_roads();
    test_sidewalks();
    test_pedestrian_surface_route();
    test_patrol_follows_corner_without_grass();
    test_fenced_destination_requires_walkable_gate();
    test_building_occupancy_blocks_pedestrian_tile();
}
