#include "src/ch_core/contracts.h"
#include "src/ch_core/grid.h"
#include "src/ch_core/projection.h"
#include "src/ch_core/map_document.h"
#include "src/ch_core/validation.h"

#include <cassert>
#include <cmath>
#include <iostream>
#include <string>

int main(int argc, char** argv) {
    // 1. Verify Contracts
    static_assert(ch::contracts::kTileWidth == 128);
    static_assert(ch::contracts::kTileHeight == 64);
    static_assert(ch::contracts::kDiamondRatio == 2.0);
    static_assert(ch::contracts::kMapMin == -24);
    static_assert(ch::contracts::kMapMax == 23);
    assert(std::string(ch::contracts::kGridContract) == "CH_GRID_V1");

    // 2. Verify Grid Math
    ch::GridCoord c1{5, -10};
    ch::GridCoord c2{5, -10};
    ch::GridCoord c3{5, 10};
    assert(c1 == c2);
    assert(!(c1 == c3));

    ch::GridBounds bounds;
    assert(bounds.contains(0, 0));
    assert(bounds.contains(-24, 23));
    assert(!bounds.contains(-25, 0));
    assert(!bounds.contains(0, 24));

    assert(ch::tile_key(5, -10) != ch::tile_key(-10, 5));

    // 3. Verify Projection & Rotation Math
    ch::CameraState camera;
    camera.pan_x = 100.0F;
    camera.pan_y = 50.0F;
    camera.zoom = 1.0F;
    camera.rotation = ch::CameraRotation::r0;

    ch::ScreenPoint sp = ch::world_to_screen_point(10.0F, 5.0F, camera, 1280.0F, 720.0F);
    ch::GridCoord gc = ch::screen_to_tile_coord(sp.x, sp.y, camera, 1280.0F, 720.0F);
    assert(gc.x == 10);
    assert(gc.y == 5);

    float depth_r0 = ch::camera_depth_key(10.0F, 5.0F, camera);
    assert(std::abs(depth_r0 - 15.0F) < 0.001F);

    ch::WorldPoint top_r0 = ch::tile_visual_top_world(10, 5, ch::CameraRotation::r0);
    assert(top_r0.x == 10.0F && top_r0.y == 5.0F);

    ch::WorldPoint top_r90 = ch::tile_visual_top_world(10, 5, ch::CameraRotation::r90);
    assert(top_r90.x == 11.0F && top_r90.y == 5.0F);

    ch::WorldPoint b_ground = ch::building_visual_ground_world(10, 5, 2, 2, ch::CameraRotation::r0);
    assert(b_ground.x == 12.0F && b_ground.y == 7.0F);

    // 4. Verify MapDocument & Validation
    if (argc > 1) {
        std::string scenario_path = argv[1];
        auto doc = ch::MapDocument::load_from_file(scenario_path);
        assert(doc.has_value());
        assert(!doc->terrain_tiles().empty());
        assert(!doc->buildings().empty());

        auto report = ch::validate_map_document(*doc);
        assert(report.valid);
        assert(report.errors.empty());
    }

    // Inline raw JSON MapDocument verification
    std::string test_json = R"({
        "terrain": [{"tileX": 0, "tileY": 0, "texture": "grass"}],
        "buildings": [{"instanceId": 1, "definitionId": "bakery", "tileX": 1, "tileY": 1, "rotation": 0}],
        "roads": [{"tileX": 2, "tileY": 2}]
    })";

    ch::MapDocument inline_doc(test_json);
    assert(inline_doc.terrain_tiles().size() == 1);
    assert(inline_doc.buildings().size() == 1);
    assert(inline_doc.roads().size() == 1);

    assert(inline_doc.get_terrain_at(0, 0).has_value());
    assert(inline_doc.get_terrain_at(0, 0)->texture == "grass");
    assert(inline_doc.get_building_at(1, 1).has_value());
    assert(inline_doc.get_building_at(1, 1)->definition_id == "bakery");
    assert(inline_doc.is_road_at(2, 2));
    assert(!inline_doc.is_road_at(0, 0));

    auto inline_report = ch::validate_map_document(inline_doc);
    assert(inline_report.valid);

    std::cout << "ch_core_test passed successfully!\n";
    return 0;
}
