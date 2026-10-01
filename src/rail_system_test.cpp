#include "rail_system.h"

#include <cassert>
#include <cmath>
#include <cstdint>
#include <limits>

namespace {

RailSplineSegment straight_segment() {
    RailSplineSegment s;
    s.start = {0.0F, 0.0F, 0.0F};
    s.control_a = {2.0F, 0.0F, 0.0F};
    s.control_b = {4.0F, 0.0F, 0.0F};
    s.end = {6.0F, 0.0F, 0.0F};
    s.subdivisions = 32;
    return s;
}

void assert_mesh_safe(const RailMesh& mesh, const RailProfile& profile) {
    const RailValidationResult result = RailMeshBuilder::validate_mesh(mesh, profile);
    assert(result.ok());
    assert(!mesh.empty());
    assert(mesh.vertices.size() <= profile.max_vertices);
    assert(mesh.indices.size() <= profile.max_indices);
    for (const std::uint32_t index : mesh.indices) assert(index < mesh.vertices.size());
    for (const RailMeshVertex& vertex : mesh.vertices) {
        assert(std::isfinite(vertex.position.x));
        assert(std::isfinite(vertex.position.y));
        assert(std::isfinite(vertex.position.z));
    }
}

} // namespace

int main() {
    const RailProfile profile{};

    // Refined visual proportions remain physically coherent. These assertions
    // intentionally protect silhouette/readability without weakening any of the
    // structural safety limits below.
    assert(profile.ballast_width > profile.sleeper_length);
    assert(profile.sleeper_length > profile.gauge);
    assert(profile.gauge > profile.rail_width * 2.0F);
    assert(profile.rail_height > profile.sleeper_height);
    assert(profile.ballast_height > 0.0F);
    assert(profile.sleeper_spacing > profile.sleeper_width);

    // Straight rail produces four volumetric material groups.
    const RailSplineSegment straight = straight_segment();
    const RailBuildResult straight_build = RailMeshBuilder::build(straight, profile);
    assert(straight_build.ok());
    assert_mesh_safe(straight_build.geometry.ballast, profile);
    assert_mesh_safe(straight_build.geometry.sleepers, profile);
    assert_mesh_safe(straight_build.geometry.left_rail, profile);
    assert_mesh_safe(straight_build.geometry.right_rail, profile);

    // Deterministic inputs must produce deterministic mesh topology and values.
    const RailBuildResult repeated = RailMeshBuilder::build(straight, profile);
    assert(repeated.ok());
    assert(repeated.geometry.ballast.vertices.size() == straight_build.geometry.ballast.vertices.size());
    assert(repeated.geometry.ballast.indices == straight_build.geometry.ballast.indices);
    assert(repeated.geometry.sleepers.vertices.size() == straight_build.geometry.sleepers.vertices.size());
    for (std::size_t i = 0; i < repeated.geometry.left_rail.vertices.size(); ++i) {
        const auto& a = repeated.geometry.left_rail.vertices[i].position;
        const auto& b = straight_build.geometry.left_rail.vertices[i].position;
        assert(a.x == b.x && a.y == b.y && a.z == b.z);
    }

    // Broad curve stays valid and retains real profile thickness.
    RailSplineSegment curve;
    curve.start = {0.0F, 0.0F, 0.0F};
    curve.control_a = {2.5F, 0.0F, 0.0F};
    curve.control_b = {5.0F, 2.5F, 0.0F};
    curve.end = {5.0F, 5.0F, 0.0F};
    curve.subdivisions = 48;
    const RailBuildResult curve_build = RailMeshBuilder::build(curve, profile);
    assert(curve_build.ok());
    assert_mesh_safe(curve_build.geometry.ballast, profile);

    // A mild grade is legal; a cliff is rejected before allocation.
    RailSplineSegment grade = straight;
    grade.control_a.z = 0.10F;
    grade.control_b.z = 0.20F;
    grade.end.z = 0.30F;
    assert(RailMeshBuilder::build(grade, profile).ok());

    RailSplineSegment cliff = straight;
    cliff.control_a.z = 2.0F;
    cliff.control_b.z = 4.0F;
    cliff.end.z = 6.0F;
    const RailBuildResult cliff_build = RailMeshBuilder::build(cliff, profile);
    assert(!cliff_build.ok());
    assert(cliff_build.validation.error == RailValidationError::grade_too_steep);
    assert(cliff_build.geometry.empty());

    // Degenerate and non-finite splines fail closed.
    RailSplineSegment zero{};
    zero.subdivisions = 32;
    const RailBuildResult zero_build = RailMeshBuilder::build(zero, profile);
    assert(!zero_build.ok());
    assert(zero_build.geometry.empty());

    RailSplineSegment nan_segment = straight;
    nan_segment.control_a.x = std::numeric_limits<float>::quiet_NaN();
    const RailBuildResult nan_build = RailMeshBuilder::build(nan_segment, profile);
    assert(!nan_build.ok());
    assert(nan_build.validation.error == RailValidationError::non_finite_input);
    assert(nan_build.geometry.empty());

    // Hard subdivision and geometry budgets are never silently clamped upward.
    RailSplineSegment excessive = straight;
    excessive.subdivisions = profile.max_subdivisions + 1;
    const RailBuildResult excessive_build = RailMeshBuilder::build(excessive, profile);
    assert(!excessive_build.ok());
    assert(excessive_build.validation.error == RailValidationError::subdivision_limit);

    RailProfile tiny_budget = profile;
    tiny_budget.max_vertices = 64U;
    tiny_budget.max_indices = 96U;
    const RailBuildResult budget_build = RailMeshBuilder::build(straight, tiny_budget);
    assert(!budget_build.ok());
    assert(budget_build.validation.error == RailValidationError::geometry_budget_exceeded);
    assert(budget_build.geometry.empty());

    // Connected segments must share position and a sufficiently continuous tangent.
    RailSplineSegment second;
    second.start = straight.end;
    second.control_a = {8.0F, 0.0F, 0.0F};
    second.control_b = {10.0F, 0.0F, 0.0F};
    second.end = {12.0F, 0.0F, 0.0F};
    second.subdivisions = 32;
    assert(RailMeshBuilder::validate_connection(straight, second, profile).ok());

    second.start.y = 0.02F;
    const RailValidationResult seam = RailMeshBuilder::validate_connection(straight, second, profile);
    assert(!seam.ok());
    assert(seam.error == RailValidationError::disconnected_endpoint);

    return 0;
}
