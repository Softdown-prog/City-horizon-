#include "procedural_road_construction.h"

#include <cassert>
#include <cmath>

namespace {

bool near_value(const float a, const float b, const float epsilon = 0.0001F) {
    return std::fabs(a - b) <= epsilon;
}

void test_class_profiles_create_expected_geometry() {
    ProceduralRoadGraph graph;
    ProceduralRoadClassCatalog classes;

    const auto a = graph.add_node({0.0F, 0.0F, 0.0F});
    const auto b = graph.add_node({5.0F, 0.0F, 0.0F});
    const auto c = graph.add_node({10.0F, 0.0F, 0.0F});
    const auto d = graph.add_node({15.0F, 0.0F, 0.0F});

    const auto local = ProceduralRoadConstructionBuilder::add_segment(
        graph, classes, a, b, ProceduralRoadClass::local);
    const auto collector = ProceduralRoadConstructionBuilder::add_segment(
        graph, classes, b, c, ProceduralRoadClass::collector);
    const auto arterial = ProceduralRoadConstructionBuilder::add_segment(
        graph, classes, c, d, ProceduralRoadClass::arterial);

    assert(local && collector && arterial);

    const auto* local_segment = graph.segment(*local);
    const auto* collector_segment = graph.segment(*collector);
    const auto* arterial_segment = graph.segment(*arterial);
    assert(local_segment && collector_segment && arterial_segment);

    assert(near_value(local_segment->width, 0.72F));
    assert(local_segment->lane_count == 2);
    assert(local_segment->subdivisions == 24);

    assert(near_value(collector_segment->width, 0.94F));
    assert(collector_segment->lane_count == 2);
    assert(collector_segment->subdivisions == 32);

    assert(near_value(arterial_segment->width, 1.32F));
    assert(arterial_segment->lane_count == 4);
    assert(arterial_segment->subdivisions == 40);

    assert(classes.road_class(graph, *local) == ProceduralRoadClass::local);
    assert(classes.road_class(graph, *collector) == ProceduralRoadClass::collector);
    assert(classes.road_class(graph, *arterial) == ProceduralRoadClass::arterial);
}

void test_build_cost_uses_class_profile_and_3d_length() {
    const RoadWorldPoint3 start{0.0F, 0.0F, 0.0F};
    const RoadWorldPoint3 end{3.0F, 4.0F, 0.0F};
    assert(ProceduralRoadConstructionBuilder::estimated_build_cost(
               start, end, ProceduralRoadClass::local) == 500);
    assert(ProceduralRoadConstructionBuilder::estimated_build_cost(
               start, end, ProceduralRoadClass::collector) == 800);
    assert(ProceduralRoadConstructionBuilder::estimated_build_cost(
               start, end, ProceduralRoadClass::arterial) == 1300);

    const RoadWorldPoint3 ramp_end{0.0F, 4.0F, 3.0F};
    assert(ProceduralRoadConstructionBuilder::estimated_build_cost(
               start, ramp_end, ProceduralRoadClass::local) == 500);
}

void test_unspecified_is_not_authored_as_a_segment_class() {
    ProceduralRoadGraph graph;
    ProceduralRoadClassCatalog classes;
    const auto a = graph.add_node({0.0F, 0.0F, 0.0F});
    const auto b = graph.add_node({1.0F, 0.0F, 0.0F});

    const auto segment = ProceduralRoadConstructionBuilder::add_segment(
        graph, classes, a, b, ProceduralRoadClass::unspecified);
    assert(!segment);
    assert(graph.segments().empty());
}

} // namespace

int main() {
    test_class_profiles_create_expected_geometry();
    test_build_cost_uses_class_profile_and_3d_length();
    test_unspecified_is_not_authored_as_a_segment_class();
}
