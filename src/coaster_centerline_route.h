#pragma once

#include "coaster_train_runtime.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <optional>
#include <vector>

namespace ch::coaster {

// CH_COASTER_CENTERLINE_ROUTE_V2
// Runtime representation shared by modular coaster pieces and the articulated
// train. V2 transports a rotation-minimizing local frame along the route so a
// car can distinguish ordinary horizontal track from the inverted top of a
// vertical loop even when both have similar forward tangents.
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
        build_vertex_frames();
        build_vertex_curvatures();
        valid_ = true;
        return true;
    }

    void clear() {
        points_.clear();
        segment_lengths_.clear();
        cumulative_.clear();
        tangents_.clear();
        right_vectors_.clear();
        up_vectors_.clear();
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

        const Vec3 segment_forward = outgoing_segment_tangent(segment);
        const Vec3 blended = {
            lerp(tangents_[segment].x, tangents_[next].x, t),
            lerp(tangents_[segment].y, tangents_[next].y, t),
            lerp(tangents_[segment].z, tangents_[next].z, t),
        };
        Vec3 tangent = normalized_or(blended, segment_forward);
        if (dot(tangent, segment_forward) <= 0.0) tangent = segment_forward;

        // Interpolate the transported up axis, remove any component that leaked
        // into forward, then rebuild an orthonormal right/up pair. This preserves
        // the inversion state continuously between authored centerline vertices.
        Vec3 up = {
            lerp(up_vectors_[segment].x, up_vectors_[next].x, t),
            lerp(up_vectors_[segment].y, up_vectors_[next].y, t),
            lerp(up_vectors_[segment].z, up_vectors_[next].z, t),
        };
        up = subtract(up, scale(tangent, dot(up, tangent)));
        up = normalized_or(up, transported_reference_up(tangent));
        Vec3 right = normalized_or(cross(tangent, up), right_vectors_[segment]);
        up = normalized_or(cross(right, tangent), up);

        result.tangent_x = tangent.x;
        result.tangent_y = tangent.y;
        result.tangent_z = tangent.z;
        result.right_x = right.x;
        result.right_y = right.y;
        result.right_z = right.z;
        result.up_x = up.x;
        result.up_y = up.y;
        result.up_z = up.z;
        result.roll_degrees = roll_degrees_from_frame(
            tangent.x, tangent.y, tangent.z, up.x, up.y, up.z);
        result.horizontal_curvature_per_m = lerp(
            horizontal_curvature_[segment], horizontal_curvature_[next], t);
        result.vertical_curvature_per_m = lerp(
            vertical_curvature_[segment], vertical_curvature_[next], t);

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

    [[nodiscard]] static Vec3 add(const Vec3 a, const Vec3 b) noexcept {
        return {a.x + b.x, a.y + b.y, a.z + b.z};
    }

    [[nodiscard]] static Vec3 subtract(const Vec3 a, const Vec3 b) noexcept {
        return {a.x - b.x, a.y - b.y, a.z - b.z};
    }

    [[nodiscard]] static Vec3 scale(const Vec3 a, const double s) noexcept {
        return {a.x * s, a.y * s, a.z * s};
    }

    [[nodiscard]] static double dot(const Vec3& a, const Vec3& b) noexcept {
        return a.x * b.x + a.y * b.y + a.z * b.z;
    }

    [[nodiscard]] static Vec3 cross(const Vec3 a, const Vec3 b) noexcept {
        return {
            a.y * b.z - a.z * b.y,
            a.z * b.x - a.x * b.z,
            a.x * b.y - a.y * b.x,
        };
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

    [[nodiscard]] static Vec3 transported_reference_up(const Vec3 tangent) noexcept {
        Vec3 up = {0.0, 0.0, 1.0};
        up = subtract(up, scale(tangent, dot(up, tangent)));
        if (length_squared(up) <= kMinimumSegmentLength * kMinimumSegmentLength) {
            up = {1.0, 0.0, 0.0};
            up = subtract(up, scale(tangent, dot(up, tangent)));
        }
        return normalized_or(up, {0.0, 1.0, 0.0});
    }

    [[nodiscard]] static Vec3 rotate_minimal(const Vec3 vector,
                                             const Vec3 from,
                                             const Vec3 to) noexcept {
        const Vec3 axis_raw = cross(from, to);
        const double axis_sq = length_squared(axis_raw);
        const double cosine = std::clamp(dot(from, to), -1.0, 1.0);
        if (axis_sq <= 1.0e-12) {
            if (cosine >= 0.0) return vector;
            // Exact reversal: choose an axis perpendicular to travel and preserve
            // deterministic frame continuity rather than introducing world yaw.
            Vec3 axis = cross(from, transported_reference_up(from));
            axis = normalized_or(axis, {1.0, 0.0, 0.0});
            return subtract(scale(axis, 2.0 * dot(axis, vector)), vector);
        }
        const double axis_len = std::sqrt(axis_sq);
        const Vec3 axis = scale(axis_raw, 1.0 / axis_len);
        const double sine = axis_len;
        // Rodrigues rotation from previous tangent to next tangent.
        return add(add(scale(vector, cosine), scale(cross(axis, vector), sine)),
                   scale(axis, dot(axis, vector) * (1.0 - cosine)));
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
            const Vec3 averaged = add(incoming, outgoing);
            tangents_[i] = normalized_or(averaged, outgoing);
            if (dot(tangents_[i], outgoing) <= 0.0) tangents_[i] = outgoing;
        }
    }

    void build_vertex_frames() {
        right_vectors_.resize(points_.size());
        up_vectors_.resize(points_.size());
        if (points_.empty()) return;

        up_vectors_[0] = transported_reference_up(tangents_[0]);
        right_vectors_[0] = normalized_or(cross(tangents_[0], up_vectors_[0]), {1.0, 0.0, 0.0});
        up_vectors_[0] = normalized_or(cross(right_vectors_[0], tangents_[0]), up_vectors_[0]);

        for (std::size_t i = 1; i < points_.size(); ++i) {
            Vec3 up = rotate_minimal(up_vectors_[i - 1U], tangents_[i - 1U], tangents_[i]);
            up = subtract(up, scale(tangents_[i], dot(up, tangents_[i])));
            up = normalized_or(up, transported_reference_up(tangents_[i]));
            Vec3 right = normalized_or(cross(tangents_[i], up), right_vectors_[i - 1U]);
            up = normalized_or(cross(right, tangents_[i]), up);
            right_vectors_[i] = right;
            up_vectors_[i] = up;
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
    std::vector<Vec3> right_vectors_;
    std::vector<Vec3> up_vectors_;
    std::vector<double> horizontal_curvature_;
    std::vector<double> vertical_curvature_;
    double route_length_m_ = 0.0;
    bool closed_ = false;
    bool valid_ = false;
};

}  // namespace ch::coaster
