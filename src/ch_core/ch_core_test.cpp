#include "src/ch_core/contracts.h"
#include "src/ch_core/grid.h"
#include "src/ch_core/projection.h"
#include "src/ch_core/map_document.h"
#include "src/ch_core/procedural_tile_2d.h"
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
    assert(std::string(ch::kProceduralTile2DContract) == "CH_PROCEDURAL_TILE_2D_V1");

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
        "terrainHeights": [{"x": 0, "y": 0, "height": 1.5}, {"x": 1, "y": 0, "height": -0.5}],
        "buildings": [{"instanceId": 1, "definitionId": "bakery", "tileX": 1, "tileY": 1, "rotation": 0}],
        "roads": [{"tileX": 2, "tileY": 2}]
    })";

    ch::MapDocument inline_doc(test_json);
    assert(inline_doc.terrain_tiles().size() == 1);
    assert(std::abs(inline_doc.terrain_height_at(0, 0) - 1.5F) < 0.001F);
    assert(std::abs(inline_doc.terrain_height_at(1, 0) + 0.5F) < 0.001F);
    assert(std::abs(inline_doc.terrain_heightfield().sample(0.5F, 0.0F) - 0.5F) < 0.001F);
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

    // 5. Verify CH_PROCEDURAL_TILE_2D_V1 recipe classification. The logical
    // grid stays unchanged while the visual recipe reacts to topology + Z.
    const TileConnectionMask straight_ns = static_cast<TileConnectionMask>(
        tile_connection_north | tile_connection_south);
    const TileConnectionMask corner_ne = static_cast<TileConnectionMask>(
        tile_connection_north | tile_connection_east);

    ch::MapDocument flat_tile = ch::MapDocument::create_empty("procedural-flat", 8, 8);
    const ch::ProceduralTileRecipe flat_recipe =
        ch::make_procedural_tile_2d_recipe(flat_tile, 0, 0, straight_ns);
    assert(flat_recipe.topology == ch::ProceduralTileTopology::straight);
    assert(flat_recipe.contour == ch::ProceduralTileContour::continuous_outline);
    assert(flat_recipe.vertical_profile == ch::ProceduralTileVerticalProfile::flat);
    assert(flat_recipe.legacy_sprite_compatible);
    assert(flat_recipe.stair_count == 0);

    ch::MapDocument ramp_tile = ch::MapDocument::create_empty("procedural-ramp", 8, 8);
    ramp_tile.set_terrain_height_at(0, 0, 0.0F);
    ramp_tile.set_terrain_height_at(1, 0, 0.0F);
    ramp_tile.set_terrain_height_at(0, 1, 0.45F);
    ramp_tile.set_terrain_height_at(1, 1, 0.45F);
    const ch::ProceduralTileRecipe ramp_recipe =
        ch::make_procedural_tile_2d_recipe(ramp_tile, 0, 0, straight_ns);
    assert(ramp_recipe.vertical_profile == ch::ProceduralTileVerticalProfile::ramp);
    assert(!ramp_recipe.legacy_sprite_compatible);
    assert(ramp_recipe.high_edge == CardinalDirection::south);
    assert(ramp_recipe.low_edge == CardinalDirection::north);

    ch::MapDocument stair_tile = ch::MapDocument::create_empty("procedural-stairs", 8, 8);
    stair_tile.set_terrain_height_at(0, 0, 0.0F);
    stair_tile.set_terrain_height_at(1, 0, 0.0F);
    stair_tile.set_terrain_height_at(0, 1, 1.60F);
    stair_tile.set_terrain_height_at(1, 1, 1.60F);
    const ch::ProceduralTileRecipe stair_recipe =
        ch::make_procedural_tile_2d_recipe(stair_tile, 0, 0, straight_ns);
    assert(stair_recipe.vertical_profile == ch::ProceduralTileVerticalProfile::stairs);
    assert(stair_recipe.stair_count >= 7);
    assert(stair_recipe.high_edge == CardinalDirection::south);
    assert(stair_recipe.low_edge == CardinalDirection::north);

    const ch::ProceduralTileRecipe corner_recipe =
        ch::make_procedural_tile_2d_recipe(stair_tile, 0, 0, corner_ne);
    assert(corner_recipe.topology == ch::ProceduralTileTopology::corner);
    assert(corner_recipe.contour == ch::ProceduralTileContour::rounded_corner);
    assert(corner_recipe.requires_subdivision);

    const ch::ProceduralTileRecipe end_recipe =
        ch::make_procedural_tile_2d_recipe(flat_tile, 0, 0, tile_connection_north);
    assert(end_recipe.topology == ch::ProceduralTileTopology::end);
    assert(end_recipe.contour == ch::ProceduralTileContour::semicircle_cap);

    std::cout << "ch_core_test passed successfully!\n";
    return 0;
}
