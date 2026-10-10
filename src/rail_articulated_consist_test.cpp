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

    // On a curve the rigid body sits between the two on-track bogies.
    const auto bend=graph.append_quarter_curve(cursor,7.0F,RailTurnDirection::left,48);
    if (!bend) return fail("cannot append bend");
    const auto curved=ch::rail_operation::compile_route(graph,start_edge);
    if (!curved.valid) return fail("cannot compile bent route");
    bool inward_offset=false;
    for (double d=49.0;d<curved.length_m-1.0;d+=0.35) {
        lead.distance_m=d;
        const auto train=ch::rail_operation::build_articulated_consist_poses(curved,lead);
        for (const auto& unit : train) {
            const double len=unit.kind==ch::rail_operation::ConsistUnitKind::locomotive?5.2:3.9;
            const double bogie=len*ch::rail_operation::kRailBogieHalfWheelbaseRatio;
            const auto f=ch::rail_operation::sample_operational_route_pose(
                curved,unit.route_distance_m+bogie);
            const auto b=ch::rail_operation::sample_operational_route_pose(
                curved,unit.route_distance_m-bogie);
            if (!f || !b) continue;
            if (!near(unit.pose.x,(f->x+b->x)*0.5,1e-5) ||
                !near(unit.pose.y,(f->y+b->y)*0.5,1e-5))
                return fail("bogie-centred chassis expected");
            const auto center=ch::rail_operation::sample_operational_route_pose(
                curved,unit.route_distance_m);
            if (center && std::hypot(unit.pose.x-center->x,
                                     unit.pose.y-center->y)>0.01)
                inward_offset=true;
            const double dx=f->x-b->x,dy=f->y-b->y;
            if ((dx*unit.pose.tangent_x+dy*unit.pose.tangent_y) /
                std::hypot(dx,dy) < 0.999) return fail("chassis yaw does not match bogies");
        }
        for (std::size_t i=1;i<train.size();++i) {
            const auto& a=train[i-1]; const auto& b=train[i];
            const double alen=a.kind==ch::rail_operation::ConsistUnitKind::locomotive?5.2:3.9;
            const double x1=a.pose.x-a.pose.tangent_x*alen*0.5;
            const double y1=a.pose.y-a.pose.tangent_y*alen*0.5;
            const double x2=b.pose.x+b.pose.tangent_x*1.95;
            const double y2=b.pose.y+b.pose.tangent_y*1.95;
            if (std::hypot(x1-x2,y1-y2)>0.75)
                return fail("couplers separate on curve");
        }
    }
    if (!inward_offset) return fail("no bogie chord offset on tight curve");

    std::cout << "rail articulated consist regression passed\n";
    return 0;
}
