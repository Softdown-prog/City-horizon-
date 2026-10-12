#pragma once
// CH_RAIL_DETACHED_LOCO_SHUNT_V1
// Real, persisted track geometry only. No phantom turntable, no fake A return.
// B -> front turnout, stop and change gear -> back through passing siding
// to rear turnout. Park awaiting a later physically constructed turning device.
#include "rail_articulated_consist.h"
#include "rail_siding_topology.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <optional>
#include <string>
#include <vector>

namespace ch::rail_operation {

struct ShuntPath {
    std::vector<ch::track::Point3> points;
    std::vector<double> cumulative_m;
    double front_turnout_m = 0.0;
    double length_m = 0.0;
    double station_b_distance_m = 0.0;
    bool valid = false;
};

namespace shunt_detail {

[[nodiscard]] inline bool near(const ch::track::Point3& a,
                               const ch::track::Point3& b,
                               const double tolerance) noexcept {
    return detail::point_distance(a,b)<=tolerance;
}

[[nodiscard]] inline ch::track::Point3 at(const RailWorldPoint3& p) noexcept {
    return {p.x,p.y,p.z};
}

[[nodiscard]] inline bool push(ShuntPath& path, const ch::track::Point3& point) {
    if (!std::isfinite(point.x) || !std::isfinite(point.y) || !std::isfinite(point.z))
        return false;
    if (path.points.empty()) {
        path.points.push_back(point);
        path.cumulative_m.push_back(0.0);
        return true;
    }
    const double gap=detail::point_distance(path.points.back(),point);
    if (gap<=1.0e-5) return true;
    if (gap>0.6 || !std::isfinite(gap)) return false; // disallow jumps
    path.points.push_back(point);
    path.cumulative_m.push_back(path.cumulative_m.back()+gap);
    return true;
}

} // namespace shunt_detail

[[nodiscard]] inline std::optional<ShuntPath> compile_detached_locomotive_shunt(
    const RailPlacementGraph& placement, const OperationalRoute& route,
    const ConnectedSiding& siding, std::string* diagnostic = nullptr) {
    const auto reject=[&](const char* why)->std::optional<ShuntPath> {
        if(diagnostic != nullptr)*diagnostic=why;
        return std::nullopt;
    };
    if(!route.valid || route.closed || route.stations.size()!=2U ||
       siding.bypass_edges.size()<3U || route.length_m<=0.0 ||
       siding.front_distance_m<=route.stations.back().distance_m+5.2 ||
       siding.front_distance_m>route.length_m+1.0e-3 ||
       siding.rear_distance_m>=route.stations.back().distance_m-41.0 ||
       siding.rear_junction>=placement.nodes().size() ||
       siding.front_junction>=placement.nodes().size())
        return reject("shunt-check-1");

    // The full graph, not only near-looking sprites, must be connected.
    if(!ch::rail::build_track_graph(placement).valid)return reject("shunt-check-2");
    ShuntPath result;
    const double b=route.stations.back().distance_m;
    result.station_b_distance_m=b;
    const double run=siding.front_distance_m-b;
    const int steps=std::max(1,static_cast<int>(std::ceil(run/0.35)));
    for(int i=0;i<=steps;++i) {
        // Distance sums are compiled independently from authored spline
        // segments and their polyline samples. Clamp their ~1e-5 endpoint
        // rounding difference rather than treating an in-map turnout as off-map.
        const double distance=std::clamp(b+run*i/steps,0.0,route.length_m);
        const auto point=sample_operational_route_pose(route,distance);
        if(!point || !shunt_detail::push(result,{point->x,point->y,point->z}))
            return reject("shunt-check-3");
    }
    const auto front=shunt_detail::at(placement.nodes()[siding.front_junction].position);
    if (!shunt_detail::near(result.points.back(),front,0.03))
        return reject("shunt-check-4");
    result.front_turnout_m=result.cumulative_m.back();

    // Existing saved siding sequence goes rear -> front. Traverse it in the
    // opposite direction: front -> rear, keeping real per-edge endpoints.
    RailPlacementNodeId cursor=siding.front_junction;
    for(auto it=siding.bypass_edges.rbegin();it!=siding.bypass_edges.rend();++it) {
        const auto* edge=placement.edge(*it);
        if(!edge || !edge->active)return reject("shunt-check-5");
        const bool forward=edge->from==cursor;
        if(!forward && edge->to!=cursor)return reject("shunt-check-6");
        const auto destination=forward?edge->to:edge->from;
        if(destination>=placement.nodes().size())return reject("shunt-check-7");
        const auto& curve=edge->segment;
        const auto chord_length=[](const RailWorldPoint3& a,const RailWorldPoint3& b) {
            return std::sqrt(static_cast<double>(a.x-b.x)*(a.x-b.x)+
                             static_cast<double>(a.y-b.y)*(a.y-b.y)+
                             static_cast<double>(a.z-b.z)*(a.z-b.z));
        };
        const double polygon=chord_length(curve.start,curve.control_a)+
                             chord_length(curve.control_a,curve.control_b)+
                             chord_length(curve.control_b,curve.end);
        if (!std::isfinite(polygon) || !(polygon>0.0))return reject("shunt-check-8");
        const int kCurveSamples=std::max(64,static_cast<int>(std::ceil(polygon/0.28)));
        if (kCurveSamples>4096)return reject("shunt-check-9");
        for(int i=0;i<=kCurveSamples;++i) {
            const float t=static_cast<float>(i)/static_cast<float>(kCurveSamples);
            const auto position=RailMeshBuilder::sample_cubic(edge->segment,forward?t:1.0F-t);
            if(i==0 && !shunt_detail::near(result.points.back(),shunt_detail::at(position),0.03))
                return reject("shunt-check-10");
            if(!shunt_detail::push(result,shunt_detail::at(position)))return reject("shunt-check-11");
        }
        cursor=destination;
    }
    if(cursor!=siding.rear_junction ||
       !shunt_detail::near(result.points.back(),
                           shunt_detail::at(placement.nodes()[cursor].position),0.03))
        return reject("shunt-check-12");

    // Physical clearance for a 1+7 consist left at B. A visually connected
    // turnout with a 0.4m offset is NOT a passing siding: loco would intersect
    // the parked coaches. Ignore the initial B->front headshunt.
    const auto stopped_lead=sample_operational_route_pose(route,b);
    if(!stopped_lead)return reject("shunt-check-13");
    const auto coaches=build_articulated_consist_poses(route,*stopped_lead);
    if(coaches.size()!=8U)return reject("shunt-check-14");
    constexpr double kMinLocoCoachCenterDistance=2.65;
    for(std::size_t i=0;i<result.points.size();++i) {
        if(result.cumulative_m[i]<=result.front_turnout_m+0.01)continue;
        for(std::size_t j=1;j<coaches.size();++j) {
            const ch::track::Point3 c{coaches[j].pose.x,coaches[j].pose.y,coaches[j].pose.z};
            if(detail::point_distance(result.points[i],c)<kMinLocoCoachCenterDistance)
                return reject("shunt-check-15");
        }
    }
    result.length_m=result.cumulative_m.back();
    if(!(result.length_m>result.front_turnout_m+10.0) ||
       !std::isfinite(result.length_m))return reject("shunt-check-16");
    result.valid=true;
    return result;
}

enum class DetachedShuntPhase {
    idle, headshunt_forward, gear_change, bypass_reverse, await_turning,
};

class DetachedLocomotiveShunt final {
public:
    [[nodiscard]] bool start(ShuntPath path) {
        if(!path.valid || path.points.size()<3U ||
           path.cumulative_m.size()!=path.points.size() ||
           !(path.front_turnout_m>0.0) ||
           !(path.length_m>path.front_turnout_m)) return false;
        path_=std::move(path);
        cursor_=0.0;
        speed_=0.0;
        pause_s_=0.0;
        phase_=DetachedShuntPhase::headshunt_forward;
        return true;
    }

