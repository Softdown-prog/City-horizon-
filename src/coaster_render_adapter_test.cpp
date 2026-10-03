#include "coaster_render_adapter.h"

#include <algorithm>
#include <cmath>
#include <iostream>
#include <vector>

namespace {

int fail(const char* message) {
    std::cerr << "coaster_render_adapter_test: " << message << '\n';
    return 1;
}

bool near(const float a, const float b, const float epsilon = 0.001F) {
    return std::abs(a - b) <= epsilon;
}

double planar_distance(const ch::coaster::CoasterTrackPoint3& a,
                       const ch::coaster::CoasterTrackPoint3& b) {
    return std::hypot(b.x - a.x, b.y - a.y);
}

}  // namespace

int main() {
    using namespace ch;
    using namespace ch::coaster;

    TrainStepResult train;
    train.valid = true;
    for (std::size_t i = 0; i < kCoasterTrainCarCount; ++i) {
        CarRuntimePose& car = train.cars[i];
        car.world_x = 10.0 + static_cast<double>(i);
        car.world_y = 20.0 + static_cast<double>(i) * 0.5;
        car.world_z = 3.0 + static_cast<double>(i) * 0.25;
        car.sprite_pose = select_car_pose(static_cast<double>(i) * 22.5, 0.0, 0);
    }

    CameraState camera;
    camera.rotation = CameraRotation::r0;
    const TrainRenderPlan plan = build_train_render_plan(train, camera);
    if (plan.car_count != kCoasterTrainCarCount) return fail("valid train must emit four render commands");

    for (std::size_t i = 0; i < kCoasterTrainCarCount; ++i) {
        const CarRenderCommand& command = plan.cars[i];
        const int expected_atlas_index = 48 + static_cast<int>(i);
        const int expected_x = static_cast<int>(i) * kCarPoseFrameWidth;
        const int expected_y = 3 * kCarPoseFrameHeight;
        if (command.car_index != i) return fail("car ordering changed");
        if (command.atlas_path != kFlameCarPoseAtlasPath) return fail("unexpected V2 atlas path");
        if (command.atlas_index != expected_atlas_index) return fail("V2 flat heading atlas mapping changed");
        if (command.source_rect.x != expected_x || command.source_rect.y != expected_y)
            return fail("V2 flat heading source rectangle changed");
        if (command.source_rect.width != kCarPoseFrameWidth || command.source_rect.height != kCarPoseFrameHeight)
            return fail("atlas source rectangle dimensions changed");
        if (!near(command.world_anchor.x, 10.0F + static_cast<float>(i))) return fail("world X changed");
        if (!near(command.world_anchor.z, 3.0F + static_cast<float>(i) * 0.25F)) return fail("world Z changed");
    }

    const float r0_depth = plan.cars[0].depth_key;
    camera.rotation = CameraRotation::r90;
    const TrainRenderPlan rotated = build_train_render_plan(train, camera);
    if (near(r0_depth, rotated.cars[0].depth_key)) return fail("camera rotation must alter ground depth ordering");

    TrainStepResult invalid;
    if (build_train_render_plan(invalid, camera).car_count != 0U)
        return fail("invalid train must not emit render commands");

    if (!near(kFlameCarSpriteAnchorX, 0.5F) || !near(kFlameCarSpriteAnchorY, 0.5F))
        return fail("approved atlas root anchor changed");

    // A tall elevated span must produce structural support members rather than
    // the former single vertical stick. The geometry contract owns this shape,
    // and the render adapter must expose every member to the SDL world renderer.
    CenterlineRoute support_route;
    std::vector<RoutePoint> support_points = {
        {0.0, 0.0, 8.0},
        {12.0, 0.0, 8.0},
    };
    if (!support_route.rebuild(support_points, false))
        return fail("elevated support route must validate");

    CoasterTrackStyle support_style;
    support_style.support_spacing_m = 6.0;
    const CoasterTrackGeometry support_geometry =
        build_coaster_track_geometry(support_route, support_style, 0.0);
    if (!support_geometry.valid())
        return fail("elevated route must produce coaster geometry");
    if (support_geometry.supports.size() < 9U)
        return fail("tall coaster span did not expand into A-frame/tower members");

    bool saw_ground_leg = false;
    bool saw_upper_beam = false;
    bool saw_diagonal_brace = false;
    for (const CoasterSupport& member : support_geometry.supports) {
        const CoasterTrackPoint3& a = member.top;
        const CoasterTrackPoint3& b = member.bottom;
        const bool a_ground = std::abs(a.z) <= 0.001;
        const bool b_ground = std::abs(b.z) <= 0.001;
        const double xy = planar_distance(a, b);
        const double dz = std::abs(a.z - b.z);

        saw_ground_leg = saw_ground_leg ||
            ((a_ground && b.z > 1.0) || (b_ground && a.z > 1.0));
        saw_upper_beam = saw_upper_beam ||
            (a.z > 0.5 && b.z > 0.5 && dz <= 0.05 && xy > 0.5);
        saw_diagonal_brace = saw_diagonal_brace ||
            (xy > 0.2 && dz > 0.5);
    }
    if (!saw_ground_leg)
        return fail("A-frame support is missing splayed ground legs");
    if (!saw_upper_beam)
        return fail("A-frame/tower support is missing an elevated cross beam");
    if (!saw_diagonal_brace)
        return fail("tall tower support is missing diagonal bracing");

    CameraState support_camera;
    const TrackRenderPlan support_plan =
        build_track_render_plan(support_geometry, support_camera);
    const auto support_line_count = static_cast<std::size_t>(std::count_if(
        support_plan.lines.begin(), support_plan.lines.end(),
        [](const TrackLineRenderCommand& line) {
            return line.kind == TrackLineKind::support;
        }));
    if (support_line_count != support_geometry.supports.size())
        return fail("render adapter dropped coaster support members");

    std::cout << "CH_COASTER_RENDER_ADAPTER_V2 regression: OK\n";
    std::cout << "support_members=" << support_geometry.supports.size()
              << " support_render_lines=" << support_line_count << '\n';
    return 0;
}
