#pragma once

#include "rail_placement_track_graph_adapter.h"
#include "rail_station_network.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <optional>
#include <unordered_map>
#include <unordered_set>
#include <vector>

inline constexpr const char* kChRailOperationRuntimeContract = "CH_RAIL_OPERATION_RUNTIME_V1";

namespace ch::rail_operation {

struct StationDefinition {
    RailPlacementPieceId piece_group = kInvalidRailPlacementPieceId;
    double dwell_seconds = 3.0;
};

struct StationStop {
    RailPlacementPieceId piece_group = kInvalidRailPlacementPieceId;
    double distance_m = 0.0;
    double dwell_seconds = 0.0;
};

struct OperationalRoute {
    ch::track::TrackGraph topology{};
    ch::track::GraphRoute graph_route{};
    ch::track::CompiledPolyline polyline{};
    std::vector<double> cumulative_m;
    std::vector<StationStop> stations;
    double length_m = 0.0;
    bool valid = false;
    bool closed = false;
};

struct TrainPose {
    double distance_m = 0.0;
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;
    double tangent_x = 1.0;
    double tangent_y = 0.0;
    double tangent_z = 0.0;
    double speed_mps = 0.0;
    bool dwelling = false;
    std::optional<RailPlacementPieceId> station_piece;
};

namespace detail {

[[nodiscard]] inline double point_distance(const ch::track::Point3& a,
                                           const ch::track::Point3& b) noexcept {
    const double dx = b.x - a.x;
    const double dy = b.y - a.y;
    const double dz = b.z - a.z;
    return std::sqrt(dx * dx + dy * dy + dz * dz);
}

[[nodiscard]] inline double route_length(const ch::track::RouteDescriptor& route) noexcept {
    if (route.centerline.size() < 2U) return 0.0;
    double length = 0.0;
    for (std::size_t i = 1U; i < route.centerline.size(); ++i) {
        const double step = point_distance(route.centerline[i - 1U].position,
                                           route.centerline[i].position);
        if (!std::isfinite(step) || !(step > 0.0)) return 0.0;
        length += step;
    }
    return length;
}

[[nodiscard]] inline RailPlacementPieceId piece_group_for_topology_piece(
    const RailPlacementGraph& placement,
    const ch::rail::RailPlacementTopologyBuildResult& built,
    const ch::track::PieceInstanceId piece) noexcept {
    for (const RailPlacementEdge& edge : placement.edges()) {
        if (!edge.active || edge.id >= built.edge_piece.size()) continue;
        if (built.edge_piece[edge.id] == piece) return edge.piece_group;
    }
    return kInvalidRailPlacementPieceId;
}

[[nodiscard]] inline bool build_cumulative(OperationalRoute& route) {
    const auto& points = route.polyline.points;
    if (points.size() < 2U) return false;
    route.cumulative_m.clear();
    route.cumulative_m.reserve(points.size() + (route.closed ? 1U : 0U));
    route.cumulative_m.push_back(0.0);
    for (std::size_t i = 1U; i < points.size(); ++i) {
        const double step = point_distance(points[i - 1U].position, points[i].position);
        if (!std::isfinite(step) || !(step > 0.0)) return false;
        route.cumulative_m.push_back(route.cumulative_m.back() + step);
    }
    if (route.closed) {
        const double closing = point_distance(points.back().position, points.front().position);
        if (!std::isfinite(closing) || !(closing > 0.0)) return false;
        route.length_m = route.cumulative_m.back() + closing;
    } else {
        route.length_m = route.cumulative_m.back();
    }
    return std::isfinite(route.length_m) && route.length_m > 0.0;
}

} // namespace detail

[[nodiscard]] inline OperationalRoute compile_route(
    const RailPlacementGraph& placement,
    const RailPlacementEdgeId start_edge,
    const std::vector<StationDefinition>& station_definitions = {}) {
    OperationalRoute result;
    const RailPlacementEdge* starting_edge = placement.edge(start_edge);
    if (starting_edge == nullptr || starting_edge->id >= placement.edges().size()) return result;

    const ch::rail::RailPlacementTopologyBuildResult built = ch::rail::build_track_graph(placement);
    if (!built.valid || start_edge >= built.edge_piece.size() ||
        built.edge_piece[start_edge] == ch::track::kInvalidPieceInstanceId) {
        return result;
    }

    result.topology = built.graph;
    const ch::track::PieceInstanceId starting_piece_id = built.edge_piece[start_edge];
    const ch::track::PieceInstance* starting_piece = result.topology.piece(starting_piece_id);
    if (starting_piece == nullptr || start_edge >= built.edge_route.size()) return {};
    const std::size_t route_index = built.edge_route[start_edge];
    if (route_index >= starting_piece->descriptor.routes.size()) return {};

    const ch::track::RouteDescriptor& starting_route = starting_piece->descriptor.routes[route_index];
    result.graph_route = result.topology.build_route({starting_piece_id, starting_route.entry_port});
    if (!result.graph_route.ok() || result.graph_route.steps.empty()) return {};

    result.polyline = result.topology.compile_polyline(result.graph_route);
    if (!result.polyline.valid) return {};
    result.closed = result.graph_route.closed;
    if (!detail::build_cumulative(result)) return {};

    std::unordered_map<RailPlacementPieceId, double> dwell_by_piece;
    for (const StationDefinition& station : station_definitions) {
        if (station.piece_group == kInvalidRailPlacementPieceId ||
            !std::isfinite(station.dwell_seconds) || station.dwell_seconds < 0.0 ||
            dwell_by_piece.contains(station.piece_group)) {
            return {};
        }
        dwell_by_piece.emplace(station.piece_group, station.dwell_seconds);
    }

    std::unordered_set<RailPlacementPieceId> visited_station_groups;
    double route_cursor = 0.0;
    for (const ch::track::RouteStep& step : result.graph_route.steps) {
        const ch::track::PieceInstance* piece = result.topology.piece(step.piece);
        if (piece == nullptr || step.route >= piece->descriptor.routes.size()) return {};
        const double step_length = detail::route_length(piece->descriptor.routes[step.route]);
        if (!(step_length > 0.0) || !std::isfinite(step_length)) return {};

        const RailPlacementPieceId group =
            detail::piece_group_for_topology_piece(placement, built, step.piece);
        const auto station = dwell_by_piece.find(group);
        if (station != dwell_by_piece.end()) {
            if (!visited_station_groups.insert(group).second) return {};
            result.stations.push_back({group, route_cursor + step_length * 0.5, station->second});
        }
        route_cursor += step_length;
    }

    if (!station_definitions.empty() && visited_station_groups.size() != station_definitions.size()) {
        return {};
    }
    std::sort(result.stations.begin(), result.stations.end(),
              [](const StationStop& a, const StationStop& b) { return a.distance_m < b.distance_m; });
    result.valid = true;
    return result;
}

// Bridge from stable station IDs to the existing operational route compiler.
// This deliberately does not assume that the first two stations are A and B.
// Current graph compiler still chooses its existing track traversal; a service
// with branches requires explicit path selection before dispatch.
[[nodiscard]] inline OperationalRoute compile_station_network_route(
    const RailPlacementGraph& placement, RailPlacementEdgeId start_edge,
    const ch::rail_network::StationRegistry& registry,
    const ch::rail_network::Service& service) {
    if (!registry.validate_service(placement, service)) return {};
    std::vector<StationDefinition> definitions;
    std::unordered_set<ch::rail_network::StationId> visited;
    for (auto id : service.stops) {
        if (!visited.insert(id).second) continue;
        const auto* station = registry.find(id);
        if (!station) return {};
        definitions.push_back({station->piece_group, station->dwell_seconds});
    }
    OperationalRoute route = compile_route(placement, start_edge, definitions);
    if (!route.valid || route.stations.size() != definitions.size()) return {};
    // Fail closed if topology traversal cannot honor the requested stop order.
    std::size_t stop = 0;
    for (const auto& actual : route.stations) {
        if (stop >= service.stops.size()) return {};
        const auto* expected = registry.find(service.stops[stop]);
        if (!expected || actual.piece_group != expected->piece_group) return {};
        ++stop;
    }
    // A return to the origin needs a separately authored return path.
    if (stop != service.stops.size()) return {};
    return route;
}

class TrainRuntime final {
public:
    explicit TrainRuntime(OperationalRoute route = {}) : route_(std::move(route)) {}

