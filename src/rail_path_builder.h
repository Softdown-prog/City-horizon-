#pragma once

#include "rail_system.h"

#include <algorithm>
#include <cmath>

// Canonical, fail-closed spline primitives for the procedural railway editor.
// These helpers only author RailSplineSegment values; RailMeshBuilder remains
// the final structural validator before any geometry reaches the renderer.
enum class RailTurnDirection {
    left,
    right,
};

struct RailPathBuildResult {
    RailValidationResult validation{};
    RailSplineSegment segment{};

    [[nodiscard]] bool ok() const { return validation.ok(); }
    explicit operator bool() const { return ok(); }
};

struct RailTurnoutBuildResult {
    RailValidationResult validation{};
    RailSplineSegment through{};
    RailSplineSegment diverging{};
    float diverging_exit_heading_radians{0.0F};

    [[nodiscard]] bool ok() const { return validation.ok(); }
    explicit operator bool() const { return ok(); }
};

class RailPathBuilder final {
public:
    // Straight cubic with collinear control points. start_heading_radians is in
    // world XY space; positive angles turn counter-clockwise.
    [[nodiscard]] static RailPathBuildResult straight(
        const RailWorldPoint3& start,
        float start_heading_radians,
        float length,
        int subdivisions = 32,
        const RailProfile& profile = {}) {
        if (!std::isfinite(start_heading_radians) || !std::isfinite(length) || length <= 0.0F) {
            return {{RailValidationError::invalid_profile, "rail straight primitive has invalid heading or length"}, {}};
        }

        const float dx = std::cos(start_heading_radians);
        const float dy = std::sin(start_heading_radians);
        RailSplineSegment segment;
        segment.start = start;
        segment.control_a = {start.x + dx * (length / 3.0F), start.y + dy * (length / 3.0F), start.z};
        segment.control_b = {start.x + dx * (length * 2.0F / 3.0F), start.y + dy * (length * 2.0F / 3.0F), start.z};
        segment.end = {start.x + dx * length, start.y + dy * length, start.z};
        segment.subdivisions = subdivisions;

        RailPathBuildResult result;
        result.segment = segment;
        result.validation = RailMeshBuilder::validate(segment, profile);
        if (!result.validation) result.segment = {};
        return result;
    }

    // Circular-arc cubic approximation for turns up to 90 degrees. This is the
    // shared primitive used by quarter curves and turnouts so every authored
    // branch follows the same minimum-radius and fail-closed validation rules.
    [[nodiscard]] static RailPathBuildResult arc_curve(
        const RailWorldPoint3& start,
        float start_heading_radians,
        float radius,
        float angle_radians,
        RailTurnDirection direction,
        int subdivisions = 48,
        const RailProfile& profile = {}) {
        constexpr float kHalfPi = 1.57079632679489661923F;
        if (!std::isfinite(start_heading_radians) || !std::isfinite(radius) ||
            !std::isfinite(angle_radians) || radius < profile.min_turn_radius ||
            angle_radians <= 0.0F || angle_radians > kHalfPi) {
            return {{RailValidationError::turn_radius_too_small, "rail arc parameters are outside safe structural bounds"}, {}};
        }

        const float turn = direction == RailTurnDirection::left ? 1.0F : -1.0F;
        const float signed_angle = turn * angle_radians;
        const float fx = std::cos(start_heading_radians);
        const float fy = std::sin(start_heading_radians);
        const float nx = -fy;
        const float ny = fx;

        // Exact endpoint of the requested circular arc in the local tangent/
        // normal frame. The cubic control distance is the standard circular
        // arc approximation h = 4/3 * tan(theta/4) * radius.
        const float sin_a = std::sin(angle_radians);
        const float cos_a = std::cos(angle_radians);
        const float handle = (4.0F / 3.0F) * std::tan(angle_radians * 0.25F) * radius;

        RailSplineSegment segment;
        segment.start = start;
        segment.control_a = {
            start.x + fx * handle,
            start.y + fy * handle,
            start.z,
        };
        segment.end = {
            start.x + fx * (radius * sin_a) + nx * (turn * radius * (1.0F - cos_a)),
            start.y + fy * (radius * sin_a) + ny * (turn * radius * (1.0F - cos_a)),
            start.z,
        };

        const float exit_heading = start_heading_radians + signed_angle;
        const float ex = std::cos(exit_heading);
        const float ey = std::sin(exit_heading);
        segment.control_b = {
            segment.end.x - ex * handle,
            segment.end.y - ey * handle,
            start.z,
        };
        segment.subdivisions = subdivisions;

        RailPathBuildResult result;
        result.segment = segment;
        result.validation = RailMeshBuilder::validate(segment, profile);
        if (!result.validation) result.segment = {};
        return result;
    }

