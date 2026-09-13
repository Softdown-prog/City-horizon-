#include "src/ch_core/shoreline_autotile.h"
#include <iostream>
#include <cassert>

void test_exhaustive_mask_domain() {
    std::cout << "Running exhaustive 256 mask-domain test...\n";
    for (int mask_val = 0; mask_val < 256; ++mask_val) {
        uint8_t mask = static_cast<uint8_t>(mask_val);
        ch::ShorelineRecipe recipe = ch::ShorelineAutotiler::resolve_shoreline(mask);
        // Verify recipe pieces are sorted and unique
        for (size_t i = 1; i < recipe.pieces.size(); ++i) {
            assert(recipe.pieces[i - 1] < recipe.pieces[i]);
        }
    }
    std::cout << "[PASS] Exhaustive 256 mask-domain test completed successfully.\n";
}

void test_rotation_invariance() {
    std::cout << "Running 90-degree rotation invariance test over 256 masks...\n";
    const ch::QuarterTurn turns[4] = {
        ch::QuarterTurn::R0,
        ch::QuarterTurn::R90,
        ch::QuarterTurn::R180,
        ch::QuarterTurn::R270
    };

    for (int mask_val = 0; mask_val < 256; ++mask_val) {
        uint8_t mask = static_cast<uint8_t>(mask_val);
        ch::ShorelineRecipe base_recipe = ch::ShorelineAutotiler::resolve_shoreline(mask);

        for (const auto turn : turns) {
            uint8_t rotated_mask = ch::ShorelineAutotiler::rotate_mask(mask, turn);
            ch::ShorelineRecipe recipe_from_rotated_mask = ch::ShorelineAutotiler::resolve_shoreline(rotated_mask);
            ch::ShorelineRecipe rotated_base_recipe = ch::ShorelineAutotiler::rotate_recipe_for_test(base_recipe, turn);

            assert(recipe_from_rotated_mask == rotated_base_recipe);
        }
    }
    std::cout << "[PASS] 90-degree rotation invariance test passed for all 256 masks across all 4 quarter turns.\n";
}

int main() {
    std::cout << "Starting CH_SHORELINE_V1 unit tests...\n";
    test_exhaustive_mask_domain();
    test_rotation_invariance();
    std::cout << "All CH_SHORELINE_V1 unit tests passed successfully!\n";
    return 0;
}
