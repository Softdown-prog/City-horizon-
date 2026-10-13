#include "rail_two_service.h"
#include "rail_live_operation_controller.h"

#include <cmath>
#include <iostream>

namespace {
int fail(const char* text) { std::cerr << "Rail two-service regression: " << text << '\n'; return 1; }
}

int main() {
    RailPlacementGraph graph;
    RailPersistentState city;
    for (int line = 0; line < 2; ++line) {
        const auto root = graph.add_root({0.0F, static_cast<float>(line * 30), 0.0F}, 0.0F);
        if (!root) return fail("independent rail root");
        auto cursor = *root;
        for (int i = 0; i < 48; ++i) {
            const auto piece = graph.append_straight(cursor, 4.0F, 12);
            if (!piece) return fail("independent rail segment");
            const auto group = graph.edges()[piece->edge].piece_group;
            if (i == 11 || i == 35) city.stations.push_back({group, 0.25});
            city.actions.push_back({group, 500, 325, true});
            cursor = piece->node;
        }
    }
    city.nodes = graph.nodes();
    city.edges = graph.edges();
    city.fleet = {true, 7U};
    city.secondary_fleet = {true, 2U};
    if (!ch::rail_persistence::validate(city)) return fail("two-service city payload");
    if (!ch::rail_two_service::second_route_safe(
            graph, city.stations, city.fleet.coach_count, city.secondary_fleet.coach_count))
        return fail("independent A1/B1 and A2/B2 routes not qualified");

    ch::rail_live_operation::LiveOperationController first;
    ch::rail_two_service::AuxiliaryService second;
    if (!first.sync_from_persistent_state(city) ||
        !second.sync_from_state(city) ||
        !first.operation_active() || !second.active() ||
        first.articulated_poses().size() != 8U ||
        second.articulated_poses().size() != 3U)
        return fail("both purchased consists not visible");
    const auto initial = second.articulated_poses();
    for (int t = 0; t < 120; ++t) {
        first.update(0.1);
        second.update(0.1);
    }
    const auto moved = second.articulated_poses();
    if (moved.size() != 3U ||
        std::abs(moved.front().pose.x - initial.front().pose.x) < 0.01)
        return fail("second service did not advance independently");

    RailPersistentState recovered;
    const auto encoded = ch::rail_persistence::serialize_payload(city);
    if (!ch::rail_persistence::deserialize_payload(encoded, recovered) ||
        recovered.secondary_fleet.coach_count != 2U ||
        !recovered.secondary_fleet.locomotive_owned ||
        !second.sync_from_state(recovered) || !second.active())
        return fail("paid second train lost on save/load");

    city.stations[2] = city.stations[0];
    city.stations[3] = city.stations[1];
    if (ch::rail_two_service::second_route_safe(
            graph, city.stations, city.fleet.coach_count, city.secondary_fleet.coach_count))
        return fail("same-track second service incorrectly dispatched");
    city.secondary_fleet = {false, 0U};
    if (!second.sync_from_state(city) || second.active() ||
        !second.articulated_poses().empty())
        return fail("unowned second locomotive spawned");
    std::cout << "CH_RAIL_TWO_INDEPENDENT_SERVICES_V1: PASS\n";
}
