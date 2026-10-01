#include "rail_path_builder.h"
#include "rail_placement_graph.h"

#include <cassert>
#include <cmath>

namespace {

constexpr float kHalfPi = 1.57079632679489661923F;
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

    assert(std::abs(left_curve.segment.end.x - 4.0F) < 0.0001F);
    assert(std::abs(left_curve.segment.end.y - 4.0F) < 0.0001F);

    const RailPathBuildResult right_curve = RailPathBuilder::quarter_curve(
        {0.0F, 0.0F, 0.0F}, 0.0F, 4.0F, RailTurnDirection::right, 48, profile);
    assert(right_curve.ok());
    assert(std::abs(right_curve.segment.end.x - 4.0F) < 0.0001F);
    assert(std::abs(right_curve.segment.end.y + 4.0F) < 0.0001F);
    const RailBuildResult right_mesh = RailMeshBuilder::build(right_curve.segment, profile);
    assert(right_mesh.ok());
    assert_geometry_safe(right_mesh.geometry, profile);

    const RailPathBuildResult shallow = RailPathBuilder::arc_curve(
        {0.0F, 0.0F, 0.0F}, 0.0F, 8.0F, kPiOverTwelve,
        RailTurnDirection::left, 48, profile);
    assert(shallow.ok());
    const RailWorldPoint3 shallow_entry_tangent = RailMeshBuilder::tangent_cubic(shallow.segment, 0.0F);
    const RailWorldPoint3 shallow_exit_tangent = RailMeshBuilder::tangent_cubic(shallow.segment, 1.0F);
    assert(normalized_planar_dot(shallow_entry_tangent, {1.0F, 0.0F, 0.0F}) > 0.9999F);
    assert(normalized_planar_dot(shallow_exit_tangent,
                                 {std::cos(kPiOverTwelve), std::sin(kPiOverTwelve), 0.0F}) > 0.9999F);

    const RailTurnoutBuildResult turnout_left = RailPathBuilder::turnout(
        {0.0F, 0.0F, 0.0F}, 0.0F, 8.0F, kPiOverTwelve,
        RailTurnDirection::left, 48, profile);
    assert(turnout_left.ok());
    assert(planar_distance(turnout_left.through.start, turnout_left.diverging.start) < 0.00001F);

    const RailWorldPoint3 through_entry_tangent = RailMeshBuilder::tangent_cubic(turnout_left.through, 0.0F);
    const RailWorldPoint3 branch_entry_tangent = RailMeshBuilder::tangent_cubic(turnout_left.diverging, 0.0F);
    assert(normalized_planar_dot(through_entry_tangent, branch_entry_tangent) > 0.9999F);
    assert(planar_distance(turnout_left.through.end, turnout_left.diverging.end) > profile.gauge * 0.5F);
    assert(turnout_left.diverging.end.y > turnout_left.through.end.y);
    assert(std::abs(turnout_left.diverging_exit_heading_radians - kPiOverTwelve) < 0.0001F);

    const RailBuildResult turnout_through_mesh = RailMeshBuilder::build(turnout_left.through, profile);
    const RailBuildResult turnout_branch_mesh = RailMeshBuilder::build(turnout_left.diverging, profile);
    assert(turnout_through_mesh.ok());
    assert(turnout_branch_mesh.ok());
    assert_geometry_safe(turnout_through_mesh.geometry, profile);
    assert_geometry_safe(turnout_branch_mesh.geometry, profile);

    const RailTurnoutBuildResult turnout_right = RailPathBuilder::turnout(
        {0.0F, 0.0F, 0.0F}, 0.0F, 8.0F, kPiOverTwelve,
        RailTurnDirection::right, 48, profile);
    assert(turnout_right.ok());
    assert(turnout_right.diverging.end.y < turnout_right.through.end.y);
    assert(std::abs(turnout_right.diverging.end.x - turnout_left.diverging.end.x) < 0.0001F);
    assert(std::abs(turnout_right.diverging.end.y + turnout_left.diverging.end.y) < 0.0001F);
    assert(std::abs(turnout_right.diverging_exit_heading_radians + kPiOverTwelve) < 0.0001F);

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

    const RailTurnoutBuildResult turnout_too_wide = RailPathBuilder::turnout(
        {0.0F, 0.0F, 0.0F}, 0.0F, 8.0F, kHalfPi,
        RailTurnDirection::left, 48, profile);
    assert(!turnout_too_wide.ok());

