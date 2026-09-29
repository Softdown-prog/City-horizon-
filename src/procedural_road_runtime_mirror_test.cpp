#include "procedural_road_placement_bridge.h"
#include "road_system.h"

#include <cassert>
#include <cmath>

namespace {

const ProceduralRoadNode* find_node_at(const ProceduralRoadGraph& graph, const float x, const float y) {
    for (const ProceduralRoadNode& node : graph.nodes()) {
        if (std::fabs(node.position.x - x) < 0.0001F &&
            std::fabs(node.position.y - y) < 0.0001F) {
            return &node;
        }
    }
    return nullptr;
}

void test_segment_and_crossing_are_mirrored() {
    RoadManager roads(-16, 15);
    assert(roads.place_segment({{-1, 0}, {0, 0}, {1, 0}}) == 3);

    const auto& first = roads.procedural_mirror();
    assert(first.graph().nodes().size() == 3U);
    assert(first.graph().segments().size() == 2U);
    for (const ProceduralRoadGraphSegment& segment : first.graph().segments()) {
        assert(segment.lane_count == 2);
        assert(std::fabs(segment.width - 0.72F) < 0.0001F);
        assert(first.classes().road_class(first.graph(), segment.id) == ProceduralRoadClass::local);
    }

    assert(roads.place_segment({{0, -1}, {0, 0}, {0, 1}}) == 2);
    const auto& crossed = roads.procedural_mirror();
    const ProceduralRoadNode* center = find_node_at(crossed.graph(), 0.5F, 0.5F);
    assert(center != nullptr);
    assert(crossed.graph().degree(center->id) == 4U);
    assert(crossed.graph().nodes().size() == 5U);
    assert(crossed.graph().segments().size() == 4U);
}

void test_direct_place_tile_matches_save_load_behavior() {
    RoadManager roads(-16, 15);

    // SaveManager restores roads one tile at a time. Deliberately insert the
    // middle tile last to prove the incremental mirror attaches both neighbors.
    assert(roads.place_tile(0, 0));
    assert(roads.place_tile(2, 0));
    assert(roads.place_tile(1, 0));

    const auto& mirror = roads.procedural_mirror();
    assert(mirror.graph().nodes().size() == 3U);
    assert(mirror.graph().segments().size() == 2U);
    const ProceduralRoadNode* middle = find_node_at(mirror.graph(), 1.5F, 0.5F);
    assert(middle != nullptr);
    assert(mirror.graph().degree(middle->id) == 2U);
}

void test_demolition_rebuild_removes_ghost_edges() {
    RoadManager roads(-16, 15);
    assert(roads.place_segment({{-1, 0}, {0, 0}, {1, 0}}) == 3);
    assert(roads.place_segment({{0, -1}, {0, 0}, {0, 1}}) == 2);
    assert(roads.procedural_mirror().graph().segments().size() == 4U);

    assert(roads.remove_tile(0, 1));
    const auto& mirror = roads.procedural_mirror();
    assert(mirror.graph().nodes().size() == 4U);
    assert(mirror.graph().segments().size() == 3U);
    const ProceduralRoadNode* center = find_node_at(mirror.graph(), 0.5F, 0.5F);
    assert(center != nullptr);
    assert(mirror.graph().degree(center->id) == 3U);
    assert(find_node_at(mirror.graph(), 0.5F, 1.5F) == nullptr);
}

void test_clear_and_copy_keep_mirror_coherent() {
    RoadManager roads(-16, 15);
    assert(roads.place_segment({{3, 4}, {4, 4}, {5, 4}}) == 3);

    RoadManager copied = roads;
    assert(copied.tiles().size() == roads.tiles().size());
    assert(copied.procedural_mirror().graph().nodes().size() == 3U);
    assert(copied.procedural_mirror().graph().segments().size() == 2U);

    roads.clear();
    assert(roads.tiles().empty());
    assert(roads.procedural_mirror().graph().nodes().empty());
    assert(roads.procedural_mirror().graph().segments().empty());

    // Copy owns its own mirror and must remain intact after the source clears.
    assert(copied.tiles().size() == 3U);
    assert(copied.procedural_mirror().graph().nodes().size() == 3U);
    assert(copied.procedural_mirror().graph().segments().size() == 2U);
}

} // namespace

int main() {
    test_segment_and_crossing_are_mirrored();
    test_direct_place_tile_matches_save_load_behavior();
    test_demolition_rebuild_removes_ghost_edges();
    test_clear_and_copy_keep_mirror_coherent();
}
