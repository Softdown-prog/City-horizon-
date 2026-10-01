#include "src/runtime_procedural_road_culling.h"
#include "src/road_system.h"

#include <cassert>

namespace {

void test_camera_bounds_are_finite() {
    ch::CameraState camera{};
    camera.zoom = 1.0F;
    const ProceduralRoad2DWorldBounds bounds =
        procedural_road_visible_world_bounds(camera, 1280.0F, 720.0F);
    assert(bounds.valid());
    assert(bounds.min_x < bounds.max_x);
    assert(bounds.min_y < bounds.max_y);
}

void test_invalid_viewport_bounds_are_rejected() {
    ch::CameraState camera{};
    camera.zoom = 1.0F;
    const ProceduralRoad2DWorldBounds zero_width =
        procedural_road_visible_world_bounds(camera, 0.0F, 720.0F);
    assert(!zero_width.valid());

    camera.zoom = 0.0F;
    const ProceduralRoad2DWorldBounds zero_zoom =
        procedural_road_visible_world_bounds(camera, 1280.0F, 720.0F);
    assert(!zero_zoom.valid());
}

void test_graph_adjacency_index_tracks_mutation() {
    ProceduralRoadGraph graph;
    const ProceduralRoadNodeId a = graph.add_node({0.0F, 0.0F, 0.0F});
    const ProceduralRoadNodeId b = graph.add_node({1.0F, 0.0F, 0.0F});
    const ProceduralRoadNodeId c = graph.add_node({1.0F, 1.0F, 0.0F});
    const auto ab = graph.add_segment(a, b);
    const auto bc = graph.add_segment(b, c);
    assert(ab.has_value());
    assert(bc.has_value());

    assert(graph.degree(a) == 1U);
    assert(graph.degree(b) == 2U);
    assert(graph.degree(c) == 1U);
    assert(graph.connected_segments(b).size() == 2U);

    assert(graph.remove_segment(*ab));
    assert(graph.degree(a) == 0U);
    assert(graph.degree(b) == 1U);
    assert(graph.connected_segments(b).size() == 1U);

    assert(graph.remove_node(c));
    assert(graph.degree(b) == 0U);
    assert(graph.segments().empty());

    graph.clear();
    assert(graph.nodes().empty());
    assert(graph.degree(a) == 0U);
}

void test_spatial_chunks_limit_candidates() {
    ProceduralRoadPlacementBridge bridge;
    assert(bridge.mirror_tile_segment(
        {{0, 0}, {1, 0}}, ProceduralRoadClass::local, 0.0F).has_value());
    assert(bridge.mirror_tile_segment(
        {{50, 50}, {51, 50}}, ProceduralRoadClass::local, 0.0F).has_value());
    assert(bridge.graph().nodes().size() == 4U);
    assert(bridge.graph().segments().size() == 2U);

    const auto near_nodes = bridge.spatial_nodes_in_bounds(-2.0F, -2.0F, 3.0F, 3.0F);
    const auto near_segments = bridge.spatial_segments_in_bounds(-2.0F, -2.0F, 3.0F, 3.0F);
    assert(near_nodes.size() == 2U);
    assert(near_segments.size() == 1U);

    const auto far_nodes = bridge.spatial_nodes_in_bounds(48.0F, 48.0F, 53.0F, 53.0F);
    const auto far_segments = bridge.spatial_segments_in_bounds(48.0F, 48.0F, 53.0F, 53.0F);
    assert(far_nodes.size() == 2U);
    assert(far_segments.size() == 1U);

    bridge.clear();
    assert(bridge.spatial_nodes_in_bounds(-100.0F, -100.0F, 100.0F, 100.0F).empty());
    assert(bridge.spatial_segments_in_bounds(-100.0F, -100.0F, 100.0F, 100.0F).empty());
}

void test_spatial_index_rebuilds_with_legacy_tiles() {
    ProceduralRoadPlacementBridge bridge;
    const std::vector<RoadTile> tiles = {
        {31, 0, 0},
        {32, 0, 0},
        {33, 0, 0},
    };
    assert(bridge.rebuild_from_legacy_tiles(tiles, ProceduralRoadClass::local, 0.0F));
    assert(bridge.graph().nodes().size() == 3U);
    assert(bridge.graph().segments().size() == 2U);

    const auto west_chunk = bridge.spatial_nodes_in_bounds(30.0F, -1.0F, 31.9F, 1.0F);
    const auto crossing_segments = bridge.spatial_segments_in_bounds(31.0F, -1.0F, 33.0F, 1.0F);
    assert(!west_chunk.empty());
    assert(crossing_segments.size() == 2U);
}

void test_far_segments_are_culled_before_tessellation() {
    ProceduralRoadPlacementBridge bridge;
    assert(bridge.mirror_tile_segment(
        {{0, 0}, {1, 0}}, ProceduralRoadClass::local, 0.0F).has_value());
    assert(bridge.mirror_tile_segment(
        {{50, 50}, {51, 50}}, ProceduralRoadClass::local, 0.0F).has_value());

    const ProceduralRoad2DWorldBounds bounds{-2.0F, -2.0F, 3.0F, 3.0F};
    const ProceduralRoadVisibleGroundRenderPlan visible =
        build_visible_procedural_road_ground_render_plan(bridge, bounds);

    assert(visible.considered_segments == 1U);
    assert(visible.culled_segments == 1U);
    assert(visible.plan.segment_meshes.size() == 1U);
    assert(visible.plan.skipped_elevated_segments == 0U);
    assert(visible.plan.skipped_mixed_junctions == 0U);
}

void test_road_manager_mirror_stays_synchronized() {
    RoadManager roads(-8, 8);

    assert(roads.place_tile(0, 0));
    assert(roads.procedural_mirror().graph().nodes().size() == 1U);
    assert(roads.procedural_mirror().graph().segments().empty());

    assert(roads.place_tile(1, 0));
    assert(roads.procedural_mirror().graph().nodes().size() == 2U);
    assert(roads.procedural_mirror().graph().segments().size() == 1U);
    assert(roads.procedural_mirror().spatial_segments_in_bounds(-2.0F, -2.0F, 3.0F, 3.0F).size() == 1U);

    assert(roads.place_tile(1, 1));
    assert(roads.procedural_mirror().graph().nodes().size() == 3U);
    assert(roads.procedural_mirror().graph().segments().size() == 2U);
    const ProceduralRoadGraph& graph = roads.procedural_mirror().graph();
    bool found_corner = false;
    for (const ProceduralRoadNode& node : graph.nodes()) {
        if (graph.degree(node.id) == 2U) {
            found_corner = true;
            assert(graph.connected_segments(node.id).size() == 2U);
        }
    }
    assert(found_corner);

    RoadManager copied = roads;
    assert(copied.procedural_mirror().graph().nodes().size() == 3U);
    assert(copied.procedural_mirror().graph().segments().size() == 2U);
    assert(copied.procedural_mirror().spatial_segments_in_bounds(-2.0F, -2.0F, 3.0F, 3.0F).size() == 2U);

    assert(roads.remove_tile(1, 0));
    assert(roads.tiles().size() == 2U);
    assert(roads.procedural_mirror().graph().nodes().size() == 2U);
    assert(roads.procedural_mirror().graph().segments().empty());
    assert(roads.procedural_mirror().spatial_segments_in_bounds(-2.0F, -2.0F, 3.0F, 3.0F).empty());

    roads.clear();
    assert(roads.tiles().empty());
    assert(roads.procedural_mirror().graph().nodes().empty());
    assert(roads.procedural_mirror().graph().segments().empty());
    assert(roads.procedural_mirror().spatial_nodes_in_bounds(-2.0F, -2.0F, 3.0F, 3.0F).empty());
}

} // namespace

int main() {
    test_camera_bounds_are_finite();
    test_invalid_viewport_bounds_are_rejected();
    test_graph_adjacency_index_tracks_mutation();
    test_spatial_chunks_limit_candidates();
    test_spatial_index_rebuilds_with_legacy_tiles();
    test_far_segments_are_culled_before_tessellation();
    test_road_manager_mirror_stays_synchronized();
    return 0;
}
