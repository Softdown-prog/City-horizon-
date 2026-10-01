#include "coaster_physics.h"

#include <cmath>
#include <iostream>

namespace {

bool near(const double a, const double b, const double tolerance) {
    return std::abs(a - b) <= tolerance;
}

int fail(const char* message) {
    std::cerr << "coaster_physics_test: " << message << '\n';
    return 1;
}

}  // namespace

int main() {
    using namespace ch::coaster;

    PhysicsConfig ideal;
    ideal.rolling_resistance_coefficient = 0.0;
    ideal.drag_area_m2 = 0.0;
    ideal.mechanical_linear_loss_per_s = 0.0;

    const double downhill = ideal_speed_after_height_change(20.0, -10.0, ideal.gravity_mps2);
    const double uphill = ideal_speed_after_height_change(20.0, 10.0, ideal.gravity_mps2);
    if (!(downhill > 20.0)) return fail("downhill energy conversion must increase speed");
    if (!(uphill < 20.0 && uphill > 0.0)) return fail("uphill energy conversion must reduce speed");
    if (!near(ideal_maximum_climb_height(20.0, ideal.gravity_mps2), 20.394, 0.01))
        return fail("ideal maximum climb height changed unexpectedly");

    MotionState state;
    state.speed_mps = 10.0;
    TrackSample slope_down;
    slope_down.tangent_z = -0.242535625;  // approximately -14.04 degrees
    for (int i = 0; i < 100; ++i) state = step(state, slope_down, 0.01, ideal).state;
    if (!(state.speed_mps > 12.0)) return fail("free downhill segment must accelerate under gravity");

    state = {};
    state.speed_mps = 10.0;
    TrackSample slope_up;
    slope_up.tangent_z = 0.242535625;
    for (int i = 0; i < 100; ++i) state = step(state, slope_up, 0.01, ideal).state;
    if (!(state.speed_mps < 8.0)) return fail("free uphill segment must lose speed under gravity");

    TrackSample flat_curve;
    flat_curve.horizontal_curvature_per_m = 0.03;
    const ForceSample curve_force = force_sample(20.0, flat_curve, ideal);
    if (!near(curve_force.vertical_g, 1.0, 0.001))
        return fail("flat curve should retain about one vertical G");
    if (!(std::abs(curve_force.lateral_g) > 1.0))
        return fail("flat curve must produce lateral G at speed");

    TrackSample crest;
    crest.vertical_curvature_per_m = -0.025;
    const ForceSample crest_force = force_sample(15.0, crest, ideal);
    TrackSample valley;
    valley.vertical_curvature_per_m = 0.025;
    const ForceSample valley_force = force_sample(15.0, valley, ideal);
    if (!(crest_force.vertical_g < 1.0)) return fail("hill crest must unload vertical G");
    if (!(valley_force.vertical_g > 1.0)) return fail("valley must increase vertical G");

    PhysicsConfig production;
    MotionState lift_state;
    TrackSample lift = slope_up;
    lift.drive_mode = DriveMode::Lift;
    for (int i = 0; i < 500; ++i) lift_state = step(lift_state, lift, 0.01, production).state;
    if (!near(lift_state.speed_mps, production.lift_target_speed_mps, 0.08))
        return fail("chain lift must pull an uphill train toward target speed");

    MotionState brake_state;
    brake_state.speed_mps = 20.0;
    TrackSample brake;
    brake.drive_mode = DriveMode::Brake;
    brake.target_speed_mps = 4.0;
    for (int i = 0; i < 400; ++i) brake_state = step(brake_state, brake, 0.01, production).state;
    if (!near(brake_state.speed_mps, 4.0, 0.12))
        return fail("brake segment must converge toward configured target speed");

    MotionState stalled_state;
    stalled_state.speed_mps = 0.2;
    TrackSample steep_up;
    steep_up.tangent_z = 0.5;
    for (int i = 0; i < 100; ++i) stalled_state = step(stalled_state, steep_up, 0.01, production).state;
    if (!stalled_state.stalled || stalled_state.speed_mps != 0.0)
        return fail("insufficient-energy uphill train must report a forward stall");

    std::cout << "CH_COASTER_PHYSICS_V1 regression: OK\n";
    std::cout << "downhill_20mps_drop10m=" << downhill << " m/s\n";
    std::cout << "uphill_20mps_rise10m=" << uphill << " m/s\n";
    std::cout << "flat_curve_lateral_g=" << curve_force.lateral_g << '\n';
    std::cout << "crest_vertical_g=" << crest_force.vertical_g << '\n';
    std::cout << "valley_vertical_g=" << valley_force.vertical_g << '\n';
    return 0;
}
