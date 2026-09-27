#include "navigation_network.h"
#include "pedestrian_decision.h"
#include "pedestrian_system.h"
#include "road_system.h"
#include "sidewalk_system.h"

#include <cassert>
#include <filesystem>
#include <fstream>
#include <vector>

namespace {

PedestrianSystem make_pedestrian_system() {
    return PedestrianSystem{{"citizen_common", 0.45F, 0.5F, 0.88F}};
}

class CountingNavigationNetwork final : public NavigationNetwork {
public:
    explicit CountingNavigationNetwork(const NavigationNetwork& inner) : inner_(inner) {}

    [[nodiscard]] bool is_navigable(const NavigationTile tile) const override {
        ++query_count_;
        return inner_.is_navigable(tile);
    }

    [[nodiscard]] bool is_connected(const NavigationTile tile, const CardinalDirection direction) const override {
        ++query_count_;
        return inner_.is_connected(tile, direction);
    }

    void reset_query_count() { query_count_ = 0; }
    [[nodiscard]] std::size_t query_count() const { return query_count_; }

private:
    const NavigationNetwork& inner_;
    mutable std::size_t query_count_ = 0;
};

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
    assert(pedestrians.send_pedestrian({0, 0}, {2, 2}, network));
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
    assert(pedestrians.send_pedestrian({0, 0}, {2, 0}, network));
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
    assert(stranded.send_pedestrian({0, 0}, {2, 0}, broken_network));
    assert(broken_sidewalks.remove_tile(1, 0));
    stranded.update_tick(0.05F, broken_network);
    assert(stranded.instances().front().state == PedestrianState::idle);
    assert(stranded.instances().front().spatial.logical_tile_x == 0);
    assert(stranded.instances().front().spatial.logical_tile_y == 0);
}

void test_surface_turn_and_idle() {
    RoadManager roads{-8, 8};
    SidewalkManager sidewalks{-8, 8};
    assert(sidewalks.place_tile(0, 0, "cement_path"));
    assert(sidewalks.place_tile(1, 0, "sand_path"));
    assert(roads.place_tile(1, 1));
    PedestrianSurfaceNavigationNetwork network{roads, sidewalks};
    PedestrianSystem pedestrians = make_pedestrian_system();
    assert(pedestrians.send_pedestrian({0, 0}, {1, 1}, network));
    assert(!pedestrians.render_entities({}, true).front().umbrella.enabled);
    assert(pedestrians.instances().front().spatial.direction == MobileEntityDirection::east);
    pedestrians.update_tick(0.46F, network);
    assert(pedestrians.instances().front().spatial.direction == MobileEntityDirection::south);
    pedestrians.update_tick(0.46F, network);
    assert(pedestrians.instances().front().state == PedestrianState::idle);
    assert(pedestrians.send_pedestrian({1, 1}, {0, 0}, network));
    assert(pedestrians.instances().front().spatial.direction == MobileEntityDirection::north);
    pedestrians.clear();
    assert(pedestrians.instances().empty());
}

void test_visiting_state_blocks_reroute_and_faces_door() {
    RoadManager roads{-8, 8};
    SidewalkManager sidewalks{-8, 8};
    assert(sidewalks.place_tile(0, 0, "concrete_01"));
    assert(sidewalks.place_tile(1, 0, "concrete_01"));
    PedestrianSurfaceNavigationNetwork network{roads, sidewalks};

    PedestrianSystem pedestrians = make_pedestrian_system();
    assert(pedestrians.send_pedestrian({0, 0}, {1, 0}, network));
    advance_until_idle(pedestrians, network);

    const std::uint64_t id = pedestrians.instances().front().id;
    assert(pedestrians.face_pedestrian(id, MobileEntityDirection::north));
    assert(pedestrians.set_visiting(id, true));
    assert(pedestrians.instances().front().state == PedestrianState::visiting);
    assert(pedestrians.instances().front().spatial.direction == MobileEntityDirection::north);
    assert(!pedestrians.send_pedestrian({1, 0}, {0, 0}, network));

    assert(pedestrians.set_visiting(id, false));
    assert(pedestrians.instances().front().state == PedestrianState::idle);
    assert(pedestrians.send_pedestrian({1, 0}, {0, 0}, network));
    assert(pedestrians.instances().front().spatial.direction == MobileEntityDirection::west);
}

