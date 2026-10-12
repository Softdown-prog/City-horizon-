// CH_RAIL_A_B_RUNAROUND_PROOF_V2
// Deterministic C++ rail geometry + continuous locomotive-only run-around.
// This is an isolated railway-motion proof, NOT the interactive game runtime.
// At B: detach -> headshunt -> eastern half-turn -> passing siding ->
// western half-turn -> turntable -> back onto coach 7 -> pull train to A.
// No sprite flip, locomotive swap, or positional teleport on reversal.
#include "rail_articulated_consist.h"
#include "rail_operation_runtime.h"
#include "rail_placement_graph.h"
#include <algorithm>
#include <array>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <string>
#include <vector>

namespace {
constexpr int kFps=16, kFrames=1120;
constexpr double kDt=1.0/kFps;
constexpr double kCruise=10.0, kAcceleration=4.0, kShuntSpeed=7.0;
constexpr double kRadius=6.0, kHalfPi=1.57079632679489661923;
constexpr double kPi=3.14159265358979323846;
constexpr double kLoco=5.2, kCoach=3.9, kGap=0.42;
constexpr double kFirstOffset=(kLoco+kCoach)*.5+kGap;
constexpr double kPitch=kCoach+kGap;
constexpr double kTotalOffset=2*kFirstOffset+6*kPitch;
constexpr int kCoaches=7;

enum class Phase { outward, at_b, shunt, turntable, back_to_coupling, inbound, at_a };
const char* name(Phase p) {
    switch(p) {
    case Phase::outward:return "A_TO_B";
    case Phase::at_b:return "DWELL_B";
    case Phase::shunt:return "RUNAROUND";
    case Phase::turntable:return "TURNTABLE";
    case Phase::back_to_coupling:return "RECOUPLE";
    case Phase::inbound:return "B_TO_A";
    case Phase::at_a:return "DWELL_A";
    }
    return "INVALID";
}

struct Pose2 { double x=0,y=0,tx=1,ty=0; };
void xy(std::ostream& out,double x,double y) {out<<'['<<x<<','<<y<<']';}
void record_pose(std::ostream& out, const Pose2& p,int index,const char* role) {
    out<<"{\"kind\":\""<<role<<"\",\"index\":"<<index<<",\"x\":"<<p.x
       <<",\"y\":"<<p.y<<",\"tx\":"<<p.tx<<",\"ty\":"<<p.ty<<"}";
}
// r=6 semicircles are actual continuous centerlines of the headshunt/loop.
// Their tangents change continuously: no angular or positional snap at joints.
Pose2 runaround_pose(double s,double station_b) {
    const double east=station_b+12.0,west=station_b-49.0;
    const double arc=kPi*kRadius, length=east-west;
    if(s<=12.0)return {station_b+s,-4.0,1.0,0.0};
    s-=12.0;
    if(s<=arc) {
        const double theta=kHalfPi-s/kRadius;
        return {east+kRadius*std::cos(theta),-10.0+kRadius*std::sin(theta),
                std::sin(theta),-std::cos(theta)};
    }
    s-=arc;
    if(s<=length)return {east-s,-16.0,-1.0,0.0};
    s-=length;
    const double theta=-kHalfPi-std::clamp(s,0.0,arc)/kRadius;
    return {west+kRadius*std::cos(theta),-10.0+kRadius*std::sin(theta),
            std::sin(theta),-std::cos(theta)};
}
double runaround_length(){return 12.0+2.0*kPi*kRadius+61.0;}
double length(Pose2 a,Pose2 b){return std::hypot(a.x-b.x,a.y-b.y);}
int fail(const std::string& msg) {std::cerr<<"Rail run-around proof failed: "<<msg<<'\n';return 1;}
} // namespace

