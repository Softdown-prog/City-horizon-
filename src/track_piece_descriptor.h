#pragma once

#include <cmath>
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace ch::track {

inline constexpr const char* kTrackPieceDescriptorContract = "CH_TRACK_PIECE_DESCRIPTOR_V1";

enum class NetworkKind : std::uint8_t {
    railway,
    coaster,
};

enum class DriveMode : std::uint8_t {
    free,
    lift,
    brake,
    station,
};

enum class PieceFlag : std::uint32_t {
    none = 0U,
    switch_piece = 1U << 0U,
    crossing = 1U << 1U,
    supports_allowed = 1U << 2U,
};

[[nodiscard]] constexpr std::uint32_t flag_mask(const PieceFlag flag) noexcept {
    return static_cast<std::uint32_t>(flag);
}

struct Point3 {
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;
};

struct PortDescriptor {
    std::string id;
    Point3 position{};
    // Outward-facing tangent from the piece. Two connected ports face each other.
    double heading_radians = 0.0;
    double pitch_radians = 0.0;
};

struct CenterlinePoint {
    Point3 position{};
    double roll_degrees = 0.0;
    DriveMode drive_mode = DriveMode::free;
    // Negative means use the runtime default for this drive mode.
    double target_speed_mps = -1.0;
};

struct RouteDescriptor {
    std::string id;
    std::size_t entry_port = 0U;
    std::size_t exit_port = 0U;
    bool reversible = true;
    std::vector<CenterlinePoint> centerline;
};

struct ClearanceEnvelope {
    double half_width_m = 0.75;
    double height_m = 2.0;
};

struct PieceDescriptor {
    std::string id;
    NetworkKind network = NetworkKind::railway;
    std::uint32_t flags = flag_mask(PieceFlag::supports_allowed);
    double build_cost = 0.0;
    ClearanceEnvelope clearance{};
    std::vector<PortDescriptor> ports;
    std::vector<RouteDescriptor> routes;
};

[[nodiscard]] inline bool finite_point(const Point3& point) noexcept {
    return std::isfinite(point.x) && std::isfinite(point.y) && std::isfinite(point.z);
}

[[nodiscard]] inline double squared_distance(const Point3& a, const Point3& b) noexcept {
    const double dx = a.x - b.x;
    const double dy = a.y - b.y;
    const double dz = a.z - b.z;
    return dx * dx + dy * dy + dz * dz;
}

[[nodiscard]] inline bool has_flag(const PieceDescriptor& descriptor, const PieceFlag flag) noexcept {
    return (descriptor.flags & flag_mask(flag)) != 0U;
}

[[nodiscard]] inline bool valid_descriptor(const PieceDescriptor& descriptor,
                                           const double endpoint_tolerance_m = 1.0e-5) noexcept {
    if (descriptor.id.empty() || descriptor.ports.size() < 2U || descriptor.routes.empty() ||
        !std::isfinite(descriptor.build_cost) || descriptor.build_cost < 0.0 ||
        !std::isfinite(descriptor.clearance.half_width_m) || descriptor.clearance.half_width_m <= 0.0 ||
        !std::isfinite(descriptor.clearance.height_m) || descriptor.clearance.height_m <= 0.0 ||
        !std::isfinite(endpoint_tolerance_m) || endpoint_tolerance_m < 0.0) {
        return false;
    }

    for (std::size_t i = 0; i < descriptor.ports.size(); ++i) {
        const PortDescriptor& port = descriptor.ports[i];
        if (port.id.empty() || !finite_point(port.position) ||
            !std::isfinite(port.heading_radians) || !std::isfinite(port.pitch_radians)) {
            return false;
        }
        for (std::size_t j = i + 1U; j < descriptor.ports.size(); ++j) {
            if (port.id == descriptor.ports[j].id) return false;
        }
    }

    const double endpoint_tolerance_sq = endpoint_tolerance_m * endpoint_tolerance_m;
    for (std::size_t i = 0; i < descriptor.routes.size(); ++i) {
        const RouteDescriptor& route = descriptor.routes[i];
        if (route.id.empty() || route.entry_port >= descriptor.ports.size() ||
            route.exit_port >= descriptor.ports.size() || route.entry_port == route.exit_port ||
            route.centerline.size() < 2U) {
            return false;
        }
        for (std::size_t j = i + 1U; j < descriptor.routes.size(); ++j) {
            if (route.id == descriptor.routes[j].id) return false;
        }
        for (const CenterlinePoint& point : route.centerline) {
            if (!finite_point(point.position) || !std::isfinite(point.roll_degrees) ||
                !std::isfinite(point.target_speed_mps) || point.target_speed_mps < -1.0) {
                return false;
            }
        }
        if (squared_distance(route.centerline.front().position, descriptor.ports[route.entry_port].position) > endpoint_tolerance_sq ||
            squared_distance(route.centerline.back().position, descriptor.ports[route.exit_port].position) > endpoint_tolerance_sq) {
            return false;
        }
    }
    return true;
}

}  // namespace ch::track
