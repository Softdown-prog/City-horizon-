#include "src/ch_core/terrain_heightfield.h"
#include "src/ch_core/terrain_projection.h"

#include <cassert>
#include <cmath>
#include <iostream>

int main() {
    static_assert(ch::kTerrainHeightfieldContract == "CH_TERRAIN_HEIGHTFIELD_V1");

    ch::TerrainHeightField field;
    field.set_height(0, 0, 1.0F);
    field.set_height(1, 0, 2.0F);
    assert(std::abs(field.sample(0.5F, 0.0F) - 1.5F) < 0.001F);

    ch::CameraState camera{};
    camera.zoom = 1.0F;
    const ch::ScreenPoint flat_mid = ch::world_to_screen_point(0.5F, 0.0F, camera, 1280.0F, 720.0F);
    const ch::ScreenPoint raised_mid = ch::terrain_world_to_screen_point(
        0.5F, 0.0F, field, camera, 1280.0F, 720.0F);
    assert(std::abs((flat_mid.y - raised_mid.y) - 24.0F) < 0.001F);

    field.apply_brush(0.5F, 0.5F, 2.5F, 0.75F, ch::TerrainBrushMode::raise);
    assert(field.height_at(0, 0) > 1.0F);
    assert(field.height_at(1, 1) > 0.0F);
    assert(field.height_at(5, 5) == 0.0F);

    const float raised = field.height_at(0, 0);
    field.apply_brush(0.5F, 0.5F, 2.5F, 0.75F, ch::TerrainBrushMode::lower);
    assert(field.height_at(0, 0) < raised);

    ch::TerrainHeightField smooth;
    smooth.set_height(0, 0, 3.0F);
    smooth.apply_brush(0.0F, 0.0F, 1.5F, 1.0F, ch::TerrainBrushMode::smooth);
    assert(smooth.height_at(0, 0) < 3.0F);

    std::cout << "terrain_heightfield_test passed successfully!\n";
    return 0;
}
