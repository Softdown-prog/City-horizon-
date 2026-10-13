#include "rail_persistence.h"
#include "rail_purchase_catalog.h"
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
    state.stations = {{last_group, 4.25}};
    std::string validation_error;
    if (!ch::rail_persistence::validate(state, &validation_error)) {
        std::cerr << validation_error << '\n';
        return fail("persistent state validation");
    }

    RailPersistentState invalid_station = state;
    invalid_station.stations = {{middle_group, 3.0}};
    if (ch::rail_persistence::validate(invalid_station)) {
        return fail("station on tombstoned piece must fail validation");
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
        loaded.state.edges.size() != state.edges.size() || loaded.state.actions.size() != state.actions.size() ||
        loaded.state.stations.size() != 1U) {
        return fail("city JSON rail round trip");
    }
    if (loaded.state.actions[1].build_cost != 500 || loaded.state.actions[1].refund_value != 325 ||
        loaded.state.actions[1].active || loaded.state.actions[3].refund_value != 552) {
        return fail("paid cost and historical refund round trip");
    }
    if (loaded.state.stations[0].piece_group != last_group ||
        loaded.state.stations[0].dwell_seconds != 4.25) {
        return fail("station designation and dwell round trip");
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

    // New cities can save an empty fleet; purchased rolling stock survives reload.
    RailPersistentState paid = state;
    paid.fleet = {true, 3U};
    RailPersistentState loaded_paid;
    if (!ch::rail_persistence::deserialize_payload(
            ch::rail_persistence::serialize_payload(paid), loaded_paid) ||
        !loaded_paid.fleet.locomotive_owned || loaded_paid.fleet.coach_count != 3U)
        return fail("V4 rolling stock purchase roundtrip");
    paid.fleet = {false, 0U};
    if (!ch::rail_persistence::deserialize_payload(
            ch::rail_persistence::serialize_payload(paid), loaded_paid) ||
        loaded_paid.fleet.locomotive_owned || loaded_paid.fleet.coach_count != 0U)
        return fail("V4 empty fleet roundtrip");
    paid.fleet = {false, 1U};
    if (ch::rail_persistence::validate(paid)) return fail("coaches without loco permitted");
    paid.fleet = {true, 8U};
    if (ch::rail_persistence::validate(paid)) return fail("more than seven coaches permitted");

    RailPersistentState two_fleets = state;
    two_fleets.secondary_fleet = {true, 2U};
    RailPersistentState restored_two;
    if (!ch::rail_persistence::deserialize_payload(
            ch::rail_persistence::serialize_payload(two_fleets), restored_two) ||
        !restored_two.secondary_fleet.locomotive_owned ||
        restored_two.secondary_fleet.coach_count != 2U)
        return fail("V5 second fleet did not survive round trip");
    two_fleets.secondary_fleet = {false, 1U};
    if (ch::rail_persistence::validate(two_fleets))
        return fail("V5 allowed second-line wagons without locomotive");

    const std::string v2_payload = ch::rail_persistence::serialize_payload(state);
    const std::size_t first_newline = v2_payload.find('\n');
    if (first_newline == std::string::npos) return fail("V2 payload header");
    std::string v1_payload = std::string(kChRailPersistenceLegacyContract) +
                             v2_payload.substr(first_newline);
    const std::size_t station_row = v1_payload.find("\nS ");
    if (station_row != std::string::npos) {
        const std::size_t station_end = v1_payload.find('\n', station_row + 1U);
        v1_payload.erase(station_row, station_end == std::string::npos
            ? std::string::npos : station_end - station_row);
    }
    const std::size_t old_fleet_row = v1_payload.find("\nV ");
    if (old_fleet_row != std::string::npos) {
        const std::size_t row_end = v1_payload.find('\n', old_fleet_row + 1U);
        v1_payload.erase(old_fleet_row, row_end == std::string::npos
            ? std::string::npos : row_end - old_fleet_row);
    }
    const std::size_t old_secondary_row = v1_payload.find("\nW ");
    if (old_secondary_row != std::string::npos) {
        const std::size_t row_end = v1_payload.find('\n', old_secondary_row + 1U);
        v1_payload.erase(old_secondary_row, row_end == std::string::npos
            ? std::string::npos : row_end - old_secondary_row);
    }
    RailPersistentState loaded_v1;
    if (!ch::rail_persistence::deserialize_payload(v1_payload, loaded_v1) ||
        !loaded_v1.stations.empty() || loaded_v1.edges.size() != state.edges.size()) {
        return fail("V1 payload compatibility");
    }

    // V3: turntable is a paid rail attachment, bound to a single long
    // straight section. Saves/load/legacy V2 compatibility remain deterministic.
    RailPlacementGraph table_graph;
    const auto table_root=table_graph.add_root({0,10,0},0);
    if(!table_root)return fail("table root");
    const auto host=table_graph.append_straight(*table_root,40.0F);
    if(!host)return fail("table host straight");
    RailPersistentState table_state;
    table_state.nodes=table_graph.nodes();
    table_state.edges=table_graph.edges();
    const auto group=table_graph.edges()[host->edge].piece_group;
    table_state.actions={{group,5000,3250,true}};
    table_state.turntables={{group,3500,2275}};
    if(!ch::rail_persistence::validate(table_state))
        return fail("V3 valid physical turntable state");
    const auto v3=ch::rail_persistence::serialize_payload(table_state);
    RailPersistentState v3_loaded;
    if(v3.find("CH_RAIL_PERSISTENCE_V5")!=0 ||
       !ch::rail_persistence::deserialize_payload(v3,v3_loaded) ||
       v3_loaded.turntables.size()!=1U ||
       v3_loaded.turntables[0].build_cost!=3500 ||
       v3_loaded.turntables[0].refund_value!=2275)
        return fail("paid turntable V3 roundtrip");
    // New purchases must use the shared catalog price; historical $3500 saves
    // above remain valid and keep their original refund amounts.
    table_state.turntables[0] = {group, ch::rail_catalog::kTurntablePurchaseCost,
        ch::rail_catalog::kTurntablePurchaseCost * 65 / 100};
    RailPersistentState new_price_roundtrip;
    if (ch::rail_catalog::kTurntablePurchaseCost != 4200 ||
        !ch::rail_persistence::deserialize_payload(
            ch::rail_persistence::serialize_payload(table_state), new_price_roundtrip) ||
        new_price_roundtrip.turntables.size() != 1U ||
        new_price_roundtrip.turntables[0].build_cost != 4200 ||
        new_price_roundtrip.turntables[0].refund_value != 2730)
        return fail("catalog-priced paid turntable persistence");
    RailPersistentState invalid_table=table_state;
    invalid_table.turntables[0].piece_group=9999;
    if(ch::rail_persistence::validate(invalid_table))
        return fail("orphaned turntable accepted");
    invalid_table=table_state;
    invalid_table.turntables[0].refund_value=99999;
    if(ch::rail_persistence::validate(invalid_table))
        return fail("turntable unbounded refund accepted");
    invalid_table=table_state;
    invalid_table.turntables.push_back(table_state.turntables.front());
    if(ch::rail_persistence::validate(invalid_table))
        return fail("duplicate turntable accepted");
    invalid_table=table_state;
    invalid_table.stations={{group,1.0}};
    if(ch::rail_persistence::validate(invalid_table))
        return fail("turntable overlapping station accepted");
    invalid_table=table_state;
    invalid_table.edges[0].active=false;
    invalid_table.actions[0].active=false;
    if(ch::rail_persistence::validate(invalid_table))
        return fail("turntable surviving demolished straight accepted");
    RailPersistentState too_short=table_state;
    too_short.nodes=state.nodes;
    too_short.edges=state.edges;
    too_short.actions=state.actions;
    too_short.turntables={{first_group,3500,2275}};
    if(ch::rail_persistence::validate(too_short))
        return fail("4 metre deck below engine length accepted");

    // V2 contains neither turntables nor their T rows; V3 serializer must
    // not break decades of city snapshots by requiring a new field.
    std::string version2=std::string(kChRailPersistenceV2Contract)+v3.substr(v3.find('\n'));
    const std::size_t table_row=version2.find("\nT ");
    if(table_row==std::string::npos)return fail("missing V3 T row");
    version2.erase(table_row,version2.find('\n',table_row+1)-table_row);
    const std::size_t fleet_row = version2.find("\nV ");
    if (fleet_row == std::string::npos) return fail("missing V4 fleet row");
    version2.erase(fleet_row, version2.find('\n',fleet_row+1)-fleet_row);
    const std::size_t auxiliary_row = version2.find("\nW ");
    if (auxiliary_row == std::string::npos) return fail("missing V5 second fleet row");
    version2.erase(auxiliary_row, version2.find('\n', auxiliary_row+1)-auxiliary_row);
    RailPersistentState old_v2;
    if(!ch::rail_persistence::deserialize_payload(version2,old_v2) ||
       !old_v2.turntables.empty() || old_v2.edges.size()!=table_state.edges.size())
        return fail("V2 old save backward compatibility");

    // Earlier save versions owned a legacy 1+7 consist without any purchase row.
    std::string legacy_v3 = std::string(kChRailPersistenceV3Contract) +
        v2_payload.substr(v2_payload.find('\n'));
    const auto legacy_fleet_row = legacy_v3.find("\nV ");
    if (legacy_fleet_row == std::string::npos) return fail("V4 fleet row missing for legacy test");
    legacy_v3.erase(legacy_fleet_row, legacy_v3.find('\n', legacy_fleet_row+1)-legacy_fleet_row);
    const auto v3_second_row = legacy_v3.find("\nW ");
    if (v3_second_row == std::string::npos) return fail("missing V5 row before V3 migration");
    legacy_v3.erase(v3_second_row, legacy_v3.find('\n',v3_second_row+1)-v3_second_row);
    RailPersistentState old_v3;
    if (!ch::rail_persistence::deserialize_payload(legacy_v3, old_v3) ||
        !old_v3.fleet.locomotive_owned || old_v3.fleet.coach_count != 7U)
        return fail("V3 fleet compatibility missing complimentary original train");

    std::string legacy_v4 = std::string(kChRailPersistenceV4Contract) +
        v2_payload.substr(v2_payload.find('\n'));
    const auto v4_second_row = legacy_v4.find("\nW ");
    if (v4_second_row == std::string::npos) return fail("missing V5 row before V4 migration");
    legacy_v4.erase(v4_second_row, legacy_v4.find('\n',v4_second_row+1)-v4_second_row);
    RailPersistentState old_v4;
    if (!ch::rail_persistence::deserialize_payload(legacy_v4, old_v4) ||
        old_v4.secondary_fleet.locomotive_owned ||
        old_v4.secondary_fleet.coach_count != 0U)
        return fail("V4 migration unexpectedly created second train");

    const ch::rail_persistence::ReadResult legacy = [&]() {
        const std::filesystem::path legacy_file = root_dir / "legacy.json";
        std::ofstream file(legacy_file, std::ios::binary | std::ios::trunc);
        file << "{\"saveVersion\":12}\n";
        file.close();
        return ch::rail_persistence::read_city_extension(legacy_file);
    }();
    if (!legacy.valid || legacy.present || !legacy.state.edges.empty() || !legacy.state.stations.empty()) {
        return fail("legacy save must map to empty rail state");
    }

    std::error_code ignored;
    std::filesystem::remove_all(root_dir, ignored);
    std::cout << "rail persistence regression passed\n";
    return 0;
}
