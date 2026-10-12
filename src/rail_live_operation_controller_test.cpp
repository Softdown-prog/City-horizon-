#include "rail_live_operation_controller.h"

#include <iostream>

namespace {

[[nodiscard]] int fail(const char* message) {
    std::cerr << "rail live operation regression failed: " << message << '\n';
    return 1;
}

} // namespace

int main() {
    RailPlacementGraph graph;
    const auto root = graph.add_root({0.0F, 0.0F, 0.0F}, 0.0F);
    const auto first = root ? graph.append_straight(*root, 4.0F) : std::nullopt;
    const auto second = first ? graph.append_straight(first->node, 4.0F) : std::nullopt;
    const auto third = second ? graph.append_straight(second->node, 4.0F) : std::nullopt;
    if (!root || !first || !second || !third) return fail("track chain creation");

    RailPersistentState state;
    state.nodes = graph.nodes();
    state.edges = graph.edges();

    ch::rail_live_operation::LiveOperationController controller;
    if (!controller.sync_from_persistent_state(state)) return fail("initial graph sync");
    if (controller.operation_active()) return fail("train should require a station");

    const RailPlacementPieceId station_group = graph.edges()[second->edge].piece_group;
    if (!controller.toggle_station(station_group, 0.5)) return fail("station designation");
    if (!controller.operation_active() || controller.stations().size() != 1U) {
        return fail("station should activate operational route");
    }
    if (ch::rail_persistence::runtime_stations().size() != 1U ||
        ch::rail_persistence::runtime_stations()[0].piece_group != station_group ||
        ch::rail_persistence::runtime_stations()[0].dwell_seconds != 0.5) {
        return fail("station designation must publish persistent operation state");
    }

    bool observed_movement = false;
    bool observed_dwell = false;
    for (int step = 0; step < 200; ++step) {
        controller.update(0.1);
        const auto pose = controller.train_pose();
        if (!pose) return fail("train pose missing");
        if (pose->distance_m > 0.05) observed_movement = true;
        if (pose->dwelling && pose->station_piece == station_group) {
            observed_dwell = true;
            break;
        }
    }
    if (!observed_movement) return fail("train never moved");
    if (!observed_dwell) return fail("train never dwelled at designated station");

    if (!controller.restart()) return fail("train restart");
    const auto restarted = controller.train_pose();
    if (!restarted || restarted->distance_m != 0.0 || restarted->speed_mps != 0.0) {
        return fail("restart should return train to route origin");
    }

    // Simulate save/load by restoring a fresh controller from the station row.
    state.stations = ch::rail_persistence::runtime_stations();
    ch::rail_live_operation::LiveOperationController restored_controller;
    if (!restored_controller.sync_from_persistent_state(state)) return fail("station restore from persistent state");
    if (!restored_controller.operation_active() || restored_controller.stations().size() != 1U ||
        restored_controller.stations()[0].piece_group != station_group ||
        restored_controller.stations()[0].dwell_seconds != 0.5) {
        return fail("loaded station must recreate operational route");
    }


    // Integration: persistent station markers A and B activate one shared
    // 1+7-coach service. It must stop at B rather than reverse or overshoot.
    RailPlacementGraph service_graph;
    const auto service_root = service_graph.add_root({0.0F, 30.0F, 0.0F}, 0.0F);
    if (!service_root) return fail("two-station service root");
    RailPlacementNodeId service_cursor = *service_root;
    RailPlacementPieceId service_a = kInvalidRailPlacementPieceId;
    RailPlacementPieceId service_b = kInvalidRailPlacementPieceId;
    for (int i = 0; i < 48; ++i) {
        const auto part = service_graph.append_straight(service_cursor, 4.0F, 12);
        if (!part) return fail("two-station service graph");
        if (i == 11) service_a = service_graph.edges()[part->edge].piece_group;
        if (i == 35) service_b = service_graph.edges()[part->edge].piece_group;
        service_cursor = part->node;
    }
    RailPersistentState service_state;
    service_state.nodes = service_graph.nodes();
    service_state.edges = service_graph.edges();
    service_state.stations = {{service_a, 0.3}, {service_b, 0.5}};
    ch::rail_live_operation::LiveOperationController pair_controller;
    if (!pair_controller.sync_from_persistent_state(service_state) ||
        !pair_controller.operation_active() || !pair_controller.two_station_service_active()) {
        return fail("two valid stations did not activate service");
    }
    const auto* service_route = pair_controller.operational_route();
    const auto initial_pose = pair_controller.train_pose();
    if (!service_route || service_route->stations.size() != 2U ||
        !initial_pose || !initial_pose->station_piece ||
        *initial_pose->station_piece != service_a ||
        std::abs(initial_pose->distance_m - service_route->stations.front().distance_m) > 1e-4) {
        return fail("train did not spawn at station A");
    }
    bool terminal_parked = false;
    for (int i = 0; i < 1000; ++i) {
        pair_controller.update(0.1);
        if (!pair_controller.awaiting_terminal_maneuver()) continue;
        const auto pose = pair_controller.train_pose();
        if (!pose || pose->station_piece != service_b || pose->speed_mps != 0.0 ||
            std::abs(pose->distance_m-service_route->stations.back().distance_m) > 1e-4) {
            return fail("station B parking state invalid");
        }
        terminal_parked = true;
        break;
    }
    if (!terminal_parked) return fail("A/B operation never reached station B");
    if (!pair_controller.restart() || !pair_controller.two_station_service_active() ||
        pair_controller.awaiting_terminal_maneuver() ||
        !pair_controller.train_pose() ||
        pair_controller.train_pose()->station_piece != service_a) {
        return fail("A/B restart did not reset to station A");
    }
    // Reject very short platform approach without inventing off-map wagons.
    service_state.stations = {{service_graph.edges()[1].piece_group,0.5},{service_b,0.5}};
    ch::rail_live_operation::LiveOperationController short_controller;
    if (short_controller.sync_from_persistent_state(service_state) &&
        short_controller.two_station_service_active()) {
        return fail("short platform approach incorrectly activated");
    }

    if (graph.remove_piece(station_group) == 0U) return fail("station piece demolition setup");
    state.nodes = graph.nodes();
    state.edges = graph.edges();
    state.stations.clear();
    if (!controller.sync_from_persistent_state(state)) return fail("post-demolition graph sync");
    if (!controller.stations().empty() || controller.operation_active()) {
        return fail("demolished station must be removed from live operation");
    }

    std::cout << "rail live operation regression passed\n";
    return 0;
}
