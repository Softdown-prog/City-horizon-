#pragma once

#include "rail_operation_runtime.h"
#include "rail_persistence.h"

#include <algorithm>
#include <cstdint>
#include <optional>
#include <utility>
#include <vector>

inline constexpr const char* kChRailLiveOperationControllerContract = "CH_RAIL_LIVE_OPERATION_CONTROLLER_V1";

namespace ch::rail_live_operation {

class LiveOperationController final {
public:
    [[nodiscard]] bool sync_from_persistent_state(const RailPersistentState& state) {
        RailPlacementGraph replacement;
        if (!replacement.restore_snapshot(state.nodes, state.edges)) return false;
        graph_ = std::move(replacement);

        stations_.erase(
            std::remove_if(stations_.begin(), stations_.end(), [&](const rail_operation::StationDefinition& station) {
                return !graph_.piece_active(station.piece_group);
            }),
            stations_.end());
        return rebuild();
    }

    [[nodiscard]] bool toggle_station(const RailPlacementPieceId piece_group,
                                      const double dwell_seconds = 3.0) {
        if (piece_group == kInvalidRailPlacementPieceId || !graph_.piece_active(piece_group) ||
            !std::isfinite(dwell_seconds) || dwell_seconds < 0.0) {
            return false;
        }

        const auto found = std::find_if(
            stations_.begin(), stations_.end(),
            [&](const rail_operation::StationDefinition& station) {
                return station.piece_group == piece_group;
            });
        if (found != stations_.end()) {
            stations_.erase(found);
            return rebuild();
        }

        const auto previous = stations_;
        stations_.push_back({piece_group, dwell_seconds});
        if (!rebuild()) {
            stations_ = previous;
            (void)rebuild();
            return false;
        }
        return true;
    }

    [[nodiscard]] bool restart() {
        return rebuild();
    }

    void update(const double seconds) noexcept {
        if (operation_active_) train_.update(seconds);
    }

    [[nodiscard]] bool operation_active() const noexcept { return operation_active_; }
    [[nodiscard]] const std::vector<rail_operation::StationDefinition>& stations() const noexcept {
        return stations_;
    }
    [[nodiscard]] const RailPlacementGraph& graph() const noexcept { return graph_; }
    [[nodiscard]] std::optional<rail_operation::TrainPose> train_pose() const noexcept {
        return operation_active_ ? train_.pose() : std::nullopt;
    }

private:
    [[nodiscard]] bool rebuild() {
        operation_active_ = false;
        train_ = rail_operation::TrainRuntime{};
        if (stations_.empty()) return true;

        for (const RailPlacementEdge& edge : graph_.edges()) {
            if (!edge.active) continue;
            rail_operation::OperationalRoute route =
                rail_operation::compile_route(graph_, edge.id, stations_);
            if (!route.valid) continue;
            if (!train_.set_route(std::move(route))) continue;
            train_.set_cruise_speed_mps(3.25);
            train_.set_acceleration_mps2(1.25);
            operation_active_ = true;
            return true;
        }
        return false;
    }

    RailPlacementGraph graph_{};
    std::vector<rail_operation::StationDefinition> stations_;
    rail_operation::TrainRuntime train_{};
    bool operation_active_ = false;
};

} // namespace ch::rail_live_operation
