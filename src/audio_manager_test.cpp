#include "audio_manager.h"

#include <SDL3/SDL.h>

#include <cmath>
#include <cstdlib>
#include <filesystem>
#include <iostream>

namespace {

[[noreturn]] void fail(const char* message) {
    std::cerr << "audio manager test failed: " << message << '\n' << std::flush;
    std::quick_exit(1);
}

}  // namespace

int main(int argc, char* argv[]) {
    if (argc != 2) fail("expected the audio asset directory");

    (void)SDL_SetHint(SDL_HINT_AUDIO_DRIVER, "dummy");
    std::cerr << "audio_manager_test: init SDL audio\n" << std::flush;
    if (!SDL_Init(SDL_INIT_AUDIO)) fail(SDL_GetError());

    AudioManager audio;
    std::cerr << "audio_manager_test: initialize catalog\n" << std::flush;
    if (!audio.initialize(std::filesystem::path(argv[1]))) fail("valid audio catalog did not initialize");
    std::cerr << "audio_manager_test: catalog initialized\n" << std::flush;

    if (!audio.is_available() || audio.cached_effect_count() != 19U)
        fail("audio cache did not contain the expected 19 unique runtime OGG effects");
    if (std::fabs(audio.volume_settings().master - 1.0F) > 0.001F ||
        std::fabs(audio.volume_settings().effects - 0.8F) > 0.001F)
        fail("catalog volume settings were not applied");

    const SoundEvent events[] = {
        SoundEvent::ui_select, SoundEvent::ui_select, SoundEvent::ui_confirm,
        SoundEvent::building_place, SoundEvent::ui_error, SoundEvent::ui_back,
        SoundEvent::ui_close_panel, SoundEvent::ui_open_panel,
    };
    for (const SoundEvent event : events) {
        if (!audio.play(event)) fail("cached audio event could not be played");
    }
    std::cerr << "audio_manager_test: one-shots playing\n" << std::flush;

    if (!audio.set_looping(SoundEvent::ferris_wheel_running, true))
        fail("ferris wheel running audio could not start looping");
    if (!audio.set_ambience_loop(SoundEvent::weather_rain, true))
        fail("rain ambience could not start independently");
    if (!audio.play_weather_effect(SoundEvent::weather_thunder))
        fail("thunder priority event could not play while ordinary tracks were busy");
    if (!audio.set_ambience_loop(SoundEvent::weather_rain, false))
        fail("rain ambience could not stop");
    if (!audio.set_looping(SoundEvent::ferris_wheel_running, false))
        fail("ferris wheel running audio could not stop");

    std::cerr << "audio_manager_test: shutdown manager\n" << std::flush;
    audio.shutdown();
    if (audio.is_available()) fail("audio manager stayed available after shutdown");
    std::cerr << "audio_manager_test: manager stopped\n" << std::flush;

    if (audio.initialize(std::filesystem::path(argv[1]) / "missing_catalog"))
        fail("missing catalog unexpectedly initialized audio");

    SDL_QuitSubSystem(SDL_INIT_AUDIO);
    std::cerr << "audio_manager_test: complete\n" << std::flush;
    std::quick_exit(0);
}
