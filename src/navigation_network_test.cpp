#include "crosswalk_system.h"
#include "navigation_network.h"
#include "park_fence_runtime.h"
#include "procedural_road_junction.h"

#include <cassert>
#include <cmath>

namespace {

void assert_path(const NavigationPathResult& result, const NavigationTile start, const NavigationTile goal,
                 const std::size_t expected_length) {
    assert(result.status == NavigationPathStatus::found);
    assert(result.tiles.size() == expected_length);
    assert(result.tiles.front() == start);
    assert(result.tiles.back() == goal);
}

bool near_value(const float left, const float right, const float epsilon = 0.0001F) {
    return std::fabs(left - right) <= epsilon;
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

void test_procedural_road_graph_and_junctions() {
    ProceduralRoadGraph graph;
    const ProceduralRoadNodeId center = graph.add_node({0.0F, 0.0F, 0.50F});
    const ProceduralRoadNodeId east = graph.add_node({4.0F, 0.0F, 0.50F});
    const ProceduralRoadNodeId west = graph.add_node({-4.0F, 0.0F, 0.50F});
    const ProceduralRoadNodeId north = graph.add_node({0.0F, -4.0F, 0.50F});

    const auto east_segment = graph.add_segment(center, east, {1.0F, 0.0F, 0.0F}, {-1.0F, 0.0F, 0.0F}, 0.80F, 2);
    const auto west_segment = graph.add_segment(center, west, {-1.0F, 0.0F, 0.0F}, {1.0F, 0.0F, 0.0F}, 0.80F, 2);
    const auto north_segment = graph.add_segment(center, north, {0.0F, -1.0F, 0.0F}, {0.0F, 1.0F, 0.0F}, 0.80F, 2);
    assert(east_segment && west_segment && north_segment);
    assert(graph.degree(center) == 3U);
    assert(RoadJunctionBuilder::classify(graph, center) == ProceduralRoadJunctionKind::tee);

    const RoadMesh tee_patch = RoadJunctionBuilder::build_patch(graph, center);
    assert(!tee_patch.empty());
    assert(tee_patch.vertices.size() == 7U); // center + two boundaries per arm
    assert(tee_patch.indices.size() == 18U);
    for (const RoadMeshVertex& vertex : tee_patch.vertices) assert(near_value(vertex.position.z, 0.50F));

    const auto before_move = graph.spline_for(*east_segment);
    assert(before_move);
    assert(near_value(before_move->start.x, 0.0F));
    assert(near_value(before_move->control_a.x, 1.0F));

    assert(graph.set_node_position(center, {0.50F, 0.25F, 1.25F}));
    const auto after_move = graph.spline_for(*east_segment);
    assert(after_move);
    assert(near_value(after_move->start.x, 0.50F));
    assert(near_value(after_move->start.y, 0.25F));
    assert(near_value(after_move->start.z, 1.25F));
    assert(near_value(after_move->control_a.x, 1.50F));
    assert(near_value(after_move->control_a.y, 0.25F));
    assert(near_value(after_move->control_a.z, 1.25F));

    const ProceduralRoadNodeId south = graph.add_node({0.50F, 4.0F, 1.25F});
    const auto south_segment = graph.add_segment(center, south, {0.0F, 1.0F, 0.0F}, {0.0F, -1.0F, 0.0F}, 0.90F, 2);
    assert(south_segment);
    assert(graph.degree(center) == 4U);
    assert(RoadJunctionBuilder::classify(graph, center) == ProceduralRoadJunctionKind::intersection);
    const RoadMesh cross_patch = RoadJunctionBuilder::build_patch(graph, center);
    assert(!cross_patch.empty());
    assert(cross_patch.vertices.size() == 9U);
    assert(cross_patch.indices.size() == 24U);
    for (const RoadMeshVertex& vertex : cross_patch.vertices) assert(near_value(vertex.position.z, 1.25F));

    // Geometric crossing is not topology. These two independent roads cross at
    // XY=(0,0) but share no node, so they remain two degree-1 segments. This is
    // the invariant that allows a future viaduct to pass over a ground road.
    ProceduralRoadGraph crossing_graph;
    const auto left = crossing_graph.add_node({-3.0F, 0.0F, 0.0F});
    const auto right = crossing_graph.add_node({3.0F, 0.0F, 0.0F});
    const auto top = crossing_graph.add_node({0.0F, -3.0F, 2.0F});
    const auto bottom = crossing_graph.add_node({0.0F, 3.0F, 2.0F});
    assert(crossing_graph.add_segment(left, right, {1.0F, 0.0F, 0.0F}, {-1.0F, 0.0F, 0.0F}));
    assert(crossing_graph.add_segment(top, bottom, {0.0F, 1.0F, 0.0F}, {0.0F, -1.0F, 0.0F}));
    assert(crossing_graph.degree(left) == 1U);
    assert(crossing_graph.degree(right) == 1U);
    assert(crossing_graph.degree(top) == 1U);
    assert(crossing_graph.degree(bottom) == 1U);
    assert(RoadJunctionBuilder::classify(crossing_graph, left) == ProceduralRoadJunctionKind::end);
    assert(RoadJunctionBuilder::build_patch(crossing_graph, left).empty());

    const ProceduralRoadNodeId highest_before_remove = south;
    assert(graph.remove_node(center));
    assert(graph.segments().empty());
    const ProceduralRoadNodeId replacement = graph.add_node({8.0F, 8.0F, 0.0F});
    assert(replacement > highest_before_remove); // compacting storage never reuses stable IDs
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
    assert(sidewalks.place_tile(1, 0, "concrete_01"));
    assert(sidewalks.place_tile(1, 2, "concrete_01"));
    assert(roads.place_tile(1, 1));

    PedestrianSurfaceNavigationNetwork floors{roads, sidewalks};
    assert(!floors.is_navigable({1, 1}));
    assert(find_navigation_path(floors, {1, 0}, {1, 2}).status == NavigationPathStatus::no_path);

    CrosswalkManager crosswalks{-8, 8};
    PedestrianCrosswalkNavigationNetwork crossings{roads, sidewalks, crosswalks};
    assert(find_navigation_path(crossings, {1, 0}, {1, 2}).status == NavigationPathStatus::no_path);
    assert(crosswalks.place(1, 1, CrosswalkAxis::north_south, roads));
    assert(crosswalks.is_active_portal(1, 1, sidewalks));
    assert_path(find_navigation_path(crossings, {1, 0}, {1, 2}), {1, 0}, {1, 2}, 3);
    assert(crossings.can_move({1, 0}, CardinalDirection::south));
    assert(!crossings.can_move({1, 1}, CardinalDirection::east));

    assert(sidewalks.remove_tile(1, 2));
    assert(!crosswalks.is_active_portal(1, 1, sidewalks));
    assert(find_navigation_path(crossings, {1, 0}, {1, 2}).status == NavigationPathStatus::no_path);
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
    test_procedural_road_graph_and_junctions();
    test_pedestrian_lanes_derive_from_roads();
    test_sidewalks();
    test_pedestrian_surface_route();
    test_patrol_follows_corner_without_grass();
    test_fenced_destination_requires_walkable_gate();
    test_building_occupancy_blocks_pedestrian_tile();
}
