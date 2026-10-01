#pragma once

#include <array>
#include <cstdint>
#include <optional>
#include <string_view>

inline constexpr const char* kChRail2dPrerenderCatalogContract =
    "CH_RAIL_2D_PRERENDER_CATALOG_V1";

// CH_RAIL_2D_PRERENDER_CATALOG_V1
//
// Runtime rail visuals are approved 2D RGBA pre-rendered sprites. The existing
// procedural graph/path system remains authoritative for connectivity and
// validation, but runtime visual selection must not require RailMeshBuilder.
//
// Direction ordinals intentionally match the directional sprite convention
// already used by City Horizon definitions: 0=SOUTH, 1=WEST, 2=NORTH, 3=EAST.
enum class Rail2dDirection : std::uint8_t {
    south = 0,
    west = 1,
    north = 2,
    east = 3,
};

enum class Rail2dPieceKind : std::uint8_t {
    straight = 0,
    curve_left_90,
    curve_right_90,
    turnout_left,
    turnout_right,
};

struct Rail2dSpriteSpec {
    Rail2dPieceKind piece = Rail2dPieceKind::straight;
    Rail2dDirection direction = Rail2dDirection::south;
    std::string_view sprite_id{};
    std::string_view png_path{};
    std::string_view anchor_policy{};

    [[nodiscard]] bool valid() const {
        return !sprite_id.empty() && !png_path.empty() && !anchor_policy.empty();
    }
};

class Rail2dVisualCatalog final {
public:
    static constexpr std::size_t kPieceCount = 5U;
    static constexpr std::size_t kDirectionCount = 4U;
    static constexpr std::size_t kRequiredSpriteCount = kPieceCount * kDirectionCount;

    [[nodiscard]] static std::optional<Rail2dSpriteSpec> resolve(
        Rail2dPieceKind piece,
        Rail2dDirection direction);

    [[nodiscard]] static Rail2dDirection rotate_clockwise(
        Rail2dDirection direction,
        int quarter_turns);

    [[nodiscard]] static std::string_view piece_name(Rail2dPieceKind piece);
    [[nodiscard]] static std::string_view direction_name(Rail2dDirection direction);

    [[nodiscard]] static constexpr std::array<Rail2dPieceKind, kPieceCount> required_pieces() {
        return {
            Rail2dPieceKind::straight,
            Rail2dPieceKind::curve_left_90,
            Rail2dPieceKind::curve_right_90,
            Rail2dPieceKind::turnout_left,
            Rail2dPieceKind::turnout_right,
        };
    }

    [[nodiscard]] static constexpr std::array<Rail2dDirection, kDirectionCount> directions() {
        return {
            Rail2dDirection::south,
            Rail2dDirection::west,
            Rail2dDirection::north,
            Rail2dDirection::east,
        };
    }
};
