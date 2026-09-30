#include "rail_system.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <limits>

namespace {

constexpr float kEpsilon = 0.00001F;
constexpr float kAreaEpsilonSquared = 1.0e-12F;

[[nodiscard]] bool finite_value(const float value) {
    return std::isfinite(value);
}

[[nodiscard]] bool finite_point(const RailWorldPoint3& point) {
    return finite_value(point.x) && finite_value(point.y) && finite_value(point.z);
}

[[nodiscard]] float planar_distance(const RailWorldPoint3& a, const RailWorldPoint3& b) {
    const float dx = b.x - a.x;
    const float dy = b.y - a.y;
    return std::sqrt(dx * dx + dy * dy);
}

[[nodiscard]] float distance_3d(const RailWorldPoint3& a, const RailWorldPoint3& b) {
    const float dx = b.x - a.x;
    const float dy = b.y - a.y;
    const float dz = b.z - a.z;
    return std::sqrt(dx * dx + dy * dy + dz * dz);
}

[[nodiscard]] RailWorldPoint3 add(const RailWorldPoint3& a, const RailWorldPoint3& b) {
    return {a.x + b.x, a.y + b.y, a.z + b.z};
}

[[nodiscard]] RailWorldPoint3 subtract(const RailWorldPoint3& a, const RailWorldPoint3& b) {
    return {a.x - b.x, a.y - b.y, a.z - b.z};
}

[[nodiscard]] RailWorldPoint3 scale(const RailWorldPoint3& point, const float factor) {
    return {point.x * factor, point.y * factor, point.z * factor};
}

[[nodiscard]] float squared_length(const RailWorldPoint3& point) {
    return point.x * point.x + point.y * point.y + point.z * point.z;
}

[[nodiscard]] RailValidationResult failure(const RailValidationError error, const char* message) {
    return {error, message};
}

[[nodiscard]] bool valid_profile(const RailProfile& p) {
    return finite_value(p.gauge) && p.gauge > 0.0F &&
           finite_value(p.ballast_width) && p.ballast_width > p.gauge &&
           finite_value(p.ballast_height) && p.ballast_height > 0.0F &&
           finite_value(p.ballast_shoulder) && p.ballast_shoulder >= 0.0F &&
           finite_value(p.sleeper_length) && p.sleeper_length > p.gauge &&
           p.sleeper_length <= p.ballast_width + p.ballast_shoulder * 2.0F &&
           finite_value(p.sleeper_width) && p.sleeper_width > 0.0F &&
           finite_value(p.sleeper_height) && p.sleeper_height > 0.0F &&
           finite_value(p.sleeper_spacing) && p.sleeper_spacing >= p.sleeper_width &&
           finite_value(p.rail_width) && p.rail_width > 0.0F && p.rail_width < p.gauge &&
           finite_value(p.rail_height) && p.rail_height > 0.0F &&
           finite_value(p.max_grade) && p.max_grade > 0.0F && p.max_grade <= 1.0F &&
           finite_value(p.min_turn_radius) && p.min_turn_radius > 0.0F &&
           finite_value(p.min_segment_length) && p.min_segment_length > 0.0F &&
           finite_value(p.connection_tolerance) && p.connection_tolerance >= 0.0F &&
           finite_value(p.max_world_abs) && p.max_world_abs > 1.0F &&
           p.min_subdivisions >= 2 && p.max_subdivisions >= p.min_subdivisions &&
           p.max_subdivisions <= 4096 && p.max_vertices >= 8U && p.max_indices >= 36U;
}

[[nodiscard]] bool within_world_extent(const RailWorldPoint3& p, const float limit) {
    return std::abs(p.x) <= limit && std::abs(p.y) <= limit && std::abs(p.z) <= limit;
}

[[nodiscard]] float triangle_area_twice_squared(
    const RailWorldPoint3& a, const RailWorldPoint3& b, const RailWorldPoint3& c) {
    const RailWorldPoint3 ab = subtract(b, a);
    const RailWorldPoint3 ac = subtract(c, a);
    const RailWorldPoint3 cross{
        ab.y * ac.z - ab.z * ac.y,
        ab.z * ac.x - ab.x * ac.z,
        ab.x * ac.y - ab.y * ac.x,
    };
    return squared_length(cross);
}

[[nodiscard]] float circumradius_xy(
    const RailWorldPoint3& a, const RailWorldPoint3& b, const RailWorldPoint3& c) {
    const float ab = planar_distance(a, b);
    const float bc = planar_distance(b, c);
    const float ca = planar_distance(c, a);
    const float twice_area = std::abs(
        (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x));
    if (twice_area < kEpsilon || ab < kEpsilon || bc < kEpsilon || ca < kEpsilon) {
        return std::numeric_limits<float>::infinity();
    }
    return (ab * bc * ca) / (2.0F * twice_area);
}

[[nodiscard]] bool planar_frame(
    const RailSplineSegment& segment, const float t,
    RailWorldPoint3* tangent_out, RailWorldPoint3* normal_out) {
    RailWorldPoint3 tangent = RailMeshBuilder::tangent_cubic(segment, t);
    const float length = std::sqrt(tangent.x * tangent.x + tangent.y * tangent.y);
    if (!finite_point(tangent) || length < kEpsilon) return false;
    tangent.x /= length;
    tangent.y /= length;
    tangent.z = 0.0F;
    *tangent_out = tangent;
    *normal_out = {-tangent.y, tangent.x, 0.0F};
    return true;
}

bool append_prism_strip(
    RailMesh& mesh,
    const RailSplineSegment& segment,
    const float center_offset,
    const float width,
    const float base_height,
    const float thickness,
    const int subdivisions,
    const RailProfile& profile) {
    const std::size_t required_vertices = static_cast<std::size_t>(subdivisions + 1) * 4U;
    const std::size_t required_indices = static_cast<std::size_t>(subdivisions) * 24U;
    if (mesh.vertices.size() + required_vertices > profile.max_vertices ||
        mesh.indices.size() + required_indices > profile.max_indices) return false;

    mesh.vertices.reserve(mesh.vertices.size() + required_vertices);
    mesh.indices.reserve(mesh.indices.size() + required_indices);
    float accumulated = 0.0F;
    RailWorldPoint3 previous = RailMeshBuilder::sample_cubic(segment, 0.0F);

    for (int step = 0; step <= subdivisions; ++step) {
        const float t = static_cast<float>(step) / static_cast<float>(subdivisions);
        const RailWorldPoint3 center = RailMeshBuilder::sample_cubic(segment, t);
        if (step > 0) accumulated += distance_3d(previous, center);
        previous = center;

        RailWorldPoint3 tangent{};
        RailWorldPoint3 normal{};
        if (!planar_frame(segment, t, &tangent, &normal)) return false;
        const RailWorldPoint3 shifted = add(center, scale(normal, center_offset));
        const float half_width = width * 0.5F;
        const RailWorldPoint3 left = add(shifted, scale(normal, half_width));
        const RailWorldPoint3 right = add(shifted, scale(normal, -half_width));
        const float bottom_z = center.z + base_height;
        const float top_z = bottom_z + thickness;
        const float v = accumulated;

        const std::uint32_t base = static_cast<std::uint32_t>(mesh.vertices.size());
        mesh.vertices.push_back({{left.x, left.y, bottom_z}, 0.0F, v});
        mesh.vertices.push_back({{right.x, right.y, bottom_z}, 1.0F, v});
        mesh.vertices.push_back({{left.x, left.y, top_z}, 0.0F, v});
        mesh.vertices.push_back({{right.x, right.y, top_z}, 1.0F, v});

        if (step == 0) continue;
        const std::uint32_t p = base - 4U;
        const std::uint32_t c = base;
        // top, bottom and both vertical sides. End caps are intentionally absent
        // so adjacent graph segments meet without doubled coplanar faces.
        const std::array<std::uint32_t, 24> indices{
            p + 2U, p + 3U, c + 2U, p + 3U, c + 3U, c + 2U,
            p + 0U, c + 0U, p + 1U, p + 1U, c + 0U, c + 1U,
            p + 0U, p + 2U, c + 0U, p + 2U, c + 2U, c + 0U,
            p + 1U, c + 1U, p + 3U, p + 3U, c + 1U, c + 3U,
        };
        mesh.indices.insert(mesh.indices.end(), indices.begin(), indices.end());
    }
    return true;
}

bool append_oriented_box(
    RailMesh& mesh,
    const RailWorldPoint3& center,
    const RailWorldPoint3& tangent,
    const RailWorldPoint3& normal,
    const float along_length,
    const float across_length,
    const float base_z,
    const float height,
    const RailProfile& profile) {
    if (mesh.vertices.size() + 8U > profile.max_vertices || mesh.indices.size() + 36U > profile.max_indices)
        return false;

    const RailWorldPoint3 along = scale(tangent, along_length * 0.5F);
    const RailWorldPoint3 across = scale(normal, across_length * 0.5F);
    const RailWorldPoint3 corners[4] = {
        add(add(center, along), across),
        add(add(center, along), scale(across, -1.0F)),
        add(add(center, scale(along, -1.0F)), scale(across, -1.0F)),
        add(add(center, scale(along, -1.0F)), across),
    };
    const std::uint32_t b = static_cast<std::uint32_t>(mesh.vertices.size());
    for (const RailWorldPoint3& corner : corners)
        mesh.vertices.push_back({{corner.x, corner.y, base_z}, 0.0F, 0.0F});
    for (const RailWorldPoint3& corner : corners)
        mesh.vertices.push_back({{corner.x, corner.y, base_z + height}, 0.0F, 1.0F});

    const std::array<std::uint32_t, 36> indices{
        b+4,b+5,b+6, b+4,b+6,b+7,
        b+0,b+2,b+1, b+0,b+3,b+2,
        b+0,b+1,b+5, b+0,b+5,b+4,
        b+1,b+2,b+6, b+1,b+6,b+5,
        b+2,b+3,b+7, b+2,b+7,b+6,
        b+3,b+0,b+4, b+3,b+4,b+7,
    };
    mesh.indices.insert(mesh.indices.end(), indices.begin(), indices.end());
    return true;
}

[[nodiscard]] RailValidationResult validate_geometry(
    const RailGeometry& geometry, const RailProfile& profile) {
    for (const RailMesh* mesh : {&geometry.ballast, &geometry.sleepers, &geometry.left_rail, &geometry.right_rail}) {
        const RailValidationResult result = RailMeshBuilder::validate_mesh(*mesh, profile);
        if (!result) return result;
    }
    return {};
}

} // namespace

