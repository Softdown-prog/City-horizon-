#include "audio_manager.h"

#include <SDL3/SDL.h>

#include <cmath>
#include <filesystem>
#include <iostream>

int main(int argc, char* argv[]) {
    if (argc != 2) {
        std::cerr << "Expected the audio asset directory.\n";
        return 1;
    }

    // A real decoder/mixer test that does not require speakers or a sound card.
    (void)SDL_SetHint(SDL_HINT_AUDIO_DRIVER, "dummy");
    AudioManager audio;
    if (!audio.initialize(std::filesystem::path(argv[1]))) {
        std::cerr << "The valid audio catalog did not initialize.\n";
        return 1;
    }
    if (!audio.is_available() || audio.cached_effect_count() != 15U) {
        std::cerr << "Audio cache did not contain the expected 15 unique OGG effects.\n";
        return 1;
    }
    if (std::fabs(audio.volume_settings().master - 1.0F) > 0.001F ||
        std::fabs(audio.volume_settings().effects - 0.8F) > 0.001F) {
        std::cerr << "Catalog volume settings were not applied.\n";
        return 1;
    }

    // Eight tracks are allocated for overlapping UI feedback. This sequence also
    // exercises both variations for events that have them.
    const SoundEvent events[] = {
        SoundEvent::ui_select, SoundEvent::ui_select, SoundEvent::ui_confirm,
        SoundEvent::building_place, SoundEvent::ui_error, SoundEvent::ui_back,
        SoundEvent::ui_close_panel, SoundEvent::ui_open_panel,
    };
    for (const SoundEvent event : events) {
        if (!audio.play(event)) {
            std::cerr << "A cached audio event could not be played.\n";
            return 1;
        }
    }

    audio.shutdown();
    if (audio.is_available()) {
        return 1;
    }

    // Missing catalogs must fail locally instead of making the game depend on audio.
    if (audio.initialize(std::filesystem::path(argv[1]) / "missing_catalog")) {
        std::cerr << "A missing catalog unexpectedly initialized audio.\n";
        return 1;
    }
    return 0;
}
