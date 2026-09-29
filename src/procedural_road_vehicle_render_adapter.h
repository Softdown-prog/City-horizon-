#pragma once

#include "mobile_entity.h"
#include "procedural_road_vehicle_follower.h"

#include <cmath>
#include <string>
#include <string_view>

// CH_PROCEDURAL_ROAD_VEHICLE_RENDER_ADAPTER_V1
//
// Converts a logical procedural-road vehicle pose into the renderer-facing
// MobileEntityRenderData contract. Camera rotation remains a renderer concern;
// this adapter reports only logical world direction. The procedural lane point
// is already the exact ground contact position, so ground_anchor is (0,0).
struct ProceduralRoadVehicleVisual {
    std::string sprite_south;
    std::string sprite_east;
    std::string sprite_north;
    std::string sprite_west;
    std::string animation_set_id;
    float art_scale = 1.0F;
    float sprite_anchor_x = 0.5F;
    float sprite_anchor_y = 0.88F;

    [[nodiscard]] const std::string& sprite_for(const MobileEntityDirection direction) const {
        switch (direction) {
            case MobileEntityDirection::south: return sprite_south;
            case MobileEntityDirection::east: return sprite_east;
            case MobileEntityDirection::north: return sprite_north;
            case MobileEntityDirection::west: return sprite_west;
        }
        return sprite_south;
    }
};

class ProceduralRoadVehicleRenderAdapter {
public:
    [[nodiscard]] static MobileEntityDirection direction_from_forward(const RoadWorldPoint3 forward) {
        if (std::fabs(forward.x) >= std::fabs(forward.y)) {
            return forward.x >= 0.0F ? MobileEntityDirection::east : MobileEntityDirection::west;
        }
        return forward.y >= 0.0F ? MobileEntityDirection::south : MobileEntityDirection::north;
    }

    [[nodiscard]] static MobileEntityRenderData make_render_data(
        const ProceduralRoadVehiclePose& pose,
        const ProceduralRoadVehicleVisual& visual,
        const std::string_view logical_state = "moving") {
        MobileEntityRenderData entity;
        entity.spatial.logical_world_x = pose.position.x;
        entity.spatial.logical_world_y = pose.position.y;
        entity.spatial.logical_world_z = pose.position.z;
        entity.spatial.logical_tile_x = static_cast<int>(std::floor(pose.position.x));
        entity.spatial.logical_tile_y = static_cast<int>(std::floor(pose.position.y));
        entity.spatial.visual_world_x = pose.position.x;
        entity.spatial.visual_world_y = pose.position.y;
        entity.spatial.visual_world_z = pose.position.z;
        entity.spatial.direction = direction_from_forward(pose.forward);
        entity.spatial.ground_anchor_x = 0.0F;
        entity.spatial.ground_anchor_y = 0.0F;

        entity.logical_state = std::string(logical_state);
        entity.sprite_asset = visual.sprite_for(entity.spatial.direction);
        entity.animation_set_id = visual.animation_set_id;
        entity.art_scale = visual.art_scale;
        entity.sprite_anchor_x = visual.sprite_anchor_x;
        entity.sprite_anchor_y = visual.sprite_anchor_y;
        return entity;
    }
};
