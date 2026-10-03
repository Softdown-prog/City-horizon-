#pragma once

#include "track_piece_descriptor.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <optional>
#include <utility>
#include <vector>

namespace ch::track {

inline constexpr const char* kTrackGraphContract = "CH_TRACK_GRAPH_V2";

using PieceInstanceId = std::uint32_t;
using ConnectionId = std::uint32_t;
inline constexpr PieceInstanceId kInvalidPieceInstanceId = std::numeric_limits<PieceInstanceId>::max();
inline constexpr ConnectionId kInvalidConnectionId = std::numeric_limits<ConnectionId>::max();

struct PieceTransform {
    Point3 origin{};
    double yaw_radians = 0.0;
};

struct PortRef {
    PieceInstanceId piece = kInvalidPieceInstanceId;
    std::size_t port = 0U;

    [[nodiscard]] bool operator==(const PortRef&) const = default;
};

struct PieceInstance {
    PieceInstanceId id = kInvalidPieceInstanceId;
    PieceDescriptor descriptor{};
    PieceTransform transform{};
    std::size_t active_route = 0U;
};

struct Connection {
    ConnectionId id = kInvalidConnectionId;
    PortRef a{};
    PortRef b{};
};

struct RouteStep {
    PieceInstanceId piece = kInvalidPieceInstanceId;
    std::size_t route = 0U;
    bool reversed = false;
};

enum class RouteStatus : std::uint8_t {
    ok,
    invalid_start,
    no_route_for_port,
    broken_connection,
    step_limit,
};

struct GraphRoute {
    RouteStatus status = RouteStatus::invalid_start;
    std::vector<RouteStep> steps;
    bool closed = false;
    std::optional<PortRef> gap;

    [[nodiscard]] bool ok() const noexcept { return status == RouteStatus::ok; }
};

struct WorldRoutePoint {
    Point3 position{};
    double roll_degrees = 0.0;
    DriveMode drive_mode = DriveMode::free;
    double target_speed_mps = -1.0;
};

struct CompiledPolyline {
    bool valid = false;
    bool closed = false;
    std::vector<WorldRoutePoint> points;
};

class TrackGraph final {
public:
    [[nodiscard]] std::optional<PieceInstanceId> add_piece(PieceDescriptor descriptor,
                                                           PieceTransform transform = {}) {
        if (!valid_descriptor(descriptor) || !finite_point(transform.origin) ||
            !std::isfinite(transform.yaw_radians) ||
            pieces_.size() >= static_cast<std::size_t>(kInvalidPieceInstanceId)) {
            return std::nullopt;
        }
        const PieceInstanceId id = static_cast<PieceInstanceId>(pieces_.size());
        pieces_.push_back({id, std::move(descriptor), transform, 0U});
        return id;
    }

    [[nodiscard]] bool set_active_route(const PieceInstanceId piece_id, const std::size_t route_index) {
        PieceInstance* instance = piece_mut(piece_id);
        if (instance == nullptr || route_index >= instance->descriptor.routes.size()) return false;
        instance->active_route = route_index;
        return true;
    }

    [[nodiscard]] std::optional<ConnectionId> connect(const PortRef a,
                                                       const PortRef b,
                                                       const double position_tolerance_m = 1.0e-4,
                                                       const double direction_tolerance_radians = 0.02) {
        if (a == b || !valid_port_ref(a) || !valid_port_ref(b) ||
            !std::isfinite(position_tolerance_m) || position_tolerance_m < 0.0 ||
            !std::isfinite(direction_tolerance_radians) || direction_tolerance_radians < 0.0 ||
            direction_tolerance_radians >= 1.57079632679489661923 ||
            connection_for(a).has_value() || connection_for(b).has_value() ||
            connections_.size() >= static_cast<std::size_t>(kInvalidConnectionId)) {
            return std::nullopt;
        }
        const PieceInstance& pa = pieces_[a.piece];
        const PieceInstance& pb = pieces_[b.piece];
        if (pa.descriptor.network != pb.descriptor.network) return std::nullopt;

        const Point3 wa = world_port_position(a);
        const Point3 wb = world_port_position(b);
        const double tolerance_sq = position_tolerance_m * position_tolerance_m;
        if (squared_distance(wa, wb) > tolerance_sq) return std::nullopt;

        const Direction3 da = world_port_direction(a);
        const Direction3 db = world_port_direction(b);
        const double facing = da.x * db.x + da.y * db.y + da.z * db.z;
        if (facing > -std::cos(direction_tolerance_radians)) return std::nullopt;

        const ConnectionId id = static_cast<ConnectionId>(connections_.size());
        connections_.push_back({id, a, b});
        return id;
    }

