#pragma once

#include <algorithm>
#include <cstdint>

inline constexpr const char* kRideStateMachineContract = "CH_RIDE_STATE_MACHINE_V1";

enum class RideOperatingState : std::uint8_t {
    idle,
    boarding,
    starting,
    running,
    stopping,
    unloading,
};

struct RideStateDurations {
    std::uint32_t boarding_ms = 2500;
    std::uint32_t starting_ms = 500;
    std::uint32_t running_ms = 3500;
    std::uint32_t stopping_ms = 500;
    std::uint32_t unloading_ms = 2000;
};

struct RideStateSnapshot {
    RideOperatingState state = RideOperatingState::idle;
    std::uint32_t elapsed_in_state_ms = 0;
    bool dispatch_requested = false;

    [[nodiscard]] float normalized_running_phase(const RideStateDurations& durations) const noexcept {
        if (state != RideOperatingState::running || durations.running_ms == 0) return 0.0F;
        return std::clamp(static_cast<float>(elapsed_in_state_ms) /
                              static_cast<float>(durations.running_ms),
                          0.0F, 1.0F);
    }
};

class RideStateMachine {
public:
    explicit RideStateMachine(RideStateDurations durations = {}) : durations_(durations) {}

    [[nodiscard]] const RideStateSnapshot& snapshot() const noexcept { return state_; }
    [[nodiscard]] const RideStateDurations& durations() const noexcept { return durations_; }

    void set_durations(const RideStateDurations durations) noexcept { durations_ = durations; }

    void request_dispatch() noexcept {
        state_.dispatch_requested = true;
        if (state_.state == RideOperatingState::idle) transition_to(RideOperatingState::boarding);
    }

    void reset() noexcept { state_ = {}; }

    void update(const std::uint32_t delta_ms) noexcept {
        std::uint64_t remaining = delta_ms;
        while (remaining > 0) {
            const std::uint32_t duration = duration_for(state_.state);
            if (state_.state == RideOperatingState::idle) return;
            if (duration == 0) {
                advance_state();
                continue;
            }

            const std::uint32_t left = duration > state_.elapsed_in_state_ms
                ? duration - state_.elapsed_in_state_ms
                : 0;
            if (remaining < left) {
                state_.elapsed_in_state_ms += static_cast<std::uint32_t>(remaining);
                return;
            }

            remaining -= left;
            state_.elapsed_in_state_ms = duration;
            advance_state();
        }
    }

private:
    [[nodiscard]] std::uint32_t duration_for(const RideOperatingState state) const noexcept {
        switch (state) {
            case RideOperatingState::idle: return 0;
            case RideOperatingState::boarding: return durations_.boarding_ms;
            case RideOperatingState::starting: return durations_.starting_ms;
            case RideOperatingState::running: return durations_.running_ms;
            case RideOperatingState::stopping: return durations_.stopping_ms;
            case RideOperatingState::unloading: return durations_.unloading_ms;
        }
        return 0;
    }

    void transition_to(const RideOperatingState next) noexcept {
        state_.state = next;
        state_.elapsed_in_state_ms = 0;
    }

    void advance_state() noexcept {
        switch (state_.state) {
            case RideOperatingState::idle:
                if (state_.dispatch_requested) transition_to(RideOperatingState::boarding);
                break;
            case RideOperatingState::boarding:
                transition_to(RideOperatingState::starting);
                break;
            case RideOperatingState::starting:
                transition_to(RideOperatingState::running);
                break;
            case RideOperatingState::running:
                transition_to(RideOperatingState::stopping);
                break;
            case RideOperatingState::stopping:
                transition_to(RideOperatingState::unloading);
                break;
            case RideOperatingState::unloading:
                state_.dispatch_requested = false;
                transition_to(RideOperatingState::idle);
                break;
        }
    }

    RideStateDurations durations_;
    RideStateSnapshot state_;
};
