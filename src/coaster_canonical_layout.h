#pragma once

#include "coaster_centerline_route.h"

#include <algorithm>
#include <cmath>
#include <vector>

namespace ch::coaster {

// CH_COASTER_CANONICAL_LAYOUT_V1
//
// A deterministic, reusable assembly of the modular coaster vocabulary authored
// for City Horizon.  The video proof and future runtime validation must consume
// this route instead of inventing private point lists.
//
// Geometry constants intentionally mirror the approved authoring builders:
//   build_coaster_track_guarded.py  -> TILE=3.0, HEIGHT_STEP=0.75
//   build_coaster_loop_guarded.py   -> LOOP_RADIUS=TILE*1.35
//   build_coaster_helix_guarded.py  -> HELIX_RADIUS=TILE*1.5,
//                                       HELIX_RISE=HEIGHT_STEP*1.5
//
// Roll-only information (bank/corkscrew orientation) is not encoded in
// CH_COASTER_CENTERLINE_ROUTE_V1 yet, so this V1 layout uses the approved
// centerline-compatible straight/slope/curve/vertical-loop/helix vocabulary.
// Corkscrew roll is deliberately not faked as heading/pitch data.

inline constexpr double kCoasterAuthoringTileM = 3.0;
inline constexpr double kCoasterHeightStepM = 0.75;
inline constexpr double kCanonicalLoopRadiusM = kCoasterAuthoringTileM * 1.35;
inline constexpr double kCanonicalHelixRadiusM = kCoasterAuthoringTileM * 1.5;
inline constexpr double kCanonicalHelixRiseM = kCoasterHeightStepM * 1.5;

namespace canonical_layout_detail {

inline constexpr double kPi = 3.14159265358979323846;
inline constexpr double kTwoPi = 2.0 * kPi;

struct Cursor {
    double x = -30.0;
    double y = -14.0;
    double z = 0.0;
    double heading_rad = 0.0; // +X
};

inline void push_unique(std::vector<RoutePoint>& out,
                        const double x,
                        const double y,
                        const double z,
                        const DriveMode mode,
                        const double target_speed_mps) {
    if (!out.empty()) {
        const RoutePoint& previous = out.back();
        const double dx = x - previous.x;
        const double dy = y - previous.y;
        const double dz = z - previous.z;
        if (dx * dx + dy * dy + dz * dz < 1.0e-10) return;
    }
    out.push_back({x, y, z, mode, target_speed_mps});
}

inline void append_straight(std::vector<RoutePoint>& out,
                            Cursor& cursor,
                            const double length_m,
                            const double rise_m,
                            const DriveMode mode,
                            const double target_speed_mps,
                            const double step_m = 0.45) {
    const double start_x = cursor.x;
    const double start_y = cursor.y;
    const double start_z = cursor.z;
    const double forward_x = std::cos(cursor.heading_rad);
    const double forward_y = std::sin(cursor.heading_rad);
    const int samples = std::max(2, static_cast<int>(std::ceil(length_m / step_m)));
    for (int i = 1; i <= samples; ++i) {
        const double t = static_cast<double>(i) / static_cast<double>(samples);
        push_unique(out,
                    start_x + forward_x * length_m * t,
                    start_y + forward_y * length_m * t,
                    start_z + rise_m * t,
                    mode,
                    target_speed_mps);
    }
    cursor.x = start_x + forward_x * length_m;
    cursor.y = start_y + forward_y * length_m;
    cursor.z = start_z + rise_m;
}

inline void append_quarter_curve(std::vector<RoutePoint>& out,
                                 Cursor& cursor,
                                 const double radius_m,
                                 const bool left,
                                 const DriveMode mode = DriveMode::Free,
                                 const double target_speed_mps = -1.0,
                                 const int samples = 32) {
    const double sign = left ? 1.0 : -1.0;
    const double left_x = -std::sin(cursor.heading_rad);
    const double left_y =  std::cos(cursor.heading_rad);
    const double center_x = cursor.x + left_x * radius_m * sign;
    const double center_y = cursor.y + left_y * radius_m * sign;
    const double radial_x = cursor.x - center_x;
    const double radial_y = cursor.y - center_y;
    const double start_heading = cursor.heading_rad;

    for (int i = 1; i <= samples; ++i) {
        const double t = static_cast<double>(i) / static_cast<double>(samples);
        const double angle = sign * (kPi * 0.5) * t;
        const double c = std::cos(angle);
        const double s = std::sin(angle);
        push_unique(out,
                    center_x + radial_x * c - radial_y * s,
                    center_y + radial_x * s + radial_y * c,
                    cursor.z,
                    mode,
                    target_speed_mps);
    }

    const double angle = sign * (kPi * 0.5);
    const double c = std::cos(angle);
    const double s = std::sin(angle);
    cursor.x = center_x + radial_x * c - radial_y * s;
    cursor.y = center_y + radial_x * s + radial_y * c;
    cursor.heading_rad = start_heading + angle;
}

inline void append_vertical_loop(std::vector<RoutePoint>& out,
                                 Cursor& cursor,
                                 const int samples = 128) {
    const double start_x = cursor.x;
    const double start_y = cursor.y;
    const double start_z = cursor.z;
    const double forward_x = std::cos(cursor.heading_rad);
    const double forward_y = std::sin(cursor.heading_rad);

    // Matches build_coaster_loop_guarded.py: theta=0 is the bottom, tangent
    // points forward, and one full revolution returns to the bottom connector.
    for (int i = 1; i <= samples; ++i) {
        const double t = static_cast<double>(i) / static_cast<double>(samples);
        const double theta = kTwoPi * t;
        const double longitudinal = kCanonicalLoopRadiusM * std::sin(theta);
        const double z = start_z + kCanonicalLoopRadiusM * (1.0 - std::cos(theta));
        push_unique(out,
                    start_x + forward_x * longitudinal,
                    start_y + forward_y * longitudinal,
                    z,
                    DriveMode::Free,
                    -1.0);
    }
    cursor.x = start_x;
    cursor.y = start_y;
    cursor.z = start_z;
}

inline void append_ascending_helix(std::vector<RoutePoint>& out,
                                   Cursor& cursor,
                                   const bool left,
                                   const int samples = 160) {
    const double sign = left ? 1.0 : -1.0;
    const double start_x = cursor.x;
    const double start_y = cursor.y;
    const double start_z = cursor.z;
    const double left_x = -std::sin(cursor.heading_rad);
    const double left_y =  std::cos(cursor.heading_rad);
    const double center_x = start_x + left_x * kCanonicalHelixRadiusM * sign;
    const double center_y = start_y + left_y * kCanonicalHelixRadiusM * sign;
    const double radial_x = start_x - center_x;
    const double radial_y = start_y - center_y;

    // Matches the one-turn helix centerline contract. Banking is an orientation
    // attribute and remains outside CenterlineRoute V1.
    for (int i = 1; i <= samples; ++i) {
        const double t = static_cast<double>(i) / static_cast<double>(samples);
        const double angle = sign * kTwoPi * t;
        const double c = std::cos(angle);
        const double s = std::sin(angle);
        push_unique(out,
                    center_x + radial_x * c - radial_y * s,
                    center_y + radial_x * s + radial_y * c,
                    start_z + kCanonicalHelixRiseM * t,
                    DriveMode::Free,
                    -1.0);
    }
    cursor.x = start_x;
    cursor.y = start_y;
    cursor.z = start_z + kCanonicalHelixRiseM;
}

} // namespace canonical_layout_detail

[[nodiscard]] inline std::vector<RoutePoint> make_canonical_flame_layout_points() {
    using namespace canonical_layout_detail;

    std::vector<RoutePoint> points;
    points.reserve(900);
    Cursor cursor;
    push_unique(points, cursor.x, cursor.y, cursor.z, DriveMode::Station, 4.5);

    // Station and lift hill.
    append_straight(points, cursor, 10.0, 0.0, DriveMode::Station, 4.5);
    append_straight(points, cursor, 36.0, 7.2, DriveMode::Lift, 6.0);
    append_straight(points, cursor, 4.0, 0.0, DriveMode::Free, -1.0);

    // Elevated turnaround into the first drop.
    append_quarter_curve(points, cursor, 6.0, true);
    append_straight(points, cursor, 28.0, -7.2, DriveMode::Free, -1.0);

    // Approved vertical-loop centerline vocabulary with flat connectors.
    append_straight(points, cursor, 3.0, 0.0, DriveMode::Free, -1.0);
    append_vertical_loop(points, cursor);
    append_straight(points, cursor, 5.0, 0.0, DriveMode::Free, -1.0);

    // Back section and the approved one-turn ascending helix vocabulary.
    append_quarter_curve(points, cursor, 8.0, true);
    append_straight(points, cursor, 20.0, 0.0, DriveMode::Free, -1.0);
    append_ascending_helix(points, cursor, true);
    append_straight(points, cursor, 8.0, -kCanonicalHelixRiseM, DriveMode::Free, -1.0);

    // Return and brake run. The final point intentionally stops one metre before
    // the first station point so CenterlineRoute's closing segment has non-zero
    // length and keeps the same +X travel direction through the seam.
    append_quarter_curve(points, cursor, 8.0, true);
    append_straight(points, cursor, 33.0, 0.0, DriveMode::Free, -1.0);
    append_quarter_curve(points, cursor, 6.0, false);
    append_quarter_curve(points, cursor, 4.0, true);
    append_quarter_curve(points, cursor, 4.0, true);
    append_straight(points, cursor, 1.0, 0.0, DriveMode::Brake, 5.0);

    return points;
}

[[nodiscard]] inline CenterlineRoute make_canonical_flame_route() {
    CenterlineRoute route;
    auto points = make_canonical_flame_layout_points();
    if (!route.rebuild(std::move(points), true)) route.clear();
    return route;
}

} // namespace ch::coaster
