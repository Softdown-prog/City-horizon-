#pragma once

#include "coaster_train_runtime.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <optional>
#include <vector>

namespace ch::coaster {

// CH_COASTER_CENTERLINE_ROUTE_V1
// Runtime representation shared by modular coaster pieces and the articulated
// train. Authoring/build tools may produce the points however they want; once
// promoted here the train sees one continuous distance-addressable 3D route.
struct RoutePoint {
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;
    DriveMode drive_mode = DriveMode::Free;
    double target_speed_mps = -1.0;
};

class CenterlineRoute final {
public:
    [[nodiscard]] bool rebuild(std::vector<RoutePoint> points, const bool closed_route) {
        clear();
        if (points.size() < 2U) return false;
        for (const RoutePoint& point : points) {
            if (!finite(point.x) || !finite(point.y) || !finite(point.z) ||
                !finite(point.target_speed_mps)) {
                return false;
            }
        }

        points_ = std::move(points);
        closed_ = closed_route;
        const std::size_t segment_count = closed_ ? points_.size() : points_.size() - 1U;
        segment_lengths_.reserve(segment_count);
        cumulative_.reserve(segment_count + 1U);
        cumulative_.push_back(0.0);

        for (std::size_t segment = 0; segment < segment_count; ++segment) {
            const RoutePoint& a = points_[segment];
            const RoutePoint& b = points_[(segment + 1U) % points_.size()];
            const double dx = b.x - a.x;
            const double dy = b.y - a.y;
            const double dz = b.z - a.z;
            const double length = std::sqrt(dx * dx + dy * dy + dz * dz);
            if (!(length > kMinimumSegmentLength) || !finite(length)) {
                clear();
                return false;
            }
            segment_lengths_.push_back(length);
            cumulative_.push_back(cumulative_.back() + length);
        }

        route_length_m_ = cumulative_.back();
        if (!(route_length_m_ > 0.0) || !finite(route_length_m_)) {
            clear();
            return false;
        }

        build_vertex_tangents();
        build_vertex_curvatures();
        valid_ = true;
        return true;
    }

    void clear() {
        points_.clear();
        segment_lengths_.clear();
        cumulative_.clear();
        tangents_.clear();
        horizontal_curvature_.clear();
        vertical_curvature_.clear();
        route_length_m_ = 0.0;
        closed_ = false;
        valid_ = false;
    }

    [[nodiscard]] bool valid() const noexcept { return valid_; }
    [[nodiscard]] bool closed() const noexcept { return closed_; }
    [[nodiscard]] double length_m() const noexcept { return route_length_m_; }
    [[nodiscard]] std::size_t point_count() const noexcept { return points_.size(); }

    [[nodiscard]] std::optional<CenterlineSample> sample(double distance_m) const noexcept {
        if (!valid_) return std::nullopt;
        distance_m = normalize_route_distance(distance_m, route_length_m_, closed_);

        std::size_t segment = 0U;
        if (!closed_ && distance_m >= route_length_m_) {
            segment = segment_lengths_.size() - 1U;
        } else {
            const auto upper = std::upper_bound(cumulative_.begin(), cumulative_.end(), distance_m);
            if (upper == cumulative_.begin()) {
                segment = 0U;
            } else {
                segment = static_cast<std::size_t>(std::distance(cumulative_.begin(), upper) - 1);
                segment = std::min(segment, segment_lengths_.size() - 1U);
            }
        }

        const std::size_t next = (segment + 1U) % points_.size();
        const RoutePoint& a = points_[segment];
        const RoutePoint& b = points_[next];
        const double local_distance = distance_m - cumulative_[segment];
        const double t = std::clamp(local_distance / segment_lengths_[segment], 0.0, 1.0);

        CenterlineSample result;
        result.distance_m = distance_m;
        result.x = lerp(a.x, b.x, t);
        result.y = lerp(a.y, b.y, t);
        result.z = lerp(a.z, b.z, t);

        // A rendered car must never face against the segment it is travelling on.
        // Vertex tangent averaging can collapse to almost zero on a tight hairpin;
        // falling back to a fixed world axis in that case makes the sprite suddenly
        // turn sideways/backwards.  Use the actual outgoing segment as the fallback
        // and reject an interpolated tangent if it points into the opposite hemisphere.
        const Vec3 segment_forward = outgoing_segment_tangent(segment);
        const Vec3 blended = {
            lerp(tangents_[segment].x, tangents_[next].x, t),
            lerp(tangents_[segment].y, tangents_[next].y, t),
            lerp(tangents_[segment].z, tangents_[next].z, t),
        };
        Vec3 tangent = normalized_or(blended, segment_forward);
        if (dot(tangent, segment_forward) <= 0.0) tangent = segment_forward;

        result.tangent_x = tangent.x;
        result.tangent_y = tangent.y;
        result.tangent_z = tangent.z;
        result.horizontal_curvature_per_m = lerp(
            horizontal_curvature_[segment], horizontal_curvature_[next], t);
        result.vertical_curvature_per_m = lerp(
            vertical_curvature_[segment], vertical_curvature_[next], t);

        // Drive semantics belong to the outgoing segment. This prevents a lift
        // or brake from bleeding backwards across a geometric interpolation.
        result.drive_mode = a.drive_mode;
        result.target_speed_mps = a.target_speed_mps;
        return result;
    }

private:
    struct Vec3 {
        double x = 0.0;
        double y = 0.0;
        double z = 0.0;
    };

