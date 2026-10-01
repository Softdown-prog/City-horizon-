#include "rail_mapforge_input_adapter.h"

#include <array>
#include <cassert>
#include <cmath>

namespace {

constexpr float kTolerance = 0.0005F;

void assert_near(const float actual, const float expected) {
    assert(std::abs(actual - expected) < kTolerance);
}

void assert_round_trip(const ch::CameraState& camera, const float world_x, const float world_y) {
    constexpr float viewport_w = 1280.0F;
    constexpr float viewport_h = 720.0F;
    const ch::ScreenPoint screen = ch::world_to_screen_point(
        world_x, world_y, camera, viewport_w, viewport_h);
    const auto recovered = RailMapForgeInputAdapter::screen_to_world(
        screen.x, screen.y, camera, viewport_w, viewport_h);
    assert(recovered.has_value());
    assert_near(recovered->x, world_x);
    assert_near(recovered->y, world_y);
    assert_near(recovered->z, 0.0F);
}

} // namespace

int main() {
    const std::array<ch::CameraRotation, 4> rotations{
        ch::CameraRotation::r0,
        ch::CameraRotation::r90,
        ch::CameraRotation::r180,
        ch::CameraRotation::r270,
    };

    // The rail bridge must use the same continuous inverse as MapForge for all
    // quarter-turns, pan offsets and zoom levels.
    for (const ch::CameraRotation rotation : rotations) {
        ch::CameraState camera;
        camera.zoom = 1.37F;
        camera.pan_x = 83.0F;
        camera.pan_y = -47.0F;
        camera.rotation = rotation;
        assert_round_trip(camera, 3.25F, -6.75F);
        assert_round_trip(camera, -12.5F, 9.125F);
    }

    const RailProfile profile{};
    RailPlacementGraph graph(profile);
    const auto root = graph.add_root({0.0F, 0.0F, 0.0F}, 0.0F);
    assert(root.has_value());
    RailPlacementController controller(graph);
    RailDragAdapter drag(controller);
    RailMapForgeInputAdapter mapforge(drag);

    ch::CameraState camera;
    camera.zoom = 1.25F;
    camera.pan_x = 120.0F;
    camera.pan_y = -35.0F;
    camera.rotation = ch::CameraRotation::r90;
    constexpr float viewport_w = 1440.0F;
    constexpr float viewport_h = 900.0F;

    // Feed actual projected screen coordinates back through the bridge. A drag
    // from world (2,3) to (5,7) is exactly 5 world units, independent of the
    // camera transform.
    const ch::ScreenPoint start_screen = ch::world_to_screen_point(
        2.0F, 3.0F, camera, viewport_w, viewport_h);
    const ch::ScreenPoint end_screen = ch::world_to_screen_point(
        5.0F, 7.0F, camera, viewport_w, viewport_h);

    assert(mapforge.begin(*root, RailPlacementMode::straight,
                          start_screen.x, start_screen.y,
                          camera, viewport_w, viewport_h));
    const auto preview = mapforge.update(
        end_screen.x, end_screen.y, camera, viewport_w, viewport_h);
    assert(preview.has_value() && preview->ok());
    assert(graph.nodes().size() == 2U);
    assert(graph.edges().size() == 1U);
    const RailPlacementNode* end = graph.node(preview->primary_node);
    assert(end != nullptr);
    assert_near(end->position.x, 5.0F); // root heading east + 5 world units
    assert_near(end->position.y, 0.0F);

    // A second screen-space mouse move replaces the previous preview. The graph
    // remains one staged edge until confirmation.
    const ch::ScreenPoint farther_screen = ch::world_to_screen_point(
        8.0F, 11.0F, camera, viewport_w, viewport_h);
    const auto farther = mapforge.update(
        farther_screen.x, farther_screen.y, camera, viewport_w, viewport_h);
    assert(farther.has_value() && farther->ok());
    assert(graph.nodes().size() == 2U);
    assert(graph.edges().size() == 1U);
    assert(mapforge.confirm());
    assert(!mapforge.active());

    // Invalid viewport/camera/screen data is rejected before it can reach the
    // rail transaction.
    assert(!RailMapForgeInputAdapter::screen_to_world(
        10.0F, 20.0F, camera, 0.0F, viewport_h).has_value());
    assert(!RailMapForgeInputAdapter::screen_to_world(
        std::nanf(""), 20.0F, camera, viewport_w, viewport_h).has_value());
    ch::CameraState bad_camera = camera;
    bad_camera.zoom = 0.0F;
    assert(!RailMapForgeInputAdapter::screen_to_world(
        10.0F, 20.0F, bad_camera, viewport_w, viewport_h).has_value());

    return 0;
}
