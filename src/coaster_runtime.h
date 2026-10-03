#pragma once

#include "coaster_track_geometry.h"

#include <utility>
#include <vector>

namespace ch::coaster {

// CH_COASTER_RUNTIME_V1
// Production facade binding one validated centerline route to the articulated
// four-car Flame train, gravity/energy solver, pose selector and the dedicated
// CH_COASTER_TRACK_GEOMETRY_V1 world geometry consumed by presentation.
class CoasterRuntime final {
public:
    [[nodiscard]] bool set_route(std::vector<RoutePoint> points, const bool closed_route) {
        CenterlineRoute candidate;
        if (!candidate.rebuild(std::move(points), closed_route)) return false;

        CoasterTrackGeometry candidate_track = build_coaster_track_geometry(candidate);
        if (!candidate_track.valid()) return false;

        route_ = std::move(candidate);
        track_geometry_ = std::move(candidate_track);
        config_.route_length_m = route_.length_m();
        config_.closed_route = route_.closed();
        reset();
        return true;
    }

    void clear_route() {
        route_.clear();
        track_geometry_.clear();
        config_.route_length_m = 0.0;
        state_ = {};
        last_step_ = {};
    }

    void reset(const double lead_distance_m = 0.0, const double speed_mps = 0.0) {
        state_ = {};
        if (!route_.valid()) {
            last_step_ = {};
            return;
        }
        state_.lead.distance_m = normalize_route_distance(
            lead_distance_m, route_.length_m(), route_.closed());
        state_.lead.speed_mps = std::max(0.0, speed_mps);
        if (const auto sample = route_.sample(state_.lead.distance_m)) {
            state_.lead.height_m = sample->z;
        }
        last_step_ = snapshot(0);
    }

    [[nodiscard]] TrainStepResult update(const double dt_seconds,
                                         const int camera_quarter_turns = 0) {
        if (!route_.valid()) {
            last_step_ = {};
            return last_step_;
        }
        const auto sampler = [this](const double distance_m) {
            const auto sample = route_.sample(distance_m);
            return sample.value_or(CenterlineSample{});
        };
        last_step_ = step_train(
            state_, config_, sampler, dt_seconds, camera_quarter_turns);
        state_ = last_step_.state;
        return last_step_;
    }

    [[nodiscard]] TrainStepResult snapshot(const int camera_quarter_turns = 0) const {
        if (!route_.valid()) return {};
        const auto sampler = [this](const double distance_m) {
            const auto sample = route_.sample(distance_m);
            return sample.value_or(CenterlineSample{});
        };
        return step_train(state_, config_, sampler, 0.0, camera_quarter_turns);
    }

    [[nodiscard]] bool ready() const noexcept {
        return route_.valid() && track_geometry_.valid();
    }
    [[nodiscard]] const CenterlineRoute& route() const noexcept { return route_; }
    [[nodiscard]] const CoasterTrackGeometry& track_geometry() const noexcept {
        return track_geometry_;
    }
    [[nodiscard]] const TrainRuntimeState& state() const noexcept { return state_; }
    [[nodiscard]] const TrainStepResult& last_step() const noexcept { return last_step_; }
    [[nodiscard]] TrainRuntimeConfig& config() noexcept { return config_; }
    [[nodiscard]] const TrainRuntimeConfig& config() const noexcept { return config_; }

private:
    CenterlineRoute route_{};
    CoasterTrackGeometry track_geometry_{};
    TrainRuntimeConfig config_{};
    TrainRuntimeState state_{};
    TrainStepResult last_step_{};
};

}  // namespace ch::coaster
