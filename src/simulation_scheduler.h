#pragma once

#include <cstdint>

// Keeps the game loop small while making the cadence of non-render work
// explicit. Frame work remains responsive; mobile simulation uses a stable,
// lower-frequency tick.
struct SimulationScheduleAdvance {
    std::uint32_t mobile_ticks = 0;
    float mobile_tick_seconds = 0.0F;
};

class SimulationScheduler {
public:
    explicit SimulationScheduler(float mobile_tick_hz = 15.0F);

    [[nodiscard]] SimulationScheduleAdvance advance_frame(float frame_seconds);
    [[nodiscard]] float mobile_tick_hz() const;
    void reset();

private:
    float mobile_tick_seconds_ = 1.0F / 15.0F;
    float mobile_accumulator_ = 0.0F;
};
