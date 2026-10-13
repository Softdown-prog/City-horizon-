#pragma once

#include "rail_operation_runtime.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <optional>

// CH_RAIL_SIGNAL_INTERLOCKING_V1
// Conservative topology and geometry safety gate for independently driven lines.
// Crossing geometry at the same height is a conflict even when the two routes
// belong to different graph pieces. This does NOT grant shared-track authority.
namespace ch::rail_signals {

enum class Aspect : std::uint8_t { stop, approach, clear };

[[nodiscard]] inline Aspect station_aspect(
    const bool service_active, const double signal_distance_m,
    const std::optional<double> lead_distance_m, const std::uint32_t coaches,
    const bool locomotive_shunting = false) noexcept {
    if (!service_active || !lead_distance_m || locomotive_shunting ||
        !std::isfinite(signal_distance_m) || !std::isfinite(*lead_distance_m) ||
        coaches > 7U) return Aspect::stop;
    constexpr double locomotive_length_m = 5.2;
    constexpr double coach_pitch_m = 3.9 + 0.42;
    const double train_length_m = locomotive_length_m +
        static_cast<double>(coaches) * coach_pitch_m;
    const double lead = *lead_distance_m;
    // An aspect turns red while any part of the consist occupies the marker.
    if (lead >= signal_distance_m - 2.0 &&
        lead - train_length_m <= signal_distance_m + 2.0) return Aspect::stop;
    // Only approaching trains receive caution; a departing train may release
    // the marker once its last carriage has passed.
    if (lead < signal_distance_m && signal_distance_m - lead <= 25.0)
        return Aspect::approach;
    return Aspect::clear;
}

[[nodiscard]] inline double cross2(
    const double ax, const double ay, const double bx, const double by) noexcept {
    return ax * by - ay * bx;
}

[[nodiscard]] inline bool close_ends(
    const ch::track::Point3& p, const ch::track::Point3& a,
    const ch::track::Point3& b,
    const double horizontal_clearance_m, const double vertical_clearance_m) noexcept {
    const double dx = b.x - a.x;
    const double dy = b.y - a.y;
    const double len2 = dx * dx + dy * dy;
    const double t = len2 > 1.0e-12
        ? std::clamp(((p.x - a.x) * dx + (p.y - a.y) * dy) / len2, 0.0, 1.0)
        : 0.0;
    const double qx = a.x + t * dx;
    const double qy = a.y + t * dy;
    const double qz = a.z + t * (b.z - a.z);
    const double ex = p.x - qx;
    const double ey = p.y - qy;
    return ex * ex + ey * ey < horizontal_clearance_m * horizontal_clearance_m &&
           std::abs(p.z - qz) < vertical_clearance_m;
}

[[nodiscard]] inline bool same_level_segment_conflict(
    const ch::track::Point3& a, const ch::track::Point3& b,
    const ch::track::Point3& c, const ch::track::Point3& d,
    const double horizontal_clearance_m = 1.0,
    const double vertical_clearance_m = 2.5) noexcept {
    if (!(horizontal_clearance_m > 0.0) || !(vertical_clearance_m > 0.0))
        return false;
    const auto separated = [horizontal_clearance_m](double a1, double a2,
                                                    double b1, double b2) {
        return std::max(a1, a2) + horizontal_clearance_m < std::min(b1, b2) ||
               std::max(b1, b2) + horizontal_clearance_m < std::min(a1, a2);
    };
    if (separated(a.x, b.x, c.x, d.x) || separated(a.y, b.y, c.y, d.y))
        return false;
    const double rx = b.x - a.x;
    const double ry = b.y - a.y;
    const double sx = d.x - c.x;
    const double sy = d.y - c.y;
    const double denominator = cross2(rx, ry, sx, sy);
    if (std::abs(denominator) > 1.0e-10) {
        const double qx = c.x - a.x;
        const double qy = c.y - a.y;
        const double t = cross2(qx, qy, sx, sy) / denominator;
        const double u = cross2(qx, qy, rx, ry) / denominator;
        if (t >= 0.0 && t <= 1.0 && u >= 0.0 && u <= 1.0) {
            const double za = a.z + t * (b.z - a.z);
            const double zb = c.z + u * (d.z - c.z);
            if (std::abs(za - zb) < vertical_clearance_m) return true;
        }
    }
    // Catch parallel, near-parallel, and close-end crossings as well.
    return close_ends(a, c, d, horizontal_clearance_m, vertical_clearance_m) ||
           close_ends(b, c, d, horizontal_clearance_m, vertical_clearance_m) ||
           close_ends(c, a, b, horizontal_clearance_m, vertical_clearance_m) ||
           close_ends(d, a, b, horizontal_clearance_m, vertical_clearance_m);
}

[[nodiscard]] inline bool routes_cross_at_grade(
    const rail_operation::OperationalRoute& first,
    const rail_operation::OperationalRoute& second) noexcept {
    if (!first.valid || !second.valid) return false;
    const auto& a = first.polyline.points;
    const auto& b = second.polyline.points;
    if (a.size() < 2U || b.size() < 2U) return false;
    for (std::size_t i = 1U; i < a.size(); ++i) {
        for (std::size_t j = 1U; j < b.size(); ++j) {
            if (same_level_segment_conflict(a[i - 1U].position, a[i].position,
                                            b[j - 1U].position, b[j].position))
                return true;
        }
    }
    return false;
}
} // namespace ch::rail_signals
