#pragma once

#include "rail_operation_runtime.h"
#include "rail_siding_topology.h"
#include "rail_detached_locomotive_shunt.h"
#include "rail_turntable_return.h"
#include "rail_persistence.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <optional>
#include <utility>
#include <vector>

inline constexpr const char* kChRailLiveOperationControllerContract = "CH_RAIL_LIVE_OPERATION_CONTROLLER_V2";

namespace ch::rail_live_operation {

class LiveOperationController final {
public:
    [[nodiscard]] bool sync_from_persistent_state(const RailPersistentState& state) {
        RailPlacementGraph replacement;
        if (!replacement.restore_snapshot(state.nodes, state.edges)) return false;
        graph_ = std::move(replacement);
        turntables_=state.turntables;

        std::vector<rail_operation::StationDefinition> restored_stations;
        restored_stations.reserve(state.stations.size());
        for (const RailPersistentStation& station : state.stations) {
            if (!std::isfinite(station.dwell_seconds) || station.dwell_seconds < 0.0) return false;
            if (!graph_.piece_active(station.piece_group)) continue;
            const auto duplicate = std::find_if(
                restored_stations.begin(), restored_stations.end(),
                [&](const rail_operation::StationDefinition& existing) {
                    return existing.piece_group == station.piece_group;
                });
            if (duplicate != restored_stations.end()) return false;
            restored_stations.push_back({station.piece_group, station.dwell_seconds});
        }
        stations_ = std::move(restored_stations);
        if (!rebuild()) return false;
        publish_stations();
        return true;
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
            const auto previous = stations_;
            stations_.erase(found);
            if (!rebuild()) {
                stations_ = previous;
                (void)rebuild();
                return false;
            }
            publish_stations();
            return true;
        }

        const auto previous = stations_;
        stations_.push_back({piece_group, dwell_seconds});
        if (!rebuild()) {
            stations_ = previous;
            (void)rebuild();
            return false;
        }
        publish_stations();
        return true;
    }

    [[nodiscard]] bool restart() {
        return rebuild();
    }

    void update(const double seconds) noexcept {
        if (!operation_active_) return;
        if(return_.active()){
            return_.update(seconds);
            return;
        }
        if (shunt_.active()) {
            shunt_.update(seconds);
            if(shunt_.awaiting_turning() && return_plan_) {
                (void)return_.start(*return_plan_);
            }
            return;
        }
        train_.update(seconds);
        // No route into invented sidings or turning platforms is allowed.
        if (train_.awaiting_terminal_maneuver() && shunt_path_) {
            (void)shunt_.start(*shunt_path_);
        }
    }

    [[nodiscard]] bool operation_active() const noexcept { return operation_active_; }
    [[nodiscard]] const std::vector<rail_operation::StationDefinition>& stations() const noexcept {
        return stations_;
    }
    [[nodiscard]] const RailPlacementGraph& graph() const noexcept { return graph_; }
    [[nodiscard]] const rail_operation::OperationalRoute* operational_route() const noexcept {
        return operation_active_ && operational_route_.valid ? &operational_route_ : nullptr;
    }
    [[nodiscard]] std::optional<rail_operation::TrainPose> train_pose() const noexcept {
        if (!operation_active_) return std::nullopt;
        if(return_.active())return return_.locomotive_pose(operational_route_);
        if (shunt_.active()) return shunt_.locomotive_pose();
        return train_.pose();
    }

    [[nodiscard]] bool shunting_locomotive() const noexcept {
        return operation_active_ &&
            (return_.active()? !return_.coupled():shunt_.active());
    }
    [[nodiscard]] bool return_service_active() const noexcept {
        return operation_active_ && return_.active();
    }
    [[nodiscard]] bool return_coupled() const noexcept {
        return operation_active_ && return_.coupled();
    }
    [[nodiscard]] rail_operation::ReturnPhase return_phase() const noexcept {
        return return_.phase();
    }
    [[nodiscard]] bool turntable_return_available() const noexcept {
        return operation_active_ && return_plan_.has_value();
    }
    [[nodiscard]] double turntable_rotation_radians() const noexcept {
        return return_.rotation_radians();
    }
    [[nodiscard]] bool locomotive_awaiting_turning() const noexcept {
        return operation_active_ && shunt_.awaiting_turning() && !return_.active();
    }
    [[nodiscard]] std::optional<rail_operation::DetachedShuntPhase> locomotive_shunt_phase() const noexcept {
        if(!shunting_locomotive())return std::nullopt;
        return shunt_.phase();
    }
    [[nodiscard]] std::vector<rail_operation::ArticulatedUnitPose> articulated_poses() const {
        if(!operation_active_ || !operational_route_.valid)return {};
        const auto lead=train_.pose();
        if(!lead)return {};
        auto units=rail_operation::build_articulated_consist_poses(operational_route_,*lead);
        if(units.size()!=8U)return {};
        if(return_.active()){
            const auto locomotive=return_.locomotive_pose(operational_route_);
            if(!locomotive)return {};
            units.front().pose=*locomotive;
            units.front().route_distance_m=locomotive->distance_m;
            if(return_.coupled()) {
                // Seven persistent coach identities reverse their ORDER
                // relative to the locomotive, not their existence.
                // Loco (west) -> coach 7 -> coach 6 ... -> coach 1 (east).
                constexpr double first=(5.2+3.9)*0.5+0.42;
                constexpr double pitch=3.9+0.42;
                for(std::size_t i=1;i<units.size();++i) {
                    const double distance=return_.distance_m()+first+(7-i)*pitch;
                    const auto coach=rail_operation::sample_operational_route_pose(
                        operational_route_,distance,return_.speed_mps(),
                        return_.phase()==rail_operation::ReturnPhase::parked_at_a);
                    if(!coach)return {};
                    units[i].pose=rail_operation::orient_train_unit_from_bogies(
                        operational_route_,*coach,3.9);
                    units[i].route_distance_m=distance;
                }
                std::reverse(units.begin()+1,units.end());
            }
        } else if(shunt_.active()){
            const auto locomotive=shunt_.locomotive_pose();
            if(!locomotive)return {};
            units.front().pose=*locomotive;
        }
        return units;
    }

