// CH_RAIL_LIVE_VIDEO_PROOF_V1
// Exports authentic poses from City Horizon's production rail graph,
// train motion runtime and articulated-consist sampler. No invented motion.
#include "rail_articulated_consist.h"
#include "rail_operation_runtime.h"
#include "rail_placement_graph.h"
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <optional>
#include <string>
#include <vector>

namespace {
constexpr int kFrames = 216;
constexpr double kStepSeconds = 0.20;
void xy(std::ostream& os, double x, double y) { os << '[' << x << ',' << y << ']'; }
[[nodiscard]] int fail(const char* error) { std::cerr << error << '\n'; return 1; }
} // namespace

int main(int argc, char** argv) {
    if (argc != 2) return fail("usage: rail_live_video_proof_export <poses.json>");
    RailPlacementGraph graph;
    const auto root = graph.add_root({-50.0F, -10.0F, 0.0F}, 0.0F);
    if (!root) return fail("cannot place rail root");
    RailPlacementNodeId cursor = *root;
    RailPlacementEdgeId first_edge = kInvalidRailPlacementEdgeId;
    RailPlacementPieceId station_group = kInvalidRailPlacementPieceId;
    auto add_straight = [&](int count, bool set_station) {
        for (int i = 0; i < count; ++i) {
            const auto piece = graph.append_straight(cursor, 4.0F, 24);
            if (!piece) return false;
            if (first_edge == kInvalidRailPlacementEdgeId) first_edge = piece->edge;
            if (set_station && i == 2) station_group = graph.edges().at(piece->edge).piece_group;
            cursor = piece->node;
        }
        return true;
    };
    auto add_curve = [&](RailTurnDirection direction) {
        const auto curve = graph.append_quarter_curve(cursor, 7.0F, direction, 48);
        if (!curve) return false;
        cursor = curve->node;
        return true;
    };
    if (!add_straight(10, false) || !add_curve(RailTurnDirection::left) ||
        !add_straight(5, true) || !add_curve(RailTurnDirection::right) ||
        !add_straight(14, false) || station_group == kInvalidRailPlacementPieceId) {
        return fail("cannot construct production straight/curve route");
    }
    const auto route = ch::rail_operation::compile_route(
        graph, first_edge, {{station_group, 2.0}});
    if (!route.valid || route.length_m < 110.0 || route.stations.size() != 1)
        return fail("production route or station invalid");

    ch::rail_operation::TrainRuntime train(route);
    train.set_cruise_speed_mps(3.25);
    train.set_acceleration_mps2(1.25);
    if (!train.valid()) return fail("production train invalid");

    std::ofstream out(argv[1]);
    if (!out) return fail("cannot open output");
    out << std::fixed << std::setprecision(6);
    out << "{\"contract\":\"CH_RAIL_LIVE_VIDEO_PROOF_V1\","
           "\"source\":\"rail_operation_runtime + rail_articulated_consist + rail_placement_graph\","
           "\"capture_type\":\"deterministic_native_runtime_trace_not_gameplay_screen_capture\","
           "\"fps\":16,\"frame_count\":" << kFrames << ",\"route_length_m\":" << route.length_m
        << ",\"station_distance_m\":" << route.stations.front().distance_m << ",\"track\":[";
    for (std::size_t i=0; i<route.polyline.points.size(); ++i) {
        if (i) out << ',';
        const auto& p = route.polyline.points[i].position;
        xy(out,p.x,p.y);
    }
    out << "],\"frames\":[";

    double prev_distance = -1.0;
    bool moved=false, dwelled=false, turned=false, full_consist=false;
    std::size_t max_units=0;
    for (int frame=0; frame<kFrames; ++frame) {
        if (frame > 0) train.update(kStepSeconds);
        const auto lead = train.pose();
        if (!lead) return fail("native train returned no pose");
        if (lead->distance_m < prev_distance - 1.0e-4) return fail("runtime distance went backward");
        if (lead->distance_m > 0.15) moved = true;
        if (lead->dwelling) dwelled = true;
        if (std::abs(lead->tangent_y) > 0.8) turned = true;
        prev_distance=lead->distance_m;
        const auto units=ch::rail_operation::build_articulated_consist_poses(route,*lead);
        if (units.empty() || units.size()>8 || units.front().kind!=ch::rail_operation::ConsistUnitKind::locomotive)
            return fail("invalid articulated unit output");
        max_units=std::max(max_units,units.size());
        if (units.size()==8) full_consist=true;
        if (frame) out << ',';
        out << "{\"time_s\":" << frame/16.0 << ",\"distance_m\":" << lead->distance_m
            << ",\"speed_mps\":" << lead->speed_mps << ",\"dwelling\":"
            << (lead->dwelling?"true":"false") << ",\"units\":[";
        for (std::size_t i=0;i<units.size();++i) {
            const auto& u=units[i];
            if (i) out << ',';
            const auto sampled=ch::rail_operation::sample_operational_route_pose(route,u.route_distance_m);
            if (!sampled || std::hypot(sampled->x-u.pose.x,sampled->y-u.pose.y)>1.0e-5)
                return fail("a vehicle has drifted off the canonical track centerline");
            if (i>0 && (u.kind!=ch::rail_operation::ConsistUnitKind::passenger_coach ||
                        u.route_distance_m>=units[i-1].route_distance_m))
                return fail("coach order or spacing invalid");
            out << "{\"kind\":\"" << (i==0?"locomotive":"coach") << "\",\"index\":" << u.unit_index
                << ",\"distance_m\":" << u.route_distance_m
                << ",\"x\":" << u.pose.x << ",\"y\":" << u.pose.y
                << ",\"tx\":" << u.pose.tangent_x << ",\"ty\":" << u.pose.tangent_y << '}';
        }
        out << "]}";
    }
    out << "],\"checks\":{\"moved\":" << (moved?"true":"false")
        << ",\"station_dwell\":" << (dwelled?"true":"false")
        << ",\"curve_heading_change\":" << (turned?"true":"false")
        << ",\"eight_units\":" << (full_consist?"true":"false")
        << ",\"max_units\":" << max_units << "}}\n";
    out.close();
    if (!moved || !dwelled || !turned || !full_consist)
        return fail("incomplete proof: motion, curve, stop, or full consist missing");
    std::cout << "CH_RAIL_LIVE_VIDEO_PROOF_V1 PASS: " << kFrames
              << " native frames; " << max_units << " consist units; curved track; station dwell\n";
    return 0;
}
