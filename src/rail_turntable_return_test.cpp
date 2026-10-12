#include "rail_live_operation_controller.h"
#include "rail_placement_controller.h"
#include "rail_persistence.h"

#include <array>
#include <cmath>
#include <iostream>
#include <optional>
#include <unordered_set>
#include <vector>

namespace {
int fail(const char* msg){std::cerr<<"CH_RAIL_TURNTABLE_RETURN_V1: "<<msg<<'\n';return 1;}
bool near(double a,double b,double tolerance=.001){return std::abs(a-b)<=tolerance;}
}

int main() {
    constexpr float pi=3.14159265358979323846F, angle=0.2617993877991494F;
    RailPlacementGraph graph;
    const auto root=graph.add_root({0.0F,0.0F,0.0F},0.0F);
    if(!root)return fail("root");
    const auto approach=graph.append_straight(*root,40.0F);
    if(!approach)return fail("turntable-bearing 40m straight");
    const auto a=graph.append_straight(approach->node,8.0F);
    if(!a)return fail("station A piece");
    const auto rear=graph.append_turnout(a->node,96.0F,angle,RailTurnDirection::left);
    if(!rear)return fail("rear turnout");
    const auto far_root=graph.add_root({240.0F,0.0F,0.0F},pi);
    if(!far_root)return fail("far root");
    const auto front=graph.append_turnout(*far_root,96.0F,angle,RailTurnDirection::right);
    if(!front)return fail("front turnout");

    RailPlacementController editor(graph);
    if(!editor.begin(rear->through_node,RailPlacementMode::straight))return fail("main track edit");
    const float main_length=graph.nodes()[front->through_node].position.x-
                            graph.nodes()[rear->through_node].position.x;
    const auto straight=editor.preview(main_length);
    if(!straight || straight->primary_node!=front->through_node || !editor.commit())
        return fail("mainline two turnout connection");
    const auto siding=graph.append_smooth_connector(rear->diverging_node,front->diverging_node);
    if(!siding)return fail("connected siding");

    RailPersistentState state;
    state.nodes=graph.nodes();
    state.edges=graph.edges();
    const auto a_group=graph.edges()[a->edge].piece_group;
    const auto b_group=graph.edges()[straight->primary_edge].piece_group;
    const auto table_group=graph.edges()[approach->edge].piece_group;
    state.stations={{a_group,0.25},{b_group,0.5}};
    std::unordered_set<RailPlacementPieceId> groups;
    for(const auto& edge:state.edges) {
        if(!groups.insert(edge.piece_group).second)continue;
        state.actions.push_back({edge.piece_group,1250,812,true});
    }
    if(!ch::rail_persistence::validate(state))return fail("baseline persisted yard");
    ch::rail_live_operation::LiveOperationController no_device;
    if(!no_device.sync_from_persistent_state(state) ||
       !no_device.connected_siding_available() || !no_device.locomotive_shunt_route_safe() ||
       no_device.turntable_return_available())return fail("unbuilt turntable gate");

    state.turntables={{table_group,3500,2275}};
    if(!ch::rail_persistence::validate(state))return fail("paid turntable validation");
    const auto v3=ch::rail_persistence::serialize_payload(state);
    RailPersistentState restored;
    if(v3.empty() || !ch::rail_persistence::deserialize_payload(v3,restored) ||
       restored.turntables.size()!=1U)return fail("persistent turntable reload");
    ch::rail_live_operation::LiveOperationController service;
    if(!service.sync_from_persistent_state(restored) ||
       !service.operation_active() || !service.two_station_service_active() ||
       !service.turntable_return_available())return fail("turntable return qualification");

    std::array<ch::track::Point3,7> parked{};
    bool fixed_coaches=false,headshunt=false,siding_seen=false,approach_seen=false;
    bool rotation_seen=false,reverse_to_coach=false,coupled=false,home=false;
    bool previous_pose=false;
    ch::track::Point3 previous{};
    int moving_return_frames=0,stationary_coach_frames=0,rotating_frames=0;
    for(int tick=0;tick<8000;++tick) {
        service.update(0.1);
        const auto units=service.articulated_poses();
        if(units.size()!=8U)return fail("eight-unit identity violated");
        const auto loc=service.train_pose();
        if(!loc)return fail("locomotive missing");
        const auto pos=ch::track::Point3{loc->x,loc->y,loc->z};
        if(previous_pose && service.shunting_locomotive()){
            const double step=ch::rail_operation::detail::point_distance(pos,previous);
            if(step>0.38)return fail("locomotive position jumped / exceeded shunt speed");
        }
        previous=pos;
        previous_pose=true;
        if(service.shunting_locomotive() && !fixed_coaches) {
            fixed_coaches=true;
            for(int j=0;j<7;++j) {
                parked[j]={units[j+1].pose.x,units[j+1].pose.y,units[j+1].pose.z};
            }
        }
        if(service.shunting_locomotive()){
            for(int j=0;j<7;++j){
                if(units[j+1].unit_index!=static_cast<std::size_t>(j+1) ||
                   !near(units[j+1].pose.x,parked[j].x) ||
                   !near(units[j+1].pose.y,parked[j].y))
                    return fail("parked coach moved or reordered during maneuver");
            }
            ++stationary_coach_frames;
        }
        if(const auto p=service.locomotive_shunt_phase()){
            if(*p==ch::rail_operation::DetachedShuntPhase::headshunt_forward)headshunt=true;
            if(*p==ch::rail_operation::DetachedShuntPhase::bypass_reverse)siding_seen=true;
        }
        if(service.return_service_active()) {
            switch(service.return_phase()){
            case ch::rail_operation::ReturnPhase::approach_turntable:
                approach_seen=true;
                break;
            case ch::rail_operation::ReturnPhase::rotate_180:
                rotation_seen=true;++rotating_frames;
                if(loc->speed_mps!=0.0)return fail("locomotive moved while turntable spinning");
                if(std::abs(std::hypot(loc->tangent_x,loc->tangent_y)-1.0)>0.001)
                    return fail("turntable orientation not unit vector");
                break;
            case ch::rail_operation::ReturnPhase::reverse_to_coach:
                reverse_to_coach=true;
                if(loc->tangent_x>-.95)return fail("locomotive wrong-facing on back-coupling");
                break;
            case ch::rail_operation::ReturnPhase::coupled_return:
                coupled=true;++moving_return_frames;
                if(loc->tangent_x>-.95 ||
                   units[1].unit_index!=7U || units[7].unit_index!=1U)
                    return fail("not pulling seven coaches in physical reversed order");
                if(!near(units[1].route_distance_m-loc->distance_m,4.97,.025))
                    return fail("incorrect locomotive-to-coach7 coupling gap");
                break;
            case ch::rail_operation::ReturnPhase::parked_at_a:
                home=true;
                if(!loc->station_piece || *loc->station_piece!=a_group ||
                   loc->speed_mps!=0.0 || !near(loc->distance_m,44.0,.05) ||
                   units[1].unit_index!=7U || units[7].unit_index!=1U)
                    return fail("train failed to park facing west at A");
                break;
            default:break;
            }
        }
        if(home)break;
    }
    if(!fixed_coaches || !headshunt || !siding_seen || !approach_seen ||
       !rotation_seen || !reverse_to_coach || !coupled || !home ||
       stationary_coach_frames<70 || moving_return_frames<50 || rotating_frames<20)
        return fail("complete A-B-shunt-turn-couple-B-A proof unfinished");
    for(int i=0;i<20;++i){
        service.update(0.1);
        if(service.return_phase()!=ch::rail_operation::ReturnPhase::parked_at_a ||
           service.train_pose()->speed_mps!=0.0)
            return fail("arrived A did not hold station stop");
    }
    if(!service.restart() || !service.turntable_return_available() ||
       service.return_service_active() ||
       !service.train_pose() || service.train_pose()->station_piece!=a_group)
        return fail("restart full service from station A");

    // Removing the table prevents B->A despite the rail siding surviving.
    restored.turntables.clear();
    ch::rail_live_operation::LiveOperationController table_removed;
    if(!table_removed.sync_from_persistent_state(restored) ||
       !table_removed.connected_siding_available() ||
       table_removed.turntable_return_available())return fail("table demolition not respected");

    // A table too close to the rear turnout or attached to an unrelated
    // station segment is not equivalent to an actually constructed turntable.
    restored.turntables={{b_group,3500,2275}};
    const auto connected=ch::rail_operation::find_connected_siding(
        graph,ch::rail_operation::compile_route(graph,approach->edge,{{a_group,.25},{b_group,.5}}));
    const auto route=ch::rail_operation::compile_route(
        graph,approach->edge,{{a_group,.25},{b_group,.5}});
    if(!connected)return fail("siding missing for negative test");
    const auto shunt=ch::rail_operation::compile_detached_locomotive_shunt(graph,route,*connected);
    if(!shunt || ch::rail_operation::compile_turntable_return(
         graph,route,*connected,*shunt,restored.turntables))
        return fail("unauthorized table near B qualified for return");
    std::cout<<"CH_RAIL_TURNTABLE_RETURN_V1: PASS complete A -> B -> A\n";
    return 0;
}
