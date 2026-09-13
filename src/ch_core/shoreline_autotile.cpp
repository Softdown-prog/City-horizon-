#include "src/ch_core/shoreline_autotile.h"

namespace ch {

uint8_t ShorelineAutotiler::compute_neighborhood_mask(const SemanticWorldView& world, GridCoord tile) {
    // Fail-closed center check: center tile must be valid LAND
    TileSemanticInfo center_info = SemanticGrid::inspect_tile_channels(world, tile);
    if (center_info.water_state == SemanticState::valid) {
        return 0; // Water tiles produce 0 shoreline recipe
    }

    uint8_t mask = 0;
    const GridCoord offsets[8] = {
        { 0, -1}, // N  (bit 0)
        { 1, -1}, // NE (bit 1)
        { 1,  0}, // E  (bit 2)
        { 1,  1}, // SE (bit 3)
        { 0,  1}, // S  (bit 4)
        {-1,  1}, // SW (bit 5)
        {-1,  0}, // W  (bit 6)
        {-1, -1}  // NW (bit 7)
    };

    for (int i = 0; i < 8; ++i) {
        GridCoord neighbor = GridCoord(tile.x + offsets[i].x, tile.y + offsets[i].y);
        TileSemanticInfo info = SemanticGrid::inspect_tile_channels(world, neighbor);
        // Fail-closed rule: only explicitly valid WATER sets bit 1
        if (info.water_state == SemanticState::valid) {
            mask |= static_cast<uint8_t>(1 << i);
        }
    }

    return mask;
}

ShorelineRecipe ShorelineAutotiler::resolve_shoreline(uint8_t mask) {
    ShorelineRecipe recipe;

    const bool n_water  = (mask & kNeighborN)  != 0;
    const bool ne_water = (mask & kNeighborNE) != 0;
    const bool e_water  = (mask & kNeighborE)  != 0;
    const bool se_water = (mask & kNeighborSE) != 0;
    const bool s_water  = (mask & kNeighborS)  != 0;
    const bool sw_water = (mask & kNeighborSW) != 0;
    const bool w_water  = (mask & kNeighborW)  != 0;
    const bool nw_water = (mask & kNeighborNW) != 0;

    // 1. Straight Borders
    if (n_water) recipe.pieces.push_back(ShorelinePiece::border_north);
    if (e_water) recipe.pieces.push_back(ShorelinePiece::border_east);
    if (s_water) recipe.pieces.push_back(ShorelinePiece::border_south);
    if (w_water) recipe.pieces.push_back(ShorelinePiece::border_west);

    // 2. Outer Corners (where two adjacent cardinals are water)
    if (n_water && e_water) recipe.pieces.push_back(ShorelinePiece::outer_ne);
    if (e_water && s_water) recipe.pieces.push_back(ShorelinePiece::outer_se);
    if (s_water && w_water) recipe.pieces.push_back(ShorelinePiece::outer_sw);
    if (w_water && n_water) recipe.pieces.push_back(ShorelinePiece::outer_nw);

    // 3. Inner Corners (where adjacent cardinals are land, but diagonal is water)
    if (!n_water && !e_water && ne_water) recipe.pieces.push_back(ShorelinePiece::inner_ne);
    if (!e_water && !s_water && se_water) recipe.pieces.push_back(ShorelinePiece::inner_se);
    if (!s_water && !w_water && sw_water) recipe.pieces.push_back(ShorelinePiece::inner_sw);
    if (!w_water && !n_water && nw_water) recipe.pieces.push_back(ShorelinePiece::inner_nw);

    recipe.normalize();
    return recipe;
}

AutotileResult ShorelineAutotiler::evaluate_shoreline(const SemanticWorldView& world, const GridBounds& bounds) {
    AutotileResult result;

    for (int y = bounds.min_y; y <= bounds.max_y; ++y) {
        for (int x = bounds.min_x; x <= bounds.max_x; ++x) {
            GridCoord tile(x, y);
            uint8_t mask = compute_neighborhood_mask(world, tile);
            if (mask > 0) {
                ShorelineRecipe recipe = resolve_shoreline(mask);
                if (!recipe.pieces.empty()) {
                    result.edits.push_back({tile, recipe});
                }
            }
        }
    }

    return result;
}

uint8_t ShorelineAutotiler::rotate_mask(uint8_t mask, QuarterTurn turn) {
    int shift = (static_cast<int>(turn) * 2) % 8;
    if (shift == 0) return mask;
    return static_cast<uint8_t>(((mask << shift) | (mask >> (8 - shift))) & 0xFF);
}

ShorelineRecipe ShorelineAutotiler::rotate_recipe_for_test(const ShorelineRecipe& recipe, QuarterTurn turn) {
    int turns = static_cast<int>(turn) % 4;
    if (turns == 0) return recipe;

    ShorelineRecipe rotated;
    rotated.pieces.reserve(recipe.pieces.size());

    for (const auto piece : recipe.pieces) {
        uint8_t val = static_cast<uint8_t>(piece);
        uint8_t group_base = (val / 4) * 4;
        uint8_t dir = val % 4;
        uint8_t new_dir = (dir + turns) % 4;
        rotated.pieces.push_back(static_cast<ShorelinePiece>(group_base + new_dir));
    }

    rotated.normalize();
    return rotated;
}

} // namespace ch
