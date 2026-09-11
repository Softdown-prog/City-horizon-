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
}