    [[nodiscard]] bool set_route(OperationalRoute route) {
        if (!route.valid || !(route.length_m > 0.0)) return false;
        route_ = std::move(route);
        terminal_pair_enabled_ = false;
        reset();
        return true;
    }

    // CH_RAIL_TWO_STATION_SERVICE_V1.
    // Only a validated open two-station route may run in terminal mode.
    // A locomotive with seven 3.9m coaches needs sufficient track behind A.
    // This is NOT a turnaround: B is a safe parking state until an actually
    // authored, connected siding/return path can be selected by the runtime.
    [[nodiscard]] bool configure_terminal_pair(const std::size_t coach_count = 7U) noexcept {
        if (!route_.valid || route_.closed || route_.stations.size() != 2U ||
            coach_count > 7U) return false;
        const StationStop& a = route_.stations[0];
        const StationStop& b = route_.stations[1];
        constexpr double locomotive_length_m = 5.2;
        constexpr double coach_length_m = 3.9;
        constexpr double coupler_gap_m = 0.42;
        const double trailing_clearance_m = coach_count == 0U ? locomotive_length_m * 0.5 :
            locomotive_length_m * 0.5 + coupler_gap_m + coach_length_m +
            static_cast<double>(coach_count - 1U) * (coach_length_m + coupler_gap_m);
        const double consist_length_m = locomotive_length_m +
            static_cast<double>(coach_count) * (coach_length_m + coupler_gap_m);
        if (!std::isfinite(a.distance_m) || !std::isfinite(b.distance_m) ||
            a.distance_m < trailing_clearance_m ||
            b.distance_m - a.distance_m < consist_length_m ||
            route_.length_m - b.distance_m < locomotive_length_m * 0.5) {
            return false;
        }
        terminal_pair_enabled_ = true;
        reset();
        return true;
    }

