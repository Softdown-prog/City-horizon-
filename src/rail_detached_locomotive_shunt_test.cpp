#include "rail_live_operation_controller.h"
#include "rail_placement_controller.h"

#include <array>
#include <cmath>
#include <iostream>
#include <optional>

namespace {
int fail(const char* message){std::cerr<<"Detached locomotive shunt: "<<message<<'\n';return 1;}
bool near(double a,double b,double tol=1.0e-4) {return std::abs(a-b)<tol;}
}

int main() {
    constexpr float kPi=3.14159265358979323846F;
    constexpr float kAngle=0.2617993877991494F;
    // A broad real passing loop: old radius-12 side tracks only separated
    // by 0.4 metres and cannot pass a locomotive next to parked coaches.
    RailPlacementGraph graph;
    const auto root=graph.add_root({0,0,0},0);
    const auto approach=root?graph.append_straight(*root,40):std::nullopt;
    const auto a=approach?graph.append_straight(approach->node,8):std::nullopt;
    const auto rear=a?graph.append_turnout(a->node,96,kAngle,RailTurnDirection::left):std::nullopt;
    const auto far_root=graph.add_root({240,0,0},kPi);
    const auto front=far_root?graph.append_turnout(*far_root,96,kAngle,RailTurnDirection::right):std::nullopt;
    if(!root || !approach || !a || !rear || !far_root || !front)return fail("basic track");

    RailPlacementController editor(graph);
    const float main_length=graph.nodes()[front->through_node].position.x-
                            graph.nodes()[rear->through_node].position.x;
    if(!editor.begin(rear->through_node,RailPlacementMode::straight))
        return fail("mainline editor");
    const auto main=editor.preview(main_length);
    if(!main || main->primary_node!=front->through_node || !editor.commit())
        return fail("mainline joined");
    const auto siding=graph.append_smooth_connector(rear->diverging_node,front->diverging_node);
    if(!siding)return fail("real passing siding");
    const auto a_group=graph.edges()[a->edge].piece_group;
    const auto b_group=graph.edges()[main->primary_edge].piece_group;
    const auto route=ch::rail_operation::compile_route(
        graph,approach->edge,{{a_group,0.25},{b_group,0.5}});
    if(!route.valid || route.closed)return fail("main route compilation");
    const auto connected=ch::rail_operation::find_connected_siding(graph,route);
    if(!connected)return fail("passing siding topology");
    const auto plan=ch::rail_operation::compile_detached_locomotive_shunt(graph,route,*connected);
    if(!plan || !plan->valid || !(plan->length_m>plan->front_turnout_m+100))
        return fail("safe shunt path from actual track");
    if(!near(plan->front_turnout_m,connected->front_distance_m-route.stations[1].distance_m,0.1))
        return fail("headshunt distance mismatch");

    RailPersistentState state;
    state.nodes=graph.nodes();
    state.edges=graph.edges();
    state.stations={{a_group,0.25},{b_group,0.5}};
    ch::rail_live_operation::LiveOperationController controller;
    if(!controller.sync_from_persistent_state(state) ||
       !controller.operation_active() ||
       !controller.connected_siding_available() ||
       !controller.locomotive_shunt_route_safe())return fail("active world controller");

    std::array<ch::track::Point3,7> stopped_coaches{};
    bool detached=false,observed_headshunt=false,observed_reverse=false;
    bool observed_pause=false,await_turntable=false;
    ch::track::Point3 previous_loco{};
    bool previous_valid=false;
    for(int tick=0;tick<7000;++tick) {
        controller.update(0.1);
        const auto units=controller.articulated_poses();
        if(units.size()!=8U)return fail("coach identity lost");
        if(!controller.shunting_locomotive())continue;
        if(!detached) {
            detached=true;
            for(std::size_t k=0;k<7;++k)
                stopped_coaches[k]={units[k+1].pose.x,units[k+1].pose.y,units[k+1].pose.z};
        }
        const auto phase=controller.locomotive_shunt_phase();
        if(!phase)return fail("phase missing");
        if(*phase==ch::rail_operation::DetachedShuntPhase::headshunt_forward)
            observed_headshunt=true;
        if(*phase==ch::rail_operation::DetachedShuntPhase::gear_change)
            observed_pause=true;
        if(*phase==ch::rail_operation::DetachedShuntPhase::bypass_reverse)
            observed_reverse=true;
        const auto loco=controller.train_pose();
        if(!loco)return fail("loco pose missing");
        if(loco->station_piece)return fail("detached engine still has station");
        if(previous_valid) {
            const double d=std::sqrt(std::pow(loco->x-previous_loco.x,2)+
                                     std::pow(loco->y-previous_loco.y,2)+
                                     std::pow(loco->z-previous_loco.z,2));
            if(d>0.41)return fail("locomotive teleport or excessive speed");
        }
        previous_loco={loco->x,loco->y,loco->z};
        previous_valid=true;
        for(std::size_t k=0;k<7;++k){
            if(units[k+1].unit_index!=k+1U ||
               !near(units[k+1].pose.x,stopped_coaches[k].x) ||
               !near(units[k+1].pose.y,stopped_coaches[k].y) ||
               !near(units[k+1].pose.z,stopped_coaches[k].z))
                return fail("coach drifted with detached locomotive");
        }
        if(controller.locomotive_awaiting_turning()) {
            await_turntable=true;
            if(loco->speed_mps!=0.0)return fail("locomotive rolled past end of siding");
            break;
        }
    }
    if(!detached || !observed_headshunt || !observed_pause ||
       !observed_reverse || !await_turntable)return fail("complete safe solo shunt not observed");
    for(int i=0;i<40;++i) {
        controller.update(0.1);
        if(!controller.locomotive_awaiting_turning())return fail("invented turntable or reverse A service");
    }
    if(!controller.restart() || controller.shunting_locomotive() ||
       !controller.locomotive_shunt_route_safe() || !controller.train_pose() ||
       controller.train_pose()->station_piece!=a_group)
        return fail("restart must reset shunt to A");

    // A connected siding with turnouts TOO NARROW for the locomotive
    // must fail the physical clearance gate, despite valid graph topology.
    RailPlacementGraph narrow;
    const auto nr=narrow.add_root({0,10,0},0);
    const auto na=nr?narrow.append_straight(*nr,40):std::nullopt;
    const auto nb=na?narrow.append_straight(na->node,8):std::nullopt;
    const auto nw=nb?narrow.append_turnout(nb->node,12,kAngle,RailTurnDirection::left):std::nullopt;
    const auto nf_root=narrow.add_root({200,10,0},kPi);
    const auto nf=nf_root?narrow.append_turnout(*nf_root,12,kAngle,RailTurnDirection::right):std::nullopt;
    if(!nr||!na||!nb||!nw||!nf_root||!nf)return fail("narrow setup");
    RailPlacementController narrow_editor(narrow);
    if(!narrow_editor.begin(nw->through_node,RailPlacementMode::straight))return fail("narrow editor");
    const auto middle=narrow_editor.preview(
        narrow.nodes()[nf->through_node].position.x-narrow.nodes()[nw->through_node].position.x);
    if(!middle||!narrow_editor.commit() ||
       !narrow.append_smooth_connector(nw->diverging_node,nf->diverging_node))
        return fail("narrow branch build");
    const auto narrow_route=ch::rail_operation::compile_route(
        narrow,na->edge,{{narrow.edges()[nb->edge].piece_group,0.0},
                          {narrow.edges()[middle->primary_edge].piece_group,0.5}});
    const auto narrow_siding=ch::rail_operation::find_connected_siding(narrow,narrow_route);
    if(!narrow_siding ||
       ch::rail_operation::compile_detached_locomotive_shunt(narrow,narrow_route,*narrow_siding))
        return fail("unsafe near-overlapping siding was accepted");
    std::cout<<"CH_RAIL_DETACHED_LOCO_SHUNT_V1: PASS\n";
    return 0;
}
