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

    // Compute due work in O(1). The previous loop executed once for every
    // accumulated simulation tick and could amplify a hitch into another hitch.
    const float due_float = std::floor(mobile_accumulator_ / mobile_tick_seconds_);
    const std::uint32_t due_ticks = due_float <= 0.0F
        ? 0U
        : static_cast<std::uint32_t>(std::min(
              due_float, static_cast<float>(kMaxMobileCatchUpTicksPerFrame)));

    mobile_accumulator_ -= static_cast<float>(due_ticks) * mobile_tick_seconds_;

    // Drop only excessive historical backlog. Keeping one partial tick retains
    // the normal fixed-step cadence while preventing a spiral-of-death after a
    // debugger pause, window stall or unusually expensive render frame.
    if (mobile_accumulator_ >= mobile_tick_seconds_) {
        mobile_accumulator_ = std::fmod(mobile_accumulator_, mobile_tick_seconds_);
    }

    return {due_ticks, mobile_tick_seconds_};
}

float SimulationScheduler::mobile_tick_hz() const {
    return 1.0F / mobile_tick_seconds_;
}

void SimulationScheduler::reset() {
    mobile_accumulator_ = 0.0F;
}
