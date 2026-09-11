#pragma once

#include "mobile_entity.h"

#include <cstddef>
#include <filesystem>
#include <string>
#include <string_view>
#include <vector>

// Immutable, shared animation data. Gameplay supplies a state and direction;
// this catalogue only resolves a clip and its current visual frame.
struct MobileAnimationClip {
    std::string id;
    std::string state;
    MobileEntityDirection direction = MobileEntityDirection::south;
    std::vector<std::string> frames;
    float frames_per_second = 1.0F;
    bool loop = true;
};

struct MobileAnimationFallback {
    std::string state;
    std::string fallback_state;
};

struct MobileAnimationSet {
    std::string id;
    std::vector<MobileAnimationClip> clips;
    std::vector<MobileAnimationFallback> fallbacks;
};

// Per-entity state. It holds no texture and no frame list, so all artwork data
// remains shared by the catalogue regardless of entity count.
struct MobileAnimationPlayer {
    std::string animation_set_id;
    std::string clip_id;
    std::size_t frame_index = 0;
    float accumulated_seconds = 0.0F;
};

class MobileAnimationCatalog {
public:
    [[nodiscard]] bool load_from_directory(const std::filesystem::path& directory);
    [[nodiscard]] const MobileAnimationSet* find_set(std::string_view id) const;
    [[nodiscard]] const MobileAnimationClip* resolve_clip(std::string_view set_id, std::string_view state,
                                                           MobileEntityDirection direction) const;
    [[nodiscard]] const MobileAnimationClip* find_clip(std::string_view set_id, std::string_view clip_id) const;
    [[nodiscard]] const std::string* current_frame(const MobileAnimationPlayer& player) const;
    [[nodiscard]] std::vector<std::string> frame_assets() const;

    // Frame time advances per render frame. It never changes game state,
    // position, direction or depth.
    void update_player(MobileAnimationPlayer& player, std::string_view state,
                       MobileEntityDirection direction, float frame_seconds) const;

private:
    [[nodiscard]] const MobileAnimationClip* find_clip(const MobileAnimationSet& set, std::string_view state,
                                                        MobileEntityDirection direction) const;
    [[nodiscard]] std::string_view fallback_for(const MobileAnimationSet& set, std::string_view state) const;
    std::vector<MobileAnimationSet> sets_;
};