    [[nodiscard]] bool terminal_pair_enabled() const noexcept { return terminal_pair_enabled_; }
    [[nodiscard]] bool awaiting_terminal_maneuver() const noexcept {
        return terminal_pair_enabled_ && stopped_ && next_station_index_ == route_.stations.size();
    }

    void reset() noexcept {
        distance_m_ = 0.0;
        speed_mps_ = 0.0;
        dwell_remaining_s_ = 0.0;
        next_station_index_ = 0U;
        stopped_ = false;
        signal_waiting_ = false;
        signal_stop_m_.reset();
        current_station_.reset();
        if (terminal_pair_enabled_) {
            distance_m_ = route_.stations.front().distance_m;
            dwell_remaining_s_ = route_.stations.front().dwell_seconds;
            current_station_ = route_.stations.front().piece_group;
            next_station_index_ = 1U;
        }
    }

    void set_cruise_speed_mps(const double speed) noexcept {
        if (std::isfinite(speed) && speed > 0.0) cruise_speed_mps_ = speed;
    }

    void set_acceleration_mps2(const double acceleration) noexcept {
        if (std::isfinite(acceleration) && acceleration > 0.0) acceleration_mps2_ = acceleration;
    }

    // Physical, gradual braking ahead of terminal B rather than snapping
    // directly from cruising speed to zero at the platform midpoint.
    void set_service_braking_mps2(const double deceleration) noexcept {
        if (std::isfinite(deceleration) && deceleration > 0.0)
            service_braking_mps2_ = deceleration;
    }

