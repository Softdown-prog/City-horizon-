#include "simulation_scheduler.h"

#include <algorithm>

SimulationScheduler::SimulationScheduler(const float mobile_tick_hz) {
    const float valid_hz = std::clamp(mobile_tick_hz, 1.0F, 120.0F);
    mobile_tick_seconds_ = 1.0F / valid_hz;
}

SimulationScheduleAdvance SimulationScheduler::advance_frame(const float frame_seconds) {
    if (frame_seconds <= 0.0F) return {0, mobile_tick_seconds_};

    mobile_accumulator_ += frame_seconds;
    SimulationScheduleAdvance result{0, mobile_tick_seconds_};
    while (mobile_accumulator_ >= mobile_tick_seconds_) {
        mobile_accumulator_ -= mobile_tick_seconds_;
        ++result.mobile_ticks;
    }
    return result;
}

float SimulationScheduler::mobile_tick_hz() const {
    return 1.0F / mobile_tick_seconds_;
}

void SimulationScheduler::reset() {
    mobile_accumulator_ = 0.0F;
}
