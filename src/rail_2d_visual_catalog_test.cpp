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
            assert(ids.insert(spec->sprite_id).second);
            assert(paths.insert(spec->png_path).second);
            ++resolved_count;
        }
    }
    assert(resolved_count == Rail2dVisualCatalog::kRequiredSpriteCount);
    assert(ids.size() == Rail2dVisualCatalog::kRequiredSpriteCount);
    assert(paths.size() == Rail2dVisualCatalog::kRequiredSpriteCount);

    // Left/right pieces are deliberately distinct assets. We do not mirror PNGs
    // at runtime because switches and lighting must remain authored/approved.
    for (const Rail2dDirection direction : Rail2dVisualCatalog::directions()) {
        const auto left_curve = Rail2dVisualCatalog::resolve(Rail2dPieceKind::curve_left_90, direction);
        const auto right_curve = Rail2dVisualCatalog::resolve(Rail2dPieceKind::curve_right_90, direction);
        const auto left_turnout = Rail2dVisualCatalog::resolve(Rail2dPieceKind::turnout_left, direction);
        const auto right_turnout = Rail2dVisualCatalog::resolve(Rail2dPieceKind::turnout_right, direction);
        assert(left_curve && right_curve && left_turnout && right_turnout);
        assert(left_curve->png_path != right_curve->png_path);
        assert(left_turnout->png_path != right_turnout->png_path);
    }

    // Four deterministic quarter-turns return to the same authored direction.
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
