#include "coaster_render_adapter.h"
#include "coaster_track_geometry.h"

#include <algorithm>
#include <cmath>
#include <iostream>
#include <vector>

namespace {

int fail(const char* message) {
    std::cerr << "coaster_track_geometry_test: " << message << '\n';
    return 1;
}

double distance(const ch::coaster::CoasterTrackPoint3& a,
                const ch::coaster::CoasterTrackPoint3& b) {
    const double dx = b.x - a.x;
    const double dy = b.y - a.y;
    const double dz = b.z - a.z;
    return std::sqrt(dx * dx + dy * dy + dz * dz);
}

bool near(const double a, const double b, const double tolerance = 0.02) {
    return std::abs(a - b) <= tolerance;
}

}  // namespace

int main() {
    using namespace ch::coaster;

    // A 75% grade is intentionally well beyond the railway system's 18% safety
    // profile. Coaster geometry must still follow it because ride track owns its
    // own structural contract.
    CenterlineRoute steep_route;
    std::vector<RoutePoint> steep = {
        {0.0, 0.0, 0.0},
        {4.0, 0.0, 3.0},
        {8.0, 0.0, 3.0},
    };
    if (!steep_route.rebuild(steep, false))
        return fail("steep coaster route must validate");

    const CoasterTrackStyle style{};
    const CoasterTrackGeometry steep_geometry =
        build_coaster_track_geometry(steep_route, style, -0.25);
    if (!steep_geometry.valid())
        return fail("steep route must produce coaster track geometry");
    if (steep_geometry.ties.empty())
        return fail("coaster track must produce cross ties");

    const CoasterTrackFrame& first = steep_geometry.frames.front();
    if (!near(distance(first.left_rail, first.right_rail), style.gauge_m, 0.01))
        return fail("rail gauge drifted from coaster style");

    // Support spacing should stay relaxed on low/straight track and tighten as
    // height, curvature and grade increase. This keeps valleys visually clean
    // while giving elevated/loaded sections enough structure.
    CenterlineSample relaxed_sample{};
    relaxed_sample.z = 1.5;
    relaxed_sample.up_z = 1.0;
    relaxed_sample.tangent_x = 1.0;

    CenterlineSample loaded_sample = relaxed_sample;
    loaded_sample.z = 9.0;
    loaded_sample.tangent_x = 0.8;
    loaded_sample.tangent_z = 0.6;
    loaded_sample.horizontal_curvature_per_m = 0.075;
    loaded_sample.vertical_curvature_per_m = 0.035;

    const double relaxed_spacing = adaptive_support_spacing_m(
        style, relaxed_sample, 0.0);
    const double loaded_spacing = adaptive_support_spacing_m(
        style, loaded_sample, 0.0);
    if (!(loaded_spacing < relaxed_spacing))
        return fail("loaded coaster sections must receive denser supports");
    if (loaded_spacing < style.support_min_spacing_m - 1.0e-9 ||
        relaxed_spacing > style.support_spacing_m + 1.0e-9)
        return fail("adaptive support spacing escaped configured bounds");

    // Verify that a vertical loop uses the transported local up/right frame.
    // At the apex local up points down; therefore the structural spine, offset
    // in -up, must move upward in world Z instead of staying beneath the car.
    constexpr double kPi = 3.14159265358979323846;
    constexpr double kRadius = 4.05;
    constexpr int kLoopSamples = 257;
    std::vector<RoutePoint> loop_points;
    loop_points.reserve(kLoopSamples);
    for (int i = 0; i < kLoopSamples; ++i) {
        const double theta =
            2.0 * kPi * static_cast<double>(i) /
            static_cast<double>(kLoopSamples - 1);
        RoutePoint point;
        point.y = kRadius * std::sin(theta);
        point.z = kRadius * (1.0 - std::cos(theta));
        loop_points.push_back(point);
    }

    CenterlineRoute loop_route;
    if (!loop_route.rebuild(loop_points, false))
        return fail("vertical loop route must validate");
    const CoasterTrackGeometry loop_geometry =
        build_coaster_track_geometry(loop_route, style, 0.0);
    if (!loop_geometry.valid())
        return fail("vertical loop must produce track geometry");

    const double apex_distance = loop_route.length_m() * 0.5;
    const auto apex_frame = std::min_element(
        loop_geometry.frames.begin(), loop_geometry.frames.end(),
        [apex_distance](const CoasterTrackFrame& a, const CoasterTrackFrame& b) {
            return std::abs(a.distance_m - apex_distance) <
                   std::abs(b.distance_m - apex_distance);
        });
    if (apex_frame == loop_geometry.frames.end())
        return fail("loop apex frame missing");
    if (!(std::abs(apex_frame->roll_degrees) > 150.0))
        return fail("loop apex must retain inverted roll");
    if (!(apex_frame->spine.z > apex_frame->center.z + 0.12))
        return fail("loop spine must follow inverted local up frame");

    const ch::CameraState camera{};
    const TrackRenderPlan render_plan =
        build_track_render_plan(loop_geometry, camera);
    if (render_plan.lines.empty())
        return fail("runtime render adapter must expose coaster track lines");

    bool saw_left_rail = false;
    bool saw_right_rail = false;
    bool saw_spine = false;
    bool saw_tie = false;
    for (const TrackLineRenderCommand& line : render_plan.lines) {
        saw_left_rail = saw_left_rail || line.kind == TrackLineKind::left_rail;
        saw_right_rail = saw_right_rail || line.kind == TrackLineKind::right_rail;
        saw_spine = saw_spine || line.kind == TrackLineKind::spine;
        saw_tie = saw_tie || line.kind == TrackLineKind::tie;
    }
    if (!saw_left_rail || !saw_right_rail || !saw_spine || !saw_tie)
        return fail("render plan is missing coaster track layers");

    std::cout << kCoasterTrackGeometryContract << " regression: OK\n";
    std::cout << "steep_frames=" << steep_geometry.frames.size()
              << " loop_frames=" << loop_geometry.frames.size()
              << " render_lines=" << render_plan.lines.size()
              << " relaxed_support_spacing=" << relaxed_spacing
              << " loaded_support_spacing=" << loaded_spacing << '\n';
    return 0;
}
