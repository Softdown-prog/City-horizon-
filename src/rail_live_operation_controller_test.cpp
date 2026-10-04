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

    if (graph.remove_piece(station_group) == 0U) return fail("station piece demolition setup");
    state.nodes = graph.nodes();
    state.edges = graph.edges();
    if (!controller.sync_from_persistent_state(state)) return fail("post-demolition graph sync");
    if (!controller.stations().empty() || controller.operation_active()) {
        return fail("demolished station must be removed from live operation");
    }

    std::cout << "rail live operation regression passed\n";
    return 0;
}
