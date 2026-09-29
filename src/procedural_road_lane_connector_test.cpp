#include "procedural_road_lane_connector.h"
#include "procedural_road_route_sampler.h"
#include "procedural_road_traffic.h"
#include "procedural_road_vehicle_follower.h"
#include "procedural_road_vehicle_render_adapter.h"

#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstddef>
#include <limits>
#include <vector>

namespace {

bool near_value(const float a, const float b, const float epsilon = 0.001F) {
    return std::fabs(a - b) <= epsilon;
}

float distance3(const RoadWorldPoint3& a, const RoadWorldPoint3& b) {
    const float dx = b.x - a.x;
    const float dy = b.y - a.y;
    const float dz = b.z - a.z;
    return std::sqrt(dx * dx + dy * dy + dz * dz);
}

void test_turn_classification() {
    assert(ProceduralRoadLaneConnectorBuilder::classify_turn({1.0F, 0.0F, 0.0F}, {1.0F, 0.0F, 0.0F}) ==
           ProceduralRoadTurnKind::straight);
    assert(ProceduralRoadLaneConnectorBuilder::classify_turn({1.0F, 0.0F, 0.0F}, {0.0F, 1.0F, 0.0F}) ==
           ProceduralRoadTurnKind::right);
    assert(ProceduralRoadLaneConnectorBuilder::classify_turn({1.0F, 0.0F, 0.0F}, {0.0F, -1.0F, 0.0F}) ==
           ProceduralRoadTurnKind::left);
    assert(ProceduralRoadLaneConnectorBuilder::classify_turn({1.0F, 0.0F, 0.0F}, {-1.0F, 0.0F, 0.0F}) ==
           ProceduralRoadTurnKind::u_turn);
}

void test_explicit_junction_connectors() {
    ProceduralRoadGraph graph;
    const auto west = graph.add_node({-4.0F, 0.0F, 1.25F});
    const auto center = graph.add_node({0.0F, 0.0F, 1.25F});
    const auto east = graph.add_node({4.0F, 0.0F, 1.25F});
    const auto south = graph.add_node({0.0F, 4.0F, 1.25F});
    const auto north = graph.add_node({0.0F, -4.0F, 1.25F});

    const auto incoming = graph.add_segment(west, center, {1.2F, 0.0F, 0.0F}, {-1.2F, 0.0F, 0.0F}, 0.80F, 2);
    const auto straight = graph.add_segment(center, east, {1.2F, 0.0F, 0.0F}, {-1.2F, 0.0F, 0.0F}, 0.80F, 2);
    const auto right = graph.add_segment(center, south, {0.0F, 1.2F, 0.0F}, {0.0F, -1.2F, 0.0F}, 0.80F, 2);
    const auto left = graph.add_segment(center, north, {0.0F, -1.2F, 0.0F}, {0.0F, 1.2F, 0.0F}, 0.80F, 2);
    assert(incoming && straight && right && left);

    const auto straight_connector = ProceduralRoadLaneConnectorBuilder::build(graph, center, *incoming, *straight, 0.18F);
    const auto right_connector = ProceduralRoadLaneConnectorBuilder::build(graph, center, *incoming, *right, 0.18F);
    const auto left_connector = ProceduralRoadLaneConnectorBuilder::build(graph, center, *incoming, *left, 0.18F);
    assert(straight_connector && right_connector && left_connector);
    assert(straight_connector->turn == ProceduralRoadTurnKind::straight);
    assert(right_connector->turn == ProceduralRoadTurnKind::right);
    assert(left_connector->turn == ProceduralRoadTurnKind::left);

    for (const auto* connector : {&*straight_connector, &*right_connector, &*left_connector}) {
        assert(near_value(connector->spline.start.z, 1.25F));
        assert(near_value(connector->spline.control_a.z, 1.25F));
        assert(near_value(connector->spline.control_b.z, 1.25F));
        assert(near_value(connector->spline.end.z, 1.25F));
        const auto samples = ProceduralRoadLaneConnectorBuilder::sample(*connector, 12);
        assert(samples.size() == 13U);
        assert(near_value(samples.front().position.z, 1.25F));
        assert(near_value(samples.back().position.z, 1.25F));
    }
}

std::vector<ProceduralRoadRoutePoint> build_sampled_vehicle_route() {
    ProceduralRoadGraph graph;
    const auto a = graph.add_node({-6.0F, 0.0F, 0.0F});
    const auto b = graph.add_node({0.0F, 0.0F, 0.75F});
    const auto c = graph.add_node({4.0F, 4.0F, 1.25F});
    const auto d = graph.add_node({10.0F, 4.0F, 1.25F});

    assert(graph.add_segment(a, b, {2.0F, 0.0F, 0.25F}, {-2.0F, 0.0F, -0.10F}, 0.82F, 2));
    assert(graph.add_segment(b, c, {1.5F, 0.8F, 0.15F}, {-1.0F, -1.4F, -0.15F}, 0.82F, 2));
    assert(graph.add_segment(c, d, {2.0F, 0.0F, 0.0F}, {-2.0F, 0.0F, 0.0F}, 0.82F, 2));

    const auto route = ProceduralRoadNavigator::find_route(graph, a, d);
    assert(route && route->segments.size() == 3U);
    const auto sampled = ProceduralRoadRouteSampler::sample_right_hand_route(graph, *route, 0.18F, 24, 12);
    assert(sampled && !sampled->empty());
    return *sampled;
}

std::vector<ProceduralRoadRoutePoint> build_straight_vehicle_route(const float z = 0.0F) {
    std::vector<ProceduralRoadRoutePoint> route;
    for (int step = 0; step <= 32; ++step) {
        route.push_back({{static_cast<float>(step) * 0.5F, 0.0F, z},
                         ProceduralRoadRoutePointKind::lane,
                         1,
                         kInvalidProceduralRoadNodeId,
                         ProceduralRoadTurnKind::straight});
    }
    return route;
}

std::vector<ProceduralRoadRoutePoint> build_crossing_vehicle_route(
    const bool horizontal,
    const ProceduralRoadNodeId junction_node = 77) {
    std::vector<ProceduralRoadRoutePoint> route;
    for (int step = 0; step <= 30; ++step) {
        const float coordinate = -3.0F + static_cast<float>(step) * 0.2F;
        const bool in_junction = std::fabs(coordinate) <= 0.4001F;
        route.push_back({
            horizontal ? RoadWorldPoint3{coordinate, 0.0F, 0.0F}
                       : RoadWorldPoint3{0.0F, coordinate, 0.0F},
            in_junction ? ProceduralRoadRoutePointKind::junction_connector
                        : ProceduralRoadRoutePointKind::lane,
            in_junction ? kInvalidProceduralRoadSegmentId
                        : static_cast<ProceduralRoadSegmentId>(horizontal ? 10 : 20),
            in_junction ? junction_node : kInvalidProceduralRoadNodeId,
            ProceduralRoadTurnKind::straight,
        });
    }
    return route;
}

ProceduralRoadVehicleVisual test_vehicle_visual() {
    ProceduralRoadVehicleVisual visual;
    visual.sprite_south = "south.png";
    visual.sprite_east = "east.png";
    visual.sprite_north = "north.png";
    visual.sprite_west = "west.png";
    visual.animation_set_id = "vehicle.test";
    visual.art_scale = 0.42F;
    visual.sprite_anchor_x = 0.50F;
    visual.sprite_anchor_y = 0.91F;
    return visual;
}

void test_continuous_route_across_two_junctions() {
    const auto sampled = build_sampled_vehicle_route();

    bool saw_first_junction = false;
    bool saw_second_junction = false;
    bool saw_elevated_point = false;
    float max_step = 0.0F;
    ProceduralRoadNodeId first_junction = kInvalidProceduralRoadNodeId;

    for (std::size_t index = 0; index < sampled.size(); ++index) {
        const auto& point = sampled[index];
        if (point.kind == ProceduralRoadRoutePointKind::junction_connector) {
            if (first_junction == kInvalidProceduralRoadNodeId) first_junction = point.junction_node;
            if (point.junction_node == first_junction) saw_first_junction = true;
            else saw_second_junction = true;
        }
        if (point.position.z > 1.0F) saw_elevated_point = true;
        if (index > 0U) max_step = std::max(max_step, distance3(sampled[index - 1U].position, point.position));
    }
    assert(saw_first_junction && saw_second_junction && saw_elevated_point);
    assert(max_step < 0.75F);
}

void test_vehicle_follower_moves_continuously_and_slows_for_turns() {
    ProceduralRoadVehicleFollower follower;
    assert(follower.set_route(build_sampled_vehicle_route()));
    assert(follower.valid());
    assert(!follower.pose().finished);

    ProceduralRoadVehicleFollowerConfig config;
    config.cruise_speed = 1.40F;
    config.junction_speed = 0.82F;
    config.turn_speed = 0.62F;
    config.acceleration = 2.0F;
    config.braking = 4.0F;

    float previous_distance = follower.pose().route_distance;
    bool saw_junction = false;
    bool saw_turn_cap = false;
    bool saw_elevation = false;
    int guard = 0;
    while (!follower.pose().finished && guard++ < 4000) {
        follower.update(0.05F, config);
        const auto& pose = follower.pose();
        assert(pose.route_distance + 0.0001F >= previous_distance);
        previous_distance = pose.route_distance;
        const float forward_length = std::sqrt(pose.forward.x * pose.forward.x + pose.forward.y * pose.forward.y + pose.forward.z * pose.forward.z);
        assert(std::fabs(forward_length - 1.0F) < 0.01F);
        if (pose.position.z > 1.0F) saw_elevation = true;
        if (pose.kind == ProceduralRoadRoutePointKind::junction_connector) {
            saw_junction = true;
            if (pose.turn != ProceduralRoadTurnKind::straight && pose.speed <= config.turn_speed + 0.001F) {
                saw_turn_cap = true;
            }
        }
    }

    assert(guard < 4000);
    assert(follower.pose().finished);
    assert(near_value(follower.pose().speed, 0.0F));
    assert(saw_junction && saw_turn_cap && saw_elevation);
    assert(near_value(follower.pose().route_distance, follower.pose().route_length, 0.001F));
}

void test_vehicle_follower_honors_external_speed_cap() {
    ProceduralRoadVehicleFollower follower;
    assert(follower.set_route(build_straight_vehicle_route()));
    ProceduralRoadVehicleFollowerConfig config;
    config.cruise_speed = 2.0F;
    config.acceleration = 10.0F;
    config.braking = 10.0F;

    follower.update(1.0F, config, 0.25F);
    assert(near_value(follower.pose().speed, 0.25F));
    assert(near_value(follower.pose().route_distance, 0.25F));
}

void test_vehicle_follower_reports_upcoming_junction() {
    ProceduralRoadVehicleFollower follower;
    assert(follower.set_route(build_crossing_vehicle_route(true, 91)));
    const auto upcoming = follower.upcoming_junction(3.0F);
    assert(upcoming);
    assert(upcoming->node_id == 91);
    assert(!upcoming->inside);
    assert(near_value(upcoming->distance, 2.6F, 0.01F));
}

void test_vehicle_render_adapter_preserves_pose_and_logical_direction() {
    assert(ProceduralRoadVehicleRenderAdapter::direction_from_forward({1.0F, 0.2F, 0.0F}) == MobileEntityDirection::east);
    assert(ProceduralRoadVehicleRenderAdapter::direction_from_forward({-1.0F, 0.2F, 0.0F}) == MobileEntityDirection::west);
    assert(ProceduralRoadVehicleRenderAdapter::direction_from_forward({0.2F, 1.0F, 0.0F}) == MobileEntityDirection::south);
    assert(ProceduralRoadVehicleRenderAdapter::direction_from_forward({0.2F, -1.0F, 0.0F}) == MobileEntityDirection::north);

    const ProceduralRoadVehicleVisual visual = test_vehicle_visual();
    ProceduralRoadVehiclePose pose;
    pose.position = {3.25F, 5.75F, 1.60F};
    pose.forward = {0.9F, 0.1F, 0.0F};
    pose.speed = 1.0F;

    const MobileEntityRenderData entity = ProceduralRoadVehicleRenderAdapter::make_render_data(pose, visual);
    assert(entity.spatial.direction == MobileEntityDirection::east);
    assert(entity.sprite_asset == "east.png");
    assert(entity.animation_set_id == "vehicle.test");
    assert(entity.logical_state == "moving");
    assert(near_value(entity.spatial.logical_world_x, 3.25F));
    assert(near_value(entity.spatial.logical_world_y, 5.75F));
    assert(near_value(entity.spatial.logical_world_z, 1.60F));
    assert(near_value(entity.spatial.visual_world_x, 3.25F));
    assert(near_value(entity.spatial.visual_world_y, 5.75F));
    assert(near_value(entity.spatial.visual_world_z, 1.60F));
    assert(entity.spatial.logical_tile_x == 3);
    assert(entity.spatial.logical_tile_y == 5);
    assert(near_value(entity.spatial.ground_anchor_x, 0.0F));
    assert(near_value(entity.spatial.ground_anchor_y, 0.0F));
    assert(near_value(entity.art_scale, 0.42F));
    assert(near_value(entity.sprite_anchor_y, 0.91F));
}

void test_procedural_traffic_manager_owns_and_renders_followers() {
    ProceduralRoadTrafficManager traffic;
    ProceduralRoadVehicleFollowerConfig config;
    config.cruise_speed = 1.45F;
    config.junction_speed = 0.82F;
    config.turn_speed = 0.62F;
    config.acceleration = 2.0F;
    config.braking = 4.0F;

    assert(traffic.add("car.1", build_sampled_vehicle_route(), test_vehicle_visual(), config));
    assert(!traffic.add("car.1", build_sampled_vehicle_route(), test_vehicle_visual(), config));
    assert(traffic.size() == 1U);
    assert(traffic.contains("car.1"));
    assert(traffic.find("car.1") != nullptr);

    auto render = traffic.render_entities();
    assert(render.size() == 1U);
    assert(render.front().logical_state == "stopped");
    assert(render.front().animation_set_id == "vehicle.test");

    traffic.update_tick(0.10F);
    render = traffic.render_entities();
    assert(render.front().logical_state == "moving");

    bool saw_elevation = false;
    int guard = 0;
    while (guard++ < 4000) {
        traffic.update_tick(0.05F);
        render = traffic.render_entities();
        assert(render.size() == 1U);
        if (render.front().spatial.visual_world_z > 1.0F) saw_elevation = true;
        const auto* instance = traffic.find("car.1");
        assert(instance != nullptr);
        if (instance->follower.pose().finished) break;
    }
    assert(guard < 4000);
    assert(saw_elevation);
    render = traffic.render_entities();
    assert(render.front().logical_state == "stopped");
    assert(traffic.remove("car.1"));
    assert(!traffic.remove("car.1"));
    assert(traffic.empty());
}

void test_procedural_traffic_follows_slower_leader_with_safe_gap() {
    ProceduralRoadTrafficManager traffic;
    ProceduralRoadTrafficFollowingConfig following;
    following.lookahead_distance = 3.0F;
    following.minimum_gap = 0.65F;
    following.time_headway = 0.85F;
    following.lane_tolerance = 0.20F;
    following.elevation_tolerance = 0.40F;
    traffic.set_following_config(following);

    ProceduralRoadVehicleFollowerConfig leader_config;
    leader_config.cruise_speed = 0.55F;
    leader_config.acceleration = 3.0F;
    leader_config.braking = 5.0F;

    ProceduralRoadVehicleFollowerConfig follower_config;
    follower_config.cruise_speed = 1.55F;
    follower_config.acceleration = 3.0F;
    follower_config.braking = 5.0F;

    assert(traffic.add("leader", build_straight_vehicle_route(), test_vehicle_visual(), leader_config));
    for (int step = 0; step < 70; ++step) traffic.update_tick(0.05F);
    const auto* leader_before_spawn = traffic.find("leader");
    assert(leader_before_spawn != nullptr);
    assert(leader_before_spawn->follower.pose().route_distance > 1.5F);

    assert(traffic.add("follower", build_straight_vehicle_route(), test_vehicle_visual(), follower_config));

    bool saw_leader = false;
    bool saw_speed_reduction = false;
    float minimum_observed_gap = std::numeric_limits<float>::infinity();
    for (int step = 0; step < 500; ++step) {
        traffic.update_tick(0.05F);
        const auto* leader = traffic.find("leader");
        const auto* follower = traffic.find("follower");
        assert(leader != nullptr && follower != nullptr);
        assert(follower->follower.pose().route_distance <= leader->follower.pose().route_distance + 0.05F);

        if (follower->leader_vehicle_id == "leader") {
            saw_leader = true;
            minimum_observed_gap = std::min(minimum_observed_gap, follower->leader_gap);
            if (follower->follower.pose().speed < follower_config.cruise_speed - 0.10F) {
                saw_speed_reduction = true;
            }
        }
        if (leader->follower.pose().route_distance > 9.0F) break;
    }

    assert(saw_leader);
    assert(saw_speed_reduction);
    assert(minimum_observed_gap >= following.minimum_gap - 0.10F);
}

void test_procedural_traffic_does_not_follow_vehicle_on_other_elevation() {
    ProceduralRoadTrafficManager traffic;
    ProceduralRoadTrafficFollowingConfig following;
    following.lookahead_distance = 4.0F;
    following.elevation_tolerance = 0.40F;
    traffic.set_following_config(following);

    ProceduralRoadVehicleFollowerConfig config;
    config.cruise_speed = 0.8F;
    config.acceleration = 3.0F;
    config.braking = 5.0F;

    assert(traffic.add("bridge", build_straight_vehicle_route(2.0F), test_vehicle_visual(), config));
    for (int step = 0; step < 50; ++step) traffic.update_tick(0.05F);
    assert(traffic.add("ground", build_straight_vehicle_route(0.0F), test_vehicle_visual(), config));
    traffic.update_tick(0.05F);

    const auto* ground = traffic.find("ground");
    assert(ground != nullptr);
    assert(ground->leader_vehicle_id.empty());
    assert(std::isinf(ground->leader_gap));
}

void test_procedural_traffic_reserves_shared_junction_without_overlap() {
    constexpr ProceduralRoadNodeId junction = 101;
    ProceduralRoadTrafficManager traffic;

    ProceduralRoadTrafficFollowingConfig following;
    following.enabled = false;
    traffic.set_following_config(following);

    ProceduralRoadJunctionReservationConfig junction_config;
    junction_config.request_lookahead = 3.0F;
    junction_config.stop_buffer = 0.25F;
    traffic.set_junction_reservation_config(junction_config);

    ProceduralRoadVehicleFollowerConfig movement;
    movement.cruise_speed = 1.0F;
    movement.junction_speed = 0.75F;
    movement.turn_speed = 0.70F;
    movement.acceleration = 4.0F;
    movement.braking = 4.0F;

    assert(traffic.add("car.a", build_crossing_vehicle_route(true, junction), test_vehicle_visual(), movement));
    assert(traffic.add("car.b", build_crossing_vehicle_route(false, junction), test_vehicle_visual(), movement));

    traffic.update_tick(0.05F);
    assert(traffic.junction_reservation_count() == 1U);
    assert(traffic.junction_owner(junction) == "car.a");
    const auto* initially_blocked = traffic.find("car.b");
    assert(initially_blocked != nullptr);
    assert(initially_blocked->blocked_junction == junction);

    bool saw_a_inside = false;
    bool saw_b_waiting = false;
    bool reservation_transferred = false;
    bool saw_b_inside = false;

    for (int step = 0; step < 600; ++step) {
        traffic.update_tick(0.05F);
        const auto* a = traffic.find("car.a");
        const auto* b = traffic.find("car.b");
        assert(a != nullptr && b != nullptr);

        const bool a_inside = a->follower.pose().kind == ProceduralRoadRoutePointKind::junction_connector;
        const bool b_inside = b->follower.pose().kind == ProceduralRoadRoutePointKind::junction_connector;
        assert(!(a_inside && b_inside));

        if (a_inside) {
            saw_a_inside = true;
            assert(traffic.junction_owner(junction) == "car.a");
        }
        if (b->blocked_junction == junction && b->follower.pose().speed < 0.10F) {
            saw_b_waiting = true;
        }
        if (traffic.junction_owner(junction) == "car.b") {
            reservation_transferred = true;
        }
        if (b_inside) {
            saw_b_inside = true;
            assert(traffic.junction_owner(junction) == "car.b");
            break;
        }
    }

    assert(saw_a_inside);
    assert(saw_b_waiting);
    assert(reservation_transferred);
    assert(saw_b_inside);
}

void test_reverse_route_is_continuous() {
    ProceduralRoadGraph graph;
    const auto west = graph.add_node({-4.0F, 0.0F, 0.0F});
    const auto center = graph.add_node({0.0F, 0.0F, 0.0F});
    const auto north = graph.add_node({0.0F, -4.0F, 0.0F});
    const auto first = graph.add_segment(west, center, {1.3F, 0.0F, 0.0F}, {-1.3F, 0.0F, 0.0F});
    const auto second = graph.add_segment(center, north, {0.0F, -1.3F, 0.0F}, {0.0F, 1.3F, 0.0F});
    assert(first && second);

    const auto route = ProceduralRoadNavigator::find_route(graph, north, west);
    assert(route);
    const auto sampled = ProceduralRoadRouteSampler::sample_right_hand_route(graph, *route, 0.18F, 20, 10);
    assert(sampled && !sampled->empty());
    bool has_connector = false;
    for (const auto& point : *sampled) {
        if (point.kind == ProceduralRoadRoutePointKind::junction_connector) has_connector = true;
    }
    assert(has_connector);
}

void test_geometric_crossing_does_not_connect() {
    ProceduralRoadGraph graph;
    const auto west = graph.add_node({-3.0F, 0.0F, 0.0F});
    const auto east = graph.add_node({3.0F, 0.0F, 0.0F});
    const auto north = graph.add_node({0.0F, -3.0F, 2.0F});
    const auto south = graph.add_node({0.0F, 3.0F, 2.0F});
    const auto ground = graph.add_segment(west, east, {1.0F, 0.0F, 0.0F}, {-1.0F, 0.0F, 0.0F});
    const auto bridge = graph.add_segment(north, south, {0.0F, 1.0F, 0.0F}, {0.0F, -1.0F, 0.0F});
    assert(ground && bridge);

    assert(!ProceduralRoadLaneConnectorBuilder::build(graph, west, *ground, *bridge, 0.18F));
    assert(!ProceduralRoadLaneConnectorBuilder::build(graph, north, *ground, *bridge, 0.18F));
    assert(!ProceduralRoadNavigator::find_route(graph, west, south));
}

} // namespace

int main() {
    test_turn_classification();
    test_explicit_junction_connectors();
    test_continuous_route_across_two_junctions();
    test_vehicle_follower_moves_continuously_and_slows_for_turns();
    test_vehicle_follower_honors_external_speed_cap();
    test_vehicle_follower_reports_upcoming_junction();
    test_vehicle_render_adapter_preserves_pose_and_logical_direction();
    test_procedural_traffic_manager_owns_and_renders_followers();
    test_procedural_traffic_follows_slower_leader_with_safe_gap();
    test_procedural_traffic_does_not_follow_vehicle_on_other_elevation();
    test_procedural_traffic_reserves_shared_junction_without_overlap();
    test_reverse_route_is_continuous();
    test_geometric_crossing_does_not_connect();
}
