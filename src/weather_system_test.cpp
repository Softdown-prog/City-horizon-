#include "weather_system.h"

#include <cassert>
#include <cmath>

int main() {
    WeatherSystem weather(123U);
    assert(weather.state() == WeatherState::sunny);
    assert(weather.tint_alpha() == 0);
    weather.update(1.0F / 60.0F, 320, 200);
    weather.cycle_state();
    assert(weather.state() == WeatherState::overcast && !weather.is_raining());
    weather.cycle_state();
    assert(weather.state() == WeatherState::raining && weather.is_raining());
    assert(weather.drops().size() == 300);
    for (int i = 0; i < 2400; ++i) {
        weather.update(1.0F / 60.0F, i < 1200 ? 320 : 480, 200);
        for (const RainDrop& drop : weather.drops()) {
            assert(std::isfinite(drop.x) && std::isfinite(drop.y));
            assert(drop.x >= -drop.length && drop.x <= 570.0F);
            assert(drop.y >= -drop.length && drop.y <= 216.0F);
        }
    }
    weather.cycle_state();
    assert(weather.state() == WeatherState::thunderstorm);
    bool flashed = false;
    for (int i = 0; i < 1000; ++i) {
        weather.update(1.0F / 60.0F, 480, 200);
        flashed |= weather.flash_alpha() != 0;
    }
    assert(flashed);
    weather.cycle_state();
    assert(weather.state() == WeatherState::sunny && weather.flash_alpha() == 0);
}
