#include "coaster_runtime.h"

#include <cmath>
#include <iostream>
#include <vector>

namespace {

int fail(const char* message) {
    std::cerr << "coaster_runtime_test: " << message << '\n';
    return 1;
}

bool near(const double a, const double b, const double tolerance = 0.08) {
    return std::abs(a - b) <= tolerance;
}

}  // namespace

int main() {
    using namespace ch::coaster;
    constexpr double kPi = 3.14159265358979323846;

    std::vector<RoutePoint> circle;
    constexpr int kSamples = 64;
    constexpr double kRadius = 9.0;
    circle.reserve(kSamples);
    for (int i = 0; i < kSamples; ++i) {
        const double angle = 2.0 * kPi * static_cast<double>(i) / static_cast<double>(kSamples);
        RoutePoint point;
        point.x = kRadius * std::sin(angle);
        point.y = kRadius * std::cos(angle);
        point.z = 2.0 + 0.75 * (1.0 - std::cos(2.0 * angle));
        circle.push_back(point);
    }

    CoasterRuntime runtime;
    if (!runtime.set_route(circle, true)) return fail("closed centerline route must validate");
    if (!runtime.ready()) return fail("runtime must become ready after route promotion");
    if (!(runtime.route().length_m() > 50.0)) return fail("circle route length is unexpectedly short");

    runtime.reset(0.0, 8.0);
    const TrainStepResult south = runtime.snapshot(0);
    if (!south.valid) return fail("valid centerline snapshot must be marked renderable");
    // The authored circle starts at (0,+R) and advances toward +X. In the
    // Flame +Y-forward convention that tangent is heading 270 degrees = h12.
    if (south.cars[0].sprite_pose.logical_heading_index != 12)
        return fail("circle start tangent must select h12");
    if (south.cars[0].sprite_pose.atlas_index < 0 || south.cars[0].sprite_pose.atlas_index >= kCarPoseFrameCount)
        return fail("lead car selected an invalid atlas frame");

    const TrainStepResult rotated = runtime.snapshot(1);
    if (rotated.cars[0].sprite_pose.visual_heading_index == south.cars[0].sprite_pose.visual_heading_index)
        return fail("camera quarter-turn must select another visual heading");

    const double before_distance = runtime.state().lead.distance_m;
    const TrainStepResult advanced = runtime.update(0.25, 0);
    if (!(advanced.state.lead.distance_m > before_distance))
        return fail("moving coaster train must advance along centerline");
    if (!(advanced.state.lead.speed_mps > 0.0))
        return fail("free-running train unexpectedly stopped");

    bool articulated = false;
    for (std::size_t i = 1; i < advanced.cars.size(); ++i) {
        if (advanced.cars[i].sprite_pose.logical_heading_index !=
            advanced.cars[0].sprite_pose.logical_heading_index) {
            articulated = true;
            break;
        }
    }
    if (!articulated) return fail("four cars must articulate independently on a curved route");

    // Tight hairpins used to make incoming + outgoing tangents nearly cancel.
    // The old normalizer then substituted world +Y, which could make a car flip
    // sideways/backwards even though its route distance kept moving forward.
    CenterlineRoute hairpin;
    std::vector<RoutePoint> hairpin_points = {
        {0.0, 0.0, 0.0},
        {0.0, 4.0, 0.0},
        {0.20, 0.0, 0.0},
        {4.0, 0.0, 0.0},
    };
    if (!hairpin.rebuild(hairpin_points, false))
        return fail("hairpin route must validate");

    const double first_segment = 4.0;
    const double second_dx = 0.20;
    const double second_dy = -4.0;
    const double second_length = std::hypot(second_dx, second_dy);
    const double forward_x = second_dx / second_length;
    const double forward_y = second_dy / second_length;
    for (int i = 1; i <= 9; ++i) {
        const double d = first_segment + second_length * (static_cast<double>(i) / 10.0);
        const auto sample = hairpin.sample(d);
        if (!sample) return fail("hairpin sample unexpectedly failed");
        const double alignment = sample->tangent_x * forward_x + sample->tangent_y * forward_y;
        if (!(alignment > 0.0))
            return fail("hairpin tangent must remain in the forward travel hemisphere");
    }

    // Exact reversal is the strongest regression case: the vertex average is zero.
    CenterlineRoute reversal;
    std::vector<RoutePoint> reversal_points = {
        {0.0, 0.0, 0.0},
        {0.0, 4.0, 0.0},
        {0.0, 0.5, 0.0},
        {3.0, 0.5, 0.0},
    };
    if (!reversal.rebuild(reversal_points, false))
        return fail("reversal route must validate");
    const auto reversal_sample = reversal.sample(4.0 + 1.0);
    if (!reversal_sample) return fail("reversal sample unexpectedly failed");
    if (!(reversal_sample->tangent_y < 0.0))
        return fail("reversal tangent must follow the outgoing -Y segment, never fixed +Y");

    // Open lift route proves that drive semantics survive the route bridge.
    std::vector<RoutePoint> lift_points;
    for (int i = 0; i <= 12; ++i) {
        RoutePoint point;
        point.y = static_cast<double>(i) * 1.5;
        point.z = static_cast<double>(i) * 0.36;
        point.drive_mode = DriveMode::Lift;
        point.target_speed_mps = 2.4;
        lift_points.push_back(point);
    }
    if (!runtime.set_route(lift_points, false)) return fail("open lift route must validate");
    runtime.reset(0.0, 0.0);
    TrainStepResult lift_step;
    for (int i = 0; i < 400; ++i) lift_step = runtime.update(0.01, 0);
    if (!near(runtime.state().lead.speed_mps, 2.4, 0.12))
        return fail("lift route must pull train toward target speed");
    if (!lift_step.valid) return fail("lift route must continue producing renderable cars");

    // Invalid duplicate points fail closed instead of poisoning runtime state.
    std::vector<RoutePoint> invalid = {{0.0, 0.0, 0.0}, {0.0, 0.0, 0.0}};
    CenterlineRoute invalid_route;
    if (invalid_route.rebuild(invalid, false)) return fail("zero-length route segment must be rejected");

    std::cout << "CH_COASTER_RUNTIME_V1 regression: OK\n";
    std::cout << "circle_length=" << runtime.route().length_m() << " m\n";
    std::cout << "lift_speed=" << runtime.state().lead.speed_mps << " m/s\n";
    return 0;
}
