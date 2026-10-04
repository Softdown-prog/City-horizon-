#pragma once

#include "coaster_track_geometry.h"
#include "coaster_train_runtime.h"
#include "src/ch_core/projection.h"

#include <array>
#include <cstddef>
#include <string_view>
#include <vector>

namespace ch::coaster {

// CH_COASTER_WORLD_SCALE_V1
// Coaster simulation/centerline data is authored in metres. City Horizon's
// canonical isometric camera projects world coordinates in tile-sized world
// units, and one gameplay tile represents 3 metres for coaster projects.
// Conversion belongs at this presentation boundary so physics never silently
// changes units and the track/train always share the exact same transform.
inline constexpr float kCoasterMetersPerWorldUnit = 3.0F;
inline constexpr float kCoasterWorldUnitsPerMeter = 1.0F / kCoasterMetersPerWorldUnit;
inline constexpr const char* kCoasterWorldScaleContract = "CH_COASTER_WORLD_SCALE_V1";

[[nodiscard]] constexpr WorldPoint3 coaster_meters_to_world(
    const double x_m,
    const double y_m,
    const double z_m) noexcept {
    return {
        static_cast<float>(x_m) * kCoasterWorldUnitsPerMeter,
        static_cast<float>(y_m) * kCoasterWorldUnitsPerMeter,
        static_cast<float>(z_m) * kCoasterWorldUnitsPerMeter,
    };
}

// SDL-facing rectangle shape kept independent from SDL so the adapter remains
// testable in the lightweight coaster regression job.
struct AtlasSourceRect {
    int x = 0;
    int y = 0;
    int width = kCarPoseFrameWidth;
    int height = kCarPoseFrameHeight;
};

// CH_COASTER_RENDER_ADAPTER_V2
// Presentation-only bridge from the articulated train simulation and dedicated
// coaster track geometry to the existing 2D isometric renderer. It does not own
// textures or simulation state. V2 explicitly converts coaster metres to the
// game's canonical world/tile units before camera projection.
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

enum class TrackLineKind {
    support,
    spine,
    tie,
    left_rail,
    right_rail,
};

struct TrackLineRenderCommand {
    TrackLineKind kind = TrackLineKind::spine;
    WorldPoint3 world_a{};
    WorldPoint3 world_b{};
    float depth_key = 0.0F;
};

struct TrackRenderPlan {
    std::vector<TrackLineRenderCommand> lines;
};

struct TrackScreenLine {
    ScreenPoint a{};
    ScreenPoint b{};
    TrackLineKind kind = TrackLineKind::spine;
    float depth_key = 0.0F;
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
        command.source_rect = {
            car.sprite_pose.source_rect.x,
            car.sprite_pose.source_rect.y,
            car.sprite_pose.source_rect.w,
            car.sprite_pose.source_rect.h,
        };
        command.world_anchor = coaster_meters_to_world(
            car.world_x, car.world_y, car.world_z);
        // Height changes screen Y, never the ground-plane occlusion order.
        command.depth_key = camera_depth_key(
            command.world_anchor.x, command.world_anchor.y, camera);
        command.atlas_index = car.sprite_pose.atlas_index;
    }
    return plan;
}

[[nodiscard]] inline WorldPoint3 coaster_track_world_point(
    const CoasterTrackPoint3& point) noexcept {
    return coaster_meters_to_world(point.x, point.y, point.z);
}

inline void append_track_line(
    TrackRenderPlan& plan,
    const TrackLineKind kind,
    const CoasterTrackPoint3& a,
    const CoasterTrackPoint3& b,
    const CameraState& camera) {
    const WorldPoint3 wa = coaster_track_world_point(a);
    const WorldPoint3 wb = coaster_track_world_point(b);
    const float da = camera_depth_key(wa.x, wa.y, camera);
    const float db = camera_depth_key(wb.x, wb.y, camera);
    plan.lines.push_back({kind, wa, wb, (da + db) * 0.5F});
}

[[nodiscard]] inline TrackRenderPlan build_track_render_plan(
    const CoasterTrackGeometry& geometry,
    const CameraState& camera) {
    TrackRenderPlan plan;
    if (!geometry.valid()) return plan;

    const std::size_t frame_segments =
        geometry.closed ? geometry.frames.size() : geometry.frames.size() - 1U;
    plan.lines.reserve(
        geometry.supports.size() +
        geometry.ties.size() +
        frame_segments * 3U);

    for (const CoasterSupport& support : geometry.supports) {
        append_track_line(
            plan, TrackLineKind::support, support.bottom, support.top, camera);
    }
    for (const CoasterCrossTie& tie : geometry.ties) {
        append_track_line(
            plan, TrackLineKind::tie, tie.left, tie.right, camera);
    }

    for (std::size_t i = 0; i < frame_segments; ++i) {
        const std::size_t next = (i + 1U) % geometry.frames.size();
        const CoasterTrackFrame& a = geometry.frames[i];
        const CoasterTrackFrame& b = geometry.frames[next];
        append_track_line(
            plan, TrackLineKind::spine, a.spine, b.spine, camera);
        append_track_line(
            plan, TrackLineKind::left_rail, a.left_rail, b.left_rail, camera);
        append_track_line(
            plan, TrackLineKind::right_rail, a.right_rail, b.right_rail, camera);
    }
    return plan;
}

[[nodiscard]] inline TrackScreenLine project_track_line(
    const TrackLineRenderCommand& command,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height) {
    return {
        world_to_screen_point(command.world_a, camera, viewport_width, viewport_height),
        world_to_screen_point(command.world_b, camera, viewport_width, viewport_height),
        command.kind,
        command.depth_key,
    };
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

static_assert(kCoasterMetersPerWorldUnit == 3.0F);
static_assert(kCoasterWorldUnitsPerMeter > 0.3333F &&
              kCoasterWorldUnitsPerMeter < 0.3334F);

}  // namespace ch::coaster