    // Exposed to the UI: a terminal train must never quietly reverse with a
    // backwards locomotive or leave station B before a track-based maneuver.
    [[nodiscard]] bool awaiting_terminal_maneuver() const noexcept {
        return operation_active_ && train_.awaiting_terminal_maneuver() &&
            !shunt_.active() && !return_.active();
    }
    [[nodiscard]] bool two_station_service_active() const noexcept {
        return operation_active_ && train_.terminal_pair_enabled();
    }
    // Presence of a built, topologically connected passing siding DOES NOT
    // authorize reversing the locomotive or moving the seven coaches.
    // The turntable and dispatch/coupling state machine remain separate.
    [[nodiscard]] bool connected_siding_available() const noexcept {
        return two_station_service_active() && connected_siding_.has_value();
    }
    [[nodiscard]] bool locomotive_shunt_route_safe() const noexcept {
        return two_station_service_active() && shunt_path_.has_value();
    }
    [[nodiscard]] const std::optional<rail_operation::ConnectedSiding>& connected_siding() const noexcept {
        return connected_siding_;
    }

private:
    void publish_stations() const {
        std::vector<RailPersistentStation> persistent;
        persistent.reserve(stations_.size());
        for (const rail_operation::StationDefinition& station : stations_) {
            persistent.push_back({station.piece_group, station.dwell_seconds});
        }
        rail_persistence::set_runtime_stations(std::move(persistent));
    }

    [[nodiscard]] bool rebuild() {
        operation_active_ = false;
        operational_route_ = {};
        connected_siding_.reset();
        shunt_path_.reset();
        return_plan_.reset();
        shunt_=rail_operation::DetachedLocomotiveShunt{};
        return_=rail_operation::TurntableReturnRuntime{};
        train_ = rail_operation::TrainRuntime{};
        if (stations_.empty()) return true;

        for (const RailPlacementEdge& edge : graph_.edges()) {
            if (!edge.active) continue;
            rail_operation::OperationalRoute route =
                rail_operation::compile_route(graph_, edge.id, stations_);
            if (!route.valid) continue;
            rail_operation::OperationalRoute runtime_route = route;
            if (!train_.set_route(std::move(runtime_route))) continue;
            // Use the ordinary multi-stop runtime for loops and legacy single
            // station saves. For exactly two stations on an OPEN line, require
            // the full 1+7 consist to fit and begin service at station A.
            // No imaginary siding is assumed or synthesized here.
            if (!route.closed && stations_.size() == 2U &&
                !train_.configure_terminal_pair()) {
                continue;
            }
            if (train_.terminal_pair_enabled()) {
                connected_siding_ = rail_operation::find_connected_siding(graph_, route);
                if (connected_siding_) {
                    shunt_path_ = rail_operation::compile_detached_locomotive_shunt(
                        graph_, route, *connected_siding_);
                    if(shunt_path_){
                        return_plan_ = rail_operation::compile_turntable_return(
                            graph_,route,*connected_siding_,*shunt_path_,turntables_);
                    }
                }
            }
            operational_route_ = std::move(route);
            train_.set_cruise_speed_mps(3.25);
            train_.set_acceleration_mps2(1.25);
            operation_active_ = true;
            return true;
        }
        return false;
    }

    RailPlacementGraph graph_{};
    std::vector<rail_operation::StationDefinition> stations_;
    rail_operation::OperationalRoute operational_route_{};
    std::optional<rail_operation::ConnectedSiding> connected_siding_{};
    std::optional<rail_operation::ShuntPath> shunt_path_{};
    std::optional<rail_operation::TurntableReturnPlan> return_plan_{};
    std::vector<RailPersistentTurntable> turntables_{};
    rail_operation::DetachedLocomotiveShunt shunt_{};
    rail_operation::TurntableReturnRuntime return_{};
    rail_operation::TrainRuntime train_{};
    bool operation_active_ = false;
};

} // namespace ch::rail_live_operation