RailWorldPoint3 RailMeshBuilder::sample_cubic(const RailSplineSegment& segment, const float t) {
    const float clamped = std::clamp(t, 0.0F, 1.0F);
    const float omt = 1.0F - clamped;
    const float b0 = omt * omt * omt;
    const float b1 = 3.0F * omt * omt * clamped;
    const float b2 = 3.0F * omt * clamped * clamped;
    const float b3 = clamped * clamped * clamped;
    return {
        segment.start.x * b0 + segment.control_a.x * b1 + segment.control_b.x * b2 + segment.end.x * b3,
        segment.start.y * b0 + segment.control_a.y * b1 + segment.control_b.y * b2 + segment.end.y * b3,
        segment.start.z * b0 + segment.control_a.z * b1 + segment.control_b.z * b2 + segment.end.z * b3,
    };
}

RailWorldPoint3 RailMeshBuilder::tangent_cubic(const RailSplineSegment& segment, const float t) {
    const float clamped = std::clamp(t, 0.0F, 1.0F);
    const float omt = 1.0F - clamped;
    const float a = 3.0F * omt * omt;
    const float b = 6.0F * omt * clamped;
    const float c = 3.0F * clamped * clamped;
    return {
        a * (segment.control_a.x - segment.start.x) + b * (segment.control_b.x - segment.control_a.x) + c * (segment.end.x - segment.control_b.x),
        a * (segment.control_a.y - segment.start.y) + b * (segment.control_b.y - segment.control_a.y) + c * (segment.end.y - segment.control_b.y),
        a * (segment.control_a.z - segment.start.z) + b * (segment.control_b.z - segment.control_a.z) + c * (segment.end.z - segment.control_b.z),
    };
}

