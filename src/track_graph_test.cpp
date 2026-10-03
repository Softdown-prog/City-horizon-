#include "coaster_track_graph_adapter.h"
#include "track_graph.h"

#include <cassert>
#include <cmath>
#include <iostream>
#include <string>

namespace {

constexpr double kPi = 3.14159265358979323846;

ch::track::PieceDescriptor straight_piece(const std::string& id,
                                          const ch::track::DriveMode mode = ch::track::DriveMode::free,
                                          const double target_speed_mps = -1.0) {
    ch::track::PieceDescriptor descriptor;
    descriptor.id = id;
    descriptor.network = ch::track::NetworkKind::coaster;
    descriptor.build_cost = 10.0;
    descriptor.ports = {
        {"in", {0.0, 0.0, 0.0}, kPi, 0.0},
        {"out", {10.0, 0.0, 0.0}, 0.0, 0.0},
    };
    descriptor.routes = {{
        "main", 0U, 1U, true,
        {
            {{0.0, 0.0, 0.0}, 0.0, mode, target_speed_mps},
            {{10.0, 0.0, 0.0}, 0.0, mode, target_speed_mps},
        },
    }};
    return descriptor;
}

ch::track::PieceDescriptor switch_piece() {
    ch::track::PieceDescriptor descriptor;
    descriptor.id = "switch";
    descriptor.network = ch::track::NetworkKind::coaster;
    descriptor.flags |= ch::track::flag_mask(ch::track::PieceFlag::switch_piece);
    descriptor.ports = {
        {"entry", {0.0, 0.0, 0.0}, kPi, 0.0},
        {"through", {10.0, 0.0, 0.0}, 0.0, 0.0},
        {"diverge", {7.0, 7.0, 0.0}, kPi * 0.25, 0.0},
    };
    descriptor.routes = {
        {"through", 0U, 1U, true,
         {{{0.0, 0.0, 0.0}}, {{10.0, 0.0, 0.0}}}},
        {"diverge", 0U, 2U, true,
         {{{0.0, 0.0, 0.0}}, {{4.0, 1.0, 0.0}}, {{7.0, 7.0, 0.0}}}},
    };
    return descriptor;
}

ch::track::PieceDescriptor corner_piece(const std::string& id) {
    ch::track::PieceDescriptor descriptor;
    descriptor.id = id;
    descriptor.network = ch::track::NetworkKind::coaster;
    descriptor.ports = {
        {"in", {0.0, 0.0, 0.0}, kPi, 0.0},
        {"out", {10.0, 10.0, 0.0}, kPi * 0.5, 0.0},
    };
    descriptor.routes = {{
        "main", 0U, 1U, true,
        {
            {{0.0, 0.0, 0.0}},
            {{5.0, 0.0, 0.0}},
            {{10.0, 5.0, 0.0}},
            {{10.0, 10.0, 0.0}},
        },
    }};
    return descriptor;
}

void test_descriptor_and_connections() {
    ch::track::TrackGraph graph;
    auto a = graph.add_piece(straight_piece("a"));
    auto b = graph.add_piece(straight_piece("b"), {{10.0, 0.0, 0.0}, 0.0});
    assert(a && b);
    assert(graph.connect({*a, 1U}, {*b, 0U}));
    assert(!graph.connect({*a, 0U}, {*b, 1U}));

    const auto route = graph.build_route({*a, 0U});
    assert(route.ok());
    assert(!route.closed);
    assert(route.steps.size() == 2U);
    assert(route.gap && route.gap->piece == *b && route.gap->port == 1U);

    const auto polyline = graph.compile_polyline(route);
    assert(polyline.valid);
    assert(polyline.points.size() == 3U);
    assert(std::abs(polyline.points.back().position.x - 20.0) < 1.0e-9);
}

void test_switch_route_selection() {
    ch::track::TrackGraph graph;
    auto sw = graph.add_piece(switch_piece());
    assert(sw);

    auto through = graph.build_route({*sw, 0U});
    assert(through.ok() && through.gap && through.gap->port == 1U);

    assert(graph.set_active_route(*sw, 1U));
    auto diverge = graph.build_route({*sw, 0U});
    assert(diverge.ok() && diverge.gap && diverge.gap->port == 2U);
    assert(diverge.steps.size() == 1U && diverge.steps.front().route == 1U);
}

void test_drive_metadata_and_coaster_adapter() {
    ch::track::TrackGraph graph;
    auto a = graph.add_piece(straight_piece("station", ch::track::DriveMode::station, 0.0));
    auto b = graph.add_piece(straight_piece("lift", ch::track::DriveMode::lift, 2.5), {{10.0, 0.0, 0.0}, 0.0});
    auto c = graph.add_piece(straight_piece("brake", ch::track::DriveMode::brake, 4.0), {{20.0, 0.0, 0.0}, 0.0});
    assert(a && b && c);
    assert(graph.connect({*a, 1U}, {*b, 0U}));
    assert(graph.connect({*b, 1U}, {*c, 0U}));

    const auto route = graph.build_route({*a, 0U});
    assert(route.ok() && !route.closed);

    ch::coaster::CenterlineRoute centerline;
    assert(ch::coaster::rebuild_centerline_from_track_graph(graph, route, centerline));
    assert(centerline.valid() && !centerline.closed());

    const auto station = centerline.sample(5.0);
    const auto lift = centerline.sample(15.0);
    const auto brake = centerline.sample(25.0);
    assert(station && station->drive_mode == ch::coaster::DriveMode::Station);
    assert(lift && lift->drive_mode == ch::coaster::DriveMode::Lift);
    assert(brake && brake->drive_mode == ch::coaster::DriveMode::Brake);
}

void test_closed_circuit() {
    ch::track::TrackGraph graph;
    auto a = graph.add_piece(corner_piece("a"), {{0.0, 0.0, 0.0}, 0.0});
    auto b = graph.add_piece(corner_piece("b"), {{10.0, 10.0, 0.0}, kPi * 0.5});
    auto c = graph.add_piece(corner_piece("c"), {{0.0, 20.0, 0.0}, kPi});
    auto d = graph.add_piece(corner_piece("d"), {{-10.0, 10.0, 0.0}, -kPi * 0.5});
    assert(a && b && c && d);
    assert(graph.connect({*a, 1U}, {*b, 0U}));
    assert(graph.connect({*b, 1U}, {*c, 0U}));
    assert(graph.connect({*c, 1U}, {*d, 0U}));
    assert(graph.connect({*d, 1U}, {*a, 0U}));

    const auto route = graph.build_route({*a, 0U});
    assert(route.ok() && route.closed && route.steps.size() == 4U);
    const auto polyline = graph.compile_polyline(route);
    assert(polyline.valid && polyline.closed);

    ch::coaster::CenterlineRoute centerline;
    assert(ch::coaster::rebuild_centerline_from_track_graph(graph, route, centerline));
    assert(centerline.valid() && centerline.closed());
}

void test_misaligned_ports_fail_closed() {
    ch::track::TrackGraph graph;
    auto a = graph.add_piece(straight_piece("a"));
    auto b = graph.add_piece(straight_piece("b"), {{10.25, 0.0, 0.0}, 0.0});
    assert(a && b);
    assert(!graph.connect({*a, 1U}, {*b, 0U}));
}

}  // namespace

int main() {
    test_descriptor_and_connections();
    test_switch_route_selection();
    test_drive_metadata_and_coaster_adapter();
    test_closed_circuit();
    test_misaligned_ports_fail_closed();
    std::cout << "CH_TRACK_GRAPH_V1: OK\n";
    return 0;
}
