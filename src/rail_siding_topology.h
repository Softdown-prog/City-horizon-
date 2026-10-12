#pragma once
// CH_RAIL_CONNECTED_SIDING_V1
// Structural discovery ONLY. A connected bypass does not itself provide a
// turntable, switch dispatch, coupling or a safe train return.
#include "rail_operation_runtime.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <limits>
#include <optional>
#include <queue>
#include <utility>
#include <vector>

namespace ch::rail_operation {

struct ConnectedSiding {
    RailPlacementNodeId rear_junction = kInvalidRailPlacementNodeId;
    RailPlacementNodeId front_junction = kInvalidRailPlacementNodeId;
    double rear_distance_m = 0.0;
    double front_distance_m = 0.0;
    std::vector<RailPlacementEdgeId> bypass_edges;
};

[[nodiscard]] inline std::optional<ConnectedSiding> find_connected_siding(
    const RailPlacementGraph& placement, const OperationalRoute& route) {
    if (!route.valid || route.closed || route.stations.size() != 2U ||
        placement.edges().empty())return std::nullopt;

    const auto built=ch::rail::build_track_graph(placement);
    if (!built.valid)return std::nullopt;
    const auto edge_count=placement.edges().size();
    const auto node_count=placement.nodes().size();
    std::vector<bool> on_main(edge_count,false);
    std::vector<double> node_distance(node_count,std::numeric_limits<double>::quiet_NaN());
    double cursor=0.0;

    // Associate every traversed topology route with its original placed edge.
    // A turnout's through (route 0) belongs to the mainline, while its
    // diverging branch (route 1) is eligible as a genuine siding.
    for(const auto& step:route.graph_route.steps) {
        const auto* piece=built.graph.piece(step.piece);
        if (!piece || step.route>=piece->descriptor.routes.size())
            return std::nullopt;
        const double edge_length=detail::route_length(piece->descriptor.routes[step.route]);
        if (!(edge_length>0) || !std::isfinite(edge_length))return std::nullopt;
        std::optional<RailPlacementEdgeId> matched;
        for(const auto& edge:placement.edges()) {
            if(!edge.active || edge.id>=built.edge_piece.size())continue;
            if(built.edge_piece[edge.id]!=step.piece ||
               built.edge_route[edge.id]!=step.route)continue;
            if(matched)return std::nullopt;
            matched=edge.id;
        }
        if(!matched)return std::nullopt;
        const auto& edge=placement.edges()[*matched];
        if(on_main[edge.id])return std::nullopt;
        on_main[edge.id]=true;
        const double at_from=cursor+(step.reversed?edge_length:0.0);
        const double at_to=cursor+(step.reversed?0.0:edge_length);
        for(const auto& [node,d]:{std::pair{edge.from,at_from},std::pair{edge.to,at_to}}) {
            if(node>=node_distance.size())return std::nullopt;
            if(std::isfinite(node_distance[node]) &&
               std::abs(node_distance[node]-d)>0.05)return std::nullopt;
            node_distance[node]=d;
        }
        cursor+=edge_length;
    }

    // Fail closed unless both ends of the bypass are AUTHORED turnout roots.
    const auto turnout_at=[&](RailPlacementNodeId node)->bool {
        for(const auto& edge:placement.edges()) {
            if (!edge.active || edge.from!=node ||
                edge.kind!=RailPlacementEdgeKind::turnout_through)continue;
            for(const auto& sibling:placement.edges()) {
                if(sibling.active && sibling.from==node &&
                   sibling.piece_group==edge.piece_group &&
                   sibling.kind==RailPlacementEdgeKind::turnout_diverging)return true;
            }
        }
        return false;
    };
    std::vector<std::vector<RailPlacementEdgeId>> adjacent(node_count);
    for(const auto& edge:placement.edges()) {
        if(!edge.active || on_main[edge.id])continue;
        if(edge.from>=node_count || edge.to>=node_count)return std::nullopt;
        adjacent[edge.from].push_back(edge.id);
        adjacent[edge.to].push_back(edge.id);
    }
    // Seven stationary coaches require clearance behind station B; the front
    // turnout must be ahead of B so the shunting locomotive is not stranded
    // inside the consist. Track position is in measured route metres.
    const double a=route.stations.front().distance_m;
    const double b=route.stations.back().distance_m;
    for(std::size_t rear=0;rear<node_count;++rear) {
        const double d=node_distance[rear];
        if(!std::isfinite(d) || d<=a+2.0 || d>=b-41.0 ||
           adjacent[rear].empty() || !turnout_at(static_cast<RailPlacementNodeId>(rear)))continue;
        std::queue<RailPlacementNodeId> pending;
        std::vector<bool> seen(node_count,false);
        std::vector<RailPlacementNodeId> prev_node(node_count,kInvalidRailPlacementNodeId);
        std::vector<RailPlacementEdgeId> prev_edge(node_count,kInvalidRailPlacementEdgeId);
        seen[rear]=true;
        pending.push(static_cast<RailPlacementNodeId>(rear));
        while(!pending.empty()) {
            const auto here=pending.front();pending.pop();
            for(const auto id:adjacent[here]) {
                const auto& edge=placement.edges()[id];
                const auto next=edge.from==here?edge.to:edge.from;
                if(seen[next])continue;
                if(std::isfinite(node_distance[next])) {
                    // Do not route through occupied mainline except at the
                    // intended front turnout beyond station B.
                    if(node_distance[next]<=b+5.0 ||
                       !turnout_at(next))continue;
                    prev_node[next]=here;
                    prev_edge[next]=id;
                    std::vector<RailPlacementEdgeId> path;
                    auto node=next;
                    while(node!=rear) {
                        const auto e=prev_edge[node];
                        if(e==kInvalidRailPlacementEdgeId)return std::nullopt;
                        path.push_back(e);
                        node=prev_node[node];
                    }
                    std::reverse(path.begin(),path.end());
                    // Both ends must be turnout-diverging edges; no arbitrary
                    // narrow shortcut or phantom direct rail-to-rail jump.
                    if(path.size()<3U ||
                       placement.edges()[path.front()].kind!=RailPlacementEdgeKind::turnout_diverging ||
                       placement.edges()[path.back()].kind!=RailPlacementEdgeKind::turnout_diverging)
                        continue;
                    return ConnectedSiding{static_cast<RailPlacementNodeId>(rear),next,
                                           d,node_distance[next],std::move(path)};
                }
                seen[next]=true;
                prev_node[next]=here;
                prev_edge[next]=id;
                pending.push(next);
            }
        }
    }
    return std::nullopt;
}

} // namespace ch::rail_operation
