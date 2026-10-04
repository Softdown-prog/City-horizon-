#include "rail_articulated_consist.h"

#include <cmath>
#include <iostream>

namespace {
[[nodiscard]] int fail(const char* message) {
    std::cerr << "rail articulated consist regression failed: " << message << '\n';
    return 1;
}

[[nodiscard]] bool near(const double a, const double b, const double epsilon = 1.0e-6) {
    return std::abs(a - b) <= epsilon;
}
} // namespace

int main() {
    RailPlacementGraph graph;
    const auto root = graph.add_root({0.0F, 0.0F, 0.0F}, 0.0F);
    if (!root) return fail("root creation");

    RailPlacementNodeId cursor = *root;
    RailPlacementEdgeId start_edge = kInvalidRailPlacementEdgeId;
    for (int index = 0; index < 12; ++index) {
        const auto piece = graph.append_straight(cursor, 4.0F);
        if (!piece) return fail("straight chain creation");
        if (index == 0) start_edge = piece->edge;
        cursor = piece->node;
    }

    const ch::rail_operation::OperationalRoute route =
        ch::rail_operation::compile_route(graph, start_edge);
    if (!route.valid || route.length_m < 47.0) return fail("operational route compile");

    ch::rail_operation::TrainPose lead;
    lead.distance_m = 40.0;
    lead.speed_mps = 3.25;
    lead.x = 40.0;
    lead.tangent_x = 1.0;

    const auto consist = ch::rail_operation::build_articulated_consist_poses(route, lead);
    if (consist.size() != 8U) return fail("locomotive plus seven coaches expected");
    if (consist.front().kind != ch::rail_operation::ConsistUnitKind::locomotive ||
        consist.front().unit_index != 0U) {
        return fail("lead unit identity");
    }

    constexpr double first_center_gap = 5.2 * 0.5 + 0.42 + 3.9 * 0.5;
    constexpr double coach_pitch = 3.9 + 0.42;
    if (!near(consist[0].route_distance_m - consist[1].route_distance_m, first_center_gap)) {
        return fail("locomotive-to-first-coach spacing");
    }
    for (std::size_t index = 2U; index < consist.size(); ++index) {
        if (consist[index].kind != ch::rail_operation::ConsistUnitKind::passenger_coach ||
            consist[index].unit_index != index ||
            !near(consist[index - 1U].route_distance_m - consist[index].route_distance_m, coach_pitch)) {
            return fail("coach pitch or identity");
        }
    }

    for (const auto& unit : consist) {
        if (!near(unit.pose.x, unit.route_distance_m, 0.02) || !near(unit.pose.tangent_x, 1.0, 0.02)) {
            return fail("each unit must sample its own route position");
        }
    }

    lead.distance_m = 6.0;
    const auto entering = ch::rail_operation::build_articulated_consist_poses(route, lead);
    if (entering.empty() || entering.size() >= 8U) {
        return fail("open route should not stack off-route trailing coaches at origin");
    }

    std::cout << "rail articulated consist regression passed\n";
    return 0;
}
