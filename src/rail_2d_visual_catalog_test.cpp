#include "rail_2d_visual_catalog.h"

#include <cassert>
#include <cstdint>
#include <set>
#include <string_view>

int main() {
    static_assert(static_cast<std::uint8_t>(Rail2dDirection::south) == 0U);
    static_assert(static_cast<std::uint8_t>(Rail2dDirection::west) == 1U);
    static_assert(static_cast<std::uint8_t>(Rail2dDirection::north) == 2U);
    static_assert(static_cast<std::uint8_t>(Rail2dDirection::east) == 3U);
    static_assert(Rail2dVisualCatalog::kRequiredSpriteCount == 18U);
    static_assert(Rail2dVisualCatalog::kLogicalResolutionCount == 20U);

    std::set<std::string_view> ids;
    std::set<std::string_view> paths;
    std::size_t resolved_count = 0U;

    for (const Rail2dPieceKind piece : Rail2dVisualCatalog::required_pieces()) {
        assert(!Rail2dVisualCatalog::piece_name(piece).empty());
        for (const Rail2dDirection direction : Rail2dVisualCatalog::directions()) {
            assert(!Rail2dVisualCatalog::direction_name(direction).empty());
            const auto spec = Rail2dVisualCatalog::resolve(piece, direction);
            assert(spec.has_value());
            assert(spec->valid());
            assert(spec->piece == piece);
            assert(spec->direction == direction);
            assert(spec->png_path.starts_with("assets/rail/prerendered_v1/"));
            assert(spec->png_path.ends_with(".png"));
            assert(spec->anchor_policy == "CH_RAIL_WORLD_ORIGIN_V1");
            ids.insert(spec->sprite_id);
            paths.insert(spec->png_path);
            ++resolved_count;
        }
    }
    assert(resolved_count == Rail2dVisualCatalog::kLogicalResolutionCount);
    assert(ids.size() == Rail2dVisualCatalog::kRequiredSpriteCount);
    assert(paths.size() == Rail2dVisualCatalog::kRequiredSpriteCount);

    // Straight track has only two physical sprites. Opposite logical directions
    // alias those approved files while preserving the requested logical direction.
    const auto straight_south = Rail2dVisualCatalog::resolve(Rail2dPieceKind::straight, Rail2dDirection::south);
    const auto straight_north = Rail2dVisualCatalog::resolve(Rail2dPieceKind::straight, Rail2dDirection::north);
    const auto straight_west = Rail2dVisualCatalog::resolve(Rail2dPieceKind::straight, Rail2dDirection::west);
    const auto straight_east = Rail2dVisualCatalog::resolve(Rail2dPieceKind::straight, Rail2dDirection::east);
    assert(straight_south && straight_north && straight_west && straight_east);
    assert(straight_south->png_path == straight_north->png_path);
    assert(straight_south->sprite_id == straight_north->sprite_id);
    assert(straight_west->png_path == straight_east->png_path);
    assert(straight_west->sprite_id == straight_east->sprite_id);
    assert(straight_south->png_path != straight_west->png_path);
    assert(Rail2dVisualCatalog::canonical_direction(Rail2dPieceKind::straight, Rail2dDirection::north) == Rail2dDirection::south);
    assert(Rail2dVisualCatalog::canonical_direction(Rail2dPieceKind::straight, Rail2dDirection::east) == Rail2dDirection::west);

    // Left/right pieces are deliberately distinct assets. We do not mirror PNGs
    // at runtime because switches and baked lighting must remain authored/approved.
    for (const Rail2dDirection direction : Rail2dVisualCatalog::directions()) {
        const auto left_curve = Rail2dVisualCatalog::resolve(Rail2dPieceKind::curve_left_90, direction);
        const auto right_curve = Rail2dVisualCatalog::resolve(Rail2dPieceKind::curve_right_90, direction);
        const auto left_turnout = Rail2dVisualCatalog::resolve(Rail2dPieceKind::turnout_left, direction);
        const auto right_turnout = Rail2dVisualCatalog::resolve(Rail2dPieceKind::turnout_right, direction);
        assert(left_curve && right_curve && left_turnout && right_turnout);
        assert(left_curve->png_path != right_curve->png_path);
        assert(left_turnout->png_path != right_turnout->png_path);
        assert(Rail2dVisualCatalog::canonical_direction(Rail2dPieceKind::curve_left_90, direction) == direction);
        assert(Rail2dVisualCatalog::canonical_direction(Rail2dPieceKind::turnout_left, direction) == direction);
    }

    // Four deterministic quarter-turns return to the same logical direction.
    for (const Rail2dDirection direction : Rail2dVisualCatalog::directions()) {
        assert(Rail2dVisualCatalog::rotate_clockwise(direction, 0) == direction);
        assert(Rail2dVisualCatalog::rotate_clockwise(direction, 4) == direction);
        assert(Rail2dVisualCatalog::rotate_clockwise(direction, -4) == direction);
    }
    assert(Rail2dVisualCatalog::rotate_clockwise(Rail2dDirection::south, 1) == Rail2dDirection::west);
    assert(Rail2dVisualCatalog::rotate_clockwise(Rail2dDirection::south, 2) == Rail2dDirection::north);
    assert(Rail2dVisualCatalog::rotate_clockwise(Rail2dDirection::south, -1) == Rail2dDirection::east);

    // Corrupt enum values fail closed at lookup boundaries.
    const auto bad_piece = static_cast<Rail2dPieceKind>(255U);
    const auto bad_direction = static_cast<Rail2dDirection>(255U);
    assert(!Rail2dVisualCatalog::resolve(bad_piece, Rail2dDirection::south).has_value());
    assert(!Rail2dVisualCatalog::resolve(Rail2dPieceKind::straight, bad_direction).has_value());
    assert(Rail2dVisualCatalog::piece_name(bad_piece).empty());
    assert(Rail2dVisualCatalog::direction_name(bad_direction).empty());

    return 0;
}
