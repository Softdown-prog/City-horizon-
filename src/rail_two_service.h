#pragma once

#include "rail_operation_runtime.h"
#include "rail_articulated_consist.h"
#include "rail_persistence.h"
#include "rail_signal_interlocking.h"

#include <array>
#include <algorithm>
#include <unordered_set>
#include <vector>

// CH_RAIL_TWO_INDEPENDENT_SERVICES_V1: no track sharing until signalling exists.
// Stations are designated as A1, B1, A2, B2 (key 7) in that order.
namespace ch::rail_two_service {
[[nodiscard]] inline std::optional<rail_operation::OperationalRoute> find_route(
    const RailPlacementGraph& graph,
    const std::vector<RailPersistentStation>& stops,
    const std::size_t offset, const std::uint32_t coaches) {
    if (stops.size() < offset + 2U || coaches > 7U) return std::nullopt;
    const std::vector<rail_operation::StationDefinition> pair{
        {stops[offset].piece_group, stops[offset].dwell_seconds},
        {stops[offset+1U].piece_group, stops[offset+1U].dwell_seconds}};
    for (const auto& edge : graph.edges()) {
        if (!edge.active) continue;
        auto route = rail_operation::compile_route(graph, edge.id, pair);
        if (!route.valid || route.closed || route.stations.size() != 2U) continue;
        rail_operation::TrainRuntime trial;
        if (trial.set_route(route) && trial.configure_terminal_pair(coaches))
            return route;
    }
    return std::nullopt;
}

[[nodiscard]] inline bool routes_share_track(
    const rail_operation::OperationalRoute& first,
    const rail_operation::OperationalRoute& second) {
    std::unordered_set<ch::track::PieceInstanceId> first_pieces;
    for (const auto& step : first.graph_route.steps) first_pieces.insert(step.piece);
    for (const auto& step : second.graph_route.steps) {
        if (first_pieces.contains(step.piece)) return true;
    }
    return false;
}

[[nodiscard]] inline bool second_route_safe(
    const RailPlacementGraph& graph,
    const std::vector<RailPersistentStation>& stations,
    const std::uint32_t first_coaches,
    const std::uint32_t second_coaches) {
    if (stations.size() != 4U) return false;
    const auto first = find_route(graph, stations, 0U, first_coaches);
    const auto second = find_route(graph, stations, 2U, second_coaches);
    return first && second && !routes_share_track(*first, *second) &&
           !ch::rail_signals::routes_cross_at_grade(*first, *second);
}

class AuxiliaryService final {
public:
    [[nodiscard]] bool sync_from_state(const RailPersistentState& state) {
        active_ = false;
        train_ = rail_operation::TrainRuntime{};
        route_ = {};
        if (!state.secondary_fleet.locomotive_owned) return true;
        RailPlacementGraph graph;
        if (!graph.restore_snapshot(state.nodes, state.edges)) return false;
        if (!second_route_safe(graph, state.stations, state.fleet.coach_count,
                               state.secondary_fleet.coach_count)) return true;
        auto route = find_route(graph, state.stations, 2U, state.secondary_fleet.coach_count);
        if (!route || !train_.set_route(*route) ||
            !train_.configure_terminal_pair(state.secondary_fleet.coach_count)) return true;
        route_ = std::move(*route);
        coach_count_ = state.secondary_fleet.coach_count;
        train_.set_cruise_speed_mps(3.25);
        train_.set_acceleration_mps2(1.25);
        active_ = true;
        return true;
    }
    void update(const double elapsed) noexcept { if (active_) train_.update(elapsed); }
    [[nodiscard]] bool active() const noexcept { return active_; }
    [[nodiscard]] std::uint32_t coach_count() const noexcept { return coach_count_; }
    [[nodiscard]] const rail_operation::OperationalRoute* route() const noexcept {
        return active_ ? &route_ : nullptr;
    }
    [[nodiscard]] std::optional<rail_operation::TrainPose> train_pose() const noexcept {
        return active_ ? train_.pose() : std::nullopt;
    }
    [[nodiscard]] std::vector<rail_operation::ArticulatedUnitPose> articulated_poses() const {
        if (!active_ || !route_.valid) return {};
        const auto lead = train_.pose();
        if (!lead) return {};
        rail_operation::ArticulatedConsistSpec spec;
        spec.coach_count = coach_count_;
        return rail_operation::build_articulated_consist_poses(route_, *lead, spec);
    }
private:
    rail_operation::TrainRuntime train_{};
    rail_operation::OperationalRoute route_{};
    std::uint32_t coach_count_ = 0U;
    bool active_ = false;
};
} // namespace ch::rail_two_service
