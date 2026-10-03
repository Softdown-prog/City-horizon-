#pragma once

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>

namespace ch::coaster {

// CH_COASTER_CAR_ATLAS_RUNTIME_V2 bridge.
//
// The shipping atlas is still the approved 40-frame V1 texture. V2 adds the
// orientation contract required by loops/banked curves/corkscrews: heading,
// pitch and roll derived from a full local track frame. Until a V2 atlas is
// baked, atlas_index/source_rect remain V1-compatible and
// requires_extended_orientation tells callers when the fallback is visually
// insufficient.
inline constexpr int kCarPoseHeadingCount = 16;
inline constexpr double kCarPoseHeadingStepDegrees = 22.5;
inline constexpr int kCarPoseFrameCount = 40;
inline constexpr int kCarPoseAtlasColumns = 8;
inline constexpr int kCarPoseAtlasRows = 5;
inline constexpr int kCarPoseFrameWidth = 256;
inline constexpr int kCarPoseFrameHeight = 256;
inline constexpr const char* kFlameCarPoseAtlasPath =
    "assets/vehicles/coaster_flame_01/car_pose_atlas.png";
inline constexpr const char* kFlameCarPoseAtlasManifestPath =
    "assets/vehicles/coaster_flame_01/car_pose_atlas_runtime.json";

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

    // Build the zero-roll reference by projecting world +Z onto the plane
    // perpendicular to forward. Near vertical tangents, world +X is the stable
    // alternate reference. This is only a measurement frame; the transported
    // track up vector remains authoritative.
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

    // right_ref = forward x up_ref.
    const double qx = ty * rz - tz * ry;
    const double qy = tz * rx - tx * rz;
    const double qz = tx * ry - ty * rx;
    const double cos_roll = std::clamp(ux * rx + uy * ry + uz * rz, -1.0, 1.0);
    const double sin_roll = std::clamp(ux * qx + uy * qy + uz * qz, -1.0, 1.0);
    return signed_degrees(std::atan2(sin_roll, cos_roll) * kRadiansToDegrees);
}

[[nodiscard]] inline int nearest_vertical_pitch_bin(const double pitch_degrees) noexcept {
    static constexpr std::array<double, 6> kPitchBins = {
        -46.0, -30.0, -14.0, 14.0, 30.0, 46.0,
    };
    int best = 0;
    double best_distance = std::abs(pitch_degrees - kPitchBins[0]);
    for (int i = 1; i < static_cast<int>(kPitchBins.size()); ++i) {
        const double distance = std::abs(pitch_degrees - kPitchBins[static_cast<std::size_t>(i)]);
        if (distance < best_distance) {
            best = i;
            best_distance = distance;
        }
    }
    return best;
}

[[nodiscard]] inline double vertical_pitch_bin_degrees(const int bin) noexcept {
    static constexpr std::array<double, 6> kPitchBins = {
        -46.0, -30.0, -14.0, 14.0, 30.0, 46.0,
    };
    const int clamped = std::clamp(bin, 0, static_cast<int>(kPitchBins.size()) - 1);
    return kPitchBins[static_cast<std::size_t>(clamped)];
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

[[nodiscard]] inline CarPoseSelection select_car_pose(const double authored_heading_degrees,
                                                      const double pitch_degrees,
                                                      const int camera_quarter_turns = 0) noexcept {
    CarPoseSelection result;
    result.authored_heading_degrees = normalize_degrees(authored_heading_degrees);
    result.sampled_pitch_degrees = std::isfinite(pitch_degrees) ? pitch_degrees : 0.0;
    result.logical_heading_index = heading_index_from_degrees(result.authored_heading_degrees);
    result.visual_heading_index = normalize_heading_index(
        result.logical_heading_index - normalize_camera_quarter_turns(camera_quarter_turns) * 4);

    if (std::abs(result.sampled_pitch_degrees) < 7.0) {
        result.atlas_index = result.visual_heading_index;
        result.snapped_pitch_degrees = 0.0;
    } else {
        result.vertical_supplement = true;
        const int cardinal_slot = ((result.visual_heading_index + 2) / 4) % 4;
        const int cardinal_heading = cardinal_slot * 4;
        result.snapped_to_cardinal_heading = cardinal_heading != result.visual_heading_index;
        result.visual_heading_index = cardinal_heading;
        const int pitch_bin = nearest_vertical_pitch_bin(result.sampled_pitch_degrees);
        result.snapped_pitch_degrees = vertical_pitch_bin_degrees(pitch_bin);
        result.atlas_index = 16 + pitch_bin * 4 + cardinal_slot;
    }

    // V1's strongest slope is +/-46 degrees. Beyond that the selected frame is
    // intentionally only a fallback and must not be treated as visually valid.
    result.requires_extended_orientation = std::abs(result.sampled_pitch_degrees) > 50.0;
    result.column = result.atlas_index % kCarPoseAtlasColumns;
    result.row = result.atlas_index / kCarPoseAtlasColumns;
    result.source_rect = source_rect_for_car_pose(result.atlas_index);
    return result;
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
    CarPoseSelection result = select_car_pose_from_tangent(
        tangent_x, tangent_y, tangent_z, camera_quarter_turns);
    result.sampled_roll_degrees = roll_degrees_from_frame(
        tangent_x, tangent_y, tangent_z, up_x, up_y, up_z);
    // Even modest banking is outside V1: all 40 approved frames have zero roll.
    // Ten degrees provides tolerance for numerical transport noise while making
    // genuine bank/inversion requirements explicit.
    if (std::abs(result.sampled_roll_degrees) > 10.0)
        result.requires_extended_orientation = true;
    return result;
}

}  // namespace ch::coaster
