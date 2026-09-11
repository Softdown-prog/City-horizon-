#pragma once

#include <cstdint>
#include <vector>

enum class SimulationSpeed : std::uint8_t {
    paused = 0,
    speed1,
    speed2,
    speed3,
};

struct GameDate {
    int day = 1;
    int month = 1;
    int year = 1;
};

struct SimulationAdvance {
    int days_advanced = 0;
    // A date identifies the final day of every month that closed while time
    // advanced. More than one close can be processed after a long frame.
    std::vector<GameDate> closed_months;
};

class SimulationClock {
public:
    explicit SimulationClock(double seconds_per_game_day = 0.75);

    [[nodiscard]] const GameDate& date() const;
    [[nodiscard]] SimulationSpeed speed() const;
    [[nodiscard]] double seconds_per_game_day() const;

    void set_speed(SimulationSpeed speed);
    void toggle_pause();
    [[nodiscard]] bool restore_state(GameDate date, SimulationSpeed speed);
    [[nodiscard]] SimulationAdvance advance_seconds(double real_seconds);

private:
    void advance_one_day(SimulationAdvance& result);
    [[nodiscard]] static double speed_multiplier(SimulationSpeed speed);

    GameDate date_;
    SimulationSpeed speed_ = SimulationSpeed::speed1;
    double seconds_per_game_day_ = 0.75;
    double accumulated_seconds_ = 0.0;
};

[[nodiscard]] const char* simulation_speed_label(SimulationSpeed speed);
