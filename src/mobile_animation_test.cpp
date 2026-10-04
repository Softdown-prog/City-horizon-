#include "mobile_animation.h"
#include "ch_core/asset_registry.h"
#include "ch_render/palette_bank.h"
#include "ch_render/sprite_animation_runtime.h"
#include "ch_render/water_surface_runtime.h"

#include <array>
#include <cmath>
#include <filesystem>
#include <iostream>
#include <utility>
#include <vector>

namespace {

bool require(const bool condition, const char* message) {
    if (!condition) {
        std::cerr << "mobile animation test failed: " << message << '\n';
        return false;
    }
    return true;
}

}  // namespace

int main(int argc, char** argv) {
    if (!require(argc == 2, "animation definitions directory argument")) return 1;

    const std::filesystem::path animation_definitions = argv[1];

    MobileAnimationCatalog catalog;
    if (!require(catalog.load_from_directory(animation_definitions), "catalog loads")) return 1;

    const std::array directions = {MobileEntityDirection::south, MobileEntityDirection::east,
                                   MobileEntityDirection::north, MobileEntityDirection::west};
    const std::array names = {"south", "east", "north", "west"};
    for (std::size_t index = 0; index < directions.size(); ++index) {
        const MobileAnimationClip* idle = catalog.resolve_clip("ch_actor_green_01", "idle", directions[index]);
        const MobileAnimationClip* walking = catalog.resolve_clip("ch_actor_green_01", "walking", directions[index]);
        if (!require(idle != nullptr && idle->id == "idle_" + std::string(names[index]) && idle->frames.size() == 1,
                     "runtime actor exposes one-frame directional idle") ||
            !require(walking != nullptr && walking->id == "walking_" + std::string(names[index]) &&
                         walking->frames.size() == 8 && std::abs(walking->frames_per_second - 7.272727F) < 0.001F,
                     "runtime actor exposes the canonical eight-frame directional walk")) {
            return 1;
        }
    }

    MobileAnimationPlayer gait{.animation_set_id = "ch_actor_green_01"};
    catalog.update_player(gait, "walking", MobileEntityDirection::east, 0.13F);
    if (!require(gait.clip_id == "walking_east" && gait.frame_index == 0,
                 "walk holds the first frame before one 137.5ms cadence")) return 1;
    catalog.update_player(gait, "walking", MobileEntityDirection::east, 0.01F);
    if (!require(gait.frame_index == 1, "walk advances after one canonical frame interval") ||
        !require(catalog.current_frame(gait) != nullptr, "advanced walk frame resolves to an asset")) return 1;

    for (const MobileEntityDirection direction : directions) {
        const MobileAnimationClip* broom = catalog.resolve_clip("ch_actor_broom_01", "walking", direction);
        if (!require(broom != nullptr && broom->frames.size() == 8,
                     "approved broom equipment preserves the actor walk cadence")) return 1;
    }

    ch::AssetRegistry registry;
    const ch::AssetDescriptor ride_descriptor{
        .id = "ride.pirate_ship.01",
        .kind = ch::AssetKind::Ride,
        .logical_path = "assets/rides/pirate_ship_01",
        .source_group = "rides",
        .contract = "CH_AMUSEMENT_RIDE_V1",
    };
    if (!require(registry.register_asset(ride_descriptor) == ch::AssetRegistrationResult::Inserted,
                 "asset registry accepts a valid typed asset") ||
        !require(registry.register_asset(ride_descriptor) == ch::AssetRegistrationResult::DuplicateId,
                 "asset registry rejects duplicate ids") ||
        !require(registry.find("ride.pirate_ship.01") != nullptr && registry.ids(ch::AssetKind::Ride).size() == 1,
                 "asset registry resolves ids and filters by kind")) {
        return 1;
    }

    ch::PaletteBank palette(std::vector<ch::Rgba8>{
        {0, 0, 0, 0},
        {20, 40, 80, 255},
        {30, 60, 110, 255},
        {40, 80, 140, 255},
        {220, 80, 40, 255},
        {235, 120, 55, 255},
    });
    if (!require(palette.define_range("water_cycle", {1, 3}), "palette accepts a named semantic range") ||
        !require(palette.define_range("primary", {4, 2}), "palette accepts a primary color range") ||
        !require(palette.cycle_range("water_cycle", 1), "palette cycles a named range") ||
        !require(palette.color(1) != nullptr && palette.color(1)->r == 40,
                 "palette cycling rotates only the selected range") ||
        !require(palette.replace_range("primary", {{120, 35, 170, 255}, {165, 70, 205, 255}}),
                 "palette replaces a semantic color ramp") ||
        !require(palette.color(4) != nullptr && palette.color(4)->b == 170,
                 "primary color remap updates the expected entries")) {
        return 1;
    }

    ch::WaterSurfaceRuntimeCatalog water_runtime;
    const std::filesystem::path water_manifest =
        animation_definitions.parent_path().parent_path() / "terrain" / "water" / "water_surfaces.json";
    if (!require(water_runtime.load_manifest(water_manifest),
                 "water runtime loads the canonical CH_WATER_SURFACE_V1 manifest") ||
        !require(water_runtime.manifest_loaded(), "water runtime records manifest-backed state") ||
        !require(water_runtime.animation().frame_count == 16 &&
                     water_runtime.animation().frame_duration_ms == 125 &&
                     water_runtime.animation().world_period_tiles == 4,
                 "water runtime uses the approved sixteen-frame two-second cycle")) {
        return 1;
    }

    const ch::WaterSurfaceRuntimeDefinition* shallow_water = water_runtime.find_surface("water_shallow");
    const ch::WaterSurfaceRuntimeDefinition* deep_water = water_runtime.find_surface("water_deep");
    if (!require(shallow_water != nullptr && shallow_water->build_cost == 50,
                 "shallow water keeps its runtime id and build cost") ||
        !require(deep_water != nullptr && deep_water->build_cost == 100,
                 "deep water keeps its runtime id and build cost")) {
        return 1;
    }

    const ch::AssetDescriptor* shallow_base = shallow_water == nullptr
        ? nullptr
        : water_runtime.find_asset(shallow_water->base_asset_id);
    const ch::AssetDescriptor* deep_atlas = deep_water == nullptr
        ? nullptr
        : water_runtime.find_asset(deep_water->rgba_atlas_asset_id);
    const ch::Rgba8* shallow_coverage = shallow_water == nullptr
        ? nullptr
        : water_runtime.coverage_color(*shallow_water);
    const ch::Rgba8* deep_coverage = deep_water == nullptr
        ? nullptr
        : water_runtime.coverage_color(*deep_water);
    if (!require(shallow_base != nullptr &&
                     shallow_base->logical_path == "assets/terrain/water/water_shallow_world.png",
                 "water runtime registers the shallow base by stable asset id") ||
        !require(deep_atlas != nullptr &&
                     deep_atlas->logical_path == "assets/terrain/water/water_deep_glint_cycle_atlas.png",
                 "water runtime registers the deep animation atlas by stable asset id") ||
        !require(shallow_coverage != nullptr && shallow_coverage->r == 115 && shallow_coverage->g == 200,
                 "water runtime exposes shallow opaque coverage through the semantic palette") ||
        !require(deep_coverage != nullptr && deep_coverage->r == 80 && deep_coverage->b == 194,
                 "water runtime exposes deep opaque coverage through the semantic palette")) {
        return 1;
    }

    if (!require(water_runtime.frame_at_seconds(0.124F) == 0,
                 "water cycle holds frame zero before 125 milliseconds") ||
        !require(water_runtime.frame_at_seconds(0.125F) == 1,
                 "water cycle advances on the manifest frame duration") ||
        !require(water_runtime.frame_at_seconds(1.999F) == 15,
                 "water cycle reaches the last frame before two seconds") ||
        !require(water_runtime.frame_at_seconds(2.0F) == 0,
                 "water cycle loops deterministically at two seconds")) {
        return 1;
    }

    ch::SpriteAnimationClip clip;
    clip.id = "validation.directional_trimmed";
    ch::SpriteTrack east_track;
    east_track.frames = {
        ch::SpriteFrame{
            .asset_path = "assets/validation/actor_atlas.png",
            .source_rect = {0, 0, 20, 34},
            .draw_offset_x = -4,
            .draw_offset_y = -2,
            .anchor_x = 10,
            .anchor_y = 33,
            .duration_ms = 80,
        },
        ch::SpriteFrame{
            .asset_path = "assets/validation/actor_atlas.png",
            .source_rect = {20, 0, 22, 36},
            .draw_offset_x = -5,
            .draw_offset_y = -3,
            .anchor_x = 11,
            .anchor_y = 35,
            .duration_ms = 120,
        },
    };
    if (!require(clip.set_track(ch::SpriteDirection::East, std::move(east_track)),
                 "sprite runtime accepts valid trimmed frames") ||
        !require(clip.set_alias(ch::SpriteDirection::West, {ch::SpriteDirection::East, true}),
                 "sprite runtime accepts an explicit mirrored direction alias") ||
        !require(!clip.resolve(ch::SpriteDirection::North),
                 "sprite runtime does not invent undeclared direction fallbacks")) {
        return 1;
    }

    ch::SpriteAnimationPlayer sprite_player;
    sprite_player.bind(&clip);
    sprite_player.set_direction(ch::SpriteDirection::West);
    const ch::SpriteFrame* first_frame = sprite_player.current_frame();
    if (!require(first_frame != nullptr && first_frame->source_rect.width == 20 && first_frame->draw_offset_x == -4,
                 "sprite runtime preserves trim rectangle and draw offset") ||
        !require(sprite_player.mirror_x(), "explicit direction alias exposes horizontal mirroring")) {
        return 1;
    }
    sprite_player.advance(80);
    const ch::SpriteFrame* second_frame = sprite_player.current_frame();
    if (!require(sprite_player.frame_index() == 1 && second_frame != nullptr && second_frame->anchor_y == 35,
                 "sprite player advances deterministically and preserves ground anchor metadata")) {
        return 1;
    }

    std::cout << "mobile animation tests passed\n";
    return 0;
}
