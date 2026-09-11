#pragma once

#include <array>
#include <cstdint>

// Shared four-neighbour topology contract for every connectable map network.
// The bit positions are stable data: N=1, E=2, S=4, W=8.
enum class CardinalDirection : std::uint8_t { north, east, south, west };

struct TileOffset {
    int x = 0;
    int y = 0;
};

using TileConnectionMask = std::uint8_t;

inline constexpr TileConnectionMask tile_connection_north = 1 << 0;
inline constexpr TileConnectionMask tile_connection_east = 1 << 1;
inline constexpr TileConnectionMask tile_connection_south = 1 << 2;
inline constexpr TileConnectionMask tile_connection_west = 1 << 3;

inline constexpr std::array<CardinalDirection, 4> kCardinalDirections = {
    CardinalDirection::north, CardinalDirection::east, CardinalDirection::south, CardinalDirection::west,
};

[[nodiscard]] constexpr TileOffset direction_offset(const CardinalDirection direction) {
    switch (direction) {
        case CardinalDirection::north: return {0, -1};
        case CardinalDirection::east: return {1, 0};
        case CardinalDirection::south: return {0, 1};
        case CardinalDirection::west: return {-1, 0};
    }
    return {};
}

[[nodiscard]] constexpr TileConnectionMask connection_bit(const CardinalDirection direction) {
    switch (direction) {
        case CardinalDirection::north: return tile_connection_north;
        case CardinalDirection::east: return tile_connection_east;
        case CardinalDirection::south: return tile_connection_south;
        case CardinalDirection::west: return tile_connection_west;
    }
    return 0;
}

[[nodiscard]] constexpr CardinalDirection opposite_direction(const CardinalDirection direction) {
    switch (direction) {
        case CardinalDirection::north: return CardinalDirection::south;
        case CardinalDirection::east: return CardinalDirection::west;
        case CardinalDirection::south: return CardinalDirection::north;
        case CardinalDirection::west: return CardinalDirection::east;
    }
    return CardinalDirection::south;
}

[[nodiscard]] constexpr bool has_connection(const TileConnectionMask mask, const CardinalDirection direction) {
    return (mask & connection_bit(direction)) != 0;
}
