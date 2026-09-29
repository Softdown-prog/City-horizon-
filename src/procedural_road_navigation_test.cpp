#include "procedural_road_navigation.h"

#include <cassert>
#include <cmath>

namespace {

bool near_value(const float a, const float b, const float epsilon = 0.001F) {
    return std::fabs(a - b) <= epsilon;
}

void test_route_and_lane_sampling() {
    ProceduralRoadGraph graph;
    const auto a = graph.add_node({-6.0F, 0.0F, 0.0F});
    const auto b = graph.add_node({0.0F, 0.0F, 0.0F});
    const auto c = graph.add_node({6.0F, 2.0F, 1.5F});
    const auto isolated_a = graph.add_node({0.0F, -4.0F, 3.0F});
    const auto isolated_b = graph.add_node({0.0F, 4.0F, 3.0F});

    const auto ab = graph.add_segment(a, b,
                                      {2.0F, 2.5F, 0.0F}, {-2.0F, -2.5F, 0.0F}, 0.8F, 2);
    const auto bc = graph.add_segment(b, c,
                                      {2.0F, 0.0F, 0.4F}, {-2.0F, 0.0F, -0.4F}, 0.8F, 2);
    const auto bridge = graph.add_segment(isolated_a, isolated_b,
                                          {0.0F, 1.0F, 0.0F}, {0.0F, -1.0F, 0.0F}, 0.8F, 2);
    assert(ab && bc && bridge);

    const auto route = ProceduralRoadNavigator::find_route(graph, a, c);
    assert(route);
    assert(route->nodes.size() == 3U);
    assert(route->segments.size() == 2U);
    assert(route->nodes[0] == a);
    assert(route->nodes[1] == b);
    assert(route->nodes[2] == c);

    const auto lane = ProceduralRoadNavigator::sample_right_hand_lane(graph, *route, 0.18F, 16);
    assert(lane.size() == 33U); // 17 first segment + 16 after shared node de-duplication
    assert(lane.front().segment_id == *ab);
    assert(lane.back().segment_id == *bc);
    assert(near_value(lane.front().segment_t, 0.0F));
    assert(near_value(lane.back().segment_t, 1.0F));
    assert(lane.back().position.z > 1.45F);

    // The elevated bridge crosses the AB/BC network geometrically but has no
    // shared node. It must remain unreachable from the ground route.
    assert(!ProceduralRoadNavigator::find_route(graph, a, isolated_b));

    // Reverse traversal must work and invert the travel tangent so the right-hand
    // lane stays on the vehicle's right side rather than the spline author's.
    const auto reverse_route = ProceduralRoadNavigator::find_route(graph, c, a);
    assert(reverse_route);
    const auto reverse_lane = ProceduralRoadNavigator::sample_right_hand_lane(graph, *reverse_route, 0.18F, 16);
    assert(reverse_lane.size() == 33U);
    assert(reverse_lane.front().segment_id == *bc);
    assert(reverse_lane.back().segment_id == *ab);
    assert(near_value(reverse_lane.front().segment_t, 1.0F));
    assert(near_value(reverse_lane.back().segment_t, 0.0F));
}

} // namespace

int main() {
    test_route_and_lane_sampling();
    return 0;
}