RailValidationResult RailMeshBuilder::validate(const RailSplineSegment& segment, const RailProfile& profile) {
    if (!valid_profile(profile)) return failure(RailValidationError::invalid_profile, "rail profile is outside safe structural bounds");
    for (const RailWorldPoint3& p : {segment.start, segment.control_a, segment.control_b, segment.end}) {
        if (!finite_point(p)) return failure(RailValidationError::non_finite_input, "rail spline contains NaN or infinity");
        if (!within_world_extent(p, profile.max_world_abs))
            return failure(RailValidationError::world_extent_exceeded, "rail spline exceeds world safety extent");
    }
    if (segment.subdivisions < profile.min_subdivisions || segment.subdivisions > profile.max_subdivisions)
        return failure(RailValidationError::subdivision_limit, "rail subdivisions exceed configured safety limits");

    const int samples = std::max(16, segment.subdivisions);
    RailWorldPoint3 previous = sample_cubic(segment, 0.0F);
    float length = 0.0F;
    std::vector<RailWorldPoint3> points;
    points.reserve(static_cast<std::size_t>(samples + 1));
    points.push_back(previous);

    for (int i = 0; i <= samples; ++i) {
        const float t = static_cast<float>(i) / static_cast<float>(samples);
        const RailWorldPoint3 point = sample_cubic(segment, t);
        const RailWorldPoint3 tangent = tangent_cubic(segment, t);
        if (!finite_point(point) || !finite_point(tangent))
            return failure(RailValidationError::non_finite_input, "rail evaluation produced non-finite values");
        const float tangent_xy = std::sqrt(tangent.x * tangent.x + tangent.y * tangent.y);
        if (tangent_xy < kEpsilon)
            return failure(RailValidationError::zero_tangent, "rail spline contains a zero planar tangent");
        if (i > 0) {
            const float planar = planar_distance(previous, point);
            if (planar < kEpsilon)
                return failure(RailValidationError::zero_tangent, "rail spline folds into a zero-length sample");
            const float grade = std::abs(point.z - previous.z) / planar;
            if (!finite_value(grade) || grade > profile.max_grade)
                return failure(RailValidationError::grade_too_steep, "rail grade exceeds structural safety limit");
            length += distance_3d(previous, point);
            points.push_back(point);
        }
        previous = point;
    }
    if (length < profile.min_segment_length)
        return failure(RailValidationError::segment_too_short, "rail segment is below minimum safe length");

    for (std::size_t i = 1; i + 1 < points.size(); ++i) {
        const float radius = circumradius_xy(points[i - 1], points[i], points[i + 1]);
        if (finite_value(radius) && radius < profile.min_turn_radius)
            return failure(RailValidationError::turn_radius_too_small, "rail curvature is tighter than minimum radius");
    }
    return {};
}

