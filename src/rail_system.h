#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

inline constexpr const char* kChProceduralRailGeometryContract = "CH_PROCEDURAL_RAIL_GEOMETRY_V1";

// CH_PROCEDURAL_RAIL_GEOMETRY_V1
//
// Runtime remains 2D. Rail geometry lives in world space (including Z thickness)
// and is projected by the existing City Horizon renderer. This contract does not
// introduce a live 3D engine, does not alter road occupancy/save data, and fails
// closed: invalid inputs produce no geometry.
struct RailWorldPoint3 {
    float x = 0.0F;
    float y = 0.0F;
    float z = 0.0F;
};

struct RailSplineSegment {
    RailWorldPoint3 start{};
    RailWorldPoint3 control_a{};
    RailWorldPoint3 control_b{};
    RailWorldPoint3 end{};
    int subdivisions = 32;
};

struct RailProfile {
    // Standard-gauge-inspired proportions expressed in City Horizon world units.
    // V2 visual tuning keeps the validated topology and safety envelope intact,
    // while giving the track a clearer classic-tycoon railway silhouette.
    float gauge = 0.50F;
    float ballast_width = 1.06F;
    float ballast_height = 0.095F;
    float ballast_shoulder = 0.16F;

    float sleeper_length = 0.90F;
    float sleeper_width = 0.125F;
    float sleeper_height = 0.060F;
    float sleeper_spacing = 0.27F;

    float rail_width = 0.052F;
    float rail_height = 0.085F;

    // Safety envelope. These are structural limits, not gameplay speed rules.
    float max_grade = 0.18F;          // |dz| / planar distance
    float min_turn_radius = 1.35F;    // world units
    float min_segment_length = 0.20F;
    float connection_tolerance = 0.0025F;
    float max_world_abs = 100000.0F;

    int min_subdivisions = 4;
    int max_subdivisions = 256;
    std::size_t max_vertices = 65536U;
    std::size_t max_indices = 196608U;
};

struct RailMeshVertex {
    RailWorldPoint3 position{};
    float u = 0.0F;
    float v = 0.0F;
};

struct RailMesh {
    std::vector<RailMeshVertex> vertices;
    std::vector<std::uint32_t> indices;

    [[nodiscard]] bool empty() const { return vertices.empty() || indices.empty(); }
    void clear() { vertices.clear(); indices.clear(); }
};

struct RailGeometry {
    RailMesh ballast;
    RailMesh sleepers;
    RailMesh left_rail;
    RailMesh right_rail;

    [[nodiscard]] bool empty() const {
        return ballast.empty() || sleepers.empty() || left_rail.empty() || right_rail.empty();
    }
    void clear() {
        ballast.clear(); sleepers.clear(); left_rail.clear(); right_rail.clear();
    }
};

enum class RailValidationError {
    none,
    non_finite_input,
    world_extent_exceeded,
    invalid_profile,
    subdivision_limit,
    segment_too_short,
    zero_tangent,
    grade_too_steep,
    turn_radius_too_small,
    geometry_budget_exceeded,
    invalid_index,
    degenerate_triangle,
    disconnected_endpoint,
};

struct RailValidationResult {
    RailValidationError error = RailValidationError::none;
    std::string message;

    [[nodiscard]] bool ok() const { return error == RailValidationError::none; }
    explicit operator bool() const { return ok(); }
};

struct RailBuildResult {
    RailValidationResult validation{};
    RailGeometry geometry{};

    [[nodiscard]] bool ok() const { return validation.ok() && !geometry.empty(); }
};

class RailMeshBuilder final {
public:
    [[nodiscard]] static RailWorldPoint3 sample_cubic(const RailSplineSegment& segment, float t);
    [[nodiscard]] static RailWorldPoint3 tangent_cubic(const RailSplineSegment& segment, float t);

    [[nodiscard]] static RailValidationResult validate(
        const RailSplineSegment& segment, const RailProfile& profile = {});

    [[nodiscard]] static RailBuildResult build(
        const RailSplineSegment& segment, const RailProfile& profile = {});

    // Explicit seam guard for independently authored graph segments. This does
    // not mutate either segment: callers can reject or snap before building.
    [[nodiscard]] static RailValidationResult validate_connection(
        const RailSplineSegment& first,
        const RailSplineSegment& second,
        const RailProfile& profile = {});

    // Post-build defensive gate suitable for renderer boundaries and tests.
    [[nodiscard]] static RailValidationResult validate_mesh(
        const RailMesh& mesh, const RailProfile& profile = {});
};

[[nodiscard]] const char* rail_validation_error_name(RailValidationError error);