    const RailTurnoutBuildResult turnout_too_narrow = RailPathBuilder::turnout(
        {0.0F, 0.0F, 0.0F}, 0.0F, 8.0F, 0.01F,
        RailTurnDirection::left, 48, profile);
    assert(!turnout_too_narrow.ok());

    // Transactional editor staging graph.
    RailPlacementGraph placement(profile);
    const auto placement_root = placement.add_root({0.0F, 0.0F, 0.0F}, 0.0F);
    assert(placement_root.has_value());

    const auto placed_straight = placement.append_straight(*placement_root, 6.0F, 32);
    assert(placed_straight.has_value() && placed_straight->ok());
    assert(placement.nodes().size() == 2U);
    assert(placement.edges().size() == 1U);
    const RailPlacementNode* straight_end = placement.node(placed_straight->node);
    assert(straight_end != nullptr);
    assert(std::abs(straight_end->position.x - 6.0F) < 0.0001F);
    assert(std::abs(straight_end->position.y) < 0.0001F);

    const auto placed_curve = placement.append_quarter_curve(
        placed_straight->node, 4.0F, RailTurnDirection::left, 48);
    assert(placed_curve.has_value() && placed_curve->ok());
    const RailPlacementNode* curve_end = placement.node(placed_curve->node);
    assert(curve_end != nullptr);
    assert(std::abs(curve_end->heading_radians - kHalfPi) < 0.0001F);
    assert(RailMeshBuilder::validate_connection(
        placement.edge(placed_straight->edge)->segment,
        placement.edge(placed_curve->edge)->segment,
        profile).ok());

    const RailPlacementCheckpoint cancel_point = placement.checkpoint();
    const auto temporary_extension = placement.append_straight(placed_curve->node, 5.0F, 32);
    assert(temporary_extension.has_value());
    assert(placement.nodes().size() == cancel_point.node_count + 1U);
    assert(placement.edges().size() == cancel_point.edge_count + 1U);
    assert(placement.rollback(cancel_point));
    assert(placement.nodes().size() == cancel_point.node_count);
    assert(placement.edges().size() == cancel_point.edge_count);
    assert(placement.node(temporary_extension->node) == nullptr);

    const RailPlacementCheckpoint before_turnout = placement.checkpoint();
    const auto placed_turnout = placement.append_turnout(
        placed_straight->node, 8.0F, kPiOverTwelve, RailTurnDirection::right, 48);
    assert(placed_turnout.has_value() && placed_turnout->ok());
    assert(placement.nodes().size() == before_turnout.node_count + 2U);
    assert(placement.edges().size() == before_turnout.edge_count + 2U);
    assert(RailMeshBuilder::build(placement.edge(placed_turnout->through_edge)->segment, profile).ok());
    assert(RailMeshBuilder::build(placement.edge(placed_turnout->diverging_edge)->segment, profile).ok());

    const RailPlacementCheckpoint before_rejected_curve = placement.checkpoint();
    const auto rejected_curve = placement.append_quarter_curve(
        placed_turnout->through_node, profile.min_turn_radius * 0.25F,
        RailTurnDirection::left, 48);
    assert(!rejected_curve.has_value());
    assert(placement.nodes().size() == before_rejected_curve.node_count);
    assert(placement.edges().size() == before_rejected_curve.edge_count);

    const RailPlacementCheckpoint before_rejected_turnout = placement.checkpoint();
    const auto rejected_turnout = placement.append_turnout(
        placed_turnout->through_node, profile.min_turn_radius * 0.25F,
        kPiOverTwelve, RailTurnDirection::left, 48);
    assert(!rejected_turnout.has_value());
    assert(placement.nodes().size() == before_rejected_turnout.node_count);
    assert(placement.edges().size() == before_rejected_turnout.edge_count);

    assert(!placement.add_root({std::nanf(""), 0.0F, 0.0F}, 0.0F).has_value());
    assert(!placement.rollback({placement.nodes().size() + 1U, placement.edges().size()}));

    const RailPathBuildResult bad_heading = RailPathBuilder::straight(
        {0.0F, 0.0F, 0.0F}, std::nanf(""), 4.0F, 32, profile);
    assert(!bad_heading.ok());

    return 0;
}
