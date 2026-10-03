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
    double support_spacing_m = 4.80;
    double minimum_support_height_m = 0.72;
    std::size_t max_frame_samples = 8192U;
    std::size_t max_ties = 4096U;
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
           std::isfinite(style.minimum_support_height_m) &&
           style.minimum_support_height_m >= 0.0 &&
           style.max_frame_samples >= 2U &&
           style.max_ties >= 1U &&
           style.max_supports >= 1U;
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

    const std::size_t support_count = coaster_track_sample_count(
        geometry.route_length_m, style.support_spacing_m, geometry.closed);
    if (support_count > style.max_supports) {
        geometry.clear();
        return geometry;
    }
    geometry.supports.reserve(support_count);
    for (std::size_t i = 0; i < support_count; ++i) {
        const double distance = coaster_track_sample_distance(
            i, support_count, geometry.route_length_m, geometry.closed);
        const auto sample = route.sample(distance);
        if (!sample) {
            geometry.clear();
            return geometry;
        }
        const CoasterTrackPoint3 top = track_point(*sample, 0.0, -style.spine_drop_m);
        if (top.z - ground_z < style.minimum_support_height_m) continue;
        geometry.supports.push_back({
            distance,
            top,
            {top.x, top.y, ground_z},
        });
    }

    return geometry;
}

}  // namespace ch::coaster
