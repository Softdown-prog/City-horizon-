#pragma once

#include "coaster_centerline_route.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <vector>

namespace ch::coaster {

inline constexpr const char* kCoasterTrackGeometryContract = "CH_COASTER_TRACK_GEOMETRY_V1";

// Dedicated world-space geometry for amusement-ride track. Unlike the railway
// profile, this contract deliberately has no railway-grade limit: offsets are
// evaluated in the transported coaster frame so steep drops, bank and inverted
// sections remain coherent in the 2D isometric renderer.
struct CoasterTrackStyle {
    double gauge_m = 0.84;
    double rail_plane_offset_m = 0.10;
    double spine_drop_m = 0.30;
    double tie_half_width_m = 0.78;
    double tie_drop_m = 0.08;
    double sample_spacing_m = 0.24;
    double tie_spacing_m = 0.78;

    // support_spacing_m is the relaxed spacing used by low/straight track.
    // The adaptive fields tighten station spacing where the route is taller,
    // more curved, or steeper so structural density follows visual/mechanical
    // demand instead of forming a uniform forest of columns.
    double support_spacing_m = 4.80;
    double support_min_spacing_m = 2.70;
    double support_height_reference_m = 8.00;
    double support_curvature_reference_per_m = 0.055;
    double support_grade_reference = 0.55;
    double support_density_gain = 0.45;

    double minimum_support_height_m = 0.72;
    double support_top_half_width_m = 0.62;
    double support_base_half_width_m = 1.05;
    double support_flare_per_height = 0.055;
    double support_max_base_half_width_m = 1.85;
    double support_tower_threshold_m = 4.80;
    double support_bay_height_m = 3.20;
    double inverted_support_up_z_threshold = -0.10;
    std::size_t max_frame_samples = 8192U;
    std::size_t max_ties = 4096U;
    // Maximum structural members, not support stations. One A-frame station
    // emits three members; tall tower stations additionally emit bracing bays.
    std::size_t max_supports = 2048U;
};

struct CoasterTrackPoint3 {
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;
};

struct CoasterTrackFrame {
    double distance_m = 0.0;
    CoasterTrackPoint3 center{};
    CoasterTrackPoint3 left_rail{};
    CoasterTrackPoint3 right_rail{};
    CoasterTrackPoint3 spine{};
    double roll_degrees = 0.0;
};

struct CoasterCrossTie {
    double distance_m = 0.0;
    CoasterTrackPoint3 left{};
    CoasterTrackPoint3 right{};
};

// One structural member belonging to a support station. Keeping the member as
// the same two-point primitive used by V1 means proof and live renderers consume
// identical geometry while a station can now form an A-frame or braced tower.
struct CoasterSupport {
    double distance_m = 0.0;
    CoasterTrackPoint3 top{};
    CoasterTrackPoint3 bottom{};
};

struct CoasterTrackGeometry {
    std::vector<CoasterTrackFrame> frames;
    std::vector<CoasterCrossTie> ties;
    std::vector<CoasterSupport> supports;
    bool closed = false;
    double route_length_m = 0.0;

    [[nodiscard]] bool valid() const noexcept {
        return route_length_m > 0.0 && frames.size() >= 2U;
    }

