#include "rail_drag_adapter.h"

#include <cassert>
#include <cmath>

int main() {
    const RailProfile profile{};
    RailPlacementGraph graph(profile);
    const auto root = graph.add_root({0.0F, 0.0F, 0.0F}, 0.0F);
    assert(root.has_value());

    RailPlacementController controller(graph);
    RailDragAdapter drag(controller);

    // Straight drag uses planar world distance. Repeated pointer updates replace
    // the current preview instead of accumulating nodes/edges.
    assert(drag.begin(*root, RailPlacementMode::straight, {10.0F, 20.0F, 0.0F}));
    const auto preview_a = drag.update({13.0F, 24.0F, 0.0F}); // distance 5
    assert(preview_a.has_value() && preview_a->ok());
    assert(graph.nodes().size() == 2U);
    assert(graph.edges().size() == 1U);
    const RailPlacementNode* end_a = graph.node(preview_a->primary_node);
    assert(end_a != nullptr);
    assert(std::abs(end_a->position.x - 5.0F) < 0.0001F);

    const auto preview_b = drag.update({16.0F, 28.0F, 0.0F}); // distance 10
    assert(preview_b.has_value() && preview_b->ok());
    assert(graph.nodes().size() == 2U);
    assert(graph.edges().size() == 1U);
    const RailPlacementNode* end_b = graph.node(preview_b->primary_node);
    assert(end_b != nullptr);
    assert(std::abs(end_b->position.x - 10.0F) < 0.0001F);
    assert(drag.confirm());
    assert(!drag.active());
    assert(graph.nodes().size() == 2U);
    assert(graph.edges().size() == 1U);

    // A curve preview may be cancelled without disturbing the committed straight.
    const RailPlacementCheckpoint before_curve = graph.checkpoint();
    assert(drag.begin(preview_b->primary_node, RailPlacementMode::curve_left,
                      {0.0F, 0.0F, 0.0F}));
    const auto curve = drag.update({4.0F, 0.0F, 0.0F});
    assert(curve.has_value() && curve->ok());
    assert(graph.edges().size() == before_curve.edge_count + 1U);
    assert(drag.cancel());
    assert(graph.nodes().size() == before_curve.node_count);
    assert(graph.edges().size() == before_curve.edge_count);

    // Invalid world input fails closed. The transaction remains cancellable and
    // no geometry is committed by a zero-length or non-finite pointer move.
    const RailPlacementCheckpoint before_invalid = graph.checkpoint();
    assert(drag.begin(preview_b->primary_node, RailPlacementMode::curve_right,
                      {2.0F, 3.0F, 0.0F}));
    assert(!drag.update({2.0F, 3.0F, 0.0F}).has_value());
    assert(!drag.update({std::nanf(""), 3.0F, 0.0F}).has_value());
    assert(graph.nodes().size() == before_invalid.node_count);
    assert(graph.edges().size() == before_invalid.edge_count);
    assert(drag.cancel());

    // Turnout previews remain atomic through the adapter: two branches or none.
    const RailPlacementCheckpoint before_turnout = graph.checkpoint();
    assert(drag.begin(preview_b->primary_node, RailPlacementMode::turnout_right,
                      {0.0F, 0.0F, 0.0F}));
    const auto turnout = drag.update({8.0F, 0.0F, 0.0F});
    assert(turnout.has_value() && turnout->ok());
    assert(turnout->has_secondary_branch());
    assert(graph.nodes().size() == before_turnout.node_count + 2U);
    assert(graph.edges().size() == before_turnout.edge_count + 2U);

    // Resize the same turnout preview. Counts remain constant because the old
    // preview is rolled back before the new one is authored.
    const auto turnout_resized = drag.update({9.0F, 0.0F, 0.0F});
    assert(turnout_resized.has_value() && turnout_resized->has_secondary_branch());
    assert(graph.nodes().size() == before_turnout.node_count + 2U);
    assert(graph.edges().size() == before_turnout.edge_count + 2U);
    assert(drag.confirm());

    // Invalid begin must not accidentally open a controller transaction.
    assert(!drag.begin(kInvalidRailPlacementNodeId, RailPlacementMode::straight,
                       {0.0F, 0.0F, 0.0F}));
    assert(!drag.begin(turnout_resized->primary_node, RailPlacementMode::straight,
                       {std::nanf(""), 0.0F, 0.0F}));

    return 0;
}
