#pragma once

#include "coaster_car_pose.h"
#include "coaster_physics.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>

namespace ch::coaster {

// CH_COASTER_TRAIN_RUNTIME_V2
//
// Runtime bridge between the logical CH_COASTER_TRACK_V1 centerline, the
// CH_COASTER_PHYSICS_V1 longitudinal solver, and the Flame car sprite atlas.
// V2 preserves the full local track frame (forward/right/up + roll), allowing
// inversions to be represented without pretending that heading+pitch alone are
// sufficient. Moving Flame cars consume the promoted occupied
// CH_COASTER_CAR_ATLAS_RUNTIME_V2; unsupported combined pitch+roll poses are
// reported explicitly instead of silently falling back to V1.
inline constexpr int kCoasterTrainCarCount = 4;
inline constexpr double kFlameCarCenterSpacingM = 2.445;

struct CenterlineSample {
    double distance_m = 0.0;
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;
    double tangent_x = 0.0;
    double tangent_y = 1.0;
    double tangent_z = 0.0;
    double right_x = 1.0;
    double right_y = 0.0;
    double right_z = 0.0;
    double up_x = 0.0;
    double up_y = 0.0;
    double up_z = 1.0;
    double roll_degrees = 0.0;
    double horizontal_curvature_per_m = 0.0;
    double vertical_curvature_per_m = 0.0;
    DriveMode drive_mode = DriveMode::Free;
    double target_speed_mps = -1.0;
};

struct TrainRuntimeConfig {
    double route_length_m = 0.0;
    bool closed_route = true;
    double car_spacing_m = kFlameCarCenterSpacingM;
    PhysicsConfig physics{};
};

struct CarRuntimePose {
    int car_index = 0;
    double route_distance_m = 0.0;
    double world_x = 0.0;
    double world_y = 0.0;
    double world_z = 0.0;
    double tangent_x = 0.0;
    double tangent_y = 1.0;
    double tangent_z = 0.0;
    double right_x = 1.0;
    double right_y = 0.0;
    double right_z = 0.0;
    double up_x = 0.0;
    double up_y = 0.0;
    double up_z = 1.0;
    double roll_degrees = 0.0;
    CarPoseSelection sprite_pose{};
    ForceSample forces{};
};

struct TrainRuntimeState {
    MotionState lead{};
};

struct TrainStepResult {
    bool valid = false;
    TrainRuntimeState state{};
    StepResult physics{};
    std::array<CarRuntimePose, kCoasterTrainCarCount> cars{};
};

[[nodiscard]] inline double normalize_route_distance(double distance_m,
                                                     const double route_length_m,
                                                     const bool closed_route) noexcept {
    if (!(route_length_m > 0.0) || !std::isfinite(route_length_m)) return 0.0;
    if (!std::isfinite(distance_m)) distance_m = 0.0;
    if (!closed_route) return std::clamp(distance_m, 0.0, route_length_m);
    distance_m = std::fmod(distance_m, route_length_m);
    if (distance_m < 0.0) distance_m += route_length_m;
    return distance_m;
}

[[nodiscard]] inline double car_route_distance(const double lead_distance_m,
                                               const int car_index,
                                               const TrainRuntimeConfig& config) noexcept {
    const double spacing = std::max(0.0, config.car_spacing_m);
    return normalize_route_distance(
        lead_distance_m - static_cast<double>(std::max(0, car_index)) * spacing,
        config.route_length_m,
        config.closed_route);
}

[[nodiscard]] inline int drive_mode_priority(const DriveMode mode) noexcept {
    switch (mode) {
        case DriveMode::Station: return 3;
        case DriveMode::Brake: return 2;
        case DriveMode::Lift: return 1;
        case DriveMode::Free: return 0;
    }
    return 0;
}

[[nodiscard]] inline TrackSample aggregate_train_track_sample(
    const std::array<CenterlineSample, kCoasterTrainCarCount>& samples) noexcept {
    TrackSample aggregate;
    double tangent_z_sum = 0.0;
    double horizontal_curvature_sum = 0.0;
    double vertical_curvature_sum = 0.0;
    double height_sum = 0.0;
    int selected_priority = 0;
    bool target_selected = false;

    for (const CenterlineSample& sample : samples) {
        tangent_z_sum += std::clamp(sample.tangent_z, -1.0, 1.0);
        horizontal_curvature_sum += sample.horizontal_curvature_per_m;
        vertical_curvature_sum += sample.vertical_curvature_per_m;
        height_sum += sample.z;

        const int priority = drive_mode_priority(sample.drive_mode);
        if (priority > selected_priority) {
            selected_priority = priority;
            aggregate.drive_mode = sample.drive_mode;
            aggregate.target_speed_mps = sample.target_speed_mps;
            target_selected = sample.target_speed_mps >= 0.0;
        } else if (priority == selected_priority && priority > 0 &&
                   sample.drive_mode == aggregate.drive_mode && sample.target_speed_mps >= 0.0) {
            if (!target_selected) {
                aggregate.target_speed_mps = sample.target_speed_mps;
                target_selected = true;
            } else if (aggregate.drive_mode == DriveMode::Lift) {
                aggregate.target_speed_mps = std::max(
                    aggregate.target_speed_mps, sample.target_speed_mps);
            } else {
                aggregate.target_speed_mps = std::min(
                    aggregate.target_speed_mps, sample.target_speed_mps);
            }
        }
    }

    constexpr double kInvCarCount = 1.0 / static_cast<double>(kCoasterTrainCarCount);
    aggregate.tangent_z = tangent_z_sum * kInvCarCount;
    aggregate.horizontal_curvature_per_m = horizontal_curvature_sum * kInvCarCount;
    aggregate.vertical_curvature_per_m = vertical_curvature_sum * kInvCarCount;
    aggregate.height_m = height_sum * kInvCarCount;
    return aggregate;
}

template <typename CenterlineSampler>
[[nodiscard]] inline std::array<CenterlineSample, kCoasterTrainCarCount> sample_train_centerline(
    const double lead_distance_m,
    const TrainRuntimeConfig& config,
    CenterlineSampler&& sampler) {
    std::array<CenterlineSample, kCoasterTrainCarCount> samples{};
    for (int car = 0; car < kCoasterTrainCarCount; ++car) {
        const double distance = car_route_distance(lead_distance_m, car, config);
        samples[static_cast<std::size_t>(car)] = sampler(distance);
        samples[static_cast<std::size_t>(car)].distance_m = distance;
    }
    return samples;
}

[[nodiscard]] inline CarRuntimePose make_car_runtime_pose(const int car_index,
                                                          const CenterlineSample& sample,
                                                          const double train_speed_mps,
                                                          const int camera_quarter_turns,
                                                          const PhysicsConfig& physics_config) noexcept {
    CarRuntimePose result;
    result.car_index = car_index;
    result.route_distance_m = sample.distance_m;
    result.world_x = sample.x;
    result.world_y = sample.y;
    result.world_z = sample.z;
    result.tangent_x = sample.tangent_x;
    result.tangent_y = sample.tangent_y;
    result.tangent_z = sample.tangent_z;
    result.right_x = sample.right_x;
    result.right_y = sample.right_y;
    result.right_z = sample.right_z;
    result.up_x = sample.up_x;
    result.up_y = sample.up_y;
    result.up_z = sample.up_z;
    result.roll_degrees = sample.roll_degrees;
    result.sprite_pose = select_car_pose_from_frame(
        sample.tangent_x,
        sample.tangent_y,
        sample.tangent_z,
        sample.up_x,
        sample.up_y,
        sample.up_z,
        camera_quarter_turns);

    TrackSample track;
    track.tangent_z = sample.tangent_z;
    track.horizontal_curvature_per_m = sample.horizontal_curvature_per_m;
    track.vertical_curvature_per_m = sample.vertical_curvature_per_m;
    track.height_m = sample.z;
    track.drive_mode = sample.drive_mode;
    track.target_speed_mps = sample.target_speed_mps;
    result.forces = force_sample(train_speed_mps, track, physics_config);
    return result;
}

template <typename CenterlineSampler>
[[nodiscard]] inline TrainStepResult step_train(const TrainRuntimeState& current,
                                                const TrainRuntimeConfig& config,
                                                CenterlineSampler&& sampler,
                                                const double dt_seconds,
                                                const int camera_quarter_turns = 0) {
    TrainStepResult result;
    result.state = current;

    if (!(config.route_length_m > 0.0) || !std::isfinite(config.route_length_m)) {
        return result;
    }

    const double current_distance = normalize_route_distance(
        current.lead.distance_m, config.route_length_m, config.closed_route);
    const auto before = sample_train_centerline(current_distance, config, sampler);
    const TrackSample aggregate_track = aggregate_train_track_sample(before);

    MotionState physics_state = current.lead;
    physics_state.distance_m = current_distance;
    physics_state.height_m = before[0].z;

    result.physics = step(physics_state, aggregate_track, dt_seconds, config.physics);

    const double next_distance = normalize_route_distance(
        result.physics.state.distance_m, config.route_length_m, config.closed_route);
    const auto after = sample_train_centerline(next_distance, config, sampler);

    result.state.lead = result.physics.state;
    result.state.lead.distance_m = next_distance;
    result.state.lead.height_m = after[0].z;
    result.physics.state = result.state.lead;
    result.physics.specific_mechanical_energy_j_per_kg = specific_mechanical_energy(
        result.state.lead.speed_mps,
        result.state.lead.height_m,
        config.physics.gravity_mps2);

    for (int car = 0; car < kCoasterTrainCarCount; ++car) {
        result.cars[static_cast<std::size_t>(car)] = make_car_runtime_pose(
            car,
            after[static_cast<std::size_t>(car)],
            result.state.lead.speed_mps,
            camera_quarter_turns,
            config.physics);
    }
    result.valid = true;
    return result;
}

}  // namespace ch::coaster