    void clear() {
        frames.clear();
        ties.clear();
        supports.clear();
        closed = false;
        route_length_m = 0.0;
    }
};

[[nodiscard]] inline bool valid_coaster_track_style(const CoasterTrackStyle& style) noexcept {
    const auto finite_positive = [](const double value) {
        return std::isfinite(value) && value > 0.0;
    };
    return finite_positive(style.gauge_m) &&
           finite_positive(style.rail_plane_offset_m) &&
           finite_positive(style.spine_drop_m) &&
           finite_positive(style.tie_half_width_m) &&
           style.tie_half_width_m > style.gauge_m * 0.5 &&
           finite_positive(style.tie_drop_m) &&
           finite_positive(style.sample_spacing_m) &&
           finite_positive(style.tie_spacing_m) &&
           finite_positive(style.support_spacing_m) &&
           finite_positive(style.support_min_spacing_m) &&
           style.support_min_spacing_m <= style.support_spacing_m &&
           finite_positive(style.support_height_reference_m) &&
           finite_positive(style.support_curvature_reference_per_m) &&
           finite_positive(style.support_grade_reference) &&
           std::isfinite(style.support_density_gain) &&
           style.support_density_gain >= 0.0 &&
           style.support_density_gain < 1.0 &&
           std::isfinite(style.minimum_support_height_m) &&
           style.minimum_support_height_m >= 0.0 &&
           finite_positive(style.support_top_half_width_m) &&
           finite_positive(style.support_base_half_width_m) &&
           std::isfinite(style.support_flare_per_height) &&
           style.support_flare_per_height >= 0.0 &&
           finite_positive(style.support_max_base_half_width_m) &&
           style.support_max_base_half_width_m >= style.support_base_half_width_m &&
           finite_positive(style.support_tower_threshold_m) &&
           finite_positive(style.support_bay_height_m) &&
           std::isfinite(style.inverted_support_up_z_threshold) &&
           style.inverted_support_up_z_threshold >= -1.0 &&
           style.inverted_support_up_z_threshold <= 1.0 &&
           style.max_frame_samples >= 2U &&
           style.max_ties >= 1U &&
           style.max_supports >= 3U;
}

[[nodiscard]] inline CoasterTrackPoint3 track_point(
    const CenterlineSample& sample,
    const double right_offset,
    const double up_offset) noexcept {
    return {
        sample.x + sample.right_x * right_offset + sample.up_x * up_offset,
        sample.y + sample.right_y * right_offset + sample.up_y * up_offset,
        sample.z + sample.right_z * right_offset + sample.up_z * up_offset,
    };
}

[[nodiscard]] inline CoasterTrackPoint3 lerp_track_point(
    const CoasterTrackPoint3& a,
    const CoasterTrackPoint3& b,
    const double t) noexcept {
    return {
        a.x + (b.x - a.x) * t,
        a.y + (b.y - a.y) * t,
        a.z + (b.z - a.z) * t,
    };
}

[[nodiscard]] inline std::size_t coaster_track_sample_count(
    const double route_length_m,
    const double spacing_m,
    const bool closed) noexcept {
    if (!(route_length_m > 0.0) || !(spacing_m > 0.0)) return 0U;
    const auto intervals = static_cast<std::size_t>(
        std::max(1.0, std::ceil(route_length_m / spacing_m)));
    return closed ? std::max<std::size_t>(3U, intervals)
                  : std::max<std::size_t>(2U, intervals + 1U);
}

[[nodiscard]] inline double coaster_track_sample_distance(
    const std::size_t index,
    const std::size_t count,
    const double route_length_m,
    const bool closed) noexcept {
    if (count < 2U) return 0.0;
    const double denominator = closed
        ? static_cast<double>(count)
        : static_cast<double>(count - 1U);
    return route_length_m * static_cast<double>(index) / denominator;
}

[[nodiscard]] inline double adaptive_support_spacing_m(
    const CoasterTrackStyle& style,
    const CenterlineSample& sample,
    const double ground_z) noexcept {
    const CoasterTrackPoint3 top_center =
        track_point(sample, 0.0, -style.spine_drop_m);
    const double height = std::max(0.0, top_center.z - ground_z);
    const double curvature = std::hypot(
        sample.horizontal_curvature_per_m,
        sample.vertical_curvature_per_m);

    const double height_load = std::clamp(
        height / style.support_height_reference_m, 0.0, 1.0);
    const double curvature_load = std::clamp(
        curvature / style.support_curvature_reference_per_m, 0.0, 1.0);
    const double grade_load = std::clamp(
        std::abs(sample.tangent_z) / style.support_grade_reference, 0.0, 1.0);

    const double structural_load = std::clamp(
        height_load * 0.45 + curvature_load * 0.35 + grade_load * 0.20,
        0.0, 1.0);
    const double spacing = style.support_spacing_m *
        (1.0 - style.support_density_gain * structural_load);
    return std::clamp(
        spacing, style.support_min_spacing_m, style.support_spacing_m);
}

[[nodiscard]] inline bool append_support_member(
    CoasterTrackGeometry& geometry,
    const CoasterTrackStyle& style,
    const double distance_m,
    const CoasterTrackPoint3& a,
    const CoasterTrackPoint3& b) {
    if (geometry.supports.size() >= style.max_supports) return false;
    geometry.supports.push_back({distance_m, a, b});
    return true;
}

[[nodiscard]] inline bool append_support_station(
    CoasterTrackGeometry& geometry,
    const CoasterTrackStyle& style,
    const CenterlineSample& sample,
    const double distance_m,
    const double ground_z) {
    // When transported local up points below world, a conventional ground tower
    // would cross through inverted track. Leave those stations unsupported until
    // a dedicated inversion/hanger support family is authored.
    if (sample.up_z < style.inverted_support_up_z_threshold) return true;

    const CoasterTrackPoint3 top_center =
        track_point(sample, 0.0, -style.spine_drop_m);
    const double height = top_center.z - ground_z;
    if (height < style.minimum_support_height_m) return true;

    const CoasterTrackPoint3 top_left = track_point(
        sample, style.support_top_half_width_m, -style.spine_drop_m);
    const CoasterTrackPoint3 top_right = track_point(
        sample, -style.support_top_half_width_m, -style.spine_drop_m);

    double axis_x = sample.right_x;
    double axis_y = sample.right_y;
    double axis_length = std::hypot(axis_x, axis_y);
    if (!(axis_length > 1.0e-6)) {
        axis_x = -sample.tangent_y;
        axis_y = sample.tangent_x;
        axis_length = std::hypot(axis_x, axis_y);
    }
    if (!(axis_length > 1.0e-6)) {
        axis_x = 1.0;
        axis_y = 0.0;
        axis_length = 1.0;
    }
    axis_x /= axis_length;
    axis_y /= axis_length;

    const double base_half_width = std::min(
        style.support_max_base_half_width_m,
        style.support_base_half_width_m +
            height * style.support_flare_per_height);
    const CoasterTrackPoint3 foot_left = {
        top_center.x + axis_x * base_half_width,
        top_center.y + axis_y * base_half_width,
        ground_z,
    };
    const CoasterTrackPoint3 foot_right = {
        top_center.x - axis_x * base_half_width,
        top_center.y - axis_y * base_half_width,
        ground_z,
    };

    // Open-base A-frame: two splayed legs plus a cap beam beneath the track.
    if (!append_support_member(geometry, style, distance_m, foot_left, top_left) ||
        !append_support_member(geometry, style, distance_m, foot_right, top_right) ||
        !append_support_member(geometry, style, distance_m, top_left, top_right)) {
        return false;
    }

    if (height < style.support_tower_threshold_m) return true;

    const auto bay_count = static_cast<std::size_t>(std::max(
        2.0, std::ceil(height / style.support_bay_height_m)));
    CoasterTrackPoint3 previous_left = foot_left;
    CoasterTrackPoint3 previous_right = foot_right;
    for (std::size_t bay = 1U; bay <= bay_count; ++bay) {
        const double t = static_cast<double>(bay) / static_cast<double>(bay_count);
        const CoasterTrackPoint3 level_left = lerp_track_point(foot_left, top_left, t);
        const CoasterTrackPoint3 level_right = lerp_track_point(foot_right, top_right, t);

        // The cap beam already supplies the final horizontal member.
        if (bay < bay_count &&
            !append_support_member(
                geometry, style, distance_m, level_left, level_right)) {
            return false;
        }

        // X-bracing keeps tall supports readable as towers rather than long
        // isolated sticks. Both diagonals stay in the support station plane.
        if (!append_support_member(
                geometry, style, distance_m, previous_left, level_right) ||
            !append_support_member(
                geometry, style, distance_m, previous_right, level_left)) {
            return false;
        }
        previous_left = level_left;
        previous_right = level_right;
    }
    return true;
}

[[nodiscard]] inline CoasterTrackGeometry build_coaster_track_geometry(
    const CenterlineRoute& route,
    const CoasterTrackStyle& style = {},
    const double ground_z = 0.0) {
    CoasterTrackGeometry geometry;
    if (!route.valid() || !valid_coaster_track_style(style) || !std::isfinite(ground_z)) {
        return geometry;
    }

    geometry.closed = route.closed();
    geometry.route_length_m = route.length_m();

    const std::size_t frame_count = coaster_track_sample_count(
        geometry.route_length_m, style.sample_spacing_m, geometry.closed);
    if (frame_count < 2U || frame_count > style.max_frame_samples) {
        geometry.clear();
        return geometry;
    }

    geometry.frames.reserve(frame_count);
    for (std::size_t i = 0; i < frame_count; ++i) {
        const double distance = coaster_track_sample_distance(
            i, frame_count, geometry.route_length_m, geometry.closed);
        const auto sample = route.sample(distance);
        if (!sample) {
            geometry.clear();
            return geometry;
        }
        const double half_gauge = style.gauge_m * 0.5;
        geometry.frames.push_back({
            distance,
            track_point(*sample, 0.0, 0.0),
            track_point(*sample, half_gauge, style.rail_plane_offset_m),
            track_point(*sample, -half_gauge, style.rail_plane_offset_m),
            track_point(*sample, 0.0, -style.spine_drop_m),
            sample->roll_degrees,
        });
    }

    const std::size_t tie_count = coaster_track_sample_count(
        geometry.route_length_m, style.tie_spacing_m, geometry.closed);
    if (tie_count > style.max_ties) {
        geometry.clear();
        return geometry;
    }
    geometry.ties.reserve(tie_count);
    for (std::size_t i = 0; i < tie_count; ++i) {
        const double distance = coaster_track_sample_distance(
            i, tie_count, geometry.route_length_m, geometry.closed);
        const auto sample = route.sample(distance);
        if (!sample) {
            geometry.clear();
            return geometry;
        }
        geometry.ties.push_back({
            distance,
            track_point(*sample, style.tie_half_width_m, -style.tie_drop_m),
            track_point(*sample, -style.tie_half_width_m, -style.tie_drop_m),
        });
    }

    const auto support_station_estimate = static_cast<std::size_t>(
        std::ceil(geometry.route_length_m / style.support_min_spacing_m)) + 1U;
    geometry.supports.reserve(std::min(
        style.max_supports, support_station_estimate * 6U));

    double support_distance = 0.0;
    std::size_t support_station_count = 0U;
    while (support_distance < geometry.route_length_m &&
           support_station_count < style.max_supports) {
        const auto sample = route.sample(support_distance);
        if (!sample) {
            geometry.clear();
            return geometry;
        }
        if (!append_support_station(
                geometry, style, *sample, support_distance, ground_z)) {
            geometry.clear();
            return geometry;
        }
        const double spacing = adaptive_support_spacing_m(
            style, *sample, ground_z);
        support_distance += spacing;
        ++support_station_count;
    }

    if (!geometry.closed) {
        const auto end_sample = route.sample(geometry.route_length_m);
        if (!end_sample || !append_support_station(
                geometry, style, *end_sample, geometry.route_length_m, ground_z)) {
            geometry.clear();
            return geometry;
        }
    }

    return geometry;
}

}  // namespace ch::coaster