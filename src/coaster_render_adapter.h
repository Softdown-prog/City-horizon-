#pragma once

#include "coaster_train_runtime.h"
#include "src/ch_core/projection.h"

#include <array>
#include <cstddef>
#include <string_view>

namespace ch::coaster {

// CH_COASTER_RENDER_ADAPTER_V1
// Presentation-only bridge from the articulated train simulation to the
// existing 2D isometric renderer. It does not own textures or simulation state.
struct CarRenderCommand {
    std::size_t car_index = 0U;
    std::string_view atlas_path = kFlameCarPoseAtlasPath;
    AtlasSourceRect source_rect{};
    WorldPoint3 world_anchor{};
    float depth_key = 0.0F;
    int atlas_index = 0;
};

struct TrainRenderPlan {
    std::array<CarRenderCommand, kCoasterTrainCarCount> cars{};
    std::size_t car_count = 0U;
};

[[nodiscard]] inline TrainRenderPlan build_train_render_plan(
    const TrainStepResult& train,
    const CameraState& camera) noexcept {
    TrainRenderPlan plan;
    if (!train.valid) return plan;

    plan.car_count = kCoasterTrainCarCount;
    for (std::size_t i = 0; i < kCoasterTrainCarCount; ++i) {
        const CarRuntimePose& car = train.cars[i];
        CarRenderCommand& command = plan.cars[i];
        command.car_index = i;
        command.source_rect = car.sprite_pose.source_rect;
        command.world_anchor = {
            static_cast<float>(car.world_x),
            static_cast<float>(car.world_y),
            static_cast<float>(car.world_z),
        };
        // Height changes screen Y, never the ground-plane occlusion order.
        command.depth_key = camera_depth_key(
            command.world_anchor.x, command.world_anchor.y, camera);
        command.atlas_index = car.sprite_pose.atlas_index;
    }
    return plan;
}

[[nodiscard]] inline ScreenPoint project_car_anchor(
    const CarRenderCommand& command,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height) {
    return world_to_screen_point(
        command.world_anchor, camera, viewport_width, viewport_height);
}

// The approved atlas is rendered around the rail contact/root at the center of
// each 256x256 cell. Keeping this normalized anchor in the adapter means the
// live renderer and any debug/proof renderer cannot silently diverge.
inline constexpr float kFlameCarSpriteAnchorX = 0.5F;
inline constexpr float kFlameCarSpriteAnchorY = 0.5F;

}  // namespace ch::coaster
