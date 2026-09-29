#include "procedural_road_lane_connector.h"
#include "procedural_road_route_sampler.h"

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

void test_continuous_route_across_two_junctions() {
    ProceduralRoadGraph graph;
    const auto a = graph.add_node({-6.0F, 0.0F, 0.0F});
    const auto b = graph.add_node({0.0F, 0.0F, 0.75F});
    const auto c = graph.add_node({4.0F, 4.0F, 1.25F});
    const auto d = graph.add_node({10.0F, 4.0F, 1.25F});

    const auto ab = graph.add_segment(a, b, {2.0F, 0.0F, 0.25F}, {-2.0F, 0.0F, -0.10F}, 0.82F, 2);
    const auto bc = graph.add_segment(b, c, {1.5F, 0.8F, 0.15F}, {-1.0F, -1.4F, -0.15F}, 0.82F, 2);
    const auto cd = graph.add_segment(c, d, {2.0F, 0.0F, 0.0F}, {-2.0F, 0.0F, 0.0F}, 0.82F, 2);
    assert(ab && bc && cd);

    const auto route = ProceduralRoadNavigator::find_route(graph, a, d);
    assert(route && route->segments.size() == 3U);
    const auto sampled = ProceduralRoadRouteSampler::sample_right_hand_route(graph, *route, 0.18F, 24, 12);
    assert(sampled && !sampled->empty());

    bool saw_b = false;
    bool saw_c = false;
    bool saw_elevated_point = false;
    float max_step = 0.0F;
    for (std::size_t index = 0; index < sampled->size(); ++index) {
        const auto& point = (*sampled)[index];
        if (point.kind == ProceduralRoadRoutePointKind::junction_connector) {
            if (point.junction_node == b) saw_b = true;
            if (point.junction_node == c) saw_c = true;
        }
        if (point.position.z > 1.0F) saw_elevated_point = true;
        if (index > 0U) {
            max_step = std::max(max_step, distance3((*sampled)[index - 1U].position, point.position));
        }
    }
    assert(saw_b && saw_c && saw_elevated_point);
    assert(max_step < 0.75F);
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
    test_reverse_route_is_continuous();
    test_geometric_crossing_does_not_connect();
}