void test_clothing_is_chosen_once_per_actor_birth() {
    RoadManager roads{-8, 8};
    SidewalkManager sidewalks{-8, 8};
    for (int x = 0; x <= 2; ++x) assert(sidewalks.place_tile(x, 0, "cement_path"));
    PedestrianSurfaceNavigationNetwork network{roads, sidewalks};
    PedestrianSystem pedestrians{{"ch_actor_green_01", 1.0F, 0.5F, 60.0F / 64.0F}};
    assert(pedestrians.send_pedestrian({0, 0}, {2, 0}, network));
    const std::uint64_t born_id = pedestrians.instances().front().id;
    const MobileClothingTint born_outfit = pedestrians.render_entities({}).front().clothing;
    const MobileUmbrellaTint born_umbrella = pedestrians.render_entities({}, true).front().umbrella;
    assert(born_outfit.enabled);
    assert(born_umbrella.enabled);
    assert(born_umbrella.fabric != MobileClothingColor{});
    assert(!pedestrians.render_entities({}).front().umbrella.enabled);
    assert(born_outfit.jacket != MobileClothingColor{});
    assert(born_outfit.pants != MobileClothingColor{});
    advance_until_idle(pedestrians, network);
    assert(pedestrians.send_pedestrian({2, 0}, {0, 0}, network));
    assert(pedestrians.instances().front().id == born_id);
    assert(pedestrians.render_entities({}).front().clothing == born_outfit);
    assert(pedestrians.render_entities({}, true).front().umbrella.fabric == born_umbrella.fabric);
    advance_until_idle(pedestrians, network);
    assert(pedestrians.render_entities({}, true).front().umbrella.enabled);
    assert(pedestrians.set_visiting(born_id, true));
    assert(!pedestrians.render_entities({}, true).front().umbrella.enabled);
    assert(pedestrians.set_visiting(born_id, false));
    assert(pedestrians.rest_at_home({0, 0}));
    assert(pedestrians.render_entities({}).front().clothing == born_outfit);
    assert(!pedestrians.render_entities({}, true).front().umbrella.enabled);
    pedestrians.wake_up();
    assert(pedestrians.render_entities({}).front().clothing == born_outfit);
    assert(pedestrians.render_entities({}, true).front().umbrella.fabric == born_umbrella.fabric);
    pedestrians.clear();
    assert(pedestrians.send_pedestrian({0, 0}, {1, 0}, network));
    assert(pedestrians.instances().front().id != born_id);
}

