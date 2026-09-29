#pragma once

#include <SDL3/SDL.h>

#include "weather_system.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <string_view>

struct ChRuntimeVideoCaptureConfig {
    bool enabled = false;
    bool ready = false;
    bool hide_ui = false;
    bool force_running = true;
    int fps = 30;
    int frame_limit = 120;
    int captured_frames = 0;
    std::uint64_t timeline_frame = 0;
    Uint64 base_ticks = 0;
    std::filesystem::path output_dir;
    std::string weather = "sunny";
};

[[nodiscard]] inline ChRuntimeVideoCaptureConfig& ch_runtime_video_capture_config() {
    static ChRuntimeVideoCaptureConfig config;
    return config;
}

[[nodiscard]] inline bool ch_runtime_video_capture_enabled() {
    return ch_runtime_video_capture_config().enabled;
}

[[nodiscard]] inline bool ch_runtime_video_capture_hide_ui() {
    const auto& config = ch_runtime_video_capture_config();
    return config.enabled && config.hide_ui;
}

[[nodiscard]] inline bool ch_runtime_video_capture_force_running() {
    const auto& config = ch_runtime_video_capture_config();
    return config.enabled && config.force_running;
}

inline bool ch_runtime_video_capture_parse_int(const char* text, int* value) {
    if (text == nullptr || value == nullptr) return false;
    try {
        const std::string input{text};
        std::size_t consumed = 0;
        const int parsed = std::stoi(input, &consumed);
        if (consumed != input.size()) return false;
        *value = parsed;
        return true;
    } catch (...) {
        return false;
    }
}

inline bool ch_runtime_video_capture_configure(int argc, char** argv) {
    auto& config = ch_runtime_video_capture_config();
    config = {};

    for (int i = 1; i < argc; ++i) {
        const std::string_view arg{argv[i]};
        const auto require_value = [&](const char* option) -> const char* {
            if (i + 1 >= argc) {
                std::cerr << option << " requires a value\n";
                return nullptr;
            }
            return argv[++i];
        };

        if (arg == "--validation-capture-dir") {
            const char* value = require_value("--validation-capture-dir");
            if (value == nullptr) return false;
            config.output_dir = std::filesystem::path{value};
            config.enabled = true;
        } else if (arg == "--validation-frames") {
            const char* value = require_value("--validation-frames");
            int parsed = 0;
            if (value == nullptr || !ch_runtime_video_capture_parse_int(value, &parsed) || parsed < 2 || parsed > 36000) {
                std::cerr << "--validation-frames must be between 2 and 36000\n";
                return false;
            }
            config.frame_limit = parsed;
        } else if (arg == "--validation-fps") {
            const char* value = require_value("--validation-fps");
            int parsed = 0;
            if (value == nullptr || !ch_runtime_video_capture_parse_int(value, &parsed) || parsed < 1 || parsed > 120) {
                std::cerr << "--validation-fps must be between 1 and 120\n";
                return false;
            }
            config.fps = parsed;
        } else if (arg == "--validation-hide-ui") {
            config.hide_ui = true;
        } else if (arg == "--validation-show-ui") {
            config.hide_ui = false;
        } else if (arg == "--validation-paused") {
            config.force_running = false;
        } else if (arg == "--validation-weather") {
            const char* value = require_value("--validation-weather");
            if (value == nullptr) return false;
            config.weather = value;
            if (config.weather != "sunny" && config.weather != "overcast" &&
                config.weather != "rain" && config.weather != "raining" &&
                config.weather != "thunder" && config.weather != "thunderstorm") {
                std::cerr << "--validation-weather expects sunny, overcast, rain, or thunderstorm\n";
                return false;
            }
        }
    }

    if (!config.enabled) return true;
    if (config.output_dir.empty()) {
        std::cerr << "validation capture requires a non-empty output directory\n";
        return false;
    }

    std::error_code error;
    std::filesystem::create_directories(config.output_dir, error);
    if (error) {
        std::cerr << "unable to create validation capture directory: " << error.message() << '\n';
        return false;
    }

    std::cout << "CH_RUNTIME_VIDEO_CAPTURE_V1 enabled"
              << " fps=" << config.fps
              << " frames=" << config.frame_limit
              << " hideUi=" << (config.hide_ui ? "true" : "false")
              << " weather=" << config.weather << '\n';
    return true;
}

inline void ch_runtime_video_capture_mark_ready() {
    auto& config = ch_runtime_video_capture_config();
    if (!config.enabled || config.ready) return;
    config.ready = true;
    // The last pre-loop SDL_GetTicks call observes base_ticks. Starting the
    // runtime timeline at frame one makes the first simulation delta exactly
    // one fixed frame instead of zero seconds.
    config.timeline_frame = 1;
}

