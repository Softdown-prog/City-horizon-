#pragma once

#include "rail_system.h"

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

    // 90-degree circular-arc approximation using the canonical cubic kappa.
    // The requested radius is checked against the same RailProfile limit used
    // by the mesh validator, and endpoint tangents are analytically continuous
    // with matching straight primitives.
    [[nodiscard]] static RailPathBuildResult quarter_curve(
        const RailWorldPoint3& start,
        float start_heading_radians,
        float radius,
        RailTurnDirection direction,
        int subdivisions = 48,
        const RailProfile& profile = {}) {
        if (!std::isfinite(start_heading_radians) || !std::isfinite(radius) || radius < profile.min_turn_radius) {
            return {{RailValidationError::turn_radius_too_small, "rail quarter curve radius is below structural minimum"}, {}};
        }

        constexpr float kKappa = 0.5522847498307936F;
        const float fx = std::cos(start_heading_radians);
        const float fy = std::sin(start_heading_radians);
        const float nx = -fy;
        const float ny = fx;
        const float turn = direction == RailTurnDirection::left ? 1.0F : -1.0F;

        RailSplineSegment segment;
        segment.start = start;
        segment.control_a = {
            start.x + fx * (kKappa * radius),
            start.y + fy * (kKappa * radius),
            start.z,
        };
        segment.end = {
            start.x + fx * radius + nx * (turn * radius),
            start.y + fy * radius + ny * (turn * radius),
            start.z,
        };
        segment.control_b = {
            segment.end.x - nx * (turn * kKappa * radius),
            segment.end.y - ny * (turn * kKappa * radius),
            start.z,
        };
        segment.subdivisions = subdivisions;

        RailPathBuildResult result;
        result.segment = segment;
        result.validation = RailMeshBuilder::validate(segment, profile);
        if (!result.validation) result.segment = {};
        return result;
    }
};
