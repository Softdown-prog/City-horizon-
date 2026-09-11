#include "audio_manager.h"

#include <SDL3/SDL.h>
#include <SDL3_mixer/SDL_mixer.h>

#include <algorithm>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <iterator>
#include <string_view>
#include <unordered_map>

namespace {

constexpr std::size_t event_index(const SoundEvent event) {
    return static_cast<std::size_t>(event);
}

constexpr std::array<std::string_view, static_cast<std::size_t>(SoundEvent::count)> kEventNames = {
    "UiClick", "UiSelect", "UiBack", "UiOpenPanel", "UiClosePanel", "UiConfirm",
    "UiError", "BuildingPlace", "UiToggle", "UiScroll", "Notification",
};

[[nodiscard]] std::string read_text_file(const std::filesystem::path& path) {
    std::ifstream input(path, std::ios::binary);
    if (!input) {
        return {};
    }
    return {std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
}

[[nodiscard]] std::string_view object_for_key(const std::string& json, std::string_view key) {
    const std::size_t key_position = json.find('"' + std::string(key) + '"');
    if (key_position == std::string::npos) {
        return {};
    }
    const std::size_t open = json.find('{', key_position);
    if (open == std::string::npos) {
        return {};
    }
    int depth = 0;
    for (std::size_t index = open; index < json.size(); ++index) {
        if (json[index] == '{') {
            ++depth;
        } else if (json[index] == '}' && --depth == 0) {
            return std::string_view(json).substr(open + 1, index - open - 1);
        }
    }
    return {};
}

[[nodiscard]] std::vector<std::string> string_array_for_key(const std::string_view json, const std::string_view key) {
    const std::size_t key_position = json.find('"' + std::string(key) + '"');
    if (key_position == std::string_view::npos) {
        return {};
    }
    const std::size_t open = json.find('[', key_position);
    const std::size_t close = open == std::string_view::npos ? std::string_view::npos : json.find(']', open);
    if (close == std::string_view::npos) {
        return {};
    }

    std::vector<std::string> values;
    for (std::size_t cursor = open + 1; cursor < close;) {
        const std::size_t first_quote = json.find('"', cursor);
        if (first_quote == std::string_view::npos || first_quote >= close) {
            break;
        }
        const std::size_t second_quote = json.find('"', first_quote + 1);
        if (second_quote == std::string_view::npos || second_quote > close) {
            return {};
        }
        values.emplace_back(json.substr(first_quote + 1, second_quote - first_quote - 1));
        cursor = second_quote + 1;
    }
    return values;
}

[[nodiscard]] bool number_for_key(const std::string& json, const std::string_view key, float& value) {
    const std::size_t key_position = json.find('"' + std::string(key) + '"');
    if (key_position == std::string::npos) {
        return false;
    }
    const std::size_t colon = json.find(':', key_position);
    if (colon == std::string::npos) {
        return false;
    }
    char* end = nullptr;
    const float parsed = std::strtof(json.c_str() + colon + 1, &end);
    if (end == json.c_str() + colon + 1) {
        return false;
    }
    value = parsed;
    return true;
}

}  // namespace

AudioManager::~AudioManager() {
    shutdown();
}

bool AudioManager::initialize(const std::filesystem::path& audio_directory) {
    shutdown();
    last_variation_.fill(-1);

    std::array<std::vector<std::string>, kEventCount> paths;
    if (!load_catalog(audio_directory / "audio_catalog.json", paths)) {
        std::cerr << "Audio disabled: invalid or unreadable catalog at " << (audio_directory / "audio_catalog.json") << '\n';
        return false;
    }

    if (!MIX_Init()) {
        std::cerr << "Audio disabled: SDL_mixer initialization failed: " << SDL_GetError() << '\n';
        return false;
    }
    mixer_initialized_ = true;

    mixer_ = MIX_CreateMixerDevice(SDL_AUDIO_DEVICE_DEFAULT_PLAYBACK, nullptr);
    if (mixer_ == nullptr) {
        std::cerr << "Audio disabled: could not open the default playback device: " << SDL_GetError() << '\n';
        shutdown();
        return false;
    }

    std::unordered_map<std::string, MIX_Audio*> decoded_cache;
    for (std::size_t event = 0; event < kEventCount; ++event) {
        for (const std::string& relative_path : paths[event]) {
            const std::filesystem::path full_path = audio_directory / relative_path;
            const std::string key = full_path.lexically_normal().generic_string();
            MIX_Audio* audio = nullptr;
            if (const auto cached = decoded_cache.find(key); cached != decoded_cache.end()) {
                audio = cached->second;
            } else if (!std::filesystem::is_regular_file(full_path)) {
                std::cerr << "Audio asset missing for " << kEventNames[event] << ": " << full_path << '\n';
            } else {
                audio = MIX_LoadAudio(mixer_, full_path.string().c_str(), true);
                if (audio == nullptr) {
                    std::cerr << "Audio asset could not be decoded for " << kEventNames[event] << ": " << full_path
                              << "\nSDL error: " << SDL_GetError() << '\n';
                } else {
                    decoded_cache.emplace(key, audio);
                    cached_audio_.push_back(audio);
                }
            }
            if (audio != nullptr) {
                effects_[event].push_back(audio);
            }
        }
    }

    constexpr int kEffectTrackCount = 8;
    for (int index = 0; index < kEffectTrackCount; ++index) {
        if (MIX_Track* track = MIX_CreateTrack(mixer_)) {
            tracks_.push_back(track);
        } else {
            std::cerr << "Audio track " << index << " could not be created: " << SDL_GetError() << '\n';
        }
    }

    if (cached_audio_.empty() || tracks_.empty()) {
        std::cerr << "Audio disabled: no usable cached effects or playback tracks.\n";
        shutdown();
        return false;
    }

    apply_volume_settings();
    available_ = true;
    std::cout << "Audio initialized: " << cached_audio_.size() << " cached effect(s), "
              << tracks_.size() << " playback track(s).\n";
    return true;
}

void AudioManager::shutdown() {
    available_ = false;
    for (MIX_Track* track : tracks_) {
        MIX_DestroyTrack(track);
    }
    tracks_.clear();

    for (MIX_Audio* audio : cached_audio_) {
        MIX_DestroyAudio(audio);
    }
    cached_audio_.clear();
    for (auto& event_effects : effects_) {
        event_effects.clear();
    }

    if (mixer_ != nullptr) {
        MIX_DestroyMixer(mixer_);
        mixer_ = nullptr;
    }
    if (mixer_initialized_) {
        MIX_Quit();
        mixer_initialized_ = false;
    }
}

bool AudioManager::play(const SoundEvent event) {
    if (!available_) {
        return false;
    }
    const std::size_t index = event_index(event);
    if (index >= kEventCount || effects_[index].empty()) {
        return false;
    }

    MIX_Track* available_track = nullptr;
    for (MIX_Track* track : tracks_) {
        if (!MIX_TrackPlaying(track)) {
            available_track = track;
            break;
        }
    }
    if (available_track == nullptr) {
        std::cerr << "Audio event skipped (all effect tracks busy): " << kEventNames[index] << '\n';
        return false;
    }

    int variation = last_variation_[index] + 1;
    if (variation >= static_cast<int>(effects_[index].size())) {
        variation = 0;
    }
    last_variation_[index] = variation;

    if (!MIX_SetTrackAudio(available_track, effects_[index][static_cast<std::size_t>(variation)]) ||
        !MIX_PlayTrack(available_track, 0)) {
        std::cerr << "Audio event could not play: " << kEventNames[index] << "\nSDL error: " << SDL_GetError() << '\n';
        return false;
    }
    return true;
}

void AudioManager::set_volume_settings(AudioVolumeSettings settings) {
    settings.master = std::clamp(settings.master, 0.0F, 1.0F);
    settings.effects = std::clamp(settings.effects, 0.0F, 1.0F);
    settings.music = std::clamp(settings.music, 0.0F, 1.0F);
    settings.ambience = std::clamp(settings.ambience, 0.0F, 1.0F);
    volume_settings_ = settings;
    if (mixer_ != nullptr) {
        apply_volume_settings();
    }
}

const AudioVolumeSettings& AudioManager::volume_settings() const {
    return volume_settings_;
}

bool AudioManager::is_available() const {
    return available_;
}

std::size_t AudioManager::cached_effect_count() const {
    return cached_audio_.size();
}

bool AudioManager::load_catalog(const std::filesystem::path& catalog_path,
                                std::array<std::vector<std::string>, kEventCount>& paths) {
    const std::string json = read_text_file(catalog_path);
    if (json.empty()) {
        return false;
    }

    float master_volume = volume_settings_.master;
    float effects_volume = volume_settings_.effects;
    if (!number_for_key(json, "masterVolume", master_volume) || !number_for_key(json, "effectsVolume", effects_volume)) {
        return false;
    }
    const std::string_view events_object = object_for_key(json, "events");
    if (events_object.empty()) {
        return false;
    }
    for (std::size_t event = 0; event < kEventCount; ++event) {
        paths[event] = string_array_for_key(events_object, kEventNames[event]);
    }

    AudioVolumeSettings catalog_settings = volume_settings_;
    catalog_settings.master = master_volume;
    catalog_settings.effects = effects_volume;
    set_volume_settings(catalog_settings);
    return true;
}

void AudioManager::apply_volume_settings() {
    if (mixer_ != nullptr && !MIX_SetMixerGain(mixer_, volume_settings_.master)) {
        std::cerr << "Could not apply master volume: " << SDL_GetError() << '\n';
    }
    for (MIX_Track* track : tracks_) {
        if (!MIX_SetTrackGain(track, volume_settings_.effects)) {
            std::cerr << "Could not apply effects volume: " << SDL_GetError() << '\n';
        }
    }
}
