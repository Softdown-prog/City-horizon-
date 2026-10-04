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
