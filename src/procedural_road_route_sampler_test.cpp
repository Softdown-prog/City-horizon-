#include "procedural_road_route_sampler.h"

#include <cassert>
#include <cmath>
#include <cstddef>

namespace {

float distance3(const RoadWorldPoint3& a, const RoadWorldPoint3& b) {
    const float dx = b.x - a.x;
    const float dy = b.y - a.y;
    const float dz = b.z - a.z;
    return std::sqrt(dx * dx + dy * dy + dz * dz);
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
    assert(route);
    assert(route->segments.size() == 3U);

    const auto sampled = ProceduralRoadRouteSampler::sample_right_hand_route(graph, *route, 0.18F, 24, 12);
    assert(sampled);
    assert(!sampled->empty());

    bool saw_first_junction = false;
    bool saw_second_junction = false;
    bool saw_elevated_point = false;
    float max_step = 0.0F;

    for (std::size_t index = 0; index < sampled->size(); ++index) {
        const auto& point = (*sampled)[index];
        if (point.kind == ProceduralRoadRoutePointKind::junction_connector) {
            if (point.junction_node == b) saw_first_junction = true;
            if (point.junction_node == c) saw_second_junction = true;
        }
        if (point.position.z > 1.0F) saw_elevated_point = true;
        if (index > 0U) {
            const float step = distance3((*sampled)[index - 1U].position, point.position);
            if (step > max_step) max_step = step;
        }
    }

    assert(saw_first_junction);
    assert(saw_second_junction);
    assert(saw_elevated_point);
    // With 24 samples/segment and 12/connector, a route this size should never
    // contain a tile-sized teleport at a graph node.
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

void test_overpass_cannot_be_spliced_without_shared_node() {
    ProceduralRoadGraph graph;
    const auto west = graph.add_node({-4.0F, 0.0F, 0.0F});
    const auto east = graph.add_node({4.0F, 0.0F, 0.0F});
    const auto north = graph.add_node({0.0F, -4.0F, 2.0F});
    const auto south = graph.add_node({0.0F, 4.0F, 2.0F});
    assert(graph.add_segment(west, east, {1.0F, 0.0F, 0.0F}, {-1.0F, 0.0F, 0.0F}));
    assert(graph.add_segment(north, south, {0.0F, 1.0F, 0.0F}, {0.0F, -1.0F, 0.0F}));

    assert(!ProceduralRoadNavigator::find_route(graph, west, south));
}

} // namespace

int main() {
    test_continuous_route_across_two_junctions();
    test_reverse_route_is_continuous();
    test_overpass_cannot_be_spliced_without_shared_node();
}
