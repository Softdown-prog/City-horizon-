#pragma once

#include <array>
#include <string_view>

namespace ch::coaster {

// CH_COASTER_TRACK_SKIN_V1
// Visual-only skin contract layered on top of CH_COASTER_TRACK_GEOMETRY_V1.
// The centerline, physics, gauge, ties and support placement remain procedural
// and authoritative. A skin may change material language without changing the
// ride layout. This also leaves a stable seam for Blender-baked modules.
inline constexpr std::string_view kCoasterTrackSkinContract = "CH_COASTER_TRACK_SKIN_V1";

enum class CoasterTrackSkinId {
    classic_steel_01,
};

struct CoasterSkinColor {
    float r = 1.0F;
    float g = 1.0F;
    float b = 1.0F;
    float a = 1.0F;
};

struct CoasterTrackSkin {
    CoasterTrackSkinId id = CoasterTrackSkinId::classic_steel_01;
    std::string_view name = "Classic Steel 01";

    CoasterSkinColor rail_shadow{0.13F, 0.16F, 0.18F, 0.28F};
    CoasterSkinColor rail_side{0.25F, 0.30F, 0.33F, 1.0F};
    CoasterSkinColor rail_body{0.63F, 0.69F, 0.72F, 1.0F};
    CoasterSkinColor rail_head{0.86F, 0.89F, 0.90F, 0.48F};

    CoasterSkinColor spine_shadow{0.12F, 0.035F, 0.035F, 0.30F};
    CoasterSkinColor spine_side{0.25F, 0.055F, 0.050F, 1.0F};
    CoasterSkinColor spine_body{0.62F, 0.14F, 0.11F, 1.0F};
    CoasterSkinColor spine_cap{0.83F, 0.28F, 0.20F, 0.56F};

    CoasterSkinColor tie_shadow{0.10F, 0.12F, 0.13F, 1.0F};
    CoasterSkinColor tie_body{0.29F, 0.33F, 0.35F, 1.0F};
    CoasterSkinColor support_shadow{0.12F, 0.15F, 0.17F, 1.0F};
    CoasterSkinColor support_body{0.38F, 0.43F, 0.46F, 1.0F};

    float rail_shadow_width_px = 5.40F;
    float rail_side_width_px = 4.15F;
    float rail_body_width_px = 2.55F;
    float rail_head_width_px = 0.58F;

    float spine_shadow_width_px = 9.40F;
    float spine_side_width_px = 7.80F;
    float spine_body_width_px = 5.25F;
    float spine_cap_width_px = 0.82F;

    float tie_shadow_width_px = 3.05F;
    float tie_body_width_px = 1.62F;
    float support_shadow_width_px = 3.00F;
    float support_body_width_px = 1.60F;

    float side_offset_x_px = 0.62F;
    float side_offset_y_px = 0.92F;
    float cap_offset_x_px = -0.14F;
    float cap_offset_y_px = -0.30F;

    // Approved CH Blender full-body skin. Direction order is the canonical
    // studio order SOUTH, EAST, WEST, NORTH. The procedural renderer remains
    // underneath as a fail-safe if any sprite cannot be loaded.
    std::array<std::string_view, 4> body_sprite_paths{
        "assets/coasters/skins/classic_steel_01/body/track_body_south.png",
        "assets/coasters/skins/classic_steel_01/body/track_body_east.png",
        "assets/coasters/skins/classic_steel_01/body/track_body_west.png",
        "assets/coasters/skins/classic_steel_01/body/track_body_north.png",
    };
    int body_sprite_width_px = 256;
    int body_sprite_height_px = 256;
    float body_sprite_anchor_x = 0.50000024F;
    float body_sprite_anchor_y = 0.79645400F;
    // 128px canonical tile / 297.43548584px projected source tile.
    float body_sprite_scale_at_zoom1 = 0.43034542F;
    // One authored body module is exactly one gameplay tile (3 metres).
    double body_sprite_spacing_m = 3.0;
    // The authored rail centre is z=0.57m while procedural rails sit 0.10m
    // above the centerline, so the sprite ground anchor sits 0.47m below it.
    double body_ground_below_center_m = 0.47;
    bool body_sprite_enabled = true;

    // Detail atlas remains optional. It can be layered later over the full body
    // for lift chains/brake fins after the full-body runtime proof is accepted.
    std::string_view overlay_atlas_path = "assets/coasters/skins/classic_steel_01/track_skin_atlas.png";
    int overlay_cell_width_px = 96;
    int overlay_cell_height_px = 72;
    float overlay_sprite_scale = 0.56F;
    double joint_plate_spacing_m = 6.0;
    double chain_lift_spacing_m = 1.35;
    double brake_fin_spacing_m = 1.55;
    bool overlay_atlas_enabled = false;
};

inline constexpr CoasterTrackSkin kClassicSteelTrackSkin{};

[[nodiscard]] constexpr const CoasterTrackSkin& default_coaster_track_skin() noexcept {
    return kClassicSteelTrackSkin;
}

static_assert(kCoasterTrackSkinContract == std::string_view{"CH_COASTER_TRACK_SKIN_V1"});
static_assert(kClassicSteelTrackSkin.rail_body_width_px > kClassicSteelTrackSkin.rail_head_width_px);
static_assert(kClassicSteelTrackSkin.spine_body_width_px > kClassicSteelTrackSkin.rail_body_width_px);
static_assert(kClassicSteelTrackSkin.body_sprite_paths.size() == 4U);
static_assert(kClassicSteelTrackSkin.body_sprite_spacing_m == 3.0);

}  // namespace ch::coaster
