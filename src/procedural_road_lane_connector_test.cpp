#include "procedural_road_lane_connector.h"
#include "procedural_road_route_sampler.h"
#include "procedural_road_vehicle_follower.h"
#include "procedural_road_vehicle_render_adapter.h"

#include <cassert>
#include <cmath>
#include <cstddef>

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

void test_vehicle_render_adapter_preserves_pose_and_logical_direction() {
    assert(ProceduralRoadVehicleRenderAdapter::direction_from_forward({1.0F, 0.2F, 0.0F}) == MobileEntityDirection::east);
    assert(ProceduralRoadVehicleRenderAdapter::direction_from_forward({-1.0F, 0.2F, 0.0F}) == MobileEntityDirection::west);
    assert(ProceduralRoadVehicleRenderAdapter::direction_from_forward({0.2F, 1.0F, 0.0F}) == MobileEntityDirection::south);
    assert(ProceduralRoadVehicleRenderAdapter::direction_from_forward({0.2F, -1.0F, 0.0F}) == MobileEntityDirection::north);

    ProceduralRoadVehicleVisual visual;
    visual.sprite_south = "south.png";
    visual.sprite_east = "east.png";
    visual.sprite_north = "north.png";
    visual.sprite_west = "west.png";
    visual.animation_set_id = "vehicle.test";
    visual.art_scale = 0.42F;
    visual.sprite_anchor_x = 0.50F;
    visual.sprite_anchor_y = 0.91F;

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
    test_vehicle_render_adapter_preserves_pose_and_logical_direction();
    test_reverse_route_is_continuous();
    test_geometric_crossing_does_not_connect();
}
