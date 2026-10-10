#pragma once
#include "src/ch_core/projection.h"
#include <cmath>
namespace ch::rail_train_heading {
// Each successive bin corresponds to 45 degrees in the camera's view plane.
[[nodiscard]] inline int octant(const float tx, const float ty,
                                const CameraRotation camera_rotation) noexcept {
    if (!std::isfinite(tx) || !std::isfinite(ty) || tx*tx+ty*ty < 1e-12F)
        return 0;
    const WorldPoint view = camera_view_point(tx, ty, camera_rotation);
    constexpr float kFourOverPi = 1.2732395447351627F;
    const long index = std::lround(std::atan2(view.y, view.x)*kFourOverPi);
    return static_cast<int>((index%8L+8L)%8L);
}
[[nodiscard]] constexpr bool is_diagonal(const int index) noexcept {
    return (index & 1) != 0;
}
[[nodiscard]] inline constexpr const char* label(const int index) noexcept {
    constexpr const char* kNames[8] = {
        "north", "north_east", "east", "east_south",
        "south", "south_west", "west", "west_north"};
    return kNames[(index%8+8)%8];
}
} // namespace ch::rail_train_heading
