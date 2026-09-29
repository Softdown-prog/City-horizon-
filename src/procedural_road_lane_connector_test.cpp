#include "procedural_road_lane_connector.h"

#include <cassert>
#include <cmath>

namespace {

bool near_value(const float a, const float b, const float epsilon = 0.001F) {
    return std::fabs(a - b) <= epsilon;
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

void test_geometric_crossing_does_not_connect() {
    ProceduralRoadGraph graph;
    const auto west = graph.add_node({-3.0F, 0.0F, 0.0F});
    const auto east = graph.add_node({3.0F, 0.0F, 0.0F});
    const auto north = graph.add_node({0.0F, -3.0F, 2.0F});
    const auto south = graph.add_node({0.0F, 3.0F, 2.0F});
    const auto ground = graph.add_segment(west, east, {1.0F, 0.0F, 0.0F}, {-1.0F, 0.0F, 0.0F});
    const auto bridge = graph.add_segment(north, south, {0.0F, 1.0F, 0.0F}, {0.0F, -1.0F, 0.0F});
    assert(ground && bridge);

    // They cross in XY but there is no shared graph node, therefore no legal
    // connector can be authored between the ground road and the bridge.
    assert(!ProceduralRoadLaneConnectorBuilder::build(graph, west, *ground, *bridge, 0.18F));
    assert(!ProceduralRoadLaneConnectorBuilder::build(graph, north, *ground, *bridge, 0.18F));
}

} // namespace

int main() {
    test_turn_classification();
    test_explicit_junction_connectors();
    test_geometric_crossing_does_not_connect();
}
