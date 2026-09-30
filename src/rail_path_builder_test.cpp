#include "rail_path_builder.h"

#include <cassert>
#include <cmath>

namespace {

constexpr float kHalfPi = 1.57079632679489661923F;

void assert_geometry_safe(const RailGeometry& geometry, const RailProfile& profile) {
    assert(!geometry.empty());
    assert(RailMeshBuilder::validate_mesh(geometry.ballast, profile).ok());
    assert(RailMeshBuilder::validate_mesh(geometry.sleepers, profile).ok());
    assert(RailMeshBuilder::validate_mesh(geometry.left_rail, profile).ok());
    assert(RailMeshBuilder::validate_mesh(geometry.right_rail, profile).ok());
}

} // namespace

int main() {
    const RailProfile profile{};

    // A straight enters a broad left 90-degree curve and exits into a second
    // straight. Both seams must be position- and tangent-continuous.
    const RailPathBuildResult approach = RailPathBuilder::straight(
        {-6.0F, 0.0F, 0.0F}, 0.0F, 6.0F, 32, profile);
    assert(approach.ok());

    const RailPathBuildResult left_curve = RailPathBuilder::quarter_curve(
        approach.segment.end, 0.0F, 4.0F, RailTurnDirection::left, 48, profile);
    assert(left_curve.ok());
    assert(RailMeshBuilder::validate_connection(approach.segment, left_curve.segment, profile).ok());

    const RailPathBuildResult exit = RailPathBuilder::straight(
        left_curve.segment.end, kHalfPi, 6.0F, 32, profile);
    assert(exit.ok());
    assert(RailMeshBuilder::validate_connection(left_curve.segment, exit.segment, profile).ok());

    const RailBuildResult approach_mesh = RailMeshBuilder::build(approach.segment, profile);
    const RailBuildResult curve_mesh = RailMeshBuilder::build(left_curve.segment, profile);
    const RailBuildResult exit_mesh = RailMeshBuilder::build(exit.segment, profile);
    assert(approach_mesh.ok());
    assert(curve_mesh.ok());
    assert(exit_mesh.ok());
    assert_geometry_safe(approach_mesh.geometry, profile);
    assert_geometry_safe(curve_mesh.geometry, profile);
    assert_geometry_safe(exit_mesh.geometry, profile);

    // Canonical quarter-curve endpoint for an eastbound left turn of radius 4.
    assert(std::abs(left_curve.segment.end.x - 4.0F) < 0.0001F);
    assert(std::abs(left_curve.segment.end.y - 4.0F) < 0.0001F);

    // Right turns use the same structural contract and mirror safely.
    const RailPathBuildResult right_curve = RailPathBuilder::quarter_curve(
        {0.0F, 0.0F, 0.0F}, 0.0F, 4.0F, RailTurnDirection::right, 48, profile);
    assert(right_curve.ok());
    assert(std::abs(right_curve.segment.end.x - 4.0F) < 0.0001F);
    assert(std::abs(right_curve.segment.end.y + 4.0F) < 0.0001F);
    const RailBuildResult right_mesh = RailMeshBuilder::build(right_curve.segment, profile);
    assert(right_mesh.ok());
    assert_geometry_safe(right_mesh.geometry, profile);

    // Requests below the railway's minimum radius fail closed and carry no
    // usable segment into the mesh builder.
    const RailPathBuildResult too_tight = RailPathBuilder::quarter_curve(
        {0.0F, 0.0F, 0.0F}, 0.0F, profile.min_turn_radius * 0.5F,
        RailTurnDirection::left, 48, profile);
    assert(!too_tight.ok());
    assert(too_tight.validation.error == RailValidationError::turn_radius_too_small);

    // Non-finite authoring input is rejected before trigonometry can poison the
    // generated control points.
    const RailPathBuildResult bad_heading = RailPathBuilder::straight(
        {0.0F, 0.0F, 0.0F}, std::nanf(""), 4.0F, 32, profile);
    assert(!bad_heading.ok());

    return 0;
}