    // 90-degree circular-arc approximation. Endpoint tangents are continuous
    // with matching straight primitives.
    [[nodiscard]] static RailPathBuildResult quarter_curve(
        const RailWorldPoint3& start,
        float start_heading_radians,
        float radius,
        RailTurnDirection direction,
        int subdivisions = 48,
        const RailProfile& profile = {}) {
        constexpr float kHalfPi = 1.57079632679489661923F;
        return arc_curve(start, start_heading_radians, radius, kHalfPi, direction, subdivisions, profile);
    }

    // Canonical turnout/points primitive. The through route remains straight,
    // while the diverging route leaves the exact same start point with the
    // exact same initial tangent and gradually opens into a shallow circular
    // arc. No runtime switch state is stored here; this only authors the two
    // structurally valid graph branches.
    [[nodiscard]] static RailTurnoutBuildResult turnout(
        const RailWorldPoint3& start,
        float start_heading_radians,
        float radius,
        float diverging_angle_radians,
        RailTurnDirection direction,
        int subdivisions = 48,
        const RailProfile& profile = {}) {
        constexpr float kMinTurnoutAngle = 0.08726646259971647F; // 5 degrees
        constexpr float kMaxTurnoutAngle = 0.5235987755982988F;  // 30 degrees

        if (!std::isfinite(diverging_angle_radians) ||
            diverging_angle_radians < kMinTurnoutAngle || diverging_angle_radians > kMaxTurnoutAngle) {
            return {{RailValidationError::invalid_profile, "rail turnout angle must be between 5 and 30 degrees"}, {}, {}, 0.0F};
        }

        const RailPathBuildResult branch = arc_curve(
            start, start_heading_radians, radius, diverging_angle_radians,
            direction, subdivisions, profile);
        if (!branch) return {branch.validation, {}, {}, 0.0F};

        // Match the through route length to the branch arc length so both exits
        // occupy the same longitudinal construction envelope.
        const float through_length = radius * diverging_angle_radians;
        const RailPathBuildResult through = straight(
            start, start_heading_radians, through_length,
            std::max(profile.min_subdivisions, subdivisions), profile);
        if (!through) return {through.validation, {}, {}, 0.0F};

        // Both routes must independently remain mesh-safe. This catches budget,
        // curvature, world-extent and degenerate authoring errors before the
        // editor/runtime can expose the turnout.
        const RailBuildResult through_mesh = RailMeshBuilder::build(through.segment, profile);
        const RailBuildResult branch_mesh = RailMeshBuilder::build(branch.segment, profile);
        if (!through_mesh) return {through_mesh.validation, {}, {}, 0.0F};
        if (!branch_mesh) return {branch_mesh.validation, {}, {}, 0.0F};

        RailTurnoutBuildResult result;
        result.through = through.segment;
        result.diverging = branch.segment;
        result.diverging_exit_heading_radians = start_heading_radians +
            (direction == RailTurnDirection::left ? diverging_angle_radians : -diverging_angle_radians);
        result.validation = {};
        return result;
    }
};
