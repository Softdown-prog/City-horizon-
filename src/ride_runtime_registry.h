#pragma once

#include "ride_state_machine.h"

#include <cstdint>
#include <string_view>
#include <unordered_map>

namespace ch::ride_runtime {

struct RideRuntimeEntry {
    RideStateMachine machine{};
    bool source_activity_active = false;
};

inline std::unordered_map<std::uint64_t, RideRuntimeEntry> g_rides;

[[nodiscard]] inline RideStateDurations durations_for(const std::string_view definition_id) noexcept {
    RideStateDurations durations{};
    if (definition_id == "pirate_ship_01") {
        durations.boarding_ms = 2500;
        durations.starting_ms = 292;
        durations.running_ms = 3500;
        durations.stopping_ms = 292;
        durations.unloading_ms = 2000;
    } else if (definition_id == "ferris_wheel_01") {
        durations.boarding_ms = 2500;
        durations.starting_ms = 125;
        durations.running_ms = 6000;
        durations.stopping_ms = 125;
        durations.unloading_ms = 2000;
    }
    return durations;
}

[[nodiscard]] inline RideRuntimeEntry& ensure(const std::uint64_t instance_id,
                                               const std::string_view definition_id) {
    auto [it, inserted] = g_rides.try_emplace(instance_id);
    if (inserted) {
        it->second.machine.set_durations(durations_for(definition_id));
    }
    return it->second;
}

inline void sync_activity(const std::uint64_t instance_id, const std::string_view definition_id,
                          const bool activity_active, const std::uint32_t delta_ms) {
    RideRuntimeEntry& entry = ensure(instance_id, definition_id);
    if (activity_active && !entry.source_activity_active &&
        entry.machine.snapshot().state == RideOperatingState::idle) {
        entry.machine.request_dispatch();
    }
    entry.source_activity_active = activity_active;
    entry.machine.update(delta_ms);
}

[[nodiscard]] inline RideOperatingState state(const std::uint64_t instance_id) noexcept {
    const auto it = g_rides.find(instance_id);
    return it == g_rides.end() ? RideOperatingState::idle : it->second.machine.snapshot().state;
}

[[nodiscard]] inline bool is_moving(const std::uint64_t instance_id) noexcept {
    const RideOperatingState current = state(instance_id);
    return current == RideOperatingState::starting ||
           current == RideOperatingState::running ||
           current == RideOperatingState::stopping;
}

[[nodiscard]] inline bool passengers_boarded(const std::uint64_t instance_id) noexcept {
    const RideOperatingState current = state(instance_id);
    return current == RideOperatingState::starting ||
           current == RideOperatingState::running ||
           current == RideOperatingState::stopping ||
           current == RideOperatingState::unloading;
}

inline void erase_missing(const std::uint64_t instance_id) {
    g_rides.erase(instance_id);
}

inline void reset() {
    g_rides.clear();
}

}  // namespace ch::ride_runtime
