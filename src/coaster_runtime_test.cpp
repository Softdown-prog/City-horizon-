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
    if (south.cars[0].sprite_pose.logical_heading_index != 0)
        return fail("circle start tangent must select h00");
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
    for (int i = 0; i < 400; ++i) runtime.update(0.01, 0);
    if (!near(runtime.state().lead.speed_mps, 2.4, 0.12))
        return fail("lift route must pull train toward target speed");

    // Invalid duplicate points fail closed instead of poisoning runtime state.
    std::vector<RoutePoint> invalid = {{0.0, 0.0, 0.0}, {0.0, 0.0, 0.0}};
    CenterlineRoute invalid_route;
    if (invalid_route.rebuild(invalid, false)) return fail("zero-length route segment must be rejected");

    std::cout << "CH_COASTER_RUNTIME_V1 regression: OK\n";
    std::cout << "circle_length=" << runtime.route().length_m() << " m\n";
    std::cout << "lift_speed=" << runtime.state().lead.speed_mps << " m/s\n";
    return 0;
}
