#include "rail_two_service.h"
#include "rail_live_operation_controller.h"
#include "rail_block_dispatcher.h"

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
    // The dispatcher leases every piece under the train and ahead of its
    // locomotive; a second train must never take even one conflicting block.
    const auto first_route = ch::rail_two_service::find_route(
        graph, city.stations, 0U, city.fleet.coach_count);
    const auto second_route = ch::rail_two_service::find_route(
        graph, city.stations, 2U, city.secondary_fleet.coach_count);
    if (!first_route || !second_route) return fail("dispatcher routes unavailable");
    ch::rail_dispatch::BlockDispatcher dispatcher;
    const double at_first_a = first_route->stations.front().distance_m;
    const double at_second_a = second_route->stations.front().distance_m;
    const auto first_block = first_route->graph_route.steps.front().piece;
    const auto second_block = second_route->graph_route.steps.at(10U).piece;
    if (!dispatcher.acquire(1U, *first_route, at_first_a, 7U) ||
        !dispatcher.acquire(2U, *second_route, at_second_a, 2U) ||
        dispatcher.reserved_count(1U) == 0U ||
        dispatcher.reserved_count(2U) == 0U)
        return fail("two disjoint consists not granted authority");
    const std::size_t previous = dispatcher.reserved_count(1U);
    const std::size_t second_previous = dispatcher.reserved_count(2U);
    if (dispatcher.acquire(2U, *first_route, at_first_a, 2U) ||
        dispatcher.reserved_count(1U) != previous ||
        dispatcher.reserved_count(2U) != second_previous ||
        !dispatcher.owned_by(2U, second_block) ||
        dispatcher.acquire(1U, *first_route, -1.0, 7U))
        return fail("conflicting or invalid block grant changed ownership");

    // The old A-section is only released once the tail passes it. Other
    // vehicles can then acquire that section without evicting train 1.
    if (!dispatcher.acquire(1U, *first_route, 175.0, 7U) ||
        dispatcher.owned_by(1U, first_block))
        return fail("occupied sections not released after last coach");
    if (!dispatcher.acquire_entire_route(1U, *first_route) ||
        !dispatcher.owned_by(1U, first_block) ||
        dispatcher.acquire(2U, *first_route, at_first_a, 2U))
        return fail("decoupling failed to protect full main-line route");
    dispatcher.release(1U);
    if (dispatcher.reserved_count(1U) != 0U ||
        !dispatcher.acquire(2U, *first_route, at_first_a, 2U) ||
        !dispatcher.owned_by(2U, first_block) ||
        dispatcher.reserved(second_block))
        return fail("old authority not transferred atomically after release");
    dispatcher.clear();
    if (dispatcher.reserved_count(2U) != 0U)
        return fail("block leases leaked across city reset");

    // Four named stops are the supported dispatch boundary. A fifth would
    // silently become an unassigned station and confuse the purchase order.
    if (first.toggle_station(graph.edges()[5].piece_group, 0.5))
        return fail("a fifth station marker was accepted");

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
    // Automatic station aspects must track occupied, approaching and clear
    // positions, and fail safely while a train is shunting.
    using ch::rail_signals::Aspect;
    if (ch::rail_signals::station_aspect(true, 50.0, 50.0, 2U) != Aspect::stop ||
        ch::rail_signals::station_aspect(true, 50.0, 35.0, 2U) != Aspect::approach ||
        ch::rail_signals::station_aspect(true, 50.0, 10.0, 2U) != Aspect::clear ||
        ch::rail_signals::station_aspect(false, 50.0, 10.0, 2U) != Aspect::stop ||
        ch::rail_signals::station_aspect(true, 50.0, 10.0, 2U, true) != Aspect::stop)
        return fail("automatic station signal aspect regression");

    const ch::track::Point3 a{0,0,0}, b{20,0,0};
    if (!ch::rail_signals::same_level_segment_conflict(a,b,{10,-10,0},{10,10,0}) ||
        ch::rail_signals::same_level_segment_conflict(a,b,{10,-10,5},{10,10,5}) ||
        ch::rail_signals::same_level_segment_conflict(a,b,{10,10,0},{10,20,0}))
        return fail("same-level crossing, overpass or separated segment test");

    // Crossing tracks can be separate topological pieces but still collide
    // physically. A crossing on the same grade must remain unpurchasable until
    // an actual track block dispatcher and railway crossing are authored.
    RailPlacementGraph crossing_graph;
    std::vector<RailPersistentStation> crossing_stops;
    for (int line = 0; line != 2; ++line) {
        const auto root = crossing_graph.add_root(
            line == 0 ? RailWorldPoint3{0,0,0} : RailWorldPoint3{100,-100,0},
            line == 0 ? 0.0F : 1.57079632679F);
        if (!root) return fail("crossing test track root");
        auto cursor = *root;
        for (int i = 0; i < 48; ++i) {
            const auto segment = crossing_graph.append_straight(cursor, 4.0F, 12);
            if (!segment) return fail("crossing test track segment");
            if (i == 11 || i == 35) crossing_stops.push_back({
                crossing_graph.edges()[segment->edge].piece_group, 0.25});
            cursor = segment->node;
        }
    }
    const auto crossing_first = ch::rail_two_service::find_route(
        crossing_graph, crossing_stops, 0U, 7U);
    const auto crossing_second = ch::rail_two_service::find_route(
        crossing_graph, crossing_stops, 2U, 2U);
    if (!crossing_first || !crossing_second ||
        ch::rail_two_service::routes_share_track(*crossing_first, *crossing_second) ||
        !ch::rail_signals::routes_cross_at_grade(*crossing_first, *crossing_second) ||
        ch::rail_two_service::second_route_safe(
            crossing_graph, crossing_stops, 7U, 2U))
        return fail("topologically independent at-grade crossing was not interlocked");

    std::cout << "CH_RAIL_TWO_INDEPENDENT_SERVICES_V1: PASS\n";
}