int main(int argc,char** argv) {
    if(argc!=2)return fail("usage: rail_ab_video_proof_export trace.json");
    RailPlacementGraph graph;
    const auto root=graph.add_root({-120.0F,-4.0F,0.0F},0.0F);
    if(!root)return fail("root");
    RailPlacementNodeId cursor=*root;
    RailPlacementEdgeId first=kInvalidRailPlacementEdgeId;
    RailPlacementPieceId station_a=kInvalidRailPlacementPieceId,station_b=kInvalidRailPlacementPieceId;
    for(int i=0;i<58;++i) {
        const auto piece=graph.append_straight(cursor,4.0F,12);
        if(!piece)return fail("cannot build railway");
        if(i==0)first=piece->edge;
        if(i==11)station_a=graph.edges().at(piece->edge).piece_group;
        if(i==47)station_b=graph.edges().at(piece->edge).piece_group;
        cursor=piece->node;
    }
    const auto route=ch::rail_operation::compile_route(graph,first,{{station_a,1.5},{station_b,1.5}});
    if(!route.valid||route.closed||route.stations.size()!=2U)return fail("compiled main route");
    const double a=route.stations[0].distance_m,b=route.stations[1].distance_m;
    if(!(b-a>135.0 && a>kTotalOffset+2.0 && route.length_m>b+20.0))
        return fail("station placement clearance");
    auto main_pose=[&](double distance)->Pose2 {
        const auto pose=ch::rail_operation::sample_operational_route_pose(route,distance);
        if(!pose)return {};
        return {pose->x,pose->y,pose->tangent_x,pose->tangent_y};
    };
    const double a_x=main_pose(a).x,b_x=main_pose(b).x;
    if(std::abs((b_x-a_x)-(b-a))>1e-3 || std::abs(main_pose(a).y+4.0)>1e-3)
        return fail("mainline must be an aligned deterministic segment");
    const double coupling=b_x-kTotalOffset;
    if(coupling<=a_x || b_x-49.0>=coupling)return fail("run-around geometry clearance");
    const double shunt_length=runaround_length();
    const auto end=runaround_pose(shunt_length,b_x);
    if(length(end,{b_x-49.0,-4.0,1,0})>1e-6)return fail("siding does not meet the main line");
    // Geometric continuity at run-around joints; all joins must be on track.
    const std::array<double,4> joins={12.0,12.0+kPi*kRadius,12.0+kPi*kRadius+61.0,shunt_length};
    for(const double join:joins) {
        const Pose2 before=runaround_pose(join-1e-5,b_x),after=runaround_pose(join+1e-5,b_x);
        if(length(before,after)>1e-3) return fail("disconnected siding switch");
    }

    std::ofstream out(argv[1]);
    if(!out)return fail("output file");
    out<<std::fixed<<std::setprecision(7);
    out<<"{\"contract\":\"CH_RAIL_A_B_RUNAROUND_PROOF_V2\","
       <<"\"source\":\"C++ RailPlacementGraph + compile_route + continuous railway shunting centerlines\","
       <<"\"capture_type\":\"deterministic_cpp_motion_proof_not_interactive_gameplay\","
       <<"\"fps\":"<<kFps<<",\"frame_count\":"<<kFrames
       <<",\"route_length_m\":"<<route.length_m
       <<",\"stations\":[";
    for(int i=0;i<2;++i) {
        if(i)out<<',';
        const auto& s=route.stations[i];
        const auto p=main_pose(s.distance_m);
        out<<"{\"name\":\""<<(i==0?"A":"B")<<"\",\"distance_m\":"<<s.distance_m
           <<",\"x\":"<<p.x<<",\"y\":"<<p.y<<"}";
    }
    out<<"],\"track\":[";
    for(std::size_t i=0;i<route.polyline.points.size();++i) {
        if(i)out<<',';
        const auto& p=route.polyline.points[i].position;
        xy(out,p.x,p.y);
    }
    out<<"],\"shunt_track\":[";
    for(int i=0;i<=256;++i) {
        if(i)out<<',';
        const Pose2 p=runaround_pose(shunt_length*i/256.,b_x);
        xy(out,p.x,p.y);
    }
    out<<"],\"turntable\":";
    xy(out,b_x-49.0,-4.0);
    out<<",\"frames\":[";

    Phase phase=Phase::outward;
    double loco_distance=a,velocity=0,dwell=1.0,shunt_cursor=0,rotation=0,back_x=b_x-49.0;
    int visits_a=1,visits_b=0,runaround_count=0,turntable_count=0,couple_count=0;
    int forward_out_frames=0,forward_return_frames=0,stationary_coach_frames=0;
    double max_loco_step=0,max_coach_step_during_shunt=0,max_coupler_error=0;
    Pose2 previous_loco{}, previous_coach{};
    bool previous_valid=false;
    // The physical 7 coach identities remain unchanged throughout reversal.
    auto coaches_at_b=[&](int coach)->double {
        return b_x-kFirstOffset-(coach-1)*kPitch;
    };
    for(int frame=0;frame<kFrames;++frame) {
        if(frame>0) {
            switch(phase) {
            case Phase::outward: {
                if(dwell>0) {dwell=std::max(0.0,dwell-kDt);break;}
                velocity=std::min(kCruise,velocity+kAcceleration*kDt);
                loco_distance=std::min(b,loco_distance+velocity*kDt);
                if(loco_distance==b) {++visits_b;phase=Phase::at_b;dwell=1.5;velocity=0;}
                break;
            }
            case Phase::at_b:
                dwell=std::max(0.0,dwell-kDt);
                if(dwell==0) {phase=Phase::shunt;shunt_cursor=0;}
                break;
            case Phase::shunt:
                shunt_cursor=std::min(shunt_length,shunt_cursor+kShuntSpeed*kDt);
                if(shunt_cursor==shunt_length){phase=Phase::turntable;rotation=0;++runaround_count;}
                break;
            case Phase::turntable:
                rotation=std::min(kPi,rotation+kPi*kDt/2.0);
                if(rotation==kPi){phase=Phase::back_to_coupling;back_x=b_x-49.0;++turntable_count;}
                break;
            case Phase::back_to_coupling:
                back_x=std::min(coupling,back_x+kShuntSpeed*kDt);
                if(back_x==coupling){phase=Phase::inbound;loco_distance=coupling-(-120.0);velocity=0;++couple_count;}
                break;
            case Phase::inbound:
                velocity=std::min(kCruise,velocity+kAcceleration*kDt);
                loco_distance=std::max(a,loco_distance-velocity*kDt);
                if(loco_distance==a){phase=Phase::at_a;velocity=0;++visits_a;}
                break;
            case Phase::at_a:break;
            }
        }
        Pose2 locomotive{};
        if(phase==Phase::outward || phase==Phase::at_b)locomotive=main_pose(loco_distance);
        else if(phase==Phase::shunt)locomotive=runaround_pose(shunt_cursor,b_x);
        else if(phase==Phase::turntable)locomotive={b_x-49.0,-4.0,std::cos(rotation),std::sin(rotation)};
        else if(phase==Phase::back_to_coupling)locomotive={back_x,-4.0,-1.0,0.0};
        else {locomotive=main_pose(loco_distance);locomotive.tx=-locomotive.tx;locomotive.ty=-locomotive.ty;}

        const bool attached=phase==Phase::outward || phase==Phase::at_b ||
                            phase==Phase::inbound || phase==Phase::at_a;
        std::array<Pose2,kCoaches> coaches{};
        for(int i=0;i<kCoaches;++i) {
            double x;
            if(phase==Phase::outward)x=locomotive.x-kFirstOffset-i*kPitch;
            else if(phase==Phase::inbound || phase==Phase::at_a)
                x=locomotive.x+kFirstOffset+(kCoaches-1-i)*kPitch;
            else x=coaches_at_b(i+1);
            coaches[static_cast<std::size_t>(i)]={x,-4.0,1.0,0.0};
        }

        if(previous_valid) {
            const double step=length(previous_loco,locomotive);
            max_loco_step=std::max(max_loco_step,step);
            if(step>kCruise*kDt+0.11)return fail("locomotive teleported between motion phases");
            if(!attached) {
                const double coach_step=length(previous_coach,coaches.front());
                max_coach_step_during_shunt=std::max(max_coach_step_during_shunt,coach_step);
                if(coach_step>1e-5)return fail("coach moved during detached maneuver");
                ++stationary_coach_frames;
            }
        }
        if(phase==Phase::outward && frame>0 && loco_distance>a+1 && velocity>0 &&
           locomotive.tx>0.99)++forward_out_frames;
        if(phase==Phase::inbound && velocity>0) {
            if(locomotive.tx>=-0.99)return fail("return locomotive facing backward");
            if(previous_valid && locomotive.x>previous_loco.x+1e-5)
                return fail("wrong return movement heading");
            ++forward_return_frames;
        }
        if(phase==Phase::inbound || phase==Phase::at_a) {
            const double loco_rear=locomotive.x+kLoco*.5;
            const double closest_coach_front=coaches.back().x-kCoach*.5;
            const double error=std::abs((closest_coach_front-loco_rear)-kGap);
            max_coupler_error=std::max(max_coupler_error,error);
            if(error>2e-3)return fail("incorrect post-maneuver locomotive coupling");
        }
        if(frame)out<<',';
        out<<"{\"time_s\":"<<frame*kDt<<",\"distance_m\":"<<loco_distance
           <<",\"phase\":\""<<name(phase)<<"\",\"attached\":"<<(attached?"true":"false")
           <<",\"direction\":"<<((phase==Phase::inbound||phase==Phase::at_a)?-1:1)
           <<",\"speed_mps\":"<<velocity
           <<",\"dwelling\":"<<((phase==Phase::at_b||phase==Phase::at_a)?"true":"false")
           <<",\"units\":[";
        record_pose(out,locomotive,0,"locomotive");
        for(int i=0;i<kCoaches;++i) {
            out<<',';
            record_pose(out,coaches[static_cast<std::size_t>(i)],i+1,"coach");
        }
        out<<"]}";
        previous_loco=locomotive;
        previous_coach=coaches.front();
        previous_valid=true;
    }
    out<<"],\"checks\":{\"visits_a\":"<<visits_a<<",\"visits_b\":"<<visits_b
       <<",\"runaround_completed\":"<<runaround_count
       <<",\"turntable_completed\":"<<turntable_count
       <<",\"recouplings\":"<<couple_count
       <<",\"forward_out_frames\":"<<forward_out_frames
       <<",\"forward_return_frames\":"<<forward_return_frames
       <<",\"stationary_coach_frames\":"<<stationary_coach_frames
       <<",\"max_locomotive_step_m\":"<<max_loco_step
       <<",\"max_detached_coach_step_m\":"<<max_coach_step_during_shunt
       <<",\"max_coupler_error_m\":"<<max_coupler_error<<"}}\n";
    out.close();
    if(visits_a<2 || visits_b!=1 || runaround_count!=1 || turntable_count!=1 ||
       couple_count!=1 || forward_out_frames<50 || forward_return_frames<50 ||
       stationary_coach_frames<50 || phase!=Phase::at_a)
        return fail("A→B shunt and forward-facing B→A did not complete");
    std::cout<<"CH_RAIL_A_B_RUNAROUND_PROOF_V2 PASS: "<<kFrames
             <<" frames, B run-around, turntable, real coach identities, forward A arrival\n";
    return 0;
}