RailBuildResult RailMeshBuilder::build(const RailSplineSegment& segment, const RailProfile& profile) {
    RailBuildResult result;
    result.validation = validate(segment, profile);
    if (!result.validation) return result;

    const int subdivisions = segment.subdivisions;
    const float sleeper_base = profile.ballast_height;
    const float rail_base = sleeper_base + profile.sleeper_height;

    if (!append_prism_strip(result.geometry.ballast, segment, 0.0F, profile.ballast_width,
                            0.0F, profile.ballast_height, subdivisions, profile) ||
        !append_prism_strip(result.geometry.left_rail, segment, profile.gauge * 0.5F, profile.rail_width,
                            rail_base, profile.rail_height, subdivisions, profile) ||
        !append_prism_strip(result.geometry.right_rail, segment, -profile.gauge * 0.5F, profile.rail_width,
                            rail_base, profile.rail_height, subdivisions, profile)) {
        result.geometry.clear();
        result.validation = failure(RailValidationError::geometry_budget_exceeded, "rail strip geometry exceeds hard mesh budget");
        return result;
    }

    // Deterministic sleeper placement by accumulated chord length. The final
    // sleeper is omitted when too close to the endpoint; a connected segment can
    // place its own first sleeper without creating a doubled stack at the seam.
    float accumulated = 0.0F;
    float next_sleeper = profile.sleeper_spacing * 0.5F;
    RailWorldPoint3 previous = sample_cubic(segment, 0.0F);
    constexpr int kPlacementSamplesPerSubdivision = 4;
    const int placement_samples = std::min(profile.max_subdivisions * kPlacementSamplesPerSubdivision,
                                           subdivisions * kPlacementSamplesPerSubdivision);
    for (int i = 1; i <= placement_samples; ++i) {
        const float t = static_cast<float>(i) / static_cast<float>(placement_samples);
        const RailWorldPoint3 current = sample_cubic(segment, t);
        const float chord = distance_3d(previous, current);
        if (chord <= kEpsilon) {
            result.geometry.clear();
            result.validation = failure(RailValidationError::zero_tangent, "rail sleeper sampling encountered zero-length chord");
            return result;
        }
        const float before = accumulated;
        accumulated += chord;
        while (next_sleeper <= accumulated && next_sleeper < accumulated + profile.sleeper_spacing * 0.25F) {
            const float local = std::clamp((next_sleeper - before) / chord, 0.0F, 1.0F);
            const float sample_t = (static_cast<float>(i - 1) + local) / static_cast<float>(placement_samples);
            RailWorldPoint3 tangent{};
            RailWorldPoint3 normal{};
            if (!planar_frame(segment, sample_t, &tangent, &normal)) {
                result.geometry.clear();
                result.validation = failure(RailValidationError::zero_tangent, "rail sleeper has invalid local frame");
                return result;
            }
            const RailWorldPoint3 center = sample_cubic(segment, sample_t);
            if (!append_oriented_box(result.geometry.sleepers, center, tangent, normal,
                                     profile.sleeper_width, profile.sleeper_length,
                                     center.z + sleeper_base, profile.sleeper_height, profile)) {
                result.geometry.clear();
                result.validation = failure(RailValidationError::geometry_budget_exceeded, "rail sleeper geometry exceeds hard mesh budget");
                return result;
            }
            next_sleeper += profile.sleeper_spacing;
        }
        previous = current;
    }

    result.validation = validate_geometry(result.geometry, profile);
    if (!result.validation) result.geometry.clear();
    return result;
}

