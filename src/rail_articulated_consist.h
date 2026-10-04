#pragma once

#include "rail_operation_runtime.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <optional>
#include <vector>

inline constexpr const char* kChRailArticulatedConsistContract = "CH_RAIL_ARTICULATED_CONSIST_V1";

namespace ch::rail_operation {

enum class ConsistUnitKind {
    locomotive,
    passenger_coach,
};

struct ArticulatedConsistSpec {
    double locomotive_length_m = 5.2;
    double coach_length_m = 3.9;
    double coupler_gap_m = 0.42;
    std::size_t coach_count = 7U;
};

struct ArticulatedUnitPose {
    ConsistUnitKind kind = ConsistUnitKind::passenger_coach;
    std::size_t unit_index = 0U;
    double route_distance_m = 0.0;
    TrainPose pose{};
};

[[nodiscard]] inline std::optional<TrainPose> sample_operational_route_pose(
    const OperationalRoute& route,
    double distance_m,
    const double speed_mps = 0.0,
    const bool dwelling = false,
    const std::optional<RailPlacementPieceId> station_piece = std::nullopt) noexcept {
    if (!route.valid || route.polyline.points.size() < 2U || route.cumulative_m.empty() ||
        !(route.length_m > 0.0) || !std::isfinite(distance_m)) {
        return std::nullopt;
    }

    if (route.closed) {
        distance_m = std::fmod(distance_m, route.length_m);
        if (distance_m < 0.0) distance_m += route.length_m;
    } else if (distance_m < 0.0 || distance_m > route.length_m) {
        return std::nullopt;
    }

    const auto& points = route.polyline.points;
    std::size_t segment = 0U;
    double segment_start = 0.0;
    double segment_length = 0.0;
    if (!route.closed && distance_m >= route.length_m) {
        segment = points.size() - 2U;
        segment_start = route.cumulative_m[segment];
        segment_length = route.cumulative_m[segment + 1U] - segment_start;
    } else if (route.closed && distance_m >= route.cumulative_m.back()) {
        segment = points.size() - 1U;
        segment_start = route.cumulative_m.back();
        segment_length = route.length_m - segment_start;
    } else {
        const auto upper = std::upper_bound(route.cumulative_m.begin(), route.cumulative_m.end(), distance_m);
        segment = upper == route.cumulative_m.begin()
            ? 0U
            : static_cast<std::size_t>(std::distance(route.cumulative_m.begin(), upper) - 1);
        segment = std::min(segment, points.size() - 2U);
        segment_start = route.cumulative_m[segment];
        segment_length = route.cumulative_m[segment + 1U] - segment_start;
    }
    if (!(segment_length > 0.0)) return std::nullopt;

    const std::size_t next = (segment + 1U) % points.size();
    const auto& a = points[segment].position;
    const auto& b = points[next].position;
    const double dx = b.x - a.x;
    const double dy = b.y - a.y;
    const double dz = b.z - a.z;
    const double tangent_length = std::sqrt(dx * dx + dy * dy + dz * dz);
    if (!(tangent_length > 0.0)) return std::nullopt;
    const double t = std::clamp((distance_m - segment_start) / segment_length, 0.0, 1.0);

    TrainPose pose;
    pose.distance_m = distance_m;
    pose.x = a.x + dx * t;
    pose.y = a.y + dy * t;
    pose.z = a.z + dz * t;
    pose.tangent_x = dx / tangent_length;
    pose.tangent_y = dy / tangent_length;
    pose.tangent_z = dz / tangent_length;
    pose.speed_mps = speed_mps;
    pose.dwelling = dwelling;
    pose.station_piece = station_piece;
    return pose;
}

[[nodiscard]] inline std::vector<ArticulatedUnitPose> build_articulated_consist_poses(
    const OperationalRoute& route,
    const TrainPose& lead,
    const ArticulatedConsistSpec& spec = {}) {
    std::vector<ArticulatedUnitPose> result;
    if (!route.valid || !(spec.locomotive_length_m > 0.0) || !(spec.coach_length_m > 0.0) ||
        spec.coupler_gap_m < 0.0 || !std::isfinite(spec.locomotive_length_m) ||
        !std::isfinite(spec.coach_length_m) || !std::isfinite(spec.coupler_gap_m)) {
        return result;
    }

    result.reserve(spec.coach_count + 1U);
    if (const auto pose = sample_operational_route_pose(
            route, lead.distance_m, lead.speed_mps, lead.dwelling, lead.station_piece)) {
        result.push_back({ConsistUnitKind::locomotive, 0U, lead.distance_m, *pose});
    }

    double cursor = lead.distance_m -
        (spec.locomotive_length_m * 0.5 + spec.coupler_gap_m + spec.coach_length_m * 0.5);
    const double coach_pitch = spec.coach_length_m + spec.coupler_gap_m;
    for (std::size_t index = 0U; index < spec.coach_count; ++index, cursor -= coach_pitch) {
        const auto pose = sample_operational_route_pose(
            route, cursor, lead.speed_mps, lead.dwelling, lead.station_piece);
        if (!pose) continue; // Open routes reveal trailing cars only after they enter the route.
        result.push_back({ConsistUnitKind::passenger_coach, index + 1U, cursor, *pose});
    }
    return result;
}

} // namespace ch::rail_operation
