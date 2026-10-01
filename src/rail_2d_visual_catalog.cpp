#include "rail_2d_visual_catalog.h"

#include <array>

namespace {

constexpr std::string_view kWorldOriginAnchor = "CH_RAIL_WORLD_ORIGIN_V1";

constexpr std::array<Rail2dSpriteSpec, Rail2dVisualCatalog::kRequiredSpriteCount> kSprites{{
    // Straight track is symmetric under a 180-degree turn. SOUTH/NORTH share
    // one approved sprite and WEST/EAST share the other; logical directions
    // are preserved by resolve() without storing duplicate PNGs.
    {Rail2dPieceKind::straight, Rail2dDirection::south, "rail.straight.south", "assets/rail/prerendered_v1/straight_south.png", kWorldOriginAnchor},
    {Rail2dPieceKind::straight, Rail2dDirection::west, "rail.straight.west", "assets/rail/prerendered_v1/straight_west.png", kWorldOriginAnchor},

    {Rail2dPieceKind::curve_left_90, Rail2dDirection::south, "rail.curve_left_90.south", "assets/rail/prerendered_v1/curve_left_90_south.png", kWorldOriginAnchor},
    {Rail2dPieceKind::curve_left_90, Rail2dDirection::west, "rail.curve_left_90.west", "assets/rail/prerendered_v1/curve_left_90_west.png", kWorldOriginAnchor},
    {Rail2dPieceKind::curve_left_90, Rail2dDirection::north, "rail.curve_left_90.north", "assets/rail/prerendered_v1/curve_left_90_north.png", kWorldOriginAnchor},
    {Rail2dPieceKind::curve_left_90, Rail2dDirection::east, "rail.curve_left_90.east", "assets/rail/prerendered_v1/curve_left_90_east.png", kWorldOriginAnchor},

    {Rail2dPieceKind::curve_right_90, Rail2dDirection::south, "rail.curve_right_90.south", "assets/rail/prerendered_v1/curve_right_90_south.png", kWorldOriginAnchor},
    {Rail2dPieceKind::curve_right_90, Rail2dDirection::west, "rail.curve_right_90.west", "assets/rail/prerendered_v1/curve_right_90_west.png", kWorldOriginAnchor},
    {Rail2dPieceKind::curve_right_90, Rail2dDirection::north, "rail.curve_right_90.north", "assets/rail/prerendered_v1/curve_right_90_north.png", kWorldOriginAnchor},
    {Rail2dPieceKind::curve_right_90, Rail2dDirection::east, "rail.curve_right_90.east", "assets/rail/prerendered_v1/curve_right_90_east.png", kWorldOriginAnchor},

    {Rail2dPieceKind::turnout_left, Rail2dDirection::south, "rail.turnout_left.south", "assets/rail/prerendered_v1/turnout_left_south.png", kWorldOriginAnchor},
    {Rail2dPieceKind::turnout_left, Rail2dDirection::west, "rail.turnout_left.west", "assets/rail/prerendered_v1/turnout_left_west.png", kWorldOriginAnchor},
    {Rail2dPieceKind::turnout_left, Rail2dDirection::north, "rail.turnout_left.north", "assets/rail/prerendered_v1/turnout_left_north.png", kWorldOriginAnchor},
    {Rail2dPieceKind::turnout_left, Rail2dDirection::east, "rail.turnout_left.east", "assets/rail/prerendered_v1/turnout_left_east.png", kWorldOriginAnchor},

    {Rail2dPieceKind::turnout_right, Rail2dDirection::south, "rail.turnout_right.south", "assets/rail/prerendered_v1/turnout_right_south.png", kWorldOriginAnchor},
    {Rail2dPieceKind::turnout_right, Rail2dDirection::west, "rail.turnout_right.west", "assets/rail/prerendered_v1/turnout_right_west.png", kWorldOriginAnchor},
    {Rail2dPieceKind::turnout_right, Rail2dDirection::north, "rail.turnout_right.north", "assets/rail/prerendered_v1/turnout_right_north.png", kWorldOriginAnchor},
    {Rail2dPieceKind::turnout_right, Rail2dDirection::east, "rail.turnout_right.east", "assets/rail/prerendered_v1/turnout_right_east.png", kWorldOriginAnchor},
}};

[[nodiscard]] constexpr bool valid_piece(const Rail2dPieceKind piece) {
    return static_cast<std::uint8_t>(piece) < Rail2dVisualCatalog::kPieceCount;
}

[[nodiscard]] constexpr bool valid_direction(const Rail2dDirection direction) {
    return static_cast<std::uint8_t>(direction) < Rail2dVisualCatalog::kDirectionCount;
}

} // namespace

Rail2dDirection Rail2dVisualCatalog::canonical_direction(
    const Rail2dPieceKind piece,
    const Rail2dDirection direction) {
    if (!valid_piece(piece) || !valid_direction(direction)) return direction;
    if (piece != Rail2dPieceKind::straight) return direction;

    switch (direction) {
        case Rail2dDirection::north: return Rail2dDirection::south;
        case Rail2dDirection::east: return Rail2dDirection::west;
        case Rail2dDirection::south:
        case Rail2dDirection::west:
            return direction;
    }
    return direction;
}

std::optional<Rail2dSpriteSpec> Rail2dVisualCatalog::resolve(
    const Rail2dPieceKind piece,
    const Rail2dDirection direction) {
    if (!valid_piece(piece) || !valid_direction(direction)) return std::nullopt;

    const Rail2dDirection canonical = canonical_direction(piece, direction);
    for (const Rail2dSpriteSpec& spec : kSprites) {
        if (spec.piece == piece && spec.direction == canonical) {
            Rail2dSpriteSpec resolved = spec;
            resolved.direction = direction;
            return resolved;
        }
    }
    return std::nullopt;
}

Rail2dDirection Rail2dVisualCatalog::rotate_clockwise(
    const Rail2dDirection direction,
    const int quarter_turns) {
    if (!valid_direction(direction)) return direction;
    int turns = quarter_turns % static_cast<int>(kDirectionCount);
    if (turns < 0) turns += static_cast<int>(kDirectionCount);
    const auto raw = static_cast<int>(static_cast<std::uint8_t>(direction));
    return static_cast<Rail2dDirection>((raw + turns) % static_cast<int>(kDirectionCount));
}

std::string_view Rail2dVisualCatalog::piece_name(const Rail2dPieceKind piece) {
    switch (piece) {
        case Rail2dPieceKind::straight: return "straight";
        case Rail2dPieceKind::curve_left_90: return "curve_left_90";
        case Rail2dPieceKind::curve_right_90: return "curve_right_90";
        case Rail2dPieceKind::turnout_left: return "turnout_left";
        case Rail2dPieceKind::turnout_right: return "turnout_right";
    }
    return {};
}

std::string_view Rail2dVisualCatalog::direction_name(const Rail2dDirection direction) {
    switch (direction) {
        case Rail2dDirection::south: return "south";
        case Rail2dDirection::west: return "west";
        case Rail2dDirection::north: return "north";
        case Rail2dDirection::east: return "east";
    }
    return {};
}
