#include "procedural_road_ground_render_plan.h"

#include <cassert>

// This gate validates only the ground/elevated admission policy. The production
// RoadMeshBuilder is compiled separately through mapforge2_editor and the real
// MapForge2ProceduralRoadPreview in the same workflow. Keeping a tiny local mesh
// double here prevents unrelated building/economy linkage from contaminating a
// topology/Z-filter test.
RoadMesh RoadMeshBuilder::build_cubic(const RoadSplineSegment& segment) {
    RoadMesh mesh;
    if (!(segment.width > 0.0F)) return mesh;
    mesh.vertices.push_back({segment.start, 0.0F, 0.0F});
    mesh.vertices.push_back({segment.end, 1.0F, 1.0F});
    mesh.vertices.push_back({segment.end, 0.0F, 1.0F});
    mesh.indices = {0U, 1U, 2U};
    return mesh;
}

namespace {

void test_ground_network_is_admitted() {
    ProceduralRoadPlacementBridge bridge;
    const auto result = bridge.mirror_tile_segment(
        {{0, 0}, {1, 0}, {2, 0}}, ProceduralRoadClass::local, 0.0F);
    assert(result.has_value());

    const ProceduralRoadGroundRenderPlan plan = build_procedural_road_ground_render_plan(bridge);
    assert(plan.segment_meshes.size() == 2U);
    assert(plan.junction_meshes.size() == 1U);
    assert(plan.skipped_elevated_segments == 0U);
    assert(plan.skipped_mixed_junctions == 0U);
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

void test_mixed_height_junction_is_not_patched() {
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
    test_ground_network_is_admitted();
    test_elevated_segment_is_rejected();
    test_mixed_height_junction_is_not_patched();
    return 0;
}
