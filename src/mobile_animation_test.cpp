#include "mobile_animation.h"

#include <cassert>
#include <array>
#include <filesystem>

int main(int argc, char** argv) {
    assert(argc == 2);
    MobileAnimationCatalog catalog;
    assert(catalog.load_from_directory(std::filesystem::path(argv[1])));

    const std::array directions = {MobileEntityDirection::south, MobileEntityDirection::east,
                                   MobileEntityDirection::north, MobileEntityDirection::west};
    const std::array names = {"south", "east", "north", "west"};
    for (std::size_t index = 0; index < directions.size(); ++index) {
        const MobileAnimationClip* idle = catalog.resolve_clip("tractor_tillage_01", "idle", directions[index]);
        const MobileAnimationClip* moving = catalog.resolve_clip("tractor_tillage_01", "moving", directions[index]);
        assert(idle != nullptr && idle->id == "idle_" + std::string(names[index]) && idle->frames.size() == 1);
        assert(moving != nullptr && moving->id == "moving_" + std::string(names[index]) && moving->frames.size() == 1);
    }

    // Working has no separate artwork yet, so its data-declared fallback must
    // select the directional idle clip without ever yielding a missing frame.
    MobileAnimationPlayer player{.animation_set_id = "tractor_tillage_01"};
    catalog.update_player(player, "working", MobileEntityDirection::west, 0.25F);
    assert(player.clip_id == "idle_west" && player.frame_index == 0);
    assert(catalog.current_frame(player) != nullptr);

    catalog.update_player(player, "returning", MobileEntityDirection::north, 0.25F);
    assert(player.clip_id == "moving_north" && player.frame_index == 0);

    // The SE gait calibration changes only this per-player visual rate.  The
    // canonical clip stays at 8 FPS (125 ms), so 125/150 must hold frame zero
    // for 149 ms and advance only after the full 150 ms preset duration.
    MobileAnimationPlayer gait{.animation_set_id = "canonical_walk", .playback_rate = 125.0F / 150.0F};
    catalog.update_player(gait, "walking", MobileEntityDirection::east, 0.149F);
    assert(gait.clip_id == "walking_east" && gait.frame_index == 0);
    catalog.update_player(gait, "walking", MobileEntityDirection::east, 0.002F);
    assert(gait.frame_index == 1);

    // The same canonical action has one real render for every camera-relative
    // cardinal direction; all clips must retain the exact four-frame cadence.
    for (const MobileEntityDirection direction : directions) {
        const MobileAnimationClip* walking = catalog.resolve_clip("canonical_walk", "walking", direction);
        assert(walking != nullptr && walking->frames.size() == 4 && walking->frames_per_second == 8.0F);
    }
}
