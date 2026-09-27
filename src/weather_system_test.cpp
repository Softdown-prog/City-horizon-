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
    assert(weather.rain_episode_remaining_seconds() >= 50.0F);
    assert(weather.rain_episode_remaining_seconds() <= 60.0F);
    assert(weather.drops().size() == 300);

    for (int i = 0; i < 2400; ++i) {
        weather.update(1.0F / 60.0F, i < 1200 ? 320 : 480, 200);
        for (const RainDrop& drop : weather.drops()) {
            assert(std::isfinite(drop.x) && std::isfinite(drop.y));
            assert(drop.x >= -drop.length && drop.x <= 570.0F);
            assert(drop.y >= -drop.length && drop.y <= 216.0F);
        }
    }
    assert(weather.is_raining());

    // Start a fresh thunderstorm episode so the thunder timer always has the
    // full 50-60 second weather window available for at least one flash.
    weather.set_state(WeatherState::sunny);
    weather.set_state(WeatherState::thunderstorm);
    bool flashed = false;
    for (int i = 0; i < 1200; ++i) {
        weather.update(1.0F / 60.0F, 480, 200);
        flashed |= weather.flash_alpha() != 0;
    }
    assert(flashed);

    // Rain ends automatically after at most one minute and leaves the darker
    // overcast state rather than snapping directly to full sun.
    for (int i = 0; i < 3000 && weather.is_raining(); ++i) {
        weather.update(1.0F / 60.0F, 480, 200);
    }
    assert(weather.state() == WeatherState::overcast);
    assert(weather.rain_episode_remaining_seconds() == 0.0F);
}
