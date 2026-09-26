#pragma once

#include <array>
#include <cstddef>
#include <filesystem>
#include <string>
#include <vector>

struct MIX_Audio;
struct MIX_Mixer;
struct MIX_Track;

// Gameplay refers to these stable logical events, never to a physical file.
enum class SoundEvent : std::size_t {
    ui_click,
    ui_select,
    ui_back,
    ui_open_panel,
    ui_close_panel,
    ui_confirm,
    ui_error,
    building_place,
    ui_toggle,
    ui_scroll,
    notification,
    count,
};

struct AudioVolumeSettings {
    float master = 1.0F;
    float effects = 1.0F;
    float music = 1.0F;
    // Ambience has no runtime source yet.
    float ambience = 1.0F;
};

class AudioManager {
public:
    AudioManager() = default;
    ~AudioManager();

    AudioManager(const AudioManager&) = delete;
    AudioManager& operator=(const AudioManager&) = delete;

    // The directory must contain audio_catalog.json and the relative asset paths it lists.
    [[nodiscard]] bool initialize(const std::filesystem::path& audio_directory);
    void shutdown();

    // Returns false when audio is unavailable or that event has no loaded variation.
    [[nodiscard]] bool play(SoundEvent event);
    // Starts the music declared under music.Loading in audio_catalog.json.
    [[nodiscard]] bool play_loading_music();

    void set_volume_settings(AudioVolumeSettings settings);
    [[nodiscard]] const AudioVolumeSettings& volume_settings() const;
    [[nodiscard]] bool is_available() const;
    [[nodiscard]] std::size_t cached_effect_count() const;

private:
    static constexpr std::size_t kEventCount = static_cast<std::size_t>(SoundEvent::count);

    [[nodiscard]] bool load_catalog(const std::filesystem::path& catalog_path,
                                    std::array<std::vector<std::string>, kEventCount>& paths);
    void apply_volume_settings();

    MIX_Mixer* mixer_ = nullptr;
    std::array<std::vector<MIX_Audio*>, kEventCount> effects_;
    std::array<int, kEventCount> last_variation_{};
    std::vector<MIX_Audio*> cached_audio_;
    std::vector<MIX_Track*> tracks_;
    MIX_Audio* loading_music_ = nullptr;
    MIX_Track* music_track_ = nullptr;
    AudioVolumeSettings volume_settings_;
    bool mixer_initialized_ = false;
    bool available_ = false;
};