    [[nodiscard]] GraphRoute build_route(const PortRef start,
                                         const std::size_t max_steps = 4096U) const {
        GraphRoute result;
        if (!valid_port_ref(start) || max_steps == 0U) {
            result.status = RouteStatus::invalid_start;
            return result;
        }

        PortRef current = start;
        std::vector<PortRef> visited;
        visited.reserve(std::min(max_steps, pieces_.size() + 1U));

        for (std::size_t step_count = 0; step_count < max_steps; ++step_count) {
            if (current == start && !result.steps.empty()) {
                result.status = RouteStatus::ok;
                result.closed = true;
                return result;
            }
            if (std::find(visited.begin(), visited.end(), current) != visited.end()) {
                result.status = RouteStatus::broken_connection;
                return result;
            }
            visited.push_back(current);

            const PieceInstance& instance = pieces_[current.piece];
            const auto traversal = route_for_entry(instance, current.port);
            if (!traversal) {
                result.status = RouteStatus::no_route_for_port;
                result.gap = current;
                return result;
            }

            result.steps.push_back({current.piece, traversal->route, traversal->reversed});
            const PortRef exit{current.piece, traversal->exit_port};
            const auto connection_id = connection_for(exit);
            if (!connection_id) {
                result.status = RouteStatus::ok;
                result.gap = exit;
                return result;
            }
            const Connection& connection = connections_[*connection_id];
            current = connection.a == exit ? connection.b : connection.a;
            if (!valid_port_ref(current)) {
                result.status = RouteStatus::broken_connection;
                return result;
            }
        }

        result.status = RouteStatus::step_limit;
        return result;
    }

    [[nodiscard]] CompiledPolyline compile_polyline(const GraphRoute& route,
                                                    const double join_tolerance_m = 1.0e-5) const {
        CompiledPolyline output;
        output.closed = route.closed;
        if (!route.ok() || route.steps.empty() || !std::isfinite(join_tolerance_m) || join_tolerance_m < 0.0) {
            return output;
        }

        const double join_tolerance_sq = join_tolerance_m * join_tolerance_m;
        for (const RouteStep& step : route.steps) {
            const PieceInstance* instance = piece(step.piece);
            if (instance == nullptr || step.route >= instance->descriptor.routes.size()) return {};
            const RouteDescriptor& descriptor_route = instance->descriptor.routes[step.route];
            if (descriptor_route.centerline.empty()) return {};

            const std::size_t count = descriptor_route.centerline.size();
            for (std::size_t local_index = 0; local_index < count; ++local_index) {
                const std::size_t source_index = step.reversed ? count - 1U - local_index : local_index;
                const CenterlinePoint& source = descriptor_route.centerline[source_index];
                WorldRoutePoint point;
                point.position = transform_point(source.position, instance->transform);
                point.roll_degrees = step.reversed ? -source.roll_degrees : source.roll_degrees;
                point.drive_mode = source.drive_mode;
                point.target_speed_mps = source.target_speed_mps;

                if (!output.points.empty() && squared_distance(output.points.back().position, point.position) <= join_tolerance_sq) {
                    output.points.back() = point;
                } else {
                    output.points.push_back(point);
                }
            }
        }

        if (output.closed && output.points.size() > 2U &&
            squared_distance(output.points.front().position, output.points.back().position) <= join_tolerance_sq) {
            output.points.pop_back();
        }
        output.valid = output.points.size() >= 2U;
        return output;
    }