    // A signal authority boundary is an absolute distance on this compiled
    // route (after the signal's safety offset). A null boundary means clear.
    // Denied blocks must never be represented by a negative or NaN distance.
    [[nodiscard]] bool set_signal_stop_m(const std::optional<double> stop_m) noexcept {
        if (stop_m && (!route_.valid || !std::isfinite(*stop_m) ||
                       *stop_m < 0.0 || *stop_m > route_.length_m))
            return false;
        signal_stop_m_ = stop_m;
        if (!stop_m) signal_waiting_ = false;
        return true;
    }
    [[nodiscard]] bool waiting_at_signal() const noexcept { return signal_waiting_; }
    [[nodiscard]] std::optional<double> signal_stop_m() const noexcept { return signal_stop_m_; }

    [[nodiscard]] bool valid() const noexcept { return route_.valid; }
    [[nodiscard]] bool stopped() const noexcept { return stopped_; }
    [[nodiscard]] double distance_m() const noexcept { return distance_m_; }
    [[nodiscard]] double speed_mps() const noexcept { return speed_mps_; }

    void update(const double seconds) noexcept {
        if (!route_.valid || !std::isfinite(seconds) || seconds <= 0.0 || stopped_) return;

        if (dwell_remaining_s_ > 0.0) {
            dwell_remaining_s_ = std::max(0.0, dwell_remaining_s_ - seconds);
            speed_mps_ = 0.0;
            if (dwell_remaining_s_ > 0.0) return;
            if (terminal_pair_enabled_ && next_station_index_ >= route_.stations.size()) {
                // The B platform is a real stop, not a point to overshoot.
                // Remain here until a physical run-around route is supported.
                stopped_ = true;
                return;
            }
            current_station_.reset();
            if (route_.closed && next_station_index_ >= route_.stations.size()) next_station_index_ = 0U;
        }

        // A denied block becomes a *stopping target* ahead of the locomotive.
        // The usual A->B service brake and the signal brake share the same
        // deceleration envelope; whichever is closer controls the speed.
        const double station_target = terminal_pair_enabled_ &&
            next_station_index_ < route_.stations.size()
            ? route_.stations[next_station_index_].distance_m
            : route_.length_m;
        const bool signal_first = signal_stop_m_ &&
            *signal_stop_m_ < station_target - 0.02;
        if (signal_first && *signal_stop_m_ <= distance_m_ + 0.02) {
            speed_mps_ = 0.0;
            signal_waiting_ = true;
            return;
        }
        signal_waiting_ = false;
        if (signal_first || (terminal_pair_enabled_ &&
                            next_station_index_ < route_.stations.size())) {
            // v² <= 2*a*distance, with the acceleration/deceleration bounded
            // per tick. A dynamic signal cannot require a backwards teleport.
            const double target = signal_first ? *signal_stop_m_ : station_target;
            const double remaining = std::max(0.0, target - distance_m_);
            const double safe_speed = std::sqrt(2.0 * service_braking_mps2_ * remaining);
            const double target_speed = std::min(cruise_speed_mps_, safe_speed);
            if (speed_mps_ > target_speed) {
                speed_mps_ = std::max(target_speed,
                    speed_mps_ - service_braking_mps2_ * seconds);
            } else {
                speed_mps_ = std::min(target_speed,
                    speed_mps_ + acceleration_mps2_ * seconds);
            }
        } else {
            speed_mps_ = std::min(cruise_speed_mps_, speed_mps_ +
                                  acceleration_mps2_ * seconds);
        }
        const double proposed = distance_m_ + speed_mps_ * seconds;
        if (signal_first &&
            (proposed >= *signal_stop_m_ - kDistanceEpsilon ||
             *signal_stop_m_ - distance_m_ <= 0.02)) {
            distance_m_ = std::max(distance_m_, *signal_stop_m_);
            speed_mps_ = 0.0;
            signal_waiting_ = true;
            return;
        }

        if (next_station_index_ < route_.stations.size()) {
            const StationStop& stop = route_.stations[next_station_index_];
            if (stop.distance_m > distance_m_ + kDistanceEpsilon &&
                (stop.distance_m <= proposed + kDistanceEpsilon ||
                 (terminal_pair_enabled_ && stop.distance_m - distance_m_ <= 0.02))) {
                distance_m_ = stop.distance_m;
                speed_mps_ = 0.0;
                dwell_remaining_s_ = stop.dwell_seconds;
                current_station_ = stop.piece_group;
                ++next_station_index_;
                if (terminal_pair_enabled_ && next_station_index_ >= route_.stations.size() &&
                    dwell_remaining_s_ <= 0.0) {
                    stopped_ = true;
                }
                return;
            }
        }

        if (route_.closed) {
            distance_m_ = std::fmod(proposed, route_.length_m);
            if (distance_m_ < 0.0) distance_m_ += route_.length_m;
            if (proposed >= route_.length_m) {
                next_station_index_ = 0U;
            }
        } else if (proposed >= route_.length_m) {
            distance_m_ = route_.length_m;
            speed_mps_ = 0.0;
            stopped_ = true;
        } else {
            distance_m_ = proposed;
        }
    }

