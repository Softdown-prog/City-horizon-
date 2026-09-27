#include "simulation_scheduler.h"

#include <algorithm>
#include <cmath>

namespace {

// A long OS stall, breakpoint or asset spike must not turn into a burst of
// dozens of mobile updates on the next rendered frame. Five ticks still allow
// the 15 Hz simulation to catch up by roughly a third of a second while
// keeping frame time bounded and input/rendering responsive.
constexpr std::uint32_t kMaxMobileCatchUpTicksPerFrame = 5;

}  // namespace

SimulationScheduler::SimulationScheduler(const float mobile_tick_hz) {
    const float valid_hz = std::clamp(mobile_tick_hz, 1.0F, 120.0F);
    mobile_tick_seconds_ = 1.0F / valid_hz;
}

SimulationScheduleAdvance SimulationScheduler::advance_frame(const float frame_seconds) {
    if (frame_seconds <= 0.0F) return {0, mobile_tick_seconds_};

    mobile_accumulator_ += frame_seconds;
    SimulationScheduleAdvance result{0, mobile_tick_seconds_};
    while (mobile_accumulator_ >= mobile_tick_seconds_ &&
           result.mobile_ticks < kMaxMobileCatchUpTicksPerFrame) {
        mobile_accumulator_ -= mobile_tick_seconds_;
        ++result.mobile_ticks;
    }

    // Drop only excessive historical backlog. Keeping at most one partial tick
    // prevents a permanent spiral-of-death after a hitch without changing the
    // normal fixed-step cadence during regular gameplay.
    if (mobile_accumulator_ >= mobile_tick_seconds_) {
        mobile_accumulator_ = std::fmod(mobile_accumulator_, mobile_tick_seconds_);
    }
    return result;
}

float SimulationScheduler::mobile_tick_hz() const {
    return 1.0F / mobile_tick_seconds_;
}

void SimulationScheduler::reset() {
    mobile_accumulator_ = 0.0F;
}
