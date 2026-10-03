#pragma once

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>

namespace ch::coaster {

// CH_COASTER_CAR_ATLAS_RUNTIME_V2
//
// The occupied Flame atlas is baked from one CH Blender source with the same
// rail anchor for all 192 frames. Ordinary slopes exist in every one of the 16
// headings; vertical, banked and inverted supplements use the same heading
// grid. The selector therefore never cardinal-snaps a sloped car.
inline constexpr char kCoasterCarAtlasContract[] = "CH_COASTER_CAR_ATLAS_RUNTIME_V2";
inline constexpr char kCoasterCarOrientationContract[] = "CH_COASTER_CAR_ORIENTATION_V2";
inline constexpr int kCarPoseHeadingCount = 16;
inline constexpr double kCarPoseHeadingStepDegrees = 22.5;
inline constexpr std::array<double, 7> kCarPosePitchBinsDegrees = {
    -46.0, -30.0, -14.0, 0.0, 14.0, 30.0, 46.0,
};
inline constexpr std::array<double, 2> kCarPoseVerticalPitchBinsDegrees = {-90.0, 90.0};
inline constexpr std::array<double, 2> kCarPoseBankRollBinsDegrees = {-24.0, 24.0};
inline constexpr double kCarPoseInvertedRollDegrees = 180.0;
inline constexpr int kCarPoseNormalFrameCount = 7 * kCarPoseHeadingCount;
inline constexpr int kCarPoseVerticalFrameBase = kCarPoseNormalFrameCount;
inline constexpr int kCarPoseVerticalFrameCount = 2 * kCarPoseHeadingCount;
inline constexpr int kCarPoseBankFrameBase = kCarPoseVerticalFrameBase + kCarPoseVerticalFrameCount;
inline constexpr int kCarPoseBankFrameCount = 2 * kCarPoseHeadingCount;
inline constexpr int kCarPoseInvertedFrameBase = kCarPoseBankFrameBase + kCarPoseBankFrameCount;
inline constexpr int kCarPoseInvertedFrameCount = kCarPoseHeadingCount;
inline constexpr int kCarPoseFrameCount = 192;
inline constexpr int kCarPoseAtlasColumns = 16;
inline constexpr int kCarPoseAtlasRows = 12;
inline constexpr int kCarPoseFrameWidth = 256;
inline constexpr int kCarPoseFrameHeight = 256;
inline constexpr const char* kFlameCarPoseAtlasPath =
    "assets/vehicles/coaster_flame_01/car_pose_atlas_v2.png";
inline constexpr const char* kFlameCarPoseAtlasManifestPath =
    "assets/vehicles/coaster_flame_01/car_pose_atlas_runtime_v2.json";

static_assert(kCarPoseInvertedFrameBase + kCarPoseInvertedFrameCount == kCarPoseFrameCount);
static_assert(kCarPoseAtlasColumns * kCarPoseAtlasRows == kCarPoseFrameCount);

struct CarPoseSourceRect {
    int x = 0;
    int y = 0;
    int w = kCarPoseFrameWidth;
    int h = kCarPoseFrameHeight;
};

struct CarPoseSelection {
    int logical_heading_index = 0;
    int visual_heading_index = 0;
    int atlas_index = 0;
    int row = 0;
    int column = 0;
    double authored_heading_degrees = 0.0;
    double sampled_pitch_degrees = 0.0;
    double sampled_roll_degrees = 0.0;
    double snapped_pitch_degrees = 0.0;
    bool vertical_supplement = false;
    bool snapped_to_cardinal_heading = false;
    bool requires_extended_orientation = false;
    CarPoseSourceRect source_rect{};
    double snapped_roll_degrees = 0.0;
};

[[nodiscard]] inline double normalize_degrees(double degrees) noexcept {
    if (!std::isfinite(degrees)) return 0.0;
    degrees = std::fmod(degrees, 360.0);
    if (degrees < 0.0) degrees += 360.0;
    return degrees;
}

[[nodiscard]] inline double signed_degrees(double degrees) noexcept {
    degrees = normalize_degrees(degrees);
    if (degrees > 180.0) degrees -= 360.0;
    return degrees;
}

[[nodiscard]] inline double angular_distance_degrees(const double a,
                                                     const double b) noexcept {
    return std::abs(signed_degrees(a - b));
}

[[nodiscard]] inline int normalize_heading_index(int index) noexcept {
    index %= kCarPoseHeadingCount;
    if (index < 0) index += kCarPoseHeadingCount;
    return index;
}

[[nodiscard]] inline int normalize_camera_quarter_turns(int turns) noexcept {
    turns %= 4;
    if (turns < 0) turns += 4;
    return turns;
}

[[nodiscard]] inline int heading_index_from_degrees(const double heading_degrees) noexcept {
    const double normalized = normalize_degrees(heading_degrees);
    return normalize_heading_index(static_cast<int>(std::llround(
        normalized / kCarPoseHeadingStepDegrees)));
}

[[nodiscard]] inline double heading_degrees_from_tangent(const double tangent_x,
                                                         const double tangent_y) noexcept {
    if (!std::isfinite(tangent_x) || !std::isfinite(tangent_y)) return 0.0;
    if (std::hypot(tangent_x, tangent_y) < 1.0e-9) return 0.0;
    constexpr double kRadiansToDegrees = 57.2957795130823208768;
    return normalize_degrees(std::atan2(-tangent_x, tangent_y) * kRadiansToDegrees);
}

[[nodiscard]] inline double pitch_degrees_from_tangent(const double tangent_x,
                                                       const double tangent_y,
                                                       const double tangent_z) noexcept {
    if (!std::isfinite(tangent_x) || !std::isfinite(tangent_y) || !std::isfinite(tangent_z))
        return 0.0;
    const double horizontal = std::hypot(tangent_x, tangent_y);
    if (horizontal < 1.0e-9 && std::abs(tangent_z) < 1.0e-9) return 0.0;
    constexpr double kRadiansToDegrees = 57.2957795130823208768;
    return std::atan2(tangent_z, horizontal) * kRadiansToDegrees;
}

[[nodiscard]] inline double roll_degrees_from_frame(const double tangent_x,
                                                    const double tangent_y,
                                                    const double tangent_z,
                                                    const double up_x,
                                                    const double up_y,
                                                    const double up_z) noexcept {
    constexpr double kRadiansToDegrees = 57.2957795130823208768;
    const double tangent_len = std::sqrt(tangent_x * tangent_x + tangent_y * tangent_y + tangent_z * tangent_z);
    const double up_len = std::sqrt(up_x * up_x + up_y * up_y + up_z * up_z);
    if (!(tangent_len > 1.0e-9) || !(up_len > 1.0e-9)) return 0.0;

    const double tx = tangent_x / tangent_len;
    const double ty = tangent_y / tangent_len;
    const double tz = tangent_z / tangent_len;
    const double ux = up_x / up_len;
    const double uy = up_y / up_len;
    const double uz = up_z / up_len;

    double rx = 0.0;
    double ry = 0.0;
    double rz = 1.0;
    double dot_rt = rx * tx + ry * ty + rz * tz;
    rx -= dot_rt * tx;
    ry -= dot_rt * ty;
    rz -= dot_rt * tz;
    double rlen = std::sqrt(rx * rx + ry * ry + rz * rz);
    if (!(rlen > 1.0e-6)) {
        rx = 1.0; ry = 0.0; rz = 0.0;
        dot_rt = rx * tx + ry * ty + rz * tz;
        rx -= dot_rt * tx;
        ry -= dot_rt * ty;
        rz -= dot_rt * tz;
        rlen = std::sqrt(rx * rx + ry * ry + rz * rz);
    }
    if (!(rlen > 1.0e-9)) return 0.0;
    rx /= rlen; ry /= rlen; rz /= rlen;

    const double qx = ty * rz - tz * ry;
    const double qy = tz * rx - tx * rz;
    const double qz = tx * ry - ty * rx;
    const double cos_roll = std::clamp(ux * rx + uy * ry + uz * rz, -1.0, 1.0);
    const double sin_roll = std::clamp(ux * qx + uy * qy + uz * qz, -1.0, 1.0);
    return signed_degrees(std::atan2(sin_roll, cos_roll) * kRadiansToDegrees);
}

template <std::size_t N>
[[nodiscard]] inline int nearest_linear_bin(const double value,
                                            const std::array<double, N>& bins) noexcept {
    int best = 0;
    double best_distance = std::abs(value - bins[0]);
    for (int i = 1; i < static_cast<int>(N); ++i) {
        const double distance = std::abs(value - bins[static_cast<std::size_t>(i)]);
        if (distance < best_distance) {
            best = i;
            best_distance = distance;
        }
    }
    return best;
}

[[nodiscard]] inline CarPoseSourceRect source_rect_for_car_pose(const int atlas_index) noexcept {
    const int safe = std::clamp(atlas_index, 0, kCarPoseFrameCount - 1);
    const int column = safe % kCarPoseAtlasColumns;
    const int row = safe / kCarPoseAtlasColumns;
    return {
        column * kCarPoseFrameWidth,
        row * kCarPoseFrameHeight,
        kCarPoseFrameWidth,
        kCarPoseFrameHeight,
    };
}

struct CarPoseCandidate {
    int atlas_index = 0;
    double pitch_degrees = 0.0;
    double roll_degrees = 0.0;
    bool vertical_supplement = false;
};

[[nodiscard]] inline CarPoseSelection select_car_pose_v2(
    const double authored_heading_degrees,
    const double pitch_degrees,
    const double roll_degrees,
    const int camera_quarter_turns = 0) noexcept {
    CarPoseSelection result;
    result.authored_heading_degrees = normalize_degrees(authored_heading_degrees);
    result.sampled_pitch_degrees = std::isfinite(pitch_degrees) ? pitch_degrees : 0.0;
    result.sampled_roll_degrees = std::isfinite(roll_degrees) ? signed_degrees(roll_degrees) : 0.0;
    result.logical_heading_index = heading_index_from_degrees(result.authored_heading_degrees);
    result.visual_heading_index = normalize_heading_index(
        result.logical_heading_index - normalize_camera_quarter_turns(camera_quarter_turns) * 4);

    CarPoseCandidate best{};
    double best_score = 1.0e300;
    auto consider = [&](const CarPoseCandidate candidate) noexcept {
        const double pitch_error = result.sampled_pitch_degrees - candidate.pitch_degrees;
        const double roll_error = angular_distance_degrees(result.sampled_roll_degrees, candidate.roll_degrees);
        const double score = pitch_error * pitch_error + roll_error * roll_error;
        if (score < best_score) {
            best = candidate;
            best_score = score;
        }
    };

    for (int p = 0; p < static_cast<int>(kCarPosePitchBinsDegrees.size()); ++p) {
        consider({p * kCarPoseHeadingCount + result.visual_heading_index,
                  kCarPosePitchBinsDegrees[static_cast<std::size_t>(p)], 0.0, false});
    }
    for (int p = 0; p < static_cast<int>(kCarPoseVerticalPitchBinsDegrees.size()); ++p) {
        consider({kCarPoseVerticalFrameBase + p * kCarPoseHeadingCount + result.visual_heading_index,
                  kCarPoseVerticalPitchBinsDegrees[static_cast<std::size_t>(p)], 0.0, true});
    }
    for (int r = 0; r < static_cast<int>(kCarPoseBankRollBinsDegrees.size()); ++r) {
        consider({kCarPoseBankFrameBase + r * kCarPoseHeadingCount + result.visual_heading_index,
                  0.0, kCarPoseBankRollBinsDegrees[static_cast<std::size_t>(r)], false});
    }
    consider({kCarPoseInvertedFrameBase + result.visual_heading_index,
              0.0, kCarPoseInvertedRollDegrees, false});

    result.atlas_index = best.atlas_index;
    result.snapped_pitch_degrees = best.pitch_degrees;
    result.snapped_roll_degrees = best.roll_degrees;
    result.vertical_supplement = best.vertical_supplement;
    result.snapped_to_cardinal_heading = false;
    result.column = result.atlas_index % kCarPoseAtlasColumns;
    result.row = result.atlas_index / kCarPoseAtlasColumns;
    result.source_rect = source_rect_for_car_pose(result.atlas_index);

    const double pitch_error = std::abs(result.sampled_pitch_degrees - result.snapped_pitch_degrees);
    const double roll_error = angular_distance_degrees(result.sampled_roll_degrees, result.snapped_roll_degrees);
    result.requires_extended_orientation = pitch_error > 8.01 || roll_error > 12.01;
    return result;
}

[[nodiscard]] inline CarPoseSelection select_car_pose(const double authored_heading_degrees,
                                                      const double pitch_degrees,
                                                      const int camera_quarter_turns = 0) noexcept {
    return select_car_pose_v2(authored_heading_degrees, pitch_degrees, 0.0, camera_quarter_turns);
}

[[nodiscard]] inline CarPoseSelection select_car_pose_from_tangent(
    const double tangent_x,
    const double tangent_y,
    const double tangent_z,
    const int camera_quarter_turns = 0) noexcept {
    return select_car_pose(
        heading_degrees_from_tangent(tangent_x, tangent_y),
        pitch_degrees_from_tangent(tangent_x, tangent_y, tangent_z),
        camera_quarter_turns);
}

[[nodiscard]] inline CarPoseSelection select_car_pose_from_frame(
    const double tangent_x,
    const double tangent_y,
    const double tangent_z,
    const double up_x,
    const double up_y,
    const double up_z,
    const int camera_quarter_turns = 0) noexcept {
    return select_car_pose_v2(
        heading_degrees_from_tangent(tangent_x, tangent_y),
        pitch_degrees_from_tangent(tangent_x, tangent_y, tangent_z),
        roll_degrees_from_frame(tangent_x, tangent_y, tangent_z, up_x, up_y, up_z),
        camera_quarter_turns);
}

}  // namespace ch::coaster
