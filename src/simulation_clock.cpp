#include "simulation_clock.h"

#include <algorithm>

namespace {

constexpr int kDaysPerMonth = 30;
constexpr int kMonthsPerYear = 12;

}  // namespace

SimulationClock::SimulationClock(const double seconds_per_game_day)
    : seconds_per_game_day_(std::max(0.001, seconds_per_game_day)) {}

const GameDate& SimulationClock::date() const {
    return date_;
}

SimulationSpeed SimulationClock::speed() const {
    return speed_;
}

double SimulationClock::seconds_per_game_day() const {
    return seconds_per_game_day_;
}

void SimulationClock::set_speed(const SimulationSpeed speed) {
    speed_ = speed;
}

void SimulationClock::toggle_pause() {
    speed_ = speed_ == SimulationSpeed::paused ? SimulationSpeed::speed1 : SimulationSpeed::paused;
}

bool SimulationClock::restore_state(const GameDate date, const SimulationSpeed speed) {
    if (date.day < 1 || date.day > 30 || date.month < 1 || date.month > 12 || date.year < 1 ||
        static_cast<std::uint8_t>(speed) > static_cast<std::uint8_t>(SimulationSpeed::speed3)) {
        return false;
    }
    date_ = date;
    speed_ = speed;
    accumulated_seconds_ = 0.0;
    return true;
}

SimulationAdvance SimulationClock::advance_seconds(const double real_seconds) {
    SimulationAdvance result;
    if (real_seconds <= 0.0 || speed_ == SimulationSpeed::paused) {
        return result;
    }

    accumulated_seconds_ += real_seconds * speed_multiplier(speed_);
    while (accumulated_seconds_ >= seconds_per_game_day_) {
        accumulated_seconds_ -= seconds_per_game_day_;
        advance_one_day(result);
    }
    return result;
}

void SimulationClock::advance_one_day(SimulationAdvance& result) {
    ++date_.day;
    ++result.days_advanced;
    if (date_.day <= kDaysPerMonth) {
        return;
    }

    date_.day = 1;
    result.closed_months.push_back({kDaysPerMonth, date_.month, date_.year});
    ++date_.month;
    if (date_.month > kMonthsPerYear) {
        date_.month = 1;
        ++date_.year;
    }
}

double SimulationClock::speed_multiplier(const SimulationSpeed speed) {
    switch (speed) {
        case SimulationSpeed::paused: return 0.0;
        case SimulationSpeed::speed1: return 1.0;
        case SimulationSpeed::speed2: return 4.0;
        case SimulationSpeed::speed3: return 12.0;
    }
    return 1.0;
}

const char* simulation_speed_label(const SimulationSpeed speed) {
    switch (speed) {
        case SimulationSpeed::paused: return "PAUSED";
        case SimulationSpeed::speed1: return "SPEED 1";
        case SimulationSpeed::speed2: return "SPEED 2";
        case SimulationSpeed::speed3: return "SPEED 3";
    }
    return "SPEED ?";
}
