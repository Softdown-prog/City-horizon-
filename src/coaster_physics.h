#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>

namespace ch::coaster {

// CH_COASTER_PHYSICS_V1
// Runtime-only longitudinal physics for the simple City Horizon coaster.
// The route remains a sampled 3D centerline and the visual runtime remains 2D.
enum class DriveMode : std::uint8_t {
    Free,
    Lift,
    Brake,
    Station,
};

struct PhysicsConfig {
    double gravity_mps2 = 9.80665;
    double air_density_kg_m3 = 1.225;
    // Effective Cd*A for the complete train, not geometric area by itself.
    double drag_area_m2 = 1.45;
    double train_mass_kg = 1800.0;
    double rolling_resistance_coefficient = 0.0045;
    // Small bearing/axle loss represented as acceleration proportional to speed.
    double mechanical_linear_loss_per_s = 0.004;
    double maximum_speed_mps = 55.0;

    double lift_target_speed_mps = 2.4;
    double lift_controller_gain_per_s = 3.0;
    double lift_max_acceleration_mps2 = 5.0;

    double brake_target_speed_mps = 4.0;
    double brake_controller_gain_per_s = 4.0;
    double brake_max_deceleration_mps2 = 6.0;
    double station_max_deceleration_mps2 = 8.0;

    double stop_epsilon_mps = 0.03;
};

struct TrackSample {
    // Unit tangent vertical component: +1 straight up, -1 straight down.
    double tangent_z = 0.0;
    // Signed curvature in 1/m. Horizontal curvature produces lateral G.
    double horizontal_curvature_per_m = 0.0;
    // Positive = valley/concave-up, negative = crest/concave-down.
    double vertical_curvature_per_m = 0.0;
    double height_m = 0.0;
    DriveMode drive_mode = DriveMode::Free;
    // Negative means use the default target from PhysicsConfig.
    double target_speed_mps = -1.0;
};

struct MotionState {
    double distance_m = 0.0;
    double speed_mps = 0.0;
    double height_m = 0.0;
    bool stalled = false;
};

struct ForceSample {
    double vertical_g = 1.0;
    double lateral_g = 0.0;
    double total_g = 1.0;
    bool airtime = false;
};

struct StepResult {
    MotionState state;
    ForceSample forces;
    double gravity_acceleration_mps2 = 0.0;
    double rolling_acceleration_mps2 = 0.0;
    double aerodynamic_acceleration_mps2 = 0.0;
    double mechanical_acceleration_mps2 = 0.0;
    double drive_acceleration_mps2 = 0.0;
    double total_acceleration_mps2 = 0.0;
    double distance_delta_m = 0.0;
    double specific_mechanical_energy_j_per_kg = 0.0;
};

[[nodiscard]] inline double specific_mechanical_energy(const double speed_mps,
                                                        const double height_m,
                                                        const double gravity_mps2 = 9.80665) {
    const double v = std::max(0.0, speed_mps);
    return 0.5 * v * v + gravity_mps2 * height_m;
}

[[nodiscard]] inline double ideal_speed_after_height_change(const double initial_speed_mps,
                                                            const double height_delta_m,
                                                            const double gravity_mps2 = 9.80665) {
    const double v0 = std::max(0.0, initial_speed_mps);
    const double squared = v0 * v0 - 2.0 * gravity_mps2 * height_delta_m;
    return std::sqrt(std::max(0.0, squared));
}

[[nodiscard]] inline double ideal_maximum_climb_height(const double speed_mps,
                                                       const double gravity_mps2 = 9.80665) {
    const double v = std::max(0.0, speed_mps);
    return (v * v) / (2.0 * gravity_mps2);
}

[[nodiscard]] inline ForceSample force_sample(const double speed_mps,
                                              const TrackSample& track,
                                              const PhysicsConfig& config = {}) {
    const double v = std::max(0.0, speed_mps);
    const double tangent_z = std::clamp(track.tangent_z, -1.0, 1.0);
    const double pitch_cosine = std::sqrt(std::max(0.0, 1.0 - tangent_z * tangent_z));

    ForceSample result;
    result.vertical_g = pitch_cosine +
        (v * v * track.vertical_curvature_per_m) / config.gravity_mps2;
    result.lateral_g =
        (v * v * track.horizontal_curvature_per_m) / config.gravity_mps2;
    result.total_g = std::hypot(result.vertical_g, result.lateral_g);
    result.airtime = result.vertical_g < 0.20;
    return result;
}

[[nodiscard]] inline StepResult step(const MotionState& current,
                                     const TrackSample& track,
                                     const double dt_seconds,
                                     const PhysicsConfig& config = {}) {
    StepResult result;
    result.state = current;
    if (!(dt_seconds > 0.0) || !(config.gravity_mps2 > 0.0) ||
        !(config.train_mass_kg > 0.0)) {
        result.forces = force_sample(current.speed_mps, track, config);
        result.specific_mechanical_energy_j_per_kg =
            specific_mechanical_energy(current.speed_mps, current.height_m, config.gravity_mps2);
        return result;
    }

    const double tangent_z = std::clamp(track.tangent_z, -1.0, 1.0);
    const double speed = std::clamp(current.speed_mps, 0.0, config.maximum_speed_mps);
    const double normal_factor = std::sqrt(std::max(0.0, 1.0 - tangent_z * tangent_z));

    // Projection of gravity onto the normalized track tangent. Going uphill
    // (positive tangent_z) removes speed; going downhill adds speed.
    result.gravity_acceleration_mps2 = -config.gravity_mps2 * tangent_z;

    if (speed > config.stop_epsilon_mps) {
        result.rolling_acceleration_mps2 =
            -config.rolling_resistance_coefficient * config.gravity_mps2 * normal_factor;
        result.aerodynamic_acceleration_mps2 =
            -0.5 * config.air_density_kg_m3 * config.drag_area_m2 * speed * speed /
            config.train_mass_kg;
        result.mechanical_acceleration_mps2 =
            -config.mechanical_linear_loss_per_s * speed;
    }

    const double passive_acceleration =
        result.gravity_acceleration_mps2 +
        result.rolling_acceleration_mps2 +
        result.aerodynamic_acceleration_mps2 +
        result.mechanical_acceleration_mps2;

    switch (track.drive_mode) {
        case DriveMode::Free:
            result.drive_acceleration_mps2 = 0.0;
            break;
        case DriveMode::Lift: {
            const double target = track.target_speed_mps >= 0.0
                ? track.target_speed_mps
                : config.lift_target_speed_mps;
            // Feed-forward cancels gravity/losses while the proportional term
            // pulls the train toward the chain-lift target speed.
            const double desired =
                -passive_acceleration +
                config.lift_controller_gain_per_s * (target - speed);
            result.drive_acceleration_mps2 = std::clamp(
                desired, 0.0, config.lift_max_acceleration_mps2);
            break;
        }
        case DriveMode::Brake:
        case DriveMode::Station: {
            const double target = track.target_speed_mps >= 0.0
                ? track.target_speed_mps
                : (track.drive_mode == DriveMode::Station ? 0.0 : config.brake_target_speed_mps);
            const double maximum_deceleration = track.drive_mode == DriveMode::Station
                ? config.station_max_deceleration_mps2
                : config.brake_max_deceleration_mps2;
            const double desired_total =
                config.brake_controller_gain_per_s * (target - speed);
            const double requested_brake = desired_total - passive_acceleration;
            result.drive_acceleration_mps2 = std::clamp(
                requested_brake, -maximum_deceleration, 0.0);
            break;
        }
    }

    result.total_acceleration_mps2 = passive_acceleration + result.drive_acceleration_mps2;
    double next_speed = std::clamp(
        speed + result.total_acceleration_mps2 * dt_seconds,
        0.0,
        config.maximum_speed_mps);

    if ((track.drive_mode == DriveMode::Station || track.drive_mode == DriveMode::Brake) &&
        next_speed < config.stop_epsilon_mps) {
        next_speed = 0.0;
    }

    const double average_speed = 0.5 * (speed + next_speed);
    result.distance_delta_m = average_speed * dt_seconds;
    result.state.distance_m = current.distance_m + result.distance_delta_m;
    result.state.speed_mps = next_speed;
    // The real route sampler is authoritative for height. This local update is
    // a deterministic approximation between two centerline samples.
    result.state.height_m = current.height_m + tangent_z * result.distance_delta_m;
    result.state.stalled =
        track.drive_mode == DriveMode::Free &&
        next_speed <= config.stop_epsilon_mps &&
        result.gravity_acceleration_mps2 < 0.0;

    result.forces = force_sample(next_speed, track, config);
    result.specific_mechanical_energy_j_per_kg =
        specific_mechanical_energy(next_speed, result.state.height_m, config.gravity_mps2);
    return result;
}

}  // namespace ch::coaster
