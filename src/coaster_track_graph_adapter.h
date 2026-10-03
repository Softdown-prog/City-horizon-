#pragma once

#include "coaster_centerline_route.h"
#include "track_graph.h"

#include <utility>
#include <vector>

namespace ch::coaster {

inline constexpr const char* kCoasterTrackGraphAdapterContract = "CH_COASTER_TRACK_GRAPH_ADAPTER_V1";

[[nodiscard]] inline DriveMode coaster_drive_mode(const track::DriveMode mode) noexcept {
    switch (mode) {
        case track::DriveMode::lift: return DriveMode::Lift;
        case track::DriveMode::brake: return DriveMode::Brake;
        case track::DriveMode::station: return DriveMode::Station;
        case track::DriveMode::free: return DriveMode::Free;
    }
    return DriveMode::Free;
}

[[nodiscard]] inline bool rebuild_centerline_from_track_graph(const track::TrackGraph& graph,
                                                               const track::GraphRoute& graph_route,
                                                               CenterlineRoute& output) {
    const track::CompiledPolyline polyline = graph.compile_polyline(graph_route);
    if (!polyline.valid) {
        output.clear();
        return false;
    }

    std::vector<RoutePoint> points;
    points.reserve(polyline.points.size());
    for (const track::WorldRoutePoint& point : polyline.points) {
        points.push_back({
            point.position.x,
            point.position.y,
            point.position.z,
            coaster_drive_mode(point.drive_mode),
            point.target_speed_mps,
        });
    }
    return output.rebuild(std::move(points), polyline.closed);
}

}  // namespace ch::coaster
