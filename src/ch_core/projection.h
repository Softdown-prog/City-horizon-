#ifndef CITY_HORIZON_CH_CORE_PROJECTION_H
#define CITY_HORIZON_CH_CORE_PROJECTION_H

#include "src/ch_core/contracts.h"
#include "src/ch_core/grid.h"
#include <cmath>
#include <string_view>

namespace ch {

enum class CameraRotation { r0 = 0, r90 = 1, r180 = 2, r270 = 3 };

struct CameraState {
    float pan_x = 0.0F;
    float pan_y = 0.0F;
    float zoom = 1.0F;
    CameraRotation rotation = CameraRotation::r0;
};

struct WorldPoint {
    float x = 0.0F;
    float y = 0.0F;
};

// Optional elevation coordinate for geometry that genuinely needs height in the
// otherwise-2D runtime. Ground tiles, sprites and existing systems remain on the
// original WorldPoint contract. Procedural roads/bridges can opt into Z without
// changing the canonical camera or turning the whole game into a 3D runtime.
struct WorldPoint3 {
    float x = 0.0F;
    float y = 0.0F;
    float z = 0.0F;
};

struct ScreenPoint {
    float x = 0.0F;
    float y = 0.0F;
};

// CH_CAMERA_V1 is a 45-degree yaw / 30-degree elevation orthographic view. The
// existing 128x64 ground projection implies this screen-space scale for one
// world unit of pure vertical elevation. Keeping it here makes roads, bridges
// and future elevated geometry share one canonical Z projection.
inline constexpr float kWorldElevationPixelsPerUnit = contracts::kTileWidth * 0.6123724357F;

// CH_ISOMETRIC_OCCLUSION_V1
//
// World depth always comes from the ground/contact plane after applying the
// current camera quarter-turn. Dynamic entities sort by their ground anchor.
// A building is a single pre-rendered sprite, so it sorts at the front-most
// corner of its complete visual footprint. This deliberately makes the whole
// sprite occlude entities that are still behind that front boundary while an
// entity reaching the same boundary may be drawn in front by the stable world
// draw queue. Keeping this rule here prevents camera rotations and large
// footprints from inventing independent depth conventions.
inline constexpr std::string_view kIsometricOcclusionContract = "CH_ISOMETRIC_OCCLUSION_V1";

struct WorldDepthSpan {
    float back = 0.0F;
    float front = 0.0F;
};

[[nodiscard]] constexpr WorldPoint camera_view_point(const float x, const float y, const CameraRotation rotation) {
    switch (rotation) {
        case CameraRotation::r0: return {x, y};
        case CameraRotation::r90: return {y, -x};
        case CameraRotation::r180: return {-x, -y};
        case CameraRotation::r270: return {-y, x};
    }
    return {x, y};
}

[[nodiscard]] constexpr WorldPoint logical_world_point(const float x, const float y, const CameraRotation rotation) {
    switch (rotation) {
        case CameraRotation::r0: return {x, y};
        case CameraRotation::r90: return {-y, x};
        case CameraRotation::r180: return {-x, -y};
        case CameraRotation::r270: return {y, -x};
    }
    return {x, y};
}

[[nodiscard]] constexpr float camera_depth_key_for_rotation(const float world_x, const float world_y,
                                                            const CameraRotation rotation) {
    const WorldPoint view = camera_view_point(world_x, world_y, rotation);
    return view.x + view.y;
}

[[nodiscard]] constexpr WorldPoint tile_visual_top_world(const int tile_x, const int tile_y, const CameraRotation rotation) {
    switch (rotation) {
        case CameraRotation::r0: return {static_cast<float>(tile_x), static_cast<float>(tile_y)};
        case CameraRotation::r90: return {static_cast<float>(tile_x + 1), static_cast<float>(tile_y)};
        case CameraRotation::r180: return {static_cast<float>(tile_x + 1), static_cast<float>(tile_y + 1)};
        case CameraRotation::r270: return {static_cast<float>(tile_x), static_cast<float>(tile_y + 1)};
    }
    return {static_cast<float>(tile_x), static_cast<float>(tile_y)};
}

[[nodiscard]] constexpr WorldDepthSpan building_depth_span(const int tile_x, const int tile_y,
                                                           const int footprint_width, const int footprint_height,
                                                           const CameraRotation rotation) {
    const float x0 = static_cast<float>(tile_x);
    const float y0 = static_cast<float>(tile_y);
    const float x1 = static_cast<float>(tile_x + footprint_width);
    const float y1 = static_cast<float>(tile_y + footprint_height);

    const float d0 = camera_depth_key_for_rotation(x0, y0, rotation);
    const float d1 = camera_depth_key_for_rotation(x1, y0, rotation);
    const float d2 = camera_depth_key_for_rotation(x0, y1, rotation);
    const float d3 = camera_depth_key_for_rotation(x1, y1, rotation);

    float back = d0;
    float front = d0;
    if (d1 < back) back = d1;
    if (d2 < back) back = d2;
    if (d3 < back) back = d3;
    if (d1 > front) front = d1;
    if (d2 > front) front = d2;
    if (d3 > front) front = d3;
    return {back, front};
}

[[nodiscard]] constexpr WorldPoint building_visual_ground_world(const int tile_x, const int tile_y,
                                                                 const int footprint_width, const int footprint_height,
                                                                 const CameraRotation rotation) {
    const WorldPoint corners[4] = {
        {static_cast<float>(tile_x), static_cast<float>(tile_y)},
        {static_cast<float>(tile_x + footprint_width), static_cast<float>(tile_y)},
        {static_cast<float>(tile_x), static_cast<float>(tile_y + footprint_height)},
        {static_cast<float>(tile_x + footprint_width), static_cast<float>(tile_y + footprint_height)},
    };

    WorldPoint front = corners[0];
    float front_depth = camera_depth_key_for_rotation(front.x, front.y, rotation);
    for (int index = 1; index < 4; ++index) {
        const float depth = camera_depth_key_for_rotation(corners[index].x, corners[index].y, rotation);
        if (depth > front_depth) {
            front = corners[index];
            front_depth = depth;
        }
    }
    return front;
}

[[nodiscard]] constexpr float camera_depth_key(const float world_x, const float world_y, const CameraState& camera) {
    return camera_depth_key_for_rotation(world_x, world_y, camera.rotation);
}

[[nodiscard]] constexpr bool depth_is_at_or_in_front_of_building(const float depth,
                                                                  const WorldDepthSpan span) {
    return depth >= span.front;
}

// Compile-time guards for the large-footprint rule on every camera quarter-turn.
// A 5x4 attraction is intentionally used here because this is where a single
// arbitrary tile anchor would produce the most obvious occlusion regressions.
static_assert(building_depth_span(10, 20, 5, 4, CameraRotation::r0).back == 30.0F);
static_assert(building_depth_span(10, 20, 5, 4, CameraRotation::r0).front == 39.0F);
static_assert(building_depth_span(10, 20, 5, 4, CameraRotation::r90).back == 5.0F);
static_assert(building_depth_span(10, 20, 5, 4, CameraRotation::r90).front == 14.0F);
static_assert(building_depth_span(10, 20, 5, 4, CameraRotation::r180).back == -39.0F);
static_assert(building_depth_span(10, 20, 5, 4, CameraRotation::r180).front == -30.0F);
static_assert(building_depth_span(10, 20, 5, 4, CameraRotation::r270).back == -14.0F);
static_assert(building_depth_span(10, 20, 5, 4, CameraRotation::r270).front == -5.0F);

[[nodiscard]] ScreenPoint world_to_screen_point(float world_x, float world_y, const CameraState& camera, float viewport_w, float viewport_h);

// Elevated overload used only by geometry that carries real Z. Z never changes
// logical tile selection or ground-plane depth; it only lifts the projected
// screen position. That preserves the existing 2D simulation contract.
[[nodiscard]] ScreenPoint world_to_screen_point(float world_x, float world_y, float world_z,
                                                const CameraState& camera, float viewport_w, float viewport_h);

[[nodiscard]] inline ScreenPoint world_to_screen_point(const WorldPoint3& world, const CameraState& camera,
                                                       const float viewport_w, const float viewport_h) {
    return world_to_screen_point(world.x, world.y, world.z, camera, viewport_w, viewport_h);
}

// Continuous inverse of the canonical ground projection. Editor gizmos use
// this when handles must move freely between tile centres. Tile picking remains
// a thin floor() wrapper around the same function, so tools cannot drift into a
// second inverse-projection convention.
[[nodiscard]] WorldPoint screen_to_world_point(float screen_x, float screen_y, const CameraState& camera,
                                               float viewport_w, float viewport_h);

[[nodiscard]] GridCoord screen_to_tile_coord(float screen_x, float screen_y, const CameraState& camera, float viewport_w, float viewport_h);

} // namespace ch

#endif // CITY_HORIZON_CH_CORE_PROJECTION_H
