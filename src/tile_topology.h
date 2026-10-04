#pragma once

#include <array>
#include <cstdint>
#include <string_view>

// Shared four-neighbour topology contract for every connectable map network.
// The bit positions are stable data: N=1, E=2, S=4, W=8.
inline constexpr std::string_view kPathTopologyContract = "CH_PATH_TOPOLOGY_V1";

enum class CardinalDirection : std::uint8_t { north, east, south, west };

enum class TileTopologyKind : std::uint8_t {
    isolated,
    endpoint,
    straight,
    corner,
    tee,
    cross,
};

struct TileOffset {
    int x = 0;
    int y = 0;
};

using TileConnectionMask = std::uint8_t;

inline constexpr TileConnectionMask tile_connection_north = 1 << 0;
inline constexpr TileConnectionMask tile_connection_east = 1 << 1;
inline constexpr TileConnectionMask tile_connection_south = 1 << 2;
inline constexpr TileConnectionMask tile_connection_west = 1 << 3;
inline constexpr TileConnectionMask tile_connection_all =
    tile_connection_north | tile_connection_east | tile_connection_south | tile_connection_west;

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

[[nodiscard]] constexpr TileConnectionMask normalize_connection_mask(const TileConnectionMask mask) {
    return mask & tile_connection_all;
}

[[nodiscard]] constexpr bool has_connection(const TileConnectionMask mask, const CardinalDirection direction) {
    return (normalize_connection_mask(mask) & connection_bit(direction)) != 0;
}

[[nodiscard]] constexpr std::uint8_t connection_count(const TileConnectionMask mask) {
    const TileConnectionMask normalized = normalize_connection_mask(mask);
    return static_cast<std::uint8_t>(
        ((normalized & tile_connection_north) != 0 ? 1 : 0) +
        ((normalized & tile_connection_east) != 0 ? 1 : 0) +
        ((normalized & tile_connection_south) != 0 ? 1 : 0) +
        ((normalized & tile_connection_west) != 0 ? 1 : 0)
    );
}

[[nodiscard]] constexpr bool is_straight_connection(const TileConnectionMask mask) {
    const TileConnectionMask normalized = normalize_connection_mask(mask);
    return normalized == (tile_connection_north | tile_connection_south) ||
           normalized == (tile_connection_east | tile_connection_west);
}

[[nodiscard]] constexpr TileTopologyKind classify_tile_topology(const TileConnectionMask mask) {
    const TileConnectionMask normalized = normalize_connection_mask(mask);
    switch (connection_count(normalized)) {
        case 0: return TileTopologyKind::isolated;
        case 1: return TileTopologyKind::endpoint;
        case 2: return is_straight_connection(normalized) ? TileTopologyKind::straight : TileTopologyKind::corner;
        case 3: return TileTopologyKind::tee;
        case 4: return TileTopologyKind::cross;
        default: return TileTopologyKind::isolated;
    }
}
