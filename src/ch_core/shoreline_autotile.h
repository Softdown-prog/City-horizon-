#ifndef CITY_HORIZON_CH_CORE_SHORELINE_AUTOTILE_H
#define CITY_HORIZON_CH_CORE_SHORELINE_AUTOTILE_H

#include "src/ch_core/shoreline_contracts.h"
#include "src/ch_core/semantic_grid.h"
#include "src/ch_core/grid.h"

namespace ch {

class ShorelineAutotiler {
public:
    static uint8_t compute_neighborhood_mask(const SemanticWorldView& world, GridCoord tile);

    static ShorelineRecipe resolve_shoreline(uint8_t mask);

    static AutotileResult evaluate_shoreline(const SemanticWorldView& world, const GridBounds& bounds);

    // Rotation helper functions for test invariance verification
    static uint8_t rotate_mask(uint8_t mask, QuarterTurn turn);

    static ShorelineRecipe rotate_recipe_for_test(const ShorelineRecipe& recipe, QuarterTurn turn);
};

} // namespace ch

#endif // CITY_HORIZON_CH_CORE_SHORELINE_AUTOTILE_H
