#include "weather_system.h"

#include <algorithm>

WeatherSystem::WeatherSystem(const std::uint32_t seed) : random_state_(seed == 0 ? 1U : seed) {
    drops_.resize(300);
}

float WeatherSystem::random_unit() {
    random_state_ ^= random_state_ << 13U;
    random_state_ ^= random_state_ >> 17U;
    random_state_ ^= random_state_ << 5U;
    return static_cast<float>(random_state_ & 0x00ffffffU) / 16777216.0F;
}

void WeatherSystem::reset_drop(RainDrop& drop, const bool anywhere) {
    drop.length = 8.0F + random_unit() * 8.0F;
    drop.speed = 370.0F + random_unit() * 160.0F;
    // Horizontal drift is to the left. Starting outside the right edge keeps
    // density uniform across the viewport instead of emptying that edge.
    drop.x = random_unit() * static_cast<float>(width_ + 90);
    drop.y = anywhere ? random_unit() * static_cast<float>(height_) : -drop.length;
}

void WeatherSystem::set_state(const WeatherState state) {
    if (state_ == state) return;
    const bool was_raining = is_raining();
    const bool will_rain = state == WeatherState::raining || state == WeatherState::thunderstorm;
    state_ = state;
    flash_alpha_ = 0;
    thunder_timer_ = 5.0F + random_unit() * 7.0F;

    if (!was_raining && will_rain) {
        rain_episode_remaining_seconds_ = 50.0F + random_unit() * 10.0F;
    } else if (!will_rain) {
        rain_episode_remaining_seconds_ = 0.0F;
    }

    if (will_rain && width_ > 0 && height_ > 0) {
        for (RainDrop& drop : drops_) reset_drop(drop, true);
    }
}

void WeatherSystem::cycle_state() {
    set_state(static_cast<WeatherState>((static_cast<unsigned>(state_) + 1U) % 4U));
}

const char* WeatherSystem::state_name() const {
    switch (state_) {
        case WeatherState::sunny: return "SUNNY";
        case WeatherState::overcast: return "OVERCAST";
        case WeatherState::raining: return "RAINING";
        case WeatherState::thunderstorm: return "THUNDERSTORM";
    }
    return "SUNNY";
}

std::uint8_t WeatherSystem::tint_alpha() const {
    switch (state_) {
        case WeatherState::sunny: return 0;
        case WeatherState::overcast: return 25;
        case WeatherState::raining: return 48;
        case WeatherState::thunderstorm: return 68;
    }
    return 0;
}

void WeatherSystem::update(const float seconds, const int width, const int height) {
    if (width <= 0 || height <= 0) return;
    if (width != width_ || height != height_) {
        width_ = width;
        height_ = height;
        for (RainDrop& drop : drops_) reset_drop(drop, true);
    }
    flash_alpha_ = 0;
    if (!is_raining()) return;

    // Rain duration follows real elapsed time rather than simulation speed.
    // Clamp only extreme stalls so a debugger pause cannot instantly consume
    // an entire weather episode.
    const float weather_dt = std::clamp(seconds, 0.0F, 0.25F);
    rain_episode_remaining_seconds_ = std::max(0.0F, rain_episode_remaining_seconds_ - weather_dt);
    if (rain_episode_remaining_seconds_ <= 0.0F) {
        set_state(WeatherState::overcast);
        return;
    }

    // Stall clamping avoids a jump across the entire screen after a breakpoint.
    const float dt = std::clamp(seconds, 0.0F, 0.05F);
    const std::size_t count = state_ == WeatherState::thunderstorm ? drops_.size() : 180U;
    for (std::size_t i = 0; i < count; ++i) {
        RainDrop& drop = drops_[i];
        drop.y += drop.speed * dt;
        drop.x -= drop.speed * 0.18F * dt;
        if (drop.y > static_cast<float>(height_) + drop.length || drop.x < -drop.length) {
            reset_drop(drop, false);
        }
    }
    if (state_ == WeatherState::thunderstorm && dt > 0.0F) {
        thunder_timer_ -= dt;
        if (thunder_timer_ <= 0.0F) {
            flash_alpha_ = 95;
            thunder_timer_ = 6.0F + random_unit() * 9.0F;
        }
    }
}
