#include "rail_path_builder.h"

#include <cassert>
#include <cmath>

namespace {

constexpr float kHalfPi = 1.57079632679489661923F;
constexpr float kPiOverSix = 0.5235987755982988F;
constexpr float kPiOverTwelve = 0.2617993877991494F;

void assert_geometry_safe(const RailGeometry& geometry, const RailProfile& profile) {
    assert(!geometry.empty());
    assert(RailMeshBuilder::validate_mesh(geometry.ballast, profile).ok());
    assert(RailMeshBuilder::validate_mesh(geometry.sleepers, profile).ok());
    assert(RailMeshBuilder::validate_mesh(geometry.left_rail, profile).ok());
    assert(RailMeshBuilder::validate_mesh(geometry.right_rail, profile).ok());
}

float planar_distance(const RailWorldPoint3& a, const RailWorldPoint3& b) {
    const float dx = b.x - a.x;
    const float dy = b.y - a.y;
    return std::sqrt(dx * dx + dy * dy);
}

float normalized_planar_dot(const RailWorldPoint3& a, const RailWorldPoint3& b) {
    const float la = std::sqrt(a.x * a.x + a.y * a.y);
    const float lb = std::sqrt(b.x * b.x + b.y * b.y);
    assert(la > 0.0F && lb > 0.0F);
    return (a.x * b.x + a.y * b.y) / (la * lb);
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

    // Shallow arc curves are the primitive used by turnouts. They preserve an
    // analytical entry tangent and a predictable rotated exit tangent.
    const RailPathBuildResult shallow = RailPathBuilder::arc_curve(
        {0.0F, 0.0F, 0.0F}, 0.0F, 8.0F, kPiOverTwelve,
        RailTurnDirection::left, 48, profile);
    assert(shallow.ok());
    const RailWorldPoint3 shallow_entry_tangent = RailMeshBuilder::tangent_cubic(shallow.segment, 0.0F);
    const RailWorldPoint3 shallow_exit_tangent = RailMeshBuilder::tangent_cubic(shallow.segment, 1.0F);
    assert(normalized_planar_dot(shallow_entry_tangent, {1.0F, 0.0F, 0.0F}) > 0.9999F);
    assert(normalized_planar_dot(shallow_exit_tangent,
                                 {std::cos(kPiOverTwelve), std::sin(kPiOverTwelve), 0.0F}) > 0.9999F);

    // Canonical turnout: both routes start at the same graph node and exact
    // heading. The branch then diverges progressively without a direction snap.
    const RailTurnoutBuildResult turnout_left = RailPathBuilder::turnout(
        {0.0F, 0.0F, 0.0F}, 0.0F, 8.0F, kPiOverTwelve,
        RailTurnDirection::left, 48, profile);
    assert(turnout_left.ok());
    assert(planar_distance(turnout_left.through.start, turnout_left.diverging.start) < 0.00001F);

    const RailWorldPoint3 through_entry_tangent = RailMeshBuilder::tangent_cubic(turnout_left.through, 0.0F);
    const RailWorldPoint3 branch_entry_tangent = RailMeshBuilder::tangent_cubic(turnout_left.diverging, 0.0F);
    assert(normalized_planar_dot(through_entry_tangent, branch_entry_tangent) > 0.9999F);

    // The exits must be meaningfully separated; otherwise a turnout would be a
    // visually duplicated straight and could not form two graph branches.
    assert(planar_distance(turnout_left.through.end, turnout_left.diverging.end) > profile.gauge * 0.5F);
    assert(turnout_left.diverging.end.y > turnout_left.through.end.y);
    assert(std::abs(turnout_left.diverging_exit_heading_radians - kPiOverTwelve) < 0.0001F);

    const RailBuildResult turnout_through_mesh = RailMeshBuilder::build(turnout_left.through, profile);
    const RailBuildResult turnout_branch_mesh = RailMeshBuilder::build(turnout_left.diverging, profile);
    assert(turnout_through_mesh.ok());
    assert(turnout_branch_mesh.ok());
    assert_geometry_safe(turnout_through_mesh.geometry, profile);
    assert_geometry_safe(turnout_branch_mesh.geometry, profile);

    // Mirrored right turnout must remain symmetric around the source heading.
    const RailTurnoutBuildResult turnout_right = RailPathBuilder::turnout(
        {0.0F, 0.0F, 0.0F}, 0.0F, 8.0F, kPiOverTwelve,
        RailTurnDirection::right, 48, profile);
    assert(turnout_right.ok());
    assert(turnout_right.diverging.end.y < turnout_right.through.end.y);
    assert(std::abs(turnout_right.diverging.end.x - turnout_left.diverging.end.x) < 0.0001F);
    assert(std::abs(turnout_right.diverging.end.y + turnout_left.diverging.end.y) < 0.0001F);
    assert(std::abs(turnout_right.diverging_exit_heading_radians + kPiOverTwelve) < 0.0001F);

    // Requests below the railway's minimum radius fail closed and carry no
    // usable segment into the mesh builder.
    const RailPathBuildResult too_tight = RailPathBuilder::quarter_curve(
        {0.0F, 0.0F, 0.0F}, 0.0F, profile.min_turn_radius * 0.5F,
        RailTurnDirection::left, 48, profile);
    assert(!too_tight.ok());
    assert(too_tight.validation.error == RailValidationError::turn_radius_too_small);

    const RailTurnoutBuildResult turnout_too_tight = RailPathBuilder::turnout(
        {0.0F, 0.0F, 0.0F}, 0.0F, profile.min_turn_radius * 0.5F,
        kPiOverTwelve, RailTurnDirection::left, 48, profile);
    assert(!turnout_too_tight.ok());
    assert(turnout_too_tight.validation.error == RailValidationError::turn_radius_too_small);

    // Turnout angles are deliberately shallow. Extreme branch angles are not
    // silently accepted because they belong to ordinary curve primitives.
    const RailTurnoutBuildResult turnout_too_wide = RailPathBuilder::turnout(
        {0.0F, 0.0F, 0.0F}, 0.0F, 8.0F, kHalfPi,
        RailTurnDirection::left, 48, profile);
    assert(!turnout_too_wide.ok());

    const RailTurnoutBuildResult turnout_too_narrow = RailPathBuilder::turnout(
        {0.0F, 0.0F, 0.0F}, 0.0F, 8.0F, 0.01F,
        RailTurnDirection::left, 48, profile);
    assert(!turnout_too_narrow.ok());

    // Non-finite authoring input is rejected before trigonometry can poison the
    // generated control points.
    const RailPathBuildResult bad_heading = RailPathBuilder::straight(
        {0.0F, 0.0F, 0.0F}, std::nanf(""), 4.0F, 32, profile);
    assert(!bad_heading.ok());

    return 0;
}
