#pragma once

#include <cstdint>
#include <vector>

enum class WeatherState : std::uint8_t { sunny, overcast, raining, thunderstorm };

struct RainDrop {
    float x = 0.0F;
    float y = 0.0F;
    float speed = 0.0F;
    float length = 0.0F;
};

// Screen-space weather. Coordinates are viewport pixels, independent of the
// isometric camera, world tiles and simulation speed.
class WeatherSystem {
public:
    explicit WeatherSystem(std::uint32_t seed = 0xC17A2026U);
    void set_state(WeatherState state);
    void cycle_state();
    void update(float seconds, int width, int height);

    [[nodiscard]] WeatherState state() const { return state_; }
    [[nodiscard]] bool is_raining() const {
        return state_ == WeatherState::raining || state_ == WeatherState::thunderstorm;
    }
    [[nodiscard]] const char* state_name() const;
    [[nodiscard]] std::uint8_t tint_alpha() const;
    [[nodiscard]] std::uint8_t flash_alpha() const { return flash_alpha_; }
    [[nodiscard]] const std::vector<RainDrop>& drops() const { return drops_; }

private:
    [[nodiscard]] float random_unit();
    void reset_drop(RainDrop& drop, bool anywhere);

    WeatherState state_ = WeatherState::sunny;
    std::uint32_t random_state_;
    int width_ = 0;
    int height_ = 0;
    float thunder_timer_ = 6.0F;
    std::uint8_t flash_alpha_ = 0;
    std::vector<RainDrop> drops_;
};
