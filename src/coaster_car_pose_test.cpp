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
    if (diagonal.atlas_index != 50 || diagonal.visual_heading_index != 2)
        return fail("45-degree flat tangent must select V2 flat h02");

    const CarPoseSelection h15 = select_car_pose(337.5, 0.0);
    if (h15.atlas_index != 63 || h15.row != 3 || h15.column != 15)
        return fail("V2 flat h15 atlas location changed unexpectedly");
    if (h15.source_rect.x != 3840 || h15.source_rect.y != 768)
        return fail("V2 flat h15 source rectangle changed unexpectedly");

    // One camera quarter-turn subtracts 90 degrees, matching the existing
    // RuntimeMapRenderer camera visual-orientation convention.
    const CarPoseSelection camera_rotated = select_car_pose(90.0, 0.0, 1);
    if (camera_rotated.logical_heading_index != 4 || camera_rotated.visual_heading_index != 0 ||
        camera_rotated.atlas_index != 48)
        return fail("camera quarter-turn must rotate h04 visually to V2 flat h00");

    constexpr double kCos30 = 0.8660254037844386;
    constexpr double kSin30 = 0.5;
    const CarPoseSelection uphill30 = select_car_pose_from_tangent(0.0, kCos30, kSin30);
    if (uphill30.vertical_supplement || uphill30.atlas_index != 80 ||
        !near(uphill30.snapped_pitch_degrees, 30.0))
        return fail("+30 degree h00 slope must select V2 16-way frame 80");
    if (uphill30.row != 5 || uphill30.column != 0 ||
        uphill30.source_rect.x != 0 || uphill30.source_rect.y != 1280)
        return fail("+30 degree h00 V2 source rectangle changed unexpectedly");

    const CarPoseSelection downhill30 = select_car_pose_from_tangent(0.0, kCos30, -kSin30);
    if (downhill30.vertical_supplement || downhill30.atlas_index != 16 ||
        !near(downhill30.snapped_pitch_degrees, -30.0))
        return fail("-30 degree h00 slope must select V2 16-way frame 16");

    // Slopes are truly 16-way in V2; no cardinal fallback is allowed.
    const CarPoseSelection h03_uphill46 = select_car_pose(67.5, 46.0);
    if (h03_uphill46.atlas_index != 99 || h03_uphill46.visual_heading_index != 3 ||
        h03_uphill46.snapped_to_cardinal_heading)
        return fail("non-cardinal steep slope must remain h03 without cardinal snap");

    const CarPoseSelection h04_uphill30 = select_car_pose(90.0, 30.0);
    if (h04_uphill30.atlas_index != 84 || h04_uphill30.visual_heading_index != 4)
        return fail("+30 degree h04 slope must select V2 frame 84");

    const CarPoseSelection h04_uphill30_rotated = select_car_pose(90.0, 30.0, 1);
    if (h04_uphill30_rotated.atlas_index != 80 || h04_uphill30_rotated.visual_heading_index != 0)
        return fail("camera rotation must rotate the complete V2 slope family");

    // Tiny grade noise should remain in the zero-pitch family.
    const CarPoseSelection almost_flat = select_car_pose(45.0, 3.0);
    if (almost_flat.vertical_supplement || almost_flat.atlas_index != 50)
        return fail("small pitch must remain in the V2 zero-pitch family");

    // Dedicated vertical supplement.
    const CarPoseSelection vertical_up = select_car_pose_v2(0.0, 90.0, 0.0);
    if (!vertical_up.vertical_supplement || vertical_up.atlas_index != 128 ||
        !near(vertical_up.snapped_pitch_degrees, 90.0))
        return fail("+90 degree h00 must use V2 vertical supplement frame 128");

    // Dedicated banking supplement. Build an up vector rolled +24 degrees
    // around a +Y tangent and ensure the selector keeps that roll.
    constexpr double kDeg24 = 0.41887902047863906;
    const CarPoseSelection banked = select_car_pose_from_frame(
        0.0, 1.0, 0.0,
        std::sin(kDeg24), 0.0, std::cos(kDeg24));
    if (banked.atlas_index != 160 || !near(banked.snapped_roll_degrees, 24.0) ||
        banked.requires_extended_orientation)
        return fail("+24 degree bank h00 must use V2 bank frame 160");

    const CarPoseSelection inverted = select_car_pose_v2(180.0, 0.0, 180.0);
    if (inverted.atlas_index != 184 || !near(inverted.snapped_roll_degrees, 180.0) ||
        inverted.requires_extended_orientation)
        return fail("inverted h08 must use V2 inverted frame 184");

    if (kCarPoseFrameCount != 192 || kCarPoseAtlasColumns != 16 || kCarPoseAtlasRows != 12)
        return fail("V2 atlas contract must remain 192 frames in a 16x12 grid");
    if (kCarPoseAtlasColumns * kCarPoseAtlasRows != kCarPoseFrameCount)
        return fail("atlas dimensions must contain exactly 192 frames");

    std::cout << "CH_COASTER_CAR_ATLAS_RUNTIME_V2 regression: OK\n";
    return 0;
}
