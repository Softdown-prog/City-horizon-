#include "coaster_car_pose.h"

#include <cmath>
#include <iostream>

namespace {

int fail(const char* message) {
    std::cerr << "coaster_car_pose_test: " << message << '\n';
    return 1;
}

bool near(const double a, const double b, const double tolerance = 0.05) {
    return std::abs(a - b) <= tolerance;
}

}  // namespace

int main() {
    using namespace ch::coaster;

    if (heading_index_from_degrees(0.0) != 0) return fail("0 degrees must map to h00");
    if (heading_index_from_degrees(22.5) != 1) return fail("22.5 degrees must map to h01");
    if (heading_index_from_degrees(337.5) != 15) return fail("337.5 degrees must map to h15");
    if (heading_index_from_degrees(360.0) != 0) return fail("360 degrees must wrap to h00");
    if (heading_index_from_degrees(-22.5) != 15) return fail("negative heading must wrap correctly");

    if (!near(heading_degrees_from_tangent(0.0, 1.0), 0.0))
        return fail("+Y tangent must be authored heading 0");
    if (!near(heading_degrees_from_tangent(-1.0, 0.0), 90.0))
        return fail("-X tangent must be authored heading 90");
    if (!near(heading_degrees_from_tangent(0.0, -1.0), 180.0))
        return fail("-Y tangent must be authored heading 180");
    if (!near(heading_degrees_from_tangent(1.0, 0.0), 270.0))
        return fail("+X tangent must be authored heading 270");

    constexpr double kSqrtHalf = 0.7071067811865476;
    const CarPoseSelection diagonal = select_car_pose_from_tangent(-kSqrtHalf, kSqrtHalf, 0.0);
    if (diagonal.atlas_index != 2 || diagonal.visual_heading_index != 2)
        return fail("45-degree flat tangent must select h02");

    const CarPoseSelection h15 = select_car_pose(337.5, 0.0);
    if (h15.atlas_index != 15 || h15.row != 1 || h15.column != 7)
        return fail("h15 atlas location changed unexpectedly");
    if (h15.source_rect.x != 1792 || h15.source_rect.y != 256)
        return fail("h15 source rectangle changed unexpectedly");

    // One camera quarter-turn subtracts 90 degrees, matching the existing
    // RuntimeMapRenderer camera visual-orientation convention.
    const CarPoseSelection camera_rotated = select_car_pose(90.0, 0.0, 1);
    if (camera_rotated.logical_heading_index != 4 || camera_rotated.visual_heading_index != 0 ||
        camera_rotated.atlas_index != 0)
        return fail("camera quarter-turn must rotate h04 visually to h00");

    constexpr double kCos30 = 0.8660254037844386;
    constexpr double kSin30 = 0.5;
    const CarPoseSelection uphill30 = select_car_pose_from_tangent(0.0, kCos30, kSin30);
    if (!uphill30.vertical_supplement || uphill30.atlas_index != 32 ||
        !near(uphill30.snapped_pitch_degrees, 30.0))
        return fail("+30 degree h00 slope must select atlas frame 32");
    if (uphill30.row != 4 || uphill30.column != 0 ||
        uphill30.source_rect.x != 0 || uphill30.source_rect.y != 1024)
        return fail("+30 degree h00 source rectangle changed unexpectedly");

    const CarPoseSelection downhill30 = select_car_pose_from_tangent(0.0, kCos30, -kSin30);
    if (!downhill30.vertical_supplement || downhill30.atlas_index != 20 ||
        !near(downhill30.snapped_pitch_degrees, -30.0))
        return fail("-30 degree h00 slope must select atlas frame 20");
    if (downhill30.row != 2 || downhill30.column != 4 ||
        downhill30.source_rect.x != 1024 || downhill30.source_rect.y != 512)
        return fail("-30 degree h00 source rectangle changed unexpectedly");

    // +30 degrees at authored h04 occupies the second cardinal slot for the p030 bin.
    const CarPoseSelection h04_uphill30 = select_car_pose(90.0, 30.0);
    if (h04_uphill30.atlas_index != 33 || h04_uphill30.visual_heading_index != 4)
        return fail("+30 degree h04 slope must select atlas frame 33");

    // After a 90-degree camera rotation the same logical h04 slope uses visual h00.
    const CarPoseSelection h04_uphill30_rotated = select_car_pose(90.0, 30.0, 1);
    if (h04_uphill30_rotated.atlas_index != 32 || h04_uphill30_rotated.visual_heading_index != 0)
        return fail("camera rotation must also rotate cardinal slope pose selection");

    // Tiny grade noise should not cause flat/slope frame flicker.
    const CarPoseSelection almost_flat = select_car_pose(45.0, 3.0);
    if (almost_flat.vertical_supplement || almost_flat.atlas_index != 2)
        return fail("small pitch must remain in the flat 16-way family");

    // Non-cardinal steep input is unsupported by current track V1, so the runtime
    // intentionally falls back to the nearest cardinal vertical supplement.
    const CarPoseSelection fallback = select_car_pose(67.5, 46.0);
    if (!fallback.vertical_supplement || !fallback.snapped_to_cardinal_heading ||
        fallback.visual_heading_index != 4 || fallback.atlas_index != 37)
        return fail("non-cardinal steep pose fallback must be deterministic");

    if (kCarPoseAtlasColumns * kCarPoseAtlasRows != kCarPoseFrameCount)
        return fail("atlas dimensions must contain exactly 40 frames");

    std::cout << "CH_COASTER_CAR_ATLAS_RUNTIME_V1 regression: OK\n";
    return 0;
}