    [[nodiscard]] const PieceInstance* piece(const PieceInstanceId id) const noexcept {
        if (id >= pieces_.size()) return nullptr;
        return &pieces_[id];
    }

    [[nodiscard]] const Connection* connection(const ConnectionId id) const noexcept {
        if (id >= connections_.size()) return nullptr;
        return &connections_[id];
    }

    [[nodiscard]] const std::vector<PieceInstance>& pieces() const noexcept { return pieces_; }
    [[nodiscard]] const std::vector<Connection>& connections() const noexcept { return connections_; }

private:
    struct Direction3 {
        double x = 0.0;
        double y = 0.0;
        double z = 0.0;
    };

    struct TraversalChoice {
        std::size_t route = 0U;
        std::size_t exit_port = 0U;
        bool reversed = false;
    };

    [[nodiscard]] PieceInstance* piece_mut(const PieceInstanceId id) noexcept {
        if (id >= pieces_.size()) return nullptr;
        return &pieces_[id];
    }

    [[nodiscard]] bool valid_port_ref(const PortRef ref) const noexcept {
        const PieceInstance* instance = piece(ref.piece);
        return instance != nullptr && ref.port < instance->descriptor.ports.size();
    }

    [[nodiscard]] static Point3 transform_point(const Point3 point, const PieceTransform& transform) noexcept {
        const double c = std::cos(transform.yaw_radians);
        const double s = std::sin(transform.yaw_radians);
        return {
            transform.origin.x + point.x * c - point.y * s,
            transform.origin.y + point.x * s + point.y * c,
            transform.origin.z + point.z,
        };
    }

    [[nodiscard]] Point3 world_port_position(const PortRef ref) const noexcept {
        const PieceInstance& instance = pieces_[ref.piece];
        return transform_point(instance.descriptor.ports[ref.port].position, instance.transform);
    }

    [[nodiscard]] Direction3 world_port_direction(const PortRef ref) const noexcept {
        const PieceInstance& instance = pieces_[ref.piece];
        const PortDescriptor& port = instance.descriptor.ports[ref.port];
        const double heading = port.heading_radians + instance.transform.yaw_radians;
        const double cp = std::cos(port.pitch_radians);
        return {cp * std::cos(heading), cp * std::sin(heading), std::sin(port.pitch_radians)};
    }

    [[nodiscard]] std::optional<ConnectionId> connection_for(const PortRef ref) const noexcept {
        for (const Connection& connection : connections_) {
            if (connection.a == ref || connection.b == ref) return connection.id;
        }
        return std::nullopt;
    }

    [[nodiscard]] static std::optional<TraversalChoice> choice_for_route(
        const RouteDescriptor& route,
        const std::size_t route_index,
        const std::size_t port) noexcept {
        if (route.entry_port == port) {
            return TraversalChoice{route_index, route.exit_port, false};
        }
        if (route.reversible && route.exit_port == port) {
            return TraversalChoice{route_index, route.entry_port, true};
        }
        return std::nullopt;
    }

    [[nodiscard]] static std::optional<TraversalChoice> route_for_entry(const PieceInstance& instance,
                                                                        const std::size_t port) noexcept {
        // Switches expose exactly one selected route. Non-switch multi-route
        // pieces (notably crossings) route by the port used to enter, allowing
        // both independent paths to remain live without mutable switch state.
        if (has_flag(instance.descriptor, PieceFlag::switch_piece)) {
            if (instance.active_route >= instance.descriptor.routes.size()) return std::nullopt;
            return choice_for_route(instance.descriptor.routes[instance.active_route], instance.active_route, port);
        }

        std::optional<TraversalChoice> match;
        for (std::size_t route_index = 0U; route_index < instance.descriptor.routes.size(); ++route_index) {
            const auto candidate = choice_for_route(instance.descriptor.routes[route_index], route_index, port);
            if (!candidate) continue;
            if (match) return std::nullopt; // ambiguous descriptor: fail closed
            match = candidate;
        }
        return match;
    }

    std::vector<PieceInstance> pieces_;
    std::vector<Connection> connections_;
};

}  // namespace ch::track