    [[nodiscard]] std::optional<TrainPose> pose() const noexcept {
        if (!route_.valid || route_.polyline.points.size() < 2U || route_.cumulative_m.empty()) return std::nullopt;
        const auto& points = route_.polyline.points;
        double distance = std::clamp(distance_m_, 0.0, route_.length_m);

        std::size_t segment = 0U;
        double segment_start = 0.0;
        double segment_length = 0.0;
        if (!route_.closed && distance >= route_.length_m) {
            segment = points.size() - 2U;
            segment_start = route_.cumulative_m[segment];
            segment_length = route_.cumulative_m[segment + 1U] - segment_start;
        } else if (route_.closed && distance >= route_.cumulative_m.back()) {
            segment = points.size() - 1U;
            segment_start = route_.cumulative_m.back();
            segment_length = route_.length_m - segment_start;
        } else {
            const auto upper = std::upper_bound(route_.cumulative_m.begin(), route_.cumulative_m.end(), distance);
            segment = upper == route_.cumulative_m.begin()
                ? 0U
                : static_cast<std::size_t>(std::distance(route_.cumulative_m.begin(), upper) - 1);
            segment = std::min(segment, points.size() - 2U);
            segment_start = route_.cumulative_m[segment];
            segment_length = route_.cumulative_m[segment + 1U] - segment_start;
        }

        const std::size_t next = (segment + 1U) % points.size();
        if (!(segment_length > 0.0)) return std::nullopt;
        const double t = std::clamp((distance - segment_start) / segment_length, 0.0, 1.0);
        const auto& a = points[segment].position;
        const auto& b = points[next].position;
        const double dx = b.x - a.x;
        const double dy = b.y - a.y;
        const double dz = b.z - a.z;
        const double tangent_length = std::sqrt(dx * dx + dy * dy + dz * dz);
        if (!(tangent_length > 0.0)) return std::nullopt;

        TrainPose result;
        result.distance_m = distance_m_;
        result.x = a.x + dx * t;
        result.y = a.y + dy * t;
        result.z = a.z + dz * t;
        result.tangent_x = dx / tangent_length;
        result.tangent_y = dy / tangent_length;
        result.tangent_z = dz / tangent_length;
        result.speed_mps = speed_mps_;
        result.dwelling = dwell_remaining_s_ > 0.0 || current_station_.has_value();
        result.station_piece = current_station_;
        return result;
    }

private:
    static constexpr double kDistanceEpsilon = 1.0e-8;

    OperationalRoute route_{};
    double distance_m_ = 0.0;
    double speed_mps_ = 0.0;
    double cruise_speed_mps_ = 4.0;
    double acceleration_mps2_ = 1.5;
    double service_braking_mps2_ = 0.8;
    std::optional<double> signal_stop_m_;
    bool signal_waiting_ = false;
    double dwell_remaining_s_ = 0.0;
    std::size_t next_station_index_ = 0U;
    bool stopped_ = false;
    bool terminal_pair_enabled_ = false;
    std::optional<RailPlacementPieceId> current_station_;
};

} // namespace ch::rail_operation
