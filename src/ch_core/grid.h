#ifndef CITY_HORIZON_CH_CORE_GRID_H
#define CITY_HORIZON_CH_CORE_GRID_H

#include <cstdint>
#include "src/ch_core/contracts.h"

namespace ch {

struct GridCoord {
    int x = 0;
    int y = 0;

    constexpr bool operator==(const GridCoord& other) const {
        return x == other.x && y == other.y;
    }
};

struct GridBounds {
    int min_x = contracts::kMapMin;
    int min_y = contracts::kMapMin;
    int max_x = contracts::kMapMax;
    int max_y = contracts::kMapMax;

    [[nodiscard]] constexpr bool contains(const int x, const int y) const {
        return x >= min_x && x <= max_x && y >= min_y && y <= max_y;
    }

    [[nodiscard]] constexpr bool contains(const GridCoord& coord) const {
        return contains(coord.x, coord.y);
    }
};

[[nodiscard]] constexpr std::uint64_t tile_key(const int x, const int y) {
    return (static_cast<std::uint64_t>(static_cast<std::uint32_t>(x)) << 32) |
           static_cast<std::uint64_t>(static_cast<std::uint32_t>(y));
}

} // namespace ch

#endif // CITY_HORIZON_CH_CORE_GRID_H
