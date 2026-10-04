#pragma once

#include "rail_placement_track_graph_adapter.h"

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

class TrainRuntime final {
public:
    explicit TrainRuntime(OperationalRoute route = {}) : route_(std::move(route)) {}

    [[nodiscard]] bool set_route(OperationalRoute route) {
        if (!route.valid || !(route.length_m > 0.0)) return false;
        route_ = std::move(route);
        reset();
        return true;
    }

    void reset() noexcept {
        distance_m_ = 0.0;
        speed_mps_ = 0.0;
        dwell_remaining_s_ = 0.0;
        next_station_index_ = 0U;
        stopped_ = false;
        current_station_.reset();
    }

    void set_cruise_speed_mps(const double speed) noexcept {
        if (std::isfinite(speed) && speed > 0.0) cruise_speed_mps_ = speed;
    }

    void set_acceleration_mps2(const double acceleration) noexcept {
        if (std::isfinite(acceleration) && acceleration > 0.0) acceleration_mps2_ = acceleration;
    }

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
            current_station_.reset();
            if (route_.closed && next_station_index_ >= route_.stations.size()) next_station_index_ = 0U;
        }

        speed_mps_ = std::min(cruise_speed_mps_, speed_mps_ + acceleration_mps2_ * seconds);
        const double proposed = distance_m_ + speed_mps_ * seconds;

        if (next_station_index_ < route_.stations.size()) {
            const StationStop& stop = route_.stations[next_station_index_];
            if (stop.distance_m > distance_m_ + kDistanceEpsilon &&
                stop.distance_m <= proposed + kDistanceEpsilon) {
                distance_m_ = stop.distance_m;
                speed_mps_ = 0.0;
                dwell_remaining_s_ = stop.dwell_seconds;
                current_station_ = stop.piece_group;
                ++next_station_index_;
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
    double dwell_remaining_s_ = 0.0;
    std::size_t next_station_index_ = 0U;
    bool stopped_ = false;
    std::optional<RailPlacementPieceId> current_station_;
};

} // namespace ch::rail_operation
