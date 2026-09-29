#include "procedural_road_class_policy.h"
#include "procedural_road_classified_route.h"
#include "procedural_road_vehicle_follower.h"

#include <cassert>
#include <cmath>
#include <vector>

namespace {

bool near_value(const float a, const float b, const float epsilon = 0.001F) {
    return std::fabs(a - b) <= epsilon;
}

std::vector<ProceduralRoadRoutePoint> straight_classified_route(const ProceduralRoadClass road_class) {
    std::vector<ProceduralRoadRoutePoint> route;
    ProceduralRoadRoutePoint a;
    a.position = {0.0F, 0.0F, 0.0F};
    a.road_class = road_class;
    route.push_back(a);

    ProceduralRoadRoutePoint b;
    b.position = {10.0F, 0.0F, 0.0F};
    b.road_class = road_class;
    route.push_back(b);
    return route;
}

void test_class_catalog_defaults_and_profiles() {
    ProceduralRoadGraph graph;
    const auto a = graph.add_node({0.0F, 0.0F, 0.0F});
    const auto b = graph.add_node({4.0F, 0.0F, 0.0F});
    const auto segment = graph.add_segment(a, b);
    assert(segment);

    ProceduralRoadClassCatalog classes;
    assert(classes.road_class(graph, *segment) == ProceduralRoadClass::local);
    assert(!classes.has_explicit_class(*segment));
    assert(classes.assign(graph, *segment, ProceduralRoadClass::collector));
    assert(classes.has_explicit_class(*segment));
    assert(classes.road_class(graph, *segment) == ProceduralRoadClass::collector);
    assert(!classes.assign(graph, kInvalidProceduralRoadSegmentId, ProceduralRoadClass::arterial));
    assert(!classes.assign(graph, *segment, ProceduralRoadClass::unspecified));

    assert(near_value(procedural_road_class_profile(ProceduralRoadClass::local).speed_limit, 1.35F));
    assert(near_value(procedural_road_class_profile(ProceduralRoadClass::collector).speed_limit, 1.70F));
    assert(near_value(procedural_road_class_profile(ProceduralRoadClass::arterial).speed_limit, 2.10F));
    assert(procedural_road_class_profile(ProceduralRoadClass::arterial).priority_rank >
           procedural_road_class_profile(ProceduralRoadClass::collector).priority_rank);
    assert(procedural_road_class_profile(ProceduralRoadClass::collector).priority_rank >
           procedural_road_class_profile(ProceduralRoadClass::local).priority_rank);
}

void test_class_annotation_preserves_approach_through_junction() {
    ProceduralRoadGraph graph;
    const auto west = graph.add_node({-4.0F, 0.0F, 0.0F});
    const auto center = graph.add_node({0.0F, 0.0F, 0.0F});
    const auto east = graph.add_node({4.0F, 0.0F, 0.0F});
    const auto incoming = graph.add_segment(west, center);
    const auto outgoing = graph.add_segment(center, east);
    assert(incoming && outgoing);

    ProceduralRoadClassCatalog classes;
    assert(classes.assign(graph, *incoming, ProceduralRoadClass::arterial));
    assert(classes.assign(graph, *outgoing, ProceduralRoadClass::collector));

    std::vector<ProceduralRoadRoutePoint> route(3);
    route[0].position = {-1.0F, 0.0F, 0.0F};
    route[0].segment_id = *incoming;
    route[1].position = {0.0F, 0.0F, 0.0F};
    route[1].kind = ProceduralRoadRoutePointKind::junction_connector;
    route[1].junction_node = center;
    route[2].position = {1.0F, 0.0F, 0.0F};
    route[2].segment_id = *outgoing;

    ProceduralRoadClassifiedRouteSampler::annotate(graph, classes, route);
    assert(route[0].road_class == ProceduralRoadClass::arterial);
    assert(route[1].road_class == ProceduralRoadClass::arterial);
    assert(route[2].road_class == ProceduralRoadClass::collector);
}

void test_follower_honors_road_class_speed_limits() {
    ProceduralRoadVehicleFollowerConfig movement;
    movement.cruise_speed = 3.0F;
    movement.acceleration = 10.0F;
    movement.braking = 10.0F;
    movement.junction_speed = 3.0F;
    movement.turn_speed = 3.0F;

    ProceduralRoadVehicleFollower local;
    ProceduralRoadVehicleFollower collector;
    ProceduralRoadVehicleFollower arterial;
    assert(local.set_route(straight_classified_route(ProceduralRoadClass::local)));
    assert(collector.set_route(straight_classified_route(ProceduralRoadClass::collector)));
    assert(arterial.set_route(straight_classified_route(ProceduralRoadClass::arterial)));

    local.update(1.0F, movement);
    collector.update(1.0F, movement);
    arterial.update(1.0F, movement);

    assert(near_value(local.pose().speed, 1.35F));
    assert(near_value(collector.pose().speed, 1.70F));
    assert(near_value(arterial.pose().speed, 2.10F));
    assert(local.pose().road_class == ProceduralRoadClass::local);
    assert(collector.pose().road_class == ProceduralRoadClass::collector);
    assert(arterial.pose().road_class == ProceduralRoadClass::arterial);
}

void test_junction_policy_is_derived_from_connected_road_classes() {
    ProceduralRoadGraph graph;
    const auto center = graph.add_node({0.0F, 0.0F, 0.0F});
    const auto west = graph.add_node({-4.0F, 0.0F, 0.0F});
    const auto east = graph.add_node({4.0F, 0.0F, 0.0F});
    const auto north = graph.add_node({0.0F, -4.0F, 0.0F});
    const auto south = graph.add_node({0.0F, 4.0F, 0.0F});

    const auto west_arm = graph.add_segment(west, center, {1.2F, 0.0F, 0.0F}, {-1.2F, 0.0F, 0.0F});
    const auto east_arm = graph.add_segment(center, east, {1.2F, 0.0F, 0.0F}, {-1.2F, 0.0F, 0.0F});
    const auto north_arm = graph.add_segment(north, center, {0.0F, 1.2F, 0.0F}, {0.0F, -1.2F, 0.0F});
    const auto south_arm = graph.add_segment(center, south, {0.0F, 1.2F, 0.0F}, {0.0F, -1.2F, 0.0F});
    assert(west_arm && east_arm && north_arm && south_arm);

    ProceduralRoadClassCatalog classes;
    assert(classes.assign(graph, *west_arm, ProceduralRoadClass::arterial));
    assert(classes.assign(graph, *east_arm, ProceduralRoadClass::arterial));
    // North/South remain the catalog default: local.

    ProceduralRoadTrafficManager traffic;
    assert(ProceduralRoadClassPolicyBuilder::apply_all_junction_policies(graph, classes, traffic) == 1U);

    const auto* policy = traffic.junction_priority_policy(center);
    assert(policy != nullptr);
    assert(policy->east_west == ProceduralRoadApproachControl::priority);
    assert(policy->north_south == ProceduralRoadApproachControl::yield);

    // Raising the perpendicular road to the same class removes the automatic
    // class advantage and returns the node to equal-priority arbitration.
    assert(classes.assign(graph, *north_arm, ProceduralRoadClass::arterial));
    assert(classes.assign(graph, *south_arm, ProceduralRoadClass::arterial));
    assert(ProceduralRoadClassPolicyBuilder::apply_junction_policy(graph, classes, center, traffic));
    policy = traffic.junction_priority_policy(center);
    assert(policy != nullptr);
    assert(policy->east_west == ProceduralRoadApproachControl::priority);
    assert(policy->north_south == ProceduralRoadApproachControl::priority);
}

} // namespace

int main() {
    test_class_catalog_defaults_and_profiles();
    test_class_annotation_preserves_approach_through_junction();
    test_follower_honors_road_class_speed_limits();
    test_junction_policy_is_derived_from_connected_road_classes();
}
