#pragma once

#include "src/ch_core/procedural_tile_2d.h"

#include <array>
#include <cmath>
#include <filesystem>
#include <optional>
#include <string>
#include <string_view>

namespace ch {

// CH_PATH_SLOPE_SPRITE_V1
//
// The runtime never paints artistic stairs from procedural geometry. It uses
// CH_TERRAIN_HEIGHTFIELD_V1 only to choose one of the approved offline-baked
// PNGs. The exact bake recipe is documented in docs/CH_PATH_SLOPE_SPRITE_V1.md.
inline constexpr std::string_view kPathSlopeSpriteContract = "CH_PATH_SLOPE_SPRITE_V1";
inline constexpr float kPathSlopeLegacySurfaceY = 32.0F;

struct PathSlopeSpriteFamily {
    std::string_view material_id;
    std::string_view prefix;
    std::string_view directory;
};

inline constexpr PathSlopeSpriteFamily kDirtPathSlopeFamily = {
    "dirt_01",
    "dirt_path",
    "assets/terrain/paths/dirt_01",
};

inline constexpr PathSlopeSpriteFamily kSandPathSlopeFamily = {
    "sand_01",
    "sand_path",
    "assets/terrain/paths/sand_01",
};

struct PathSlopeSpriteSelection {
    std::filesystem::path path;
    float base_height = 0.0F;
    float rise_units = 0.0F;
};

[[nodiscard]] inline std::string ground_path_flat_filename(
    const PathSlopeSpriteFamily& family,
    const TileConnectionMask visual_connections
) {
    static constexpr std::array<std::string_view, 16> kSuffixes = {
        "00_isolated.png",
        "01_end_n.png",
        "02_end_e.png",
        "03_curve_ne.png",
        "04_end_s.png",
        "05_straight_ns.png",
        "06_curve_es.png",
        "07_tee_no_w.png",
        "08_end_w.png",
        "09_curve_nw.png",
        "10_straight_ew.png",
        "11_tee_no_s.png",
        "12_curve_sw.png",
        "13_tee_no_e.png",
        "14_tee_no_n.png",
        "15_cross.png",
    };

    const std::size_t index = static_cast<std::size_t>(visual_connections & 0x0F);
    return std::string(family.directory) + "/" + std::string(family.prefix) + "_" +
           std::string(kSuffixes.at(index));
}

[[nodiscard]] inline std::optional<std::string_view> path_slope_axis(
    const TileConnectionMask visual_connections
) {
    const TileConnectionMask ns = connection_bit(CardinalDirection::north) |
                                  connection_bit(CardinalDirection::south);
    const TileConnectionMask ew = connection_bit(CardinalDirection::east) |
                                  connection_bit(CardinalDirection::west);
    if (visual_connections == ns) return std::string_view{"ns"};
    if (visual_connections == ew) return std::string_view{"ew"};
    return std::nullopt;
}

[[nodiscard]] inline std::string_view path_slope_high_end_name(
    const CardinalDirection visual_high_edge
) {
    switch (visual_high_edge) {
        case CardinalDirection::north: return "n";
        case CardinalDirection::east: return "e";
        case CardinalDirection::south: return "s";
        case CardinalDirection::west: return "w";
    }
    return "n";
}

[[nodiscard]] inline bool path_slope_high_end_matches_axis(
    const std::string_view axis,
    const CardinalDirection visual_high_edge
) {
    if (axis == "ns") {
        return visual_high_edge == CardinalDirection::north ||
               visual_high_edge == CardinalDirection::south;
    }
    if (axis == "ew") {
        return visual_high_edge == CardinalDirection::east ||
               visual_high_edge == CardinalDirection::west;
    }
    return false;
}

[[nodiscard]] inline std::string_view nearest_path_slope_profile(
    const ProceduralTileRecipe& recipe
) {
    if (recipe.vertical_profile == ProceduralTileVerticalProfile::ramp) {
        return recipe.height_delta <= 0.375F ? "ramp_025" : "ramp_050";
    }
    if (recipe.vertical_profile == ProceduralTileVerticalProfile::stairs) {
        if (recipe.height_delta <= 0.625F) return "stairs_050_4";
        if (recipe.height_delta <= 0.875F) return "stairs_075_6";
        return "stairs_100_8";
    }
    return {};
}

[[nodiscard]] inline float path_slope_profile_rise_units(const std::string_view profile) {
    if (profile == "ramp_025") return 0.25F;
    if (profile == "ramp_050" || profile == "stairs_050_4") return 0.50F;
    if (profile == "stairs_075_6") return 0.75F;
    if (profile == "stairs_100_8") return 1.00F;
    return 0.0F;
}

[[nodiscard]] inline std::optional<PathSlopeSpriteSelection> select_path_slope_sprite(
    const PathSlopeSpriteFamily& family,
    const ProceduralTileRecipe& recipe,
    const TileConnectionMask visual_connections,
    const CardinalDirection visual_high_edge
) {
    if (recipe.vertical_profile == ProceduralTileVerticalProfile::flat ||
        recipe.topology != ProceduralTileTopology::straight) {
        return std::nullopt;
    }

    const auto axis = path_slope_axis(visual_connections);
    if (!axis.has_value() || !path_slope_high_end_matches_axis(*axis, visual_high_edge)) {
        return std::nullopt;
    }

    const std::string_view profile = nearest_path_slope_profile(recipe);
    if (profile.empty()) return std::nullopt;

    PathSlopeSpriteSelection selection;
    selection.base_height = recipe.min_height;
    selection.rise_units = path_slope_profile_rise_units(profile);
    selection.path = std::filesystem::path(std::string(family.directory)) /
        "slopes" /
        (std::string(family.prefix) + "_straight_" + std::string(*axis) + "_" +
         std::string(profile) + "_high_" + std::string(path_slope_high_end_name(visual_high_edge)) + ".png");
    return selection;
}

} // namespace ch
