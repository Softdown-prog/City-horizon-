#include "coaster_render_adapter.h"

#include <cmath>
#include <iostream>

namespace {

int fail(const char* message) {
    std::cerr << "coaster_render_adapter_test: " << message << '\n';
    return 1;
}

bool near(const float a, const float b, const float epsilon = 0.001F) {
    return std::abs(a - b) <= epsilon;
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

    std::cout << "CH_COASTER_RENDER_ADAPTER_V2 regression: OK\n";
    return 0;
}
