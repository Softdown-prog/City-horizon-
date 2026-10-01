#include "procedural_road_ground_render_plan.h"

#include <cassert>
#include <cmath>

namespace {

void test_ground_network_is_admitted_as_flat_2d() {
    ProceduralRoadPlacementBridge bridge;
    const auto result = bridge.mirror_tile_segment(
        {{0, 0}, {1, 0}, {2, 0}}, ProceduralRoadClass::local, 0.0F);
    assert(result.has_value());

    const ProceduralRoadGroundRenderPlan plan = build_procedural_road_ground_render_plan(bridge);
    assert(plan.segment_meshes.size() == 2U);
    assert(plan.junction_meshes.size() == 1U);
    assert(plan.skipped_elevated_segments == 0U);
    assert(plan.skipped_mixed_junctions == 0U);

    for (const ProceduralRoad2DMesh& mesh : plan.segment_meshes) {
        assert(!mesh.empty());
        for (const ProceduralRoad2DVertex& vertex : mesh.vertices) {
            assert(std::isfinite(vertex.position.x));
            assert(std::isfinite(vertex.position.y));
        }
    }
    assert(!plan.junction_meshes.front().empty());
}

void test_straight_ribbon_preserves_authored_width() {
    RoadSplineSegment segment;
    segment.start = {0.0F, 0.0F, 0.0F};
    segment.control_a = {1.0F / 3.0F, 0.0F, 0.0F};
    segment.control_b = {2.0F / 3.0F, 0.0F, 0.0F};
    segment.end = {1.0F, 0.0F, 0.0F};
    segment.width = 0.72F;
    segment.subdivisions = 4;

    const ProceduralRoad2DMesh mesh = build_procedural_road_2d_ribbon(segment);
    assert(mesh.vertices.size() == 10U);
    assert(mesh.indices.size() == 24U);

    const float first_pair_width = std::abs(
        mesh.vertices[0].position.y - mesh.vertices[1].position.y);
    assert(std::abs(first_pair_width - segment.width) < 0.0001F);
}

void test_elevated_segment_is_rejected() {
    ProceduralRoadPlacementBridge bridge;
    const auto result = bridge.mirror_tile_segment(
        {{0, 0}, {1, 0}}, ProceduralRoadClass::local, 1.0F);
    assert(result.has_value());

    const ProceduralRoadGroundRenderPlan plan = build_procedural_road_ground_render_plan(bridge);
    assert(plan.segment_meshes.empty());
    assert(plan.junction_meshes.empty());
    assert(plan.skipped_elevated_segments == 1U);
}

void test_mixed_height_junction_is_not_rendered() {
    ProceduralRoadPlacementBridge bridge;
    ProceduralRoadGraph& graph = bridge.graph();
    ProceduralRoadClassCatalog& classes = bridge.classes();

    const auto center = graph.add_node({0.0F, 0.0F, 0.0F});
    const auto ground = graph.add_node({1.0F, 0.0F, 0.0F});
    const auto elevated = graph.add_node({0.0F, 1.0F, 1.0F});

    const auto ground_segment = ProceduralRoadConstructionBuilder::add_segment(
        graph, classes, center, ground, ProceduralRoadClass::local,
        {0.33F, 0.0F, 0.0F}, {-0.33F, 0.0F, 0.0F});
    const auto elevated_segment = ProceduralRoadConstructionBuilder::add_segment(
        graph, classes, center, elevated, ProceduralRoadClass::local,
        {0.0F, 0.33F, 0.33F}, {0.0F, -0.33F, -0.33F});
    assert(ground_segment.has_value());
    assert(elevated_segment.has_value());

    const ProceduralRoadGroundRenderPlan plan = build_procedural_road_ground_render_plan(bridge);
    assert(plan.segment_meshes.size() == 1U);
    assert(plan.junction_meshes.empty());
    assert(plan.skipped_elevated_segments == 1U);
    assert(plan.skipped_mixed_junctions == 1U);
}

} // namespace

int main() {
    test_ground_network_is_admitted_as_flat_2d();
    test_straight_ribbon_preserves_authored_width();
    test_elevated_segment_is_rejected();
    test_mixed_height_junction_is_not_rendered();
    return 0;
}
