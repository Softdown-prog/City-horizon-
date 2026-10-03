#include "rail_placement_controller.h"
#include "rail_placement_track_graph_adapter.h"

#include <cassert>
#include <cmath>
#include <iostream>

namespace {

constexpr float kPiOverTwelve = 0.2617993877991494F;

void test_editor_graph_compiles_to_shared_topology() {
    RailPlacementGraph placement;
    const auto root = placement.add_root({0.0F, 0.0F, 0.0F}, 0.0F);
    assert(root);

    const auto straight = placement.append_straight(*root, 6.0F);
    assert(straight && straight->ok());
    const auto curve = placement.append_quarter_curve(straight->node, 4.0F, RailTurnDirection::left);
    assert(curve && curve->ok());
    const auto turnout = placement.append_turnout(
        curve->node, 8.0F, kPiOverTwelve, RailTurnDirection::right);
    assert(turnout && turnout->ok());
    const auto crossing = placement.append_crossing(turnout->through_node, 6.0F);
    assert(crossing && crossing->ok());

    assert(placement.edge(turnout->through_edge)->piece_group ==
           placement.edge(turnout->diverging_edge)->piece_group);
    assert(placement.edge(crossing->primary_edge)->piece_group ==
           placement.edge(crossing->secondary_edge)->piece_group);

    const auto built = ch::rail::build_track_graph(placement);
    assert(built.valid);
    assert(built.error.empty());
    assert(built.graph.pieces().size() == 4U);
    assert(built.edge_piece.size() == placement.edges().size());

    const auto turnout_piece = built.edge_piece[turnout->through_edge];
    assert(turnout_piece == built.edge_piece[turnout->diverging_edge]);
    const auto crossing_piece = built.edge_piece[crossing->primary_edge];
    assert(crossing_piece == built.edge_piece[crossing->secondary_edge]);

    const auto* turnout_instance = built.graph.piece(turnout_piece);
    assert(turnout_instance != nullptr);
    assert(ch::track::has_flag(turnout_instance->descriptor, ch::track::PieceFlag::switch_piece));
    assert(turnout_instance->descriptor.routes.size() == 2U);

    const auto* crossing_instance = built.graph.piece(crossing_piece);
    assert(crossing_instance != nullptr);
    assert(ch::track::has_flag(crossing_instance->descriptor, ch::track::PieceFlag::crossing));
    assert(crossing_instance->descriptor.routes.size() == 2U);
    assert(crossing_instance->descriptor.ports.size() == 4U);

    const auto start_piece = built.edge_piece[straight->edge];
    const auto through_route = built.graph.build_route({start_piece, 0U});
    assert(through_route.ok());
    assert(!through_route.closed);
    assert(through_route.steps.size() == 4U);
    assert(through_route.steps[2].piece == turnout_piece);
    assert(through_route.steps[2].route == 0U);
    assert(through_route.steps[3].piece == crossing_piece);
    assert(through_route.steps[3].route == 0U);

    const auto through_polyline = built.graph.compile_polyline(through_route);
    assert(through_polyline.valid);
    assert(through_polyline.points.size() > 20U);

    auto switched = ch::rail::build_track_graph(placement);
    assert(switched.valid);
    const auto switched_turnout_piece = switched.edge_piece[turnout->through_edge];
    assert(switched.graph.set_active_route(switched_turnout_piece, 1U));
    const auto diverging_route = switched.graph.build_route({switched.edge_piece[straight->edge], 0U});
    assert(diverging_route.ok());
    assert(diverging_route.steps.size() == 3U);
    assert(diverging_route.steps.back().piece == switched_turnout_piece);
    assert(diverging_route.steps.back().route == 1U);
}

void test_crossing_routes_are_independent_and_live() {
    RailPlacementGraph placement;
    const auto root = placement.add_root({0.0F, 0.0F, 0.0F}, 0.0F);
    assert(root);
    const auto crossing = placement.append_crossing(*root, 8.0F);
    assert(crossing && crossing->ok());

    const auto primary_extension = placement.append_straight(crossing->primary_node, 4.0F);
    const auto secondary_before = placement.append_straight(crossing->secondary_entry_node, 4.0F);
    const auto secondary_after = placement.append_straight(crossing->secondary_exit_node, 4.0F);
    assert(primary_extension && secondary_before && secondary_after);

    const auto built = ch::rail::build_track_graph(placement);
    assert(built.valid);
    const auto crossing_piece = built.edge_piece[crossing->primary_edge];

    const auto primary = built.graph.build_route({crossing_piece, 0U});
    assert(primary.ok());
    assert(primary.steps.front().piece == crossing_piece);
    assert(primary.steps.front().route == 0U);
    assert(primary.steps.size() == 2U);

    const auto secondary = built.graph.build_route({crossing_piece, 2U});
    assert(secondary.ok());
    assert(secondary.steps.front().piece == crossing_piece);
    assert(secondary.steps.front().route == 1U);
    assert(secondary.steps.size() == 2U);

    // Traversing the primary path must never transfer to the secondary path at
    // the geometric intersection: no graph node exists at the crossing center.
    for (const auto& step : primary.steps) {
        assert(!(step.piece == crossing_piece && step.route == 1U));
    }
}

void test_crossing_preview_is_transactional() {
    RailPlacementGraph placement;
    const auto root = placement.add_root({0.0F, 0.0F, 0.0F}, 0.0F);
    assert(root);
    RailPlacementController controller(placement);

    const RailPlacementCheckpoint before = placement.checkpoint();
    assert(controller.begin(*root, RailPlacementMode::crossing));
    const auto preview_a = controller.preview(6.0F);
    assert(preview_a && preview_a->ok());
    assert(preview_a->has_secondary_branch());
    assert(preview_a->has_auxiliary_node());
    assert(placement.nodes().size() == before.node_count + 3U);
    assert(placement.edges().size() == before.edge_count + 2U);

    const auto preview_b = controller.preview(8.0F);
    assert(preview_b && preview_b->ok());
    assert(placement.nodes().size() == before.node_count + 3U);
    assert(placement.edges().size() == before.edge_count + 2U);
    assert(controller.cancel());
    assert(placement.nodes().size() == before.node_count);
    assert(placement.edges().size() == before.edge_count);

    assert(controller.begin(*root, RailPlacementMode::crossing));
    assert(controller.preview(8.0F));
    assert(controller.commit());
    assert(placement.nodes().size() == before.node_count + 3U);
    assert(placement.edges().size() == before.edge_count + 2U);
}

void test_ambiguous_node_fails_closed() {
    RailPlacementGraph placement;
    const auto root = placement.add_root({0.0F, 0.0F, 0.0F}, 0.0F);
    assert(root);
    assert(placement.append_straight(*root, 4.0F));
    assert(placement.append_quarter_curve(*root, 4.0F, RailTurnDirection::left));

    const auto built = ch::rail::build_track_graph(placement);
    assert(!built.valid);
    assert(!built.error.empty());
}

}  // namespace

int main() {
    test_editor_graph_compiles_to_shared_topology();
    test_crossing_routes_are_independent_and_live();
    test_crossing_preview_is_transactional();
    test_ambiguous_node_fails_closed();
    std::cout << "CH_RAIL_PLACEMENT_TRACK_GRAPH_ADAPTER_V1: OK\n";
    return 0;
}
