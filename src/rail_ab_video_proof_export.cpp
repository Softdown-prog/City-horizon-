// CH_RAIL_A_B_PROOF_V1: deterministic native C++ station-to-station shuttle trace.
// The locomotive remains physically attached on reversal: this is a push-pull
// consist; there is no teleport or fake forward-facing locomotive on the return.
#include "rail_articulated_consist.h"
#include "rail_operation_runtime.h"
#include "rail_placement_graph.h"
#include <algorithm>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>

namespace {
constexpr int kFrames=640, kFps=16;
constexpr double kDt=1.0/kFps, kSpeed=7.5, kAccel=3.0, kDwell=2.0;
void xy(std::ostream& out,double x,double y) {out<<'['<<x<<','<<y<<']';}
}

int main(int argc,char** argv) {
    if(argc!=2){std::cerr<<"usage: rail_ab_video_export trace.json\n";return 1;}
    RailPlacementGraph graph;
    auto start=graph.add_root({-72.0F,-4.0F,0.0F},0.0F);
    if(!start)return 2;
    RailPlacementNodeId cursor=*start;
    RailPlacementEdgeId first=kInvalidRailPlacementEdgeId;
    RailPlacementPieceId station_a=kInvalidRailPlacementPieceId,station_b=kInvalidRailPlacementPieceId;
    for(int i=0;i<38;++i) {
        auto part=graph.append_straight(cursor,4.0F,16);
        if(!part)return 3;
        if(i==0)first=part->edge;
        if(i==11)station_a=graph.edges().at(part->edge).piece_group;
        if(i==27)station_b=graph.edges().at(part->edge).piece_group;
        cursor=part->node;
    }
    const auto route=ch::rail_operation::compile_route(graph,first,{{station_a,kDwell},{station_b,kDwell}});
    if(!route.valid||route.closed||route.stations.size()!=2||route.length_m<150.)return 4;
    const double a=route.stations[0].distance_m,b=route.stations[1].distance_m;
    if(!(b>a+45.&&a>35.&&b+8.<route.length_m))return 5;
    double distance=a,velocity=0,dwell=kDwell;
    int direction=1,visits_a=1,visits_b=0,reversals=0,fully_visible=0;
    double max_gap=0;
    std::ofstream out(argv[1]);
    if(!out)return 6;
    out<<std::fixed<<std::setprecision(6);
    out<<"{\"contract\":\"CH_RAIL_A_B_PROOF_V1\",\"source\":\"C++ RailPlacementGraph + compile_route + articulated consist\",\"capture_type\":\"native_cpp_trace_composited_not_gameplay_capture\",\"fps\":"<<kFps<<",\"frame_count\":"<<kFrames
       <<",\"route_length_m\":"<<route.length_m<<",\"stations\":[";
    for(int i=0;i<2;++i) {
        const auto& s=route.stations[i];
        const auto p=ch::rail_operation::sample_operational_route_pose(route,s.distance_m);
        if(!p)return 7;
        if(i)out<<',';
        out<<"{\"name\":\""<<(i==0?"A":"B")<<"\",\"distance_m\":"<<s.distance_m<<",\"x\":"<<p->x<<",\"y\":"<<p->y<<"}";
    }
    out<<"],\"track\":[";
    for(std::size_t i=0;i<route.polyline.points.size();++i) {
        if(i)out<<',';
        const auto& p=route.polyline.points[i].position;
        xy(out,p.x,p.y);
    }
    out<<"],\"frames\":[";
    for(int frame=0;frame<kFrames;++frame) {
        if(frame>0) {
            if(dwell>0) {
                dwell=std::max(0.0,dwell-kDt);
                velocity=0;
            } else {
                velocity=std::min(kSpeed,velocity+kAccel*kDt);
                const double target=direction>0?b:a;
                const double step=std::min(std::abs(target-distance),velocity*kDt);
                distance+=direction*step;
                if(std::abs(target-distance)<1e-7) {
                    distance=target;
                    dwell=kDwell;
                    velocity=0;
                    if(direction>0)++visits_b;else ++visits_a;
                    direction=-direction;
                    ++reversals;
                }
            }
        }
        const auto sampled=ch::rail_operation::sample_operational_route_pose(route,distance,velocity,dwell>0);
        if(!sampled)return 8;
        const auto units=ch::rail_operation::build_articulated_consist_poses(route,*sampled);
        if(units.size()!=8)return 9; // both stations must support all seven coaches
        ++fully_visible;
        for(std::size_t i=1;i<units.size();++i) {
            const auto& front=units[i-1],&rear=units[i];
            const double front_len=front.kind==ch::rail_operation::ConsistUnitKind::locomotive?5.2:3.9;
            const double back_len=3.9;
            const double gap=std::hypot(
                front.pose.x-front.pose.tangent_x*front_len*.5-(rear.pose.x+rear.pose.tangent_x*back_len*.5),
                front.pose.y-front.pose.tangent_y*front_len*.5-(rear.pose.y+rear.pose.tangent_y*back_len*.5));
            max_gap=std::max(max_gap,gap);
            if(gap>.75)return 10;
        }
        if(frame)out<<',';
        out<<"{\"time_s\":"<<frame*kDt<<",\"distance_m\":"<<distance
           <<",\"direction\":"<<direction<<",\"speed_mps\":"<<velocity
           <<",\"dwelling\":"<<(dwell>0?"true":"false")<<",\"units\":[";
        for(std::size_t i=0;i<units.size();++i) {
            if(i)out<<',';
            const auto& u=units[i];
            // Rotation of the complete train is not faked: every physical unit
            // stays at its C++ sampled position when the direction reverses.
            out<<"{\"kind\":\""<<(i==0?"locomotive":"coach")<<"\",\"index\":"<<u.unit_index
               <<",\"x\":"<<u.pose.x<<",\"y\":"<<u.pose.y
               <<",\"tx\":"<<u.pose.tangent_x<<",\"ty\":"<<u.pose.tangent_y<<"}";
        }
        out<<"]}";
    }
    out<<"],\"checks\":{\"visits_a\":"<<visits_a<<",\"visits_b\":"<<visits_b
       <<",\"reversals\":"<<reversals<<",\"full_consist_frames\":"<<fully_visible
       <<",\"max_coupler_gap_m\":"<<max_gap<<"}}\n";
    out.close();
    if(visits_a<2||visits_b<1||reversals<2)return 11;
    std::cout<<"CH_RAIL_A_B_PROOF_V1 PASS: "<<kFrames<<" frames; A visits "<<visits_a<<"; B visits "<<visits_b<<"; reversals "<<reversals<<"\n";
    return 0;
}