[[nodiscard]] inline Uint64 ch_runtime_video_capture_ticks() {
    auto& config = ch_runtime_video_capture_config();
    if (!config.enabled) return SDL_GetTicks();
    if (config.base_ticks == 0) config.base_ticks = SDL_GetTicks();
    if (!config.ready) return config.base_ticks;
    const double elapsed_ms = static_cast<double>(config.timeline_frame) * 1000.0 /
                              static_cast<double>(config.fps);
    return config.base_ticks + static_cast<Uint64>(std::llround(elapsed_ms));
}

[[nodiscard]] inline const bool* ch_runtime_video_capture_keyboard_state(int* count) {
    if (!ch_runtime_video_capture_enabled()) return SDL_GetKeyboardState(count);
    static const std::array<bool, SDL_SCANCODE_COUNT> empty{};
    if (count != nullptr) *count = static_cast<int>(empty.size());
    return empty.data();
}

[[nodiscard]] inline SDL_MouseButtonFlags ch_runtime_video_capture_mouse_state(float* x, float* y) {
    if (!ch_runtime_video_capture_enabled()) return SDL_GetMouseState(x, y);
    // Runtime capture uses the default 1280x800 viewport. A centred pointer
    // prevents edge-pan and hover-driven camera changes from contaminating a
    // deterministic sequence.
    if (x != nullptr) *x = 640.0F;
    if (y != nullptr) *y = 400.0F;
    return 0;
}

[[nodiscard]] inline SDL_Window* ch_runtime_video_capture_create_window(
    const char* title, int width, int height, SDL_WindowFlags flags) {
    if (ch_runtime_video_capture_enabled()) flags |= SDL_WINDOW_HIDDEN;
    return SDL_CreateWindow(title, width, height, flags);
}

inline bool ch_runtime_video_capture_set_vsync(SDL_Renderer* renderer, int vsync) {
    return SDL_SetRenderVSync(renderer, ch_runtime_video_capture_enabled() ? 0 : vsync);
}

inline void ch_runtime_video_capture_write_report() {
    const auto& config = ch_runtime_video_capture_config();
    if (!config.enabled) return;
    const std::filesystem::path report_path = config.output_dir / "runtime_capture_report.json";
    std::ofstream report(report_path, std::ios::binary | std::ios::trunc);
    if (!report) return;
    report << "{\n"
           << "  \"contract\": \"CH_RUNTIME_FRAME_CAPTURE_V1\",\n"
           << "  \"status\": \"ok\",\n"
           << "  \"fps\": " << config.fps << ",\n"
           << "  \"frameCount\": " << config.captured_frames << ",\n"
           << "  \"hideUi\": " << (config.hide_ui ? "true" : "false") << ",\n"
           << "  \"forceRunning\": " << (config.force_running ? "true" : "false") << ",\n"
           << "  \"weather\": \"" << config.weather << "\",\n"
           << "  \"framePattern\": \"frame_%06d.png\"\n"
           << "}\n";
}

inline bool ch_runtime_video_capture_present(SDL_Renderer* renderer) {
    auto& config = ch_runtime_video_capture_config();
    if (config.enabled && config.ready && config.captured_frames < config.frame_limit) {
        SDL_Surface* surface = SDL_RenderReadPixels(renderer, nullptr);
        if (surface == nullptr) {
            std::cerr << "validation capture readback failed: " << SDL_GetError() << '\n';
        } else {
            std::ostringstream name;
            name << "frame_" << std::setw(6) << std::setfill('0') << config.captured_frames << ".png";
            const std::filesystem::path output = config.output_dir / name.str();
            if (!SDL_SavePNG(surface, output.string().c_str())) {
                std::cerr << "validation capture PNG write failed: " << SDL_GetError() << '\n';
            } else {
                ++config.captured_frames;
            }
            SDL_DestroySurface(surface);
        }
    }

    const bool presented = SDL_RenderPresent(renderer);

    if (config.enabled && config.ready) {
        ++config.timeline_frame;
        if (config.captured_frames >= config.frame_limit) {
            ch_runtime_video_capture_write_report();
            SDL_Event quit{};
            quit.type = SDL_EVENT_QUIT;
            (void)SDL_PushEvent(&quit);
        }
    }
    return presented;
}

class ChCaptureWeatherSystem : public WeatherSystem {
public:
    explicit ChCaptureWeatherSystem(std::uint32_t seed = 0xC17A2026U)
        : WeatherSystem(seed) {
        const auto& config = ch_runtime_video_capture_config();
        if (config.enabled) {
            if (config.weather == "overcast") set_state(WeatherState::overcast);
            else if (config.weather == "rain" || config.weather == "raining") set_state(WeatherState::raining);
            else if (config.weather == "thunder" || config.weather == "thunderstorm") set_state(WeatherState::thunderstorm);
            else set_state(WeatherState::sunny);
        }
        ch_runtime_video_capture_mark_ready();
    }
};