RailValidationResult RailMeshBuilder::validate_connection(
    const RailSplineSegment& first, const RailSplineSegment& second, const RailProfile& profile) {
    if (const RailValidationResult a = validate(first, profile); !a) return a;
    if (const RailValidationResult b = validate(second, profile); !b) return b;
    if (distance_3d(first.end, second.start) > profile.connection_tolerance)
        return failure(RailValidationError::disconnected_endpoint, "rail endpoints exceed seam tolerance");

    const RailWorldPoint3 ta = tangent_cubic(first, 1.0F);
    const RailWorldPoint3 tb = tangent_cubic(second, 0.0F);
    const float la = std::sqrt(ta.x * ta.x + ta.y * ta.y);
    const float lb = std::sqrt(tb.x * tb.x + tb.y * tb.y);
    if (la < kEpsilon || lb < kEpsilon)
        return failure(RailValidationError::zero_tangent, "rail connection has zero tangent");
    const float dot = (ta.x * tb.x + ta.y * tb.y) / (la * lb);
    if (!finite_value(dot) || dot < 0.94F)
        return failure(RailValidationError::disconnected_endpoint, "rail connection tangent discontinuity is unsafe");
    return {};
}

RailValidationResult RailMeshBuilder::validate_mesh(const RailMesh& mesh, const RailProfile& profile) {
    if (mesh.empty()) return failure(RailValidationError::degenerate_triangle, "rail mesh is empty");
    if (mesh.vertices.size() > profile.max_vertices || mesh.indices.size() > profile.max_indices)
        return failure(RailValidationError::geometry_budget_exceeded, "rail mesh exceeds hard geometry budget");
    if (mesh.indices.size() % 3U != 0U)
        return failure(RailValidationError::invalid_index, "rail index count is not triangular");

    for (const RailMeshVertex& vertex : mesh.vertices) {
        if (!finite_point(vertex.position) || !finite_value(vertex.u) || !finite_value(vertex.v))
            return failure(RailValidationError::non_finite_input, "rail mesh contains non-finite vertex data");
        if (!within_world_extent(vertex.position, profile.max_world_abs + profile.ballast_width))
            return failure(RailValidationError::world_extent_exceeded, "rail mesh vertex exceeds world safety extent");
    }
    for (std::size_t i = 0; i < mesh.indices.size(); i += 3U) {
        const std::uint32_t ia = mesh.indices[i];
        const std::uint32_t ib = mesh.indices[i + 1U];
        const std::uint32_t ic = mesh.indices[i + 2U];
        if (ia >= mesh.vertices.size() || ib >= mesh.vertices.size() || ic >= mesh.vertices.size())
            return failure(RailValidationError::invalid_index, "rail mesh contains out-of-range index");
        if (ia == ib || ib == ic || ia == ic ||
            triangle_area_twice_squared(mesh.vertices[ia].position, mesh.vertices[ib].position,
                                        mesh.vertices[ic].position) <= kAreaEpsilonSquared)
            return failure(RailValidationError::degenerate_triangle, "rail mesh contains degenerate triangle");
    }
    return {};
}

const char* rail_validation_error_name(const RailValidationError error) {
    switch (error) {
        case RailValidationError::none: return "none";
        case RailValidationError::non_finite_input: return "non_finite_input";
        case RailValidationError::world_extent_exceeded: return "world_extent_exceeded";
        case RailValidationError::invalid_profile: return "invalid_profile";
        case RailValidationError::subdivision_limit: return "subdivision_limit";
        case RailValidationError::segment_too_short: return "segment_too_short";
        case RailValidationError::zero_tangent: return "zero_tangent";
        case RailValidationError::grade_too_steep: return "grade_too_steep";
        case RailValidationError::turn_radius_too_small: return "turn_radius_too_small";
        case RailValidationError::geometry_budget_exceeded: return "geometry_budget_exceeded";
        case RailValidationError::invalid_index: return "invalid_index";
        case RailValidationError::degenerate_triangle: return "degenerate_triangle";
        case RailValidationError::disconnected_endpoint: return "disconnected_endpoint";
    }
    return "unknown";
}
