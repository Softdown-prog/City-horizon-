#include "rail_operation_runtime.h"

#include <cmath>
#include <iostream>

namespace {

[[nodiscard]] bool near(const double a, const double b, const double tolerance = 1.0e-6) {
    return std::abs(a - b) <= tolerance;
}

[[nodiscard]] int fail(const char* message) {
    std::cerr << "rail operation regression failed: " << message << '\n';
    return 1;
}

} // namespace

int main() {
    RailPlacementGraph graph;
    const auto root = graph.add_root({0.0F, 0.0F, 0.0F}, 0.0F);
    if (!root) return fail("root creation");

    const auto first = graph.append_straight(*root, 4.0F, 16);
    const auto station_piece = first ? graph.append_straight(first->node, 4.0F, 16) : std::nullopt;
    const auto last = station_piece ? graph.append_straight(station_piece->node, 4.0F, 16) : std::nullopt;
    if (!first || !station_piece || !last) return fail("three-piece line creation");

    const RailPlacementPieceId station_group = graph.edges()[station_piece->edge].piece_group;
    const ch::rail_operation::OperationalRoute route = ch::rail_operation::compile_route(
        graph, first->edge, {{station_group, 2.0}});
    if (!route.valid || route.closed || route.stations.size() != 1U) {
        return fail("open operational route with one station");
    }
    if (!near(route.length_m, 12.0, 1.0e-4) ||
        !near(route.stations.front().distance_m, 6.0, 1.0e-4) ||
        !near(route.stations.front().dwell_seconds, 2.0)) {
        return fail("station stop distance and route length");
    }

    ch::rail_operation::TrainRuntime train(route);
    train.set_cruise_speed_mps(4.0);
    train.set_acceleration_mps2(20.0);
    if (!train.valid()) return fail("train accepts operational route");

    train.update(1.0);
    if (!near(train.distance_m(), 4.0, 1.0e-4)) return fail("train advances continuously");
    train.update(1.0);
    const auto station_pose = train.pose();
    if (!station_pose || !station_pose->dwelling || !station_pose->station_piece ||
        *station_pose->station_piece != station_group || !near(train.distance_m(), 6.0, 1.0e-4) ||
        !near(train.speed_mps(), 0.0)) {
        return fail("train stops at station midpoint");
    }

    train.update(1.0);
    if (!train.pose() || !train.pose()->dwelling || !near(train.distance_m(), 6.0, 1.0e-4)) {
        return fail("station dwell holds train");
    }
    train.update(1.0);
    if (!(train.distance_m() > 6.0) || train.pose()->dwelling) {
        return fail("train departs after dwell");
    }

    train.update(10.0);
    if (!train.stopped() || !near(train.distance_m(), route.length_m, 1.0e-4) ||
        !near(train.speed_mps(), 0.0)) {
        return fail("open route stops at terminal gap");
    }


    // An operational open A/B service must start AT station A with enough
    // rear clearance for locomotive + seven coaches, and park exactly at B.
    RailPlacementGraph ab_graph;
    const auto ab_root = ab_graph.add_root({0.0F, 12.0F, 0.0F}, 0.0F);
    if (!ab_root) return fail("A/B root");
    RailPlacementNodeId ab_cursor = *ab_root;
    RailPlacementEdgeId ab_first = kInvalidRailPlacementEdgeId;
    RailPlacementPieceId a_id = kInvalidRailPlacementPieceId;
    RailPlacementPieceId b_id = kInvalidRailPlacementPieceId;
    for (int i = 0; i < 48; ++i) {
        const auto part = ab_graph.append_straight(ab_cursor, 4.0F, 12);
        if (!part) return fail("A/B track construction");
        if (i == 0) ab_first = part->edge;
        if (i == 11) a_id = ab_graph.edges()[part->edge].piece_group;
        if (i == 35) b_id = ab_graph.edges()[part->edge].piece_group;
        ab_cursor = part->node;
    }
    const auto ab_route = ch::rail_operation::compile_route(
        ab_graph, ab_first, {{a_id, 0.5}, {b_id, 1.0}});
    if (!ab_route.valid || ab_route.stations.size() != 2U || ab_route.closed)
        return fail("A/B route compilation");
    ch::rail_operation::TrainRuntime ab_train;
    if (!ab_train.set_route(ab_route) || !ab_train.configure_terminal_pair() ||
        !ab_train.terminal_pair_enabled()) return fail("two-terminal route activation");
    const auto start_at_a = ab_train.pose();
    if (!start_at_a || !near(start_at_a->distance_m, ab_route.stations[0].distance_m) ||
        !start_at_a->dwelling || start_at_a->station_piece != a_id ||
        !near(ab_train.speed_mps(), 0.0)) {
        return fail("service must begin at station A, not the track origin");
    }
    bool reached_b = false;
    for (int frame = 0; frame < 1500; ++frame) {
        ab_train.update(0.1);
        const auto p = ab_train.pose();
        if (!p || p->distance_m < ab_route.stations[0].distance_m - 1.0e-5 ||
            p->distance_m > ab_route.stations[1].distance_m + 1.0e-5) {
            return fail("service escaped station bounds");
        }
        if (ab_train.awaiting_terminal_maneuver()) {
            if (!near(p->distance_m, ab_route.stations[1].distance_m) ||
                p->station_piece != b_id || ab_train.speed_mps() != 0.0)
                return fail("parked B terminal does not preserve position");
            reached_b = true;
            break;
        }
    }
    if (!reached_b || !ab_train.stopped()) return fail("service never parked at B");
    for (int frame = 0; frame < 40; ++frame) {
        ab_train.update(0.1);
        if (!near(ab_train.distance_m(), ab_route.stations[1].distance_m) ||
            !ab_train.awaiting_terminal_maneuver()) {
            return fail("terminal train moved without a physical return route");
        }
    }
    ab_train.reset();
    if (!near(ab_train.distance_m(), ab_route.stations[0].distance_m) ||
        ab_train.awaiting_terminal_maneuver()) return fail("terminal restart at A");

    // Reject configurations that cannot fit all seven coaches behind A.
    RailPlacementGraph short_graph;
    const auto short_root = short_graph.add_root({0.0F, 20.0F, 0.0F}, 0.0F);
    if (!short_root) return fail("short root");
    auto short_cursor = *short_root;
    RailPlacementEdgeId short_first = kInvalidRailPlacementEdgeId;
    RailPlacementPieceId short_a = kInvalidRailPlacementPieceId;
    RailPlacementPieceId short_b = kInvalidRailPlacementPieceId;
    for (int i=0;i<22;++i) {
        const auto part=short_graph.append_straight(short_cursor, 4.0F, 12);
        if (!part) return fail("short graph");
        if (i == 0)short_first=part->edge;
        if (i == 1)short_a=short_graph.edges()[part->edge].piece_group;
        if (i == 18)short_b=short_graph.edges()[part->edge].piece_group;
        short_cursor=part->node;
    }
    const auto short_route=ch::rail_operation::compile_route(
        short_graph,short_first,{{short_a,0.0},{short_b,0.0}});
    ch::rail_operation::TrainRuntime invalid_terminal;
    if (!short_route.valid || !invalid_terminal.set_route(short_route) ||
        invalid_terminal.configure_terminal_pair() || invalid_terminal.terminal_pair_enabled())
        return fail("insufficient seven-coach staging clearance accepted");
    // Legacy open one-station train should retain its existing behavior.
    if (train.terminal_pair_enabled()) return fail("legacy train changed to terminal mode");

    RailPlacementGraph tombstoned = graph;
    if (tombstoned.remove_piece(station_group) != 1U) return fail("station piece tombstone");
    const ch::rail_operation::OperationalRoute invalid_station = ch::rail_operation::compile_route(
        tombstoned, first->edge, {{station_group, 2.0}});
    if (invalid_station.valid) return fail("tombstoned station cannot be scheduled");

    const ch::rail_operation::OperationalRoute no_station =
        ch::rail_operation::compile_route(graph, first->edge, {});
    if (!no_station.valid || !no_station.stations.empty()) return fail("station metadata remains optional");

    std::cout << "CH_RAIL_OPERATION_RUNTIME_V1: OK\n";
    return 0;
}
