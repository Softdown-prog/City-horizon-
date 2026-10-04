#include "rail_persistence.h"
#include "rail_placement_track_graph_adapter.h"

#include <filesystem>
#include <fstream>
#include <iostream>

namespace {

[[nodiscard]] int fail(const char* message) {
    std::cerr << "rail persistence regression failed: " << message << '\n';
    return 1;
}

RailPersistentAction action_for(const RailPlacementPieceId group,
                                const std::int64_t cost,
                                const bool active) {
    return {group, cost, cost * 65 / 100, active};
}

}  // namespace

int main() {
    RailPlacementGraph graph;
    const auto root = graph.add_root({0.0F, 0.0F, 0.0F}, 0.0F);
    if (!root) return fail("root creation");

    const auto first = graph.append_straight(*root, 4.0F);
    const auto middle = first ? graph.append_straight(first->node, 4.0F) : std::nullopt;
    const auto last = middle ? graph.append_straight(middle->node, 4.0F) : std::nullopt;
    if (!first || !middle || !last) return fail("three-piece chain creation");

    const RailPlacementPieceId first_group = graph.edges()[first->edge].piece_group;
    const RailPlacementPieceId middle_group = graph.edges()[middle->edge].piece_group;
    const RailPlacementPieceId last_group = graph.edges()[last->edge].piece_group;
    if (graph.remove_piece(middle_group) != 1U) return fail("middle piece tombstone");
    if (graph.edge(first->edge) == nullptr || graph.edge(middle->edge) != nullptr ||
        graph.edge(last->edge) == nullptr || graph.edges()[last->edge].id != last->edge) {
        return fail("middle deletion must preserve later IDs");
    }

    constexpr float kTurnoutAngle = 0.2617993877991494F;
    const auto turnout = graph.append_turnout(last->node, 2.5F, kTurnoutAngle, RailTurnDirection::left);
    if (!turnout || !turnout->ok()) return fail("turnout creation");
    const RailPlacementPieceId turnout_group = graph.edges()[turnout->through_edge].piece_group;
    if (turnout_group != graph.edges()[turnout->diverging_edge].piece_group ||
        graph.remove_piece(turnout_group) != 2U ||
        graph.edge(turnout->through_edge) != nullptr || graph.edge(turnout->diverging_edge) != nullptr) {
        return fail("turnout demolition must be atomic");
    }

    const auto topology = ch::rail::build_track_graph(graph);
    if (!topology.valid) return fail("topology must ignore tombstones");

    RailPersistentState state;
    state.nodes = graph.nodes();
    state.edges = graph.edges();
    state.actions = {
        action_for(first_group, 500, true),
        action_for(middle_group, 500, false),
        action_for(last_group, 500, true),
        action_for(turnout_group, 850, false),
    };
    std::string validation_error;
    if (!ch::rail_persistence::validate(state, &validation_error)) {
        std::cerr << validation_error << '\n';
        return fail("persistent state validation");
    }

    const std::filesystem::path root_dir =
        std::filesystem::temp_directory_path() / "city_horizon_rail_persistence_test";
    const std::filesystem::path city_file = root_dir / "city.json";
    std::filesystem::create_directories(root_dir);
    {
        std::ofstream city(city_file, std::ios::binary | std::ios::trunc);
        city << "{\n  \"saveVersion\": 12,\n  \"sentinel\": 1\n}\n";
    }

    std::string inject_error;
    if (!ch::rail_persistence::inject_city_extension(city_file, state, &inject_error)) {
        std::cerr << inject_error << '\n';
        return fail("city JSON extension injection");
    }
    const ch::rail_persistence::ReadResult loaded =
        ch::rail_persistence::read_city_extension(city_file);
    if (!loaded.valid || !loaded.present || loaded.state.nodes.size() != state.nodes.size() ||
        loaded.state.edges.size() != state.edges.size() || loaded.state.actions.size() != state.actions.size()) {
        return fail("city JSON rail round trip");
    }
    if (loaded.state.actions[1].build_cost != 500 || loaded.state.actions[1].refund_value != 325 ||
        loaded.state.actions[1].active || loaded.state.actions[3].refund_value != 552) {
        return fail("paid cost and historical refund round trip");
    }

    RailPlacementGraph restored;
    if (!restored.restore_snapshot(loaded.state.nodes, loaded.state.edges)) {
        return fail("graph snapshot restore");
    }
    if (restored.edge(first->edge) == nullptr || restored.edge(middle->edge) != nullptr ||
        restored.edge(last->edge) == nullptr || restored.edge(turnout->through_edge) != nullptr) {
        return fail("active/tombstoned routes restore");
    }

    const auto appended = restored.append_straight(last->node, 3.0F);
    if (!appended || appended->edge != state.edges.size()) {
        return fail("new IDs must append after restored tombstones");
    }

    const ch::rail_persistence::ReadResult legacy = [&]() {
        const std::filesystem::path legacy_file = root_dir / "legacy.json";
        std::ofstream file(legacy_file, std::ios::binary | std::ios::trunc);
        file << "{\"saveVersion\":12}\n";
        file.close();
        return ch::rail_persistence::read_city_extension(legacy_file);
    }();
    if (!legacy.valid || legacy.present || !legacy.state.edges.empty()) {
        return fail("legacy save must map to empty rail state");
    }

    std::error_code ignored;
    std::filesystem::remove_all(root_dir, ignored);
    std::cout << "rail persistence regression passed\n";
    return 0;
}