void test_resident_leaves_and_returns_to_a_real_entrance() {
    const auto fixture = std::filesystem::temp_directory_path() / "ch_pedestrian_decision_fixture";
    std::filesystem::create_directories(fixture);
    {
        std::ofstream out(fixture / "house.json");
        out << R"({"id":"test_home","name":"Home","category":"residential","texture":"house.png",
            "footprint":{"width":3,"height":3},"residentialCapacity":4,
            "roadAccessMode":"front_edge","frontEdge":"south"})";
    }
    BuildingCatalog catalog;
    assert(catalog.load_from_directory(fixture));
    const BuildingDefinition* house = catalog.find("test_home");
    assert(house != nullptr);
    BuildingManager buildings{-12, 12};
    const auto id = buildings.place(*house, 0, 0);
    assert(id);
    RoadManager roads{-12, 12};
    SidewalkManager sidewalks{-12, 12};
    assert(sidewalks.place_tile(1, 3, "cement_path"));
    PedestrianSurfaceNavigationNetwork surface_network{roads, sidewalks};
    CountingNavigationNetwork network{surface_network};
    PedestrianSystem pedestrians = make_pedestrian_system();
    PedestrianDecisionNode decisions;
    decisions.update(0.25F, pedestrians, network, buildings, catalog, roads, sidewalks);
    assert(decisions.home_id() == id);
    assert(decisions.decision() == PedestrianDecision::resting_at_home);
    assert(pedestrians.instances().front().spatial.logical_tile_x == 1);
    assert(pedestrians.instances().front().spatial.logical_tile_y == 3);
    assert(pedestrians.render_entities({}).size() == 1); // bridge filters resting residents after visitors
    // With no outing available, the resident stays inside after each retry.
    for (int i = 0; i < 20; ++i) decisions.update(0.25F, pedestrians, network, buildings, catalog, roads, sidewalks);
    assert(pedestrians.instances().front().state == PedestrianState::resting);
    for (int y = 4; y <= 8; ++y) assert(sidewalks.place_tile(1, y, "cement_path"));
    // A rainy resident stays sheltered even when a walk is available.
    for (int i = 0; i < 40; ++i) {
        pedestrians.update_tick(0.25F, network);
        decisions.update(0.25F, pedestrians, network, buildings, catalog, roads, sidewalks, true);
        assert(decisions.decision() == PedestrianDecision::resting_at_home);
        assert(pedestrians.instances().front().state == PedestrianState::resting);
    }
    bool left = false;
    bool returned = false;
    for (int i = 0; i < 250; ++i) {
        pedestrians.update_tick(0.25F, network);
        decisions.update(0.25F, pedestrians, network, buildings, catalog, roads, sidewalks);
        left |= decisions.decision() == PedestrianDecision::walking_to_activity;
        returned |= decisions.decision() == PedestrianDecision::returning_home;
        if (left && returned && decisions.decision() == PedestrianDecision::resting_at_home) break;
    }
    assert(left && returned);
    assert(pedestrians.instances().front().state == PedestrianState::resting);
    assert(pedestrians.instances().front().spatial.logical_tile_y == 3);

    // Rain during an outing completes the current segment, then returns home;
    // clearing the weather permits another autonomous walk.
    for (int i = 0; i < 60; ++i) {
        pedestrians.update_tick(0.25F, network);
        decisions.update(0.25F, pedestrians, network, buildings, catalog, roads, sidewalks);
        if (decisions.decision() == PedestrianDecision::walking_to_activity) break;
    }
    assert(decisions.decision() == PedestrianDecision::walking_to_activity);

    // Decision work is event-driven while route execution is active. A walking
    // resident must not re-run home reachability/pathfinding on every movement tick.
    network.reset_query_count();
    decisions.update(0.25F, pedestrians, network, buildings, catalog, roads, sidewalks);
    assert(network.query_count() == 0);

    for (int i = 0; i < 80; ++i) {
        pedestrians.update_tick(0.25F, network);
        decisions.update(0.25F, pedestrians, network, buildings, catalog, roads, sidewalks, true);
        if (decisions.decision() == PedestrianDecision::resting_at_home) break;
    }
    assert(decisions.decision() == PedestrianDecision::resting_at_home);
    assert(pedestrians.instances().front().state == PedestrianState::resting);

    pedestrians.wake_up();
    const auto pedestrian_id = pedestrians.instances().front().id;
    assert(pedestrians.set_visiting(pedestrian_id, true));
    assert(!pedestrians.rest_at_home({1, 3}));
    decisions.update(10.0F, pedestrians, network, buildings, catalog, roads, sidewalks);
    assert(pedestrians.instances().front().state == PedestrianState::visiting);
    assert(pedestrians.set_visiting(pedestrian_id, false));
    assert(pedestrians.rest_at_home({1, 3}));

    assert(buildings.remove_instance(*house, *id));
    decisions.update(0.25F, pedestrians, network, buildings, catalog, roads, sidewalks);
    assert(!decisions.home_id());
    assert(pedestrians.instances().front().state != PedestrianState::resting);
    std::filesystem::remove_all(fixture);
}

} // namespace

int main() {
    test_sidewalk_route_and_turns();
    test_demolition_replans_once_then_stops_safely();
    test_surface_turn_and_idle();
    test_resident_leaves_and_returns_to_a_real_entrance();
    test_visiting_state_blocks_reroute_and_faces_door();
    test_clothing_is_chosen_once_per_actor_birth();
}
