#include "mobile_animation.h"

#include <array>
#include <cmath>
#include <filesystem>
#include <iostream>

namespace {

bool require(const bool condition, const char* message) {
    if (!condition) {
        std::cerr << "mobile animation test failed: " << message << '\n';
        return false;
    }
    return true;
}

}  // namespace

int main(int argc, char** argv) {
    if (!require(argc == 2, "animation definitions directory argument")) return 1;

    MobileAnimationCatalog catalog;
    if (!require(catalog.load_from_directory(std::filesystem::path(argv[1])), "catalog loads")) return 1;

    const std::array directions = {MobileEntityDirection::south, MobileEntityDirection::east,
                                   MobileEntityDirection::north, MobileEntityDirection::west};
    const std::array names = {"south", "east", "north", "west"};
    for (std::size_t index = 0; index < directions.size(); ++index) {
        const MobileAnimationClip* idle = catalog.resolve_clip("ch_actor_green_01", "idle", directions[index]);
        const MobileAnimationClip* walking = catalog.resolve_clip("ch_actor_green_01", "walking", directions[index]);
        if (!require(idle != nullptr && idle->id == "idle_" + std::string(names[index]) && idle->frames.size() == 1,
                     "runtime actor exposes one-frame directional idle") ||
            !require(walking != nullptr && walking->id == "walking_" + std::string(names[index]) &&
                         walking->frames.size() == 8 && std::abs(walking->frames_per_second - 7.272727F) < 0.001F,
                     "runtime actor exposes the canonical eight-frame directional walk")) {
            return 1;
        }
    }

    MobileAnimationPlayer gait{.animation_set_id = "ch_actor_green_01"};
    catalog.update_player(gait, "walking", MobileEntityDirection::east, 0.13F);
    if (!require(gait.clip_id == "walking_east" && gait.frame_index == 0,
                 "walk holds the first frame before one 137.5ms cadence")) return 1;
    catalog.update_player(gait, "walking", MobileEntityDirection::east, 0.01F);
    if (!require(gait.frame_index == 1, "walk advances after one canonical frame interval") ||
        !require(catalog.current_frame(gait) != nullptr, "advanced walk frame resolves to an asset")) return 1;

    for (const MobileEntityDirection direction : directions) {
        const MobileAnimationClip* broom = catalog.resolve_clip("ch_actor_broom_01", "walking", direction);
        if (!require(broom != nullptr && broom->frames.size() == 8,
                     "approved broom equipment preserves the actor walk cadence")) return 1;
    }

    std::cout << "mobile animation tests passed\n";
    return 0;
}
