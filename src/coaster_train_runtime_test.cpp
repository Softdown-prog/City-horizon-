#include "coaster_train_runtime.h"

#include <cmath>
#include <iostream>

namespace {

int fail(const char* message) {
    std::cerr << "coaster_train_runtime_test: " << message << '\n';
    return 1;
}

bool near(const double a, const double b, const double tolerance = 0.05) {
    return std::abs(a - b) <= tolerance;
}

}  // namespace

int main() {
    using namespace ch::coaster;

    TrainRuntimeConfig config;
    config.route_length_m = 40.0;
    config.closed_route = true;
    config.car_spacing_m = kFlameCarCenterSpacingM;
    config.physics.rolling_resistance_coefficient = 0.0;
    config.physics.drag_area_m2 = 0.0;
    config.physics.mechanical_linear_loss_per_s = 0.0;

    const auto straight_sampler = [](const double distance) {
        CenterlineSample s;
        s.distance_m = distance;
        s.x = 0.0;
        s.y = distance;
        s.z = 0.0;
        s.tangent_x = 0.0;
        s.tangent_y = 1.0;
        s.tangent_z = 0.0;
        return s;
    };

    TrainRuntimeState straight_state;
    straight_state.lead.distance_m = 12.0;
    straight_state.lead.speed_mps = 5.0;
    const TrainStepResult straight = step_train(straight_state, config, straight_sampler, 0.0);
    for (const CarRuntimePose& car : straight.cars) {
        if (car.sprite_pose.atlas_index != 0)
            return fail("straight +Y train must use flat h00 for every car");
    }
    if (!near(straight.cars[1].route_distance_m, 12.0 - kFlameCarCenterSpacingM, 0.001))
        return fail("car center spacing changed unexpectedly");

    // A synthetic quarter-circle proves articulation: each car samples a
    // different tangent, therefore it can select a different 22.5-degree pose.
    constexpr double kPi = 3.14159265358979323846;
    constexpr double kRadius = 6.0;
    const auto curve_sampler = [](const double distance) {
        CenterlineSample s;
        s.distance_m = distance;
        const double theta = distance / kRadius;
        s.x = kRadius * (std::cos(theta) - 1.0);
        s.y = kRadius * std::sin(theta);
        s.z = 0.0;
        s.tangent_x = -std::sin(theta);
        s.tangent_y = std::cos(theta);
        s.tangent_z = 0.0;
        s.horizontal_curvature_per_m = 1.0 / kRadius;
        return s;
    };

    TrainRuntimeState curve_state;
    curve_state.lead.distance_m = 0.5 * kPi * kRadius;
    curve_state.lead.speed_mps = 8.0;
    const TrainStepResult curve = step_train(curve_state, config, curve_sampler, 0.0);
    if (curve.cars[0].sprite_pose.logical_heading_index ==
        curve.cars[3].sprite_pose.logical_heading_index)
        return fail("front and rear cars must articulate to different curve headings");
    if (curve.cars[0].sprite_pose.logical_heading_index != 4)
        return fail("quarter-circle lead car must reach authored h04");
    if (!(curve.cars[0].forces.lateral_g > 1.0))
        return fail("curve car must expose lateral G telemetry");

    // Rear cars on a closed route wrap across distance zero rather than clamp.
    TrainRuntimeState wrap_state;
    wrap_state.lead.distance_m = 1.0;
    const TrainStepResult wrapped = step_train(wrap_state, config, straight_sampler, 0.0);
    if (!(wrapped.cars[1].route_distance_m > 38.0 && wrapped.cars[1].route_distance_m < 39.0))
        return fail("closed route must wrap rear-car distance");

    // The pose selector and train runtime must use the approved +30 degree
    // vertical supplement when the route tangent climbs at 30 degrees.
    const auto slope_sampler = [](const double distance) {
        CenterlineSample s;
        s.distance_m = distance;
        constexpr double kCos30 = 0.8660254037844386;
        constexpr double kSin30 = 0.5;
        s.y = distance * kCos30;
        s.z = distance * kSin30;
        s.tangent_y = kCos30;
        s.tangent_z = kSin30;
        return s;
    };
    TrainRuntimeState slope_state;
    slope_state.lead.distance_m = 10.0;
    slope_state.lead.speed_mps = 6.0;
    const TrainStepResult slope = step_train(slope_state, config, slope_sampler, 0.0);
    if (slope.cars[0].sprite_pose.atlas_index != 32 ||
        !near(slope.cars[0].sprite_pose.snapped_pitch_degrees, 30.0))
        return fail("+30 degree route must select approved vertical frame 32");

    // Longitudinal gravity is averaged across all four cars, not taken only
    // from the lead car. Here every car is descending so train speed must rise.
    const auto downhill_sampler = [](const double distance) {
        CenterlineSample s;
        s.distance_m = distance;
        constexpr double kCos14 = 0.9702957262759965;
        constexpr double kSin14 = -0.2419218955996677;
        s.y = distance * kCos14;
        s.z = 20.0 + distance * kSin14;
        s.tangent_y = kCos14;
        s.tangent_z = kSin14;
        return s;
    };
    TrainRuntimeState downhill_state;
    downhill_state.lead.distance_m = 15.0;
    downhill_state.lead.speed_mps = 10.0;
    const TrainStepResult downhill = step_train(downhill_state, config, downhill_sampler, 0.25);
    if (!(downhill.state.lead.speed_mps > 10.0))
        return fail("gravity must accelerate an articulated train downhill");
    if (!(downhill.physics.gravity_acceleration_mps2 > 0.0))
        return fail("downhill aggregate gravity acceleration must be positive");

    // A mixed profile verifies the important train-level behavior: the lead car
    // can already be descending while rear cars are still climbing. The solver
    // averages the gravity component over the complete train, avoiding a fake
    // acceleration jump when only the first car crosses a crest.
    const auto mixed_sampler = [](const double distance) {
        CenterlineSample s;
        s.distance_m = distance;
        s.y = distance;
        if (distance >= 10.0) {
            s.tangent_z = -0.25;
            s.z = 5.0 - 0.25 * (distance - 10.0);
        } else {
            s.tangent_z = 0.25;
            s.z = 2.5 + 0.25 * distance;
        }
        s.tangent_y = std::sqrt(1.0 - s.tangent_z * s.tangent_z);
        return s;
    };
    TrainRuntimeState mixed_state;
    mixed_state.lead.distance_m = 11.0;
    mixed_state.lead.speed_mps = 8.0;
    const auto mixed_samples = sample_train_centerline(11.0, config, mixed_sampler);
    const TrackSample mixed_track = aggregate_train_track_sample(mixed_samples);
    if (!(mixed_samples[0].tangent_z < 0.0 && mixed_samples[1].tangent_z < 0.0 &&
          mixed_samples[2].tangent_z > 0.0 && mixed_samples[3].tangent_z > 0.0))
        return fail("mixed crest test did not place cars on both sides of crest");
    if (!near(mixed_track.tangent_z, 0.0, 0.001))
        return fail("opposing car gravity components must average across train");

    // Open routes clamp rear cars at the start instead of wrapping to the end.
    TrainRuntimeConfig open_config = config;
    open_config.closed_route = false;
    const auto open_samples = sample_train_centerline(1.0, open_config, straight_sampler);
    if (!near(open_samples[1].distance_m, 0.0, 0.001) ||
        !near(open_samples[3].distance_m, 0.0, 0.001))
        return fail("open route rear cars must clamp to route start");

    std::cout << "CH_COASTER_TRAIN_RUNTIME_V1 regression: OK\n";
    std::cout << "curve_front_frame=" << curve.cars[0].sprite_pose.atlas_index << '\n';
    std::cout << "curve_rear_frame=" << curve.cars[3].sprite_pose.atlas_index << '\n';
    std::cout << "downhill_speed=" << downhill.state.lead.speed_mps << " m/s\n";
    return 0;
}
