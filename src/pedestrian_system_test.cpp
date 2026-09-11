#include "navigation_network.h"
#include "pedestrian_system.h"
#include "road_system.h"
#include "sidewalk_system.h"

#include <cassert>
#include <vector>

namespace {

PedestrianSystem make_pedestrian_system() {
    return PedestrianSystem{{"citizen_common", 0.45F, 0.5F, 0.88F}};
}

void advance_until_idle(PedestrianSystem& pedestrians, const NavigationNetwork& network) {
    for (int tick = 0; tick < 32 && pedestrians.instances().front().state == PedestrianState::walking; ++tick) {
        pedestrians.update_tick(0.25F, network);
        pedestrians.interpolate_visual(1.0F / 60.0F);
    }
}

void test_sidewalk_route_and_turns() {
    RoadManager roads{-8, 8};
    SidewalkManager sidewalks{-8, 8};
    SidewalkNavigationNetwork network{sidewalks};
    const std::vector<NavigationTile> tiles = {{0, 0}, {1, 0}, {2, 0}, {2, 1}, {2, 2}, {1, 1}};
    for (const NavigationTile tile : tiles) {
        assert(sidewalks.place_tile(tile.x, tile.y, "concrete_01"));
    }

    PedestrianSystem pedestrians = make_pedestrian_system();
    assert(pedestrians.send_test_pedestrian({0, 0}, {2, 2}, network));
    assert(pedestrians.instances().front().state == PedestrianState::walking);
    assert(pedestrians.instances().front().spatial.direction == MobileEntityDirection::east);
    advance_until_idle(pedestrians, network);
    const PedestrianInstance& pedestrian = pedestrians.instances().front();
    assert(pedestrian.state == PedestrianState::idle);
    assert(pedestrian.spatial.logical_tile_x == 2 && pedestrian.spatial.logical_tile_y == 2);
    assert(pedestrian.spatial.direction == MobileEntityDirection::south);
}

void test_demolition_replans_once_then_stops_safely() {
    RoadManager roads{-8, 8};
    SidewalkManager sidewalks{-8, 8};
    SidewalkNavigationNetwork network{sidewalks};
    // Two alternatives connect the same endpoints. Removing the upper middle
    // forces a live replan onto the lower branch.
    const std::vector<NavigationTile> tiles = {{0, 0}, {1, 0}, {2, 0}, {0, 1}, {1, 1}, {2, 1}};
    for (const NavigationTile tile : tiles) {
        assert(sidewalks.place_tile(tile.x, tile.y, "concrete_01"));
    }
    PedestrianSystem pedestrians = make_pedestrian_system();
    assert(pedestrians.send_test_pedestrian({0, 0}, {2, 0}, network));
    assert(sidewalks.remove_tile(1, 0));
    pedestrians.update_tick(0.05F, network);
    assert(pedestrians.instances().front().state == PedestrianState::walking);
    assert(pedestrians.instances().front().replanned_after_network_change);
    advance_until_idle(pedestrians, network);
    assert(pedestrians.instances().front().spatial.logical_tile_x == 2);
    assert(pedestrians.instances().front().spatial.logical_tile_y == 0);

    // No alternative means no crossing of the removed tile and an idle stop.
    SidewalkManager broken_sidewalks{-8, 8};
    SidewalkNavigationNetwork broken_network{broken_sidewalks};
    assert(broken_sidewalks.place_tile(0, 0, "concrete_01"));
    assert(broken_sidewalks.place_tile(1, 0, "concrete_01"));
    assert(broken_sidewalks.place_tile(2, 0, "concrete_01"));
    PedestrianSystem stranded = make_pedestrian_system();
    assert(stranded.send_test_pedestrian({0, 0}, {2, 0}, broken_network));
    assert(broken_sidewalks.remove_tile(1, 0));
    stranded.update_tick(0.05F, broken_network);
    assert(stranded.instances().front().state == PedestrianState::idle);
    assert(stranded.instances().front().spatial.logical_tile_x == 0);
    assert(stranded.instances().front().spatial.logical_tile_y == 0);
}

} // namespace

int main() {
    test_sidewalk_route_and_turns();
    test_demolition_replans_once_then_stops_safely();
}