    void update(const double dt) noexcept {
        if (!std::isfinite(dt) || dt<=0.0)return;
        if(phase_==DetachedShuntPhase::gear_change) {
            pause_s_=std::max(0.0,pause_s_-dt);
            if(pause_s_==0.0)phase_=DetachedShuntPhase::bypass_reverse;
            return;
        }
        if (phase_!=DetachedShuntPhase::headshunt_forward &&
            phase_!=DetachedShuntPhase::bypass_reverse)return;
        speed_=std::min(3.25,speed_+1.25*dt);
        const double limit=phase_==DetachedShuntPhase::headshunt_forward?
            path_.front_turnout_m:path_.length_m;
        cursor_=std::min(limit,cursor_+speed_*dt);
        if(cursor_==limit) {
            speed_=0.0;
            if(phase_==DetachedShuntPhase::headshunt_forward) {
                phase_=DetachedShuntPhase::gear_change;
                pause_s_=1.5;
            } else {
                phase_=DetachedShuntPhase::await_turning;
            }
        }
    }

    [[nodiscard]] DetachedShuntPhase phase() const noexcept{return phase_;}
    [[nodiscard]] bool active() const noexcept{return phase_!=DetachedShuntPhase::idle;}
    [[nodiscard]] bool awaiting_turning() const noexcept {
        return phase_==DetachedShuntPhase::await_turning;
    }
    [[nodiscard]] double travel_m() const noexcept{return cursor_;}
    [[nodiscard]] double headshunt_m() const noexcept{return path_.front_turnout_m;}
    [[nodiscard]] double path_length_m() const noexcept{return path_.length_m;}

    [[nodiscard]] std::optional<TrainPose> locomotive_pose() const noexcept {
        if(!active() || path_.points.size()<2U)return std::nullopt;
        const auto it=std::upper_bound(path_.cumulative_m.begin(),path_.cumulative_m.end(),cursor_);
        std::size_t section=it==path_.cumulative_m.begin()?0U:
            static_cast<std::size_t>(it-path_.cumulative_m.begin()-1);
        section=std::min(section,path_.points.size()-2U);
        const double begin=path_.cumulative_m[section];
        const double end=path_.cumulative_m[section+1U];
        if(!(end>begin))return std::nullopt;
        const double t=std::clamp((cursor_-begin)/(end-begin),0.0,1.0);
        const auto& a=path_.points[section];
        const auto& b=path_.points[section+1U];
        const double dx=b.x-a.x,dy=b.y-a.y,dz=b.z-a.z;
        const double norm=std::sqrt(dx*dx+dy*dy+dz*dz);
        if(!(norm>1.0e-8))return std::nullopt;
        const bool reversing=phase_==DetachedShuntPhase::bypass_reverse ||
            phase_==DetachedShuntPhase::await_turning;
        const double facing=reversing?-1.0:1.0;
        TrainPose pose;
        pose.distance_m=path_.station_b_distance_m;
        pose.x=a.x+dx*t;pose.y=a.y+dy*t;pose.z=a.z+dz*t;
        pose.tangent_x=facing*dx/norm;
        pose.tangent_y=facing*dy/norm;
        pose.tangent_z=facing*dz/norm;
        pose.speed_mps=speed_;
        pose.dwelling=phase_==DetachedShuntPhase::gear_change || awaiting_turning();
        return pose;
    }

private:
    ShuntPath path_{};
    double cursor_=0.0,speed_=0.0,pause_s_=0.0;
    DetachedShuntPhase phase_=DetachedShuntPhase::idle;
};

} // namespace ch::rail_operation
