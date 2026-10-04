#pragma once

#include <string_view>

namespace ch::coaster {

// CH_COASTER_TRACK_SKIN_V1
// Visual-only skin contract layered on top of CH_COASTER_TRACK_GEOMETRY_V1.
// The centerline, physics, gauge, ties and support placement remain procedural
// and authoritative. A skin may change material language without changing the
// ride layout. This also leaves a stable seam for future Blender-baked modules.
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

    // Detail atlas retained for the approved joint/lift/brake modules, but it
    // stays disabled until the complete Blender track-body skin is approved.
    // This prevents the temporary vector body + baked details combination from
    // being mistaken for the final hybrid visual.
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

}  // namespace ch::coaster
