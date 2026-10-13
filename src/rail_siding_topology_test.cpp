#include "rail_live_operation_controller.h"
#include "rail_placement_controller.h"
#include "rail_siding_topology.h"

#include <cmath>
#include <iostream>
#include <optional>
#include <string>

namespace {
[[nodiscard]] int fail(const char* message) {
    std::cerr<<"CH connected siding regression failed: "<<message<<'\n';
    return 1;
}
}

int main() {
    constexpr float kPi=3.14159265358979323846F;
    constexpr float kAngle=0.2617993877991494F;
    RailPlacementGraph graph;
    const auto root=graph.add_root({0.0F,0.0F,0.0F},0.0F);
    if (!root)return fail("root");
    const auto approach=graph.append_straight(*root,40.0F);
    const auto a_piece=approach?graph.append_straight(approach->node,8.0F):std::nullopt;
    if (!approach||!a_piece)return fail("A approach");
    const auto rear=graph.append_turnout(a_piece->node,12.0F,kAngle,RailTurnDirection::left);
    if(!rear)return fail("rear turnout");
    const auto front_root=graph.add_root({200.0F,0.0F,0.0F},kPi);
    const auto front=front_root?graph.append_turnout(
        *front_root,12.0F,kAngle,RailTurnDirection::right):std::nullopt;
    if(!front)return fail("front turnout");

    RailPlacementController editor(graph);
    if(!editor.begin(rear->through_node,RailPlacementMode::straight))
        return fail("open mainline editor");
    const float span=graph.nodes()[front->through_node].position.x-
                     graph.nodes()[rear->through_node].position.x;
    const auto main_preview=editor.preview(span);
    if(!main_preview || main_preview->primary_node!=front->through_node ||
       !editor.commit())return fail("mainline not welded");
    const auto main_id=graph.edges()[main_preview->primary_edge].piece_group;
    const auto branch=graph.append_smooth_connector(
        rear->diverging_node,front->diverging_node);
    if(!branch)return fail("passing siding not authored");
    const auto siding_group=graph.edges()[branch->edge].piece_group;

    const auto route=ch::rail_operation::compile_route(
        graph,approach->edge,{{graph.edges()[a_piece->edge].piece_group,0.25},
                              {main_id,0.50}});
    if(!route.valid||route.closed||route.stations.size()!=2U)
        return fail("two stations on common mainline invalid");
    if(!(route.stations.front().distance_m<route.stations.back().distance_m))
        return fail("stations not sorted by line position");
    const auto link=ch::rail_operation::find_connected_siding(graph,route);
    if(!link || link->bypass_edges.size()!=3U ||
       link->rear_junction!=a_piece->node ||
       link->front_junction!=*front_root ||
       link->bypass_edges[1]!=branch->edge)
        return fail("true connected siding not detected");

    std::string narrow_diagnostic;
    const auto rejected_shunt=ch::rail_operation::compile_detached_locomotive_shunt(
        graph,route,*link,&narrow_diagnostic);
    if(!rejected_shunt) {
        std::cerr<<"physically authored siding path rejected: "<<narrow_diagnostic<<'\n';
        return fail("connected siding with actual clearance cannot dispatch");
    }

    RailPersistentState state;
    state.fleet = {true, 7U};
    state.nodes=graph.nodes();
    state.edges=graph.edges();
    state.stations={{graph.edges()[a_piece->edge].piece_group,0.25},{main_id,0.5}};
    ch::rail_live_operation::LiveOperationController controller;
    if(!controller.sync_from_persistent_state(state)||
       !controller.operation_active() || !controller.two_station_service_active() ||
       !controller.connected_siding_available())
        return fail("live controller cannot identify constructed siding");

    // Passing siding now allows solo locomotive dispatch; the seven coaches
    // remain at station B. A turning device is still required for B -> A.
    bool dispatched=false;
    for(int i=0;i<1500;++i) {
        controller.update(0.1);
        if(!controller.shunting_locomotive())continue;
        const auto poses=controller.articulated_poses();
        if(poses.size()!=8U)return fail("detached consist lost units");
        if(poses[1].pose.speed_mps!=0.0 ||
           poses[1].pose.station_piece!=main_id)return fail("parked coach moved");
        dispatched=true;
        break;
    }
    if(!dispatched)return fail("actual connected siding never dispatched");

    // Deleting only the connector leaves the stations/mainline intact,
    // but the previous maneuver qualification MUST be invalidated.
    if(graph.remove_piece(siding_group)!=1U)return fail("demolish connector");
    state.nodes=graph.nodes();
    state.edges=graph.edges();
    ch::rail_live_operation::LiveOperationController without_siding;
    if(!without_siding.sync_from_persistent_state(state)||
       !without_siding.two_station_service_active() ||
       without_siding.connected_siding_available())
        return fail("phantom siding survived connector demolition");

    // A crossing or nearby but disconnected graphic should never qualify.
    RailPlacementGraph disconnected;
    const auto dr=disconnected.add_root({0.0F,10.0F,0.0F},0.0F);
    if(!dr)return fail("disconnected root");
    const auto ds=disconnected.append_straight(*dr,80.0F);
    const auto dt=ds?disconnected.append_straight(ds->node,40.0F):std::nullopt;
    if(!ds||!dt)return fail("disconnected track");
    const auto drt=ch::rail_operation::compile_route(disconnected,ds->edge,{
        {disconnected.edges()[ds->edge].piece_group,.5},
        {disconnected.edges()[dt->edge].piece_group,.5}});
    if(!drt.valid || ch::rail_operation::find_connected_siding(disconnected,drt))
        return fail("false positive connected siding on simple straight");

    std::cout<<"CH_RAIL_CONNECTED_SIDING_V1: PASS\n";
    return 0;
}
