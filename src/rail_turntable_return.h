#pragma once
// CH_RAIL_TURNTABLE_RETURN_V1
// Turntable is an authored, paid & persisted device centered on a physical
// mainline straight before the rear turnout. Only then may the locomotive
// leave the passing siding, rotate, recouple and pull toward station A.
#include "rail_detached_locomotive_shunt.h"
#include "rail_persistence.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <optional>

namespace ch::rail_operation {

struct TurntableReturnPlan {
    double turntable_distance_m = 0.0;
    double rear_junction_distance_m = 0.0;
    double recouple_locomotive_distance_m = 0.0;
    double station_a_distance_m = 0.0;
    RailPlacementPieceId station_a_piece = kInvalidRailPlacementPieceId;
    RailPlacementPieceId turntable_piece_group = kInvalidRailPlacementPieceId;
    bool valid = false;
};

[[nodiscard]] inline std::optional<TurntableReturnPlan> compile_turntable_return(
    const RailPlacementGraph& graph, const OperationalRoute& route,
    const ConnectedSiding& siding, const ShuntPath& shunt,
    const std::vector<RailPersistentTurntable>& turntables) {
    if(!route.valid || route.closed || route.stations.size()!=2U ||
       !shunt.valid || turntables.size()!=1U)return std::nullopt;
    // One locomotive leads 7 original coaches in the *opposite* direction.
    // World-space rear coach remains at B-first_offset-6*pitch.
    constexpr double kLocomotiveLength=5.2,kCoachLength=3.9,kGap=0.42;
    constexpr double kFirst=(kLocomotiveLength+kCoachLength)*0.5+kGap;
    constexpr double kPitch=kCoachLength+kGap;
    constexpr double kRecoupleOffset=2*kFirst+6*kPitch;
    const double b=route.stations.back().distance_m;
    const double coupling=b-kRecoupleOffset;
    const double rear=siding.rear_distance_m;
    const double a=route.stations.front().distance_m;
    if(!(coupling>rear+8.0 && coupling>a+3.0 &&
         rear>a+1.0 && rear<shunt.station_b_distance_m &&
         std::isfinite(coupling)))return std::nullopt;

    const auto built=ch::rail::build_track_graph(graph);
    if(!built.valid)return std::nullopt;
    // Read the position from the selected actual *route step*, not an
    // arbitrary piece placed nearby. Ignore unused parallel branches.
    double cursor=0;
    std::optional<double> table_at;
    const auto group=turntables.front().piece_group;
    for(const auto& step:route.graph_route.steps) {
        const auto* piece=built.graph.piece(step.piece);
        if(piece==nullptr || step.route>=piece->descriptor.routes.size())return std::nullopt;
        const double segment_length=detail::route_length(piece->descriptor.routes[step.route]);
        if(!(segment_length>0.0))return std::nullopt;
        for(const auto& edge:graph.edges()) {
            if(!edge.active || edge.piece_group!=group ||
               edge.kind!=RailPlacementEdgeKind::straight ||
               edge.id>=built.edge_piece.size() || built.edge_piece[edge.id]!=step.piece ||
               built.edge_route[edge.id]!=step.route)continue;
            if(table_at)return std::nullopt;
            const auto geom=RailMeshBuilder::sample_cubic(edge.segment,0.5F);
            const auto midpoint=sample_operational_route_pose(
                route,cursor+segment_length*0.5);
            if(!midpoint || std::hypot(midpoint->x-geom.x,midpoint->y-geom.y)>0.12 ||
               std::abs(midpoint->z-geom.z)>0.12)return std::nullopt;
            table_at=cursor+segment_length*0.5;
            // A turntable deck requires an actually long, level straight.
            if(rail_persistence::detail_unused_turntable_length(edge.segment)<8.0)
                return std::nullopt;
        }
        cursor+=segment_length;
    }
    if(!table_at || *table_at<=kLocomotiveLength/2+0.6 ||
       *table_at>=rear-4.0 || *table_at>=a-3.5)return std::nullopt;

    // 3.6m rotating deck may not overlap other rail sections. This rejects
    // fraudulent/old saves even if their persistence rows parse.
    const auto center=sample_operational_route_pose(route,*table_at);
    if(!center)return std::nullopt;
    for(const auto& edge:graph.edges()) {
        if(!edge.active || edge.piece_group==group)continue;
        for(int i=0;i<=32;++i) {
            const auto sample=RailMeshBuilder::sample_cubic(edge.segment,static_cast<float>(i)/32.0F);
            if(std::hypot(sample.x-center->x,sample.y-center->y)<3.6)return std::nullopt;
        }
    }
    return TurntableReturnPlan{*table_at,rear,coupling,a,
                               route.stations.front().piece_group,group,true};
}

enum class ReturnPhase { idle, approach_turntable, rotate_180, reverse_to_coach,
                         coupled_return, parked_at_a };

class TurntableReturnRuntime final {
public:
    [[nodiscard]] bool start(const TurntableReturnPlan& plan) noexcept {
        if(!plan.valid || plan.turntable_piece_group==kInvalidRailPlacementPieceId ||
           !(plan.turntable_distance_m+4.0<plan.rear_junction_distance_m) ||
           !(plan.rear_junction_distance_m+8.0<plan.recouple_locomotive_distance_m) ||
           !(plan.station_a_distance_m<plan.recouple_locomotive_distance_m))return false;
        plan_=plan;
        current_distance_m_=plan.rear_junction_distance_m;
        speed_mps_=0;
        rotation_radians_=0;
        phase_=ReturnPhase::approach_turntable;
        return true;
    }
    void update(double dt) noexcept {
        if(!std::isfinite(dt) || dt<=0.0 || !active())return;
        if(phase_==ReturnPhase::rotate_180) {
            rotation_radians_=std::min(kPi,rotation_radians_+kPi*dt/3.0);
            if(rotation_radians_==kPi)phase_=ReturnPhase::reverse_to_coach;
            return;
        }
        if(phase_==ReturnPhase::parked_at_a)return;
        speed_mps_=std::min(3.25,speed_mps_+1.25*dt);
        const double step=speed_mps_*dt;
        switch(phase_) {
        case ReturnPhase::approach_turntable:
            current_distance_m_=std::max(plan_.turntable_distance_m,current_distance_m_-step);
            if(current_distance_m_==plan_.turntable_distance_m) {
                speed_mps_=0;phase_=ReturnPhase::rotate_180;
            }
            break;
        case ReturnPhase::reverse_to_coach:
            current_distance_m_=std::min(plan_.recouple_locomotive_distance_m,current_distance_m_+step);
            if(current_distance_m_==plan_.recouple_locomotive_distance_m) {
                speed_mps_=0;phase_=ReturnPhase::coupled_return;
            }
            break;
        case ReturnPhase::coupled_return:
            current_distance_m_=std::max(plan_.station_a_distance_m,current_distance_m_-step);
            if(current_distance_m_==plan_.station_a_distance_m) {
                speed_mps_=0;phase_=ReturnPhase::parked_at_a;
            }
            break;
        default:break;
        }
    }
    [[nodiscard]] bool active() const noexcept {return phase_!=ReturnPhase::idle;}
    [[nodiscard]] bool coupled() const noexcept {
        return phase_==ReturnPhase::coupled_return || phase_==ReturnPhase::parked_at_a;
    }
    [[nodiscard]] ReturnPhase phase() const noexcept{return phase_;}
    [[nodiscard]] double distance_m() const noexcept{return current_distance_m_;}
    [[nodiscard]] double rotation_radians() const noexcept{return rotation_radians_;}
    [[nodiscard]] RailPlacementPieceId turntable_piece_group() const noexcept {
        return active()?plan_.turntable_piece_group:kInvalidRailPlacementPieceId;
    }
    [[nodiscard]] double speed_mps() const noexcept{return speed_mps_;}
    [[nodiscard]] std::optional<TrainPose> locomotive_pose(const OperationalRoute& route) const noexcept {
        if(!active())return std::nullopt;
        auto base=sample_operational_route_pose(
            route,current_distance_m_,speed_mps_,
            phase_==ReturnPhase::rotate_180 || phase_==ReturnPhase::parked_at_a,
            phase_==ReturnPhase::parked_at_a?
                std::optional<RailPlacementPieceId>{plan_.station_a_piece}:std::nullopt);
        if(!base)return std::nullopt;
        const double x=base->tangent_x,y=base->tangent_y,z=base->tangent_z;
        if(phase_==ReturnPhase::approach_turntable) {
            // Loco reverses west but continues facing east.
        } else if(phase_==ReturnPhase::rotate_180) {
            const double cosine=std::cos(rotation_radians_);
            const double sine=std::sin(rotation_radians_);
            base->tangent_x=x*cosine-y*sine;
            base->tangent_y=x*sine+y*cosine;
            base->tangent_z=z*cosine;
        } else {
            base->tangent_x=-x;base->tangent_y=-y;base->tangent_z=-z;
        }
        return base;
    }
private:
    static constexpr double kPi=3.14159265358979323846;
    TurntableReturnPlan plan_{};
    double current_distance_m_=0,rotation_radians_=0,speed_mps_=0;
    ReturnPhase phase_=ReturnPhase::idle;
};

} // namespace ch::rail_operation
