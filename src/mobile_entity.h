#pragma once

#include <cstddef>
#include <cstdint>
#include <string>

// Shared vocabulary for any moving map entity. It deliberately contains no
// pathfinding, farming, vehicle, or renderer implementation details.
enum class MobileEntityDirection { south, east, north, west };

struct MobileClothingColor {
    std::uint8_t r = 255;
    std::uint8_t g = 255;
    std::uint8_t b = 255;
    [[nodiscard]] bool operator==(const MobileClothingColor&) const = default;
};

struct MobileClothingTint {
    bool enabled = false;
    MobileClothingColor jacket;
    MobileClothingColor pants;
    [[nodiscard]] bool operator==(const MobileClothingTint&) const = default;
};

struct MobileUmbrellaTint {
    bool enabled = false;
    MobileClothingColor fabric;
};

struct MobileEntitySpatialState {
    // The logical world position changes on the fixed simulation tick.
    float logical_world_x = 0.0F;
    float logical_world_y = 0.0F;
    int logical_tile_x = 0;
    int logical_tile_y = 0;

    // The visual position approaches the logical position every render frame.
    float visual_world_x = 0.0F;
    float visual_world_y = 0.0F;

    MobileEntityDirection direction = MobileEntityDirection::south;
    // Contact point inside the logical tile, used for isometric placement and
    // depth sorting. A centred entity therefore uses (0.5, 0.5).
    float ground_anchor_x = 0.5F;
    float ground_anchor_y = 0.5F;

    [[nodiscard]] float depth_sort_key() const {
        return visual_world_x + ground_anchor_x + visual_world_y + ground_anchor_y;
    }
};

// Renderer-facing description. The renderer receives the already-selected
// frame, never gameplay or animation-selection rules.
struct MobileEntityRenderData {
    MobileEntitySpatialState spatial;
    std::string logical_state;
    std::string sprite_asset;
    std::string animation_set_id;
    std::string animation_clip_id;
    std::size_t animation_frame_index = 0;
    float art_scale = 1.0F;
    float sprite_anchor_x = 0.5F;
    float sprite_anchor_y = 1.0F;
    MobileClothingTint clothing;
    MobileUmbrellaTint umbrella;
};