    static constexpr double kMinimumSegmentLength = 1.0e-5;
    static constexpr double kPi = 3.14159265358979323846;

    [[nodiscard]] static bool finite(const double value) noexcept {
        return std::isfinite(value);
    }

    [[nodiscard]] static double lerp(const double a, const double b, const double t) noexcept {
        return a + (b - a) * t;
    }

    [[nodiscard]] static double dot(const Vec3& a, const Vec3& b) noexcept {
        return a.x * b.x + a.y * b.y + a.z * b.z;
    }

    [[nodiscard]] static double length_squared(const Vec3& value) noexcept {
        return dot(value, value);
    }

    [[nodiscard]] static Vec3 normalized_or(const Vec3 value, const Vec3 fallback) noexcept {
        const double squared = length_squared(value);
        if (!(squared > kMinimumSegmentLength * kMinimumSegmentLength) || !finite(squared)) {
            return fallback;
        }
        const double length = std::sqrt(squared);
        return {value.x / length, value.y / length, value.z / length};
    }

    [[nodiscard]] static Vec3 normalized(const Vec3 value) noexcept {
        return normalized_or(value, {0.0, 1.0, 0.0});
    }

    [[nodiscard]] static double wrapped_angle_delta(double value) noexcept {
        while (value > kPi) value -= 2.0 * kPi;
        while (value < -kPi) value += 2.0 * kPi;
        return value;
    }

    [[nodiscard]] Vec3 outgoing_segment_tangent(const std::size_t index) const noexcept {
        const std::size_t next = (index + 1U) % points_.size();
        return normalized({
            points_[next].x - points_[index].x,
            points_[next].y - points_[index].y,
            points_[next].z - points_[index].z,
        });
    }

    void build_vertex_tangents() {
        tangents_.resize(points_.size());
        for (std::size_t i = 0; i < points_.size(); ++i) {
            if (!closed_ && i == 0U) {
                tangents_[i] = outgoing_segment_tangent(0U);
                continue;
            }
            if (!closed_ && i + 1U == points_.size()) {
                tangents_[i] = outgoing_segment_tangent(i - 1U);
                continue;
            }
            const std::size_t previous = (i + points_.size() - 1U) % points_.size();
            const Vec3 incoming = outgoing_segment_tangent(previous);
            const Vec3 outgoing = outgoing_segment_tangent(i);
            const Vec3 averaged = {
                incoming.x + outgoing.x,
                incoming.y + outgoing.y,
                incoming.z + outgoing.z,
            };
            // Near a 180-degree reversal the average is undefined.  Preserve the
            // authored direction of travel instead of snapping to a world axis.
            tangents_[i] = normalized_or(averaged, outgoing);
            if (dot(tangents_[i], outgoing) <= 0.0) tangents_[i] = outgoing;
        }
    }

    void build_vertex_curvatures() {
        horizontal_curvature_.assign(points_.size(), 0.0);
        vertical_curvature_.assign(points_.size(), 0.0);
        if (points_.size() < 3U) return;

        for (std::size_t i = 0; i < points_.size(); ++i) {
            if (!closed_ && (i == 0U || i + 1U == points_.size())) continue;
            const std::size_t previous = (i + points_.size() - 1U) % points_.size();
            const std::size_t next = (i + 1U) % points_.size();
            const Vec3& before = tangents_[previous];
            const Vec3& after = tangents_[next];
            const double before_heading = std::atan2(before.y, before.x);
            const double after_heading = std::atan2(after.y, after.x);
            const double before_pitch = std::atan2(before.z, std::hypot(before.x, before.y));
            const double after_pitch = std::atan2(after.z, std::hypot(after.x, after.y));

            const double previous_length = segment_lengths_[previous % segment_lengths_.size()];
            const std::size_t next_segment_index = std::min(i, segment_lengths_.size() - 1U);
            const double next_length = segment_lengths_[next_segment_index];
            const double span = std::max(kMinimumSegmentLength, 0.5 * (previous_length + next_length));
            horizontal_curvature_[i] = wrapped_angle_delta(after_heading - before_heading) / (2.0 * span);
            vertical_curvature_[i] = wrapped_angle_delta(after_pitch - before_pitch) / (2.0 * span);
        }

        if (!closed_) {
            horizontal_curvature_.front() = horizontal_curvature_[1U];
            vertical_curvature_.front() = vertical_curvature_[1U];
            horizontal_curvature_.back() = horizontal_curvature_[points_.size() - 2U];
            vertical_curvature_.back() = vertical_curvature_[points_.size() - 2U];
        }
    }

    std::vector<RoutePoint> points_;
    std::vector<double> segment_lengths_;
    std::vector<double> cumulative_;
    std::vector<Vec3> tangents_;
    std::vector<double> horizontal_curvature_;
    std::vector<double> vertical_curvature_;
    double route_length_m_ = 0.0;
    bool closed_ = false;
    bool valid_ = false;
};

}  // namespace ch::coaster
