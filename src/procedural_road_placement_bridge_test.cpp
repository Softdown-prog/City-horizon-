#include "procedural_road_placement_bridge.h"

#include <cassert>
#include <vector>

namespace {

void test_crossing_reuses_explicit_ground_node() {
    ProceduralRoadPlacementBridge bridge;

    const std::vector<TileCoordinate> horizontal = {
        {-2, 0}, {-1, 0}, {0, 0}, {1, 0}, {2, 0},
    };
    const auto local = bridge.mirror_tile_segment(horizontal, ProceduralRoadClass::local);
    assert(local);
    assert(local->created_nodes == 5U);
    assert(local->created_segments == 4U);
    assert(bridge.graph().nodes().size() == 5U);
    assert(bridge.graph().segments().size() == 4U);

    const ProceduralRoadNodeId center = local->nodes[2U];
    assert(bridge.graph().degree(center) == 2U);

    const std::vector<TileCoordinate> vertical = {
        {0, -2}, {0, -1}, {0, 0}, {0, 1}, {0, 2},
    };
    const auto collector = bridge.mirror_tile_segment(vertical, ProceduralRoadClass::collector);
    assert(collector);
    assert(collector->created_nodes == 4U);
    assert(collector->reused_nodes == 1U);
    assert(collector->nodes[2U] == center);
    assert(bridge.graph().degree(center) == 4U);
    assert(bridge.graph().nodes().size() == 9U);
    assert(bridge.graph().segments().size() == 8U);

    for (const ProceduralRoadSegmentId segment_id : local->segments) {
        assert(bridge.classes().road_class(bridge.graph(), segment_id) == ProceduralRoadClass::local);
    }
    for (const ProceduralRoadSegmentId segment_id : collector->segments) {
        assert(bridge.classes().road_class(bridge.graph(), segment_id) == ProceduralRoadClass::collector);
    }
}

void test_elevated_crossing_does_not_reuse_ground_node() {
    ProceduralRoadPlacementBridge bridge;

    const auto ground = bridge.mirror_tile_segment(
        {{-1, 0}, {0, 0}, {1, 0}}, ProceduralRoadClass::local, 0.0F);
    const auto bridge_span = bridge.mirror_tile_segment(
        {{0, -1}, {0, 0}, {0, 1}}, ProceduralRoadClass::arterial, 2.0F);
    assert(ground && bridge_span);

    const ProceduralRoadNodeId ground_center = ground->nodes[1U];
    const ProceduralRoadNodeId bridge_center = bridge_span->nodes[1U];
    assert(ground_center != bridge_center);
    assert(bridge.graph().degree(ground_center) == 2U);
    assert(bridge.graph().degree(bridge_center) == 2U);
    assert(bridge.graph().nodes().size() == 6U);
    assert(bridge.graph().segments().size() == 4U);
}

void test_repeated_identical_segment_reuses_nodes_and_edges() {
    ProceduralRoadPlacementBridge bridge;
    const std::vector<TileCoordinate> tiles = {{3, 4}, {4, 4}, {5, 4}};

    const auto first = bridge.mirror_tile_segment(tiles, ProceduralRoadClass::local);
    const auto second = bridge.mirror_tile_segment(tiles, ProceduralRoadClass::local);
    assert(first && second);
    assert(second->created_nodes == 0U);
    assert(second->reused_nodes == 3U);
    assert(second->created_segments == 0U);
    assert(second->reused_segments == 2U);
    assert(first->nodes == second->nodes);
    assert(first->segments == second->segments);
}

void test_invalid_non_adjacent_tile_path_is_rejected_without_mutation() {
    ProceduralRoadPlacementBridge bridge;
    const auto result = bridge.mirror_tile_segment(
        {{0, 0}, {2, 0}}, ProceduralRoadClass::local);
    assert(!result);
    assert(bridge.graph().nodes().empty());
    assert(bridge.graph().segments().empty());
}

void test_existing_edge_class_can_be_reprofiled_explicitly() {
    ProceduralRoadPlacementBridge bridge;
    const auto result = bridge.mirror_tile_segment(
        {{0, 0}, {1, 0}}, ProceduralRoadClass::local);
    assert(result && result->segments.size() == 1U);
    const ProceduralRoadSegmentId segment_id = result->segments.front();

    assert(bridge.set_existing_edge_class(segment_id, ProceduralRoadClass::arterial));
    const auto* segment = bridge.graph().segment(segment_id);
    assert(segment != nullptr);
    assert(segment->lane_count == 4);
    assert(segment->width == 1.32F);
    assert(bridge.classes().road_class(bridge.graph(), segment_id) == ProceduralRoadClass::arterial);
}

} // namespace

int main() {
    test_crossing_reuses_explicit_ground_node();
    test_elevated_crossing_does_not_reuse_ground_node();
    test_repeated_identical_segment_reuses_nodes_and_edges();
    test_invalid_non_adjacent_tile_path_is_rejected_without_mutation();
    test_existing_edge_class_can_be_reprofiled_explicitly();
}
