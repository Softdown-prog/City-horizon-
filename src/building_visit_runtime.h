#pragma once

#include <SDL3/SDL.h>

#include "building_system.h"
#include "pedestrian_system.h"

#include <algorithm>
#include <array>
#include <cstdint>
#include <limits>
#include <optional>
#include <unordered_map>
#include <utility>
#include <vector>

// CH_VISITOR_MVP_V1 building entry bridge.
//
// Road-access placement and pedestrian entry are intentionally separate:
// placement may accept a whole facade, while a visitor must use one authored
// door. All visible movement stays on the pedestrian surface graph. Ticketed
// attractions additionally require a live booth -> ride sequence: the visitor
// stops at a reachable booth window, then walks to the attraction's authored
// boarding access before the ride activity begins.
namespace ch::building_visit_runtime {

constexpr Uint64 kDoorAlignMs = 180;
constexpr Uint64 kTicketServiceMs = 450;
constexpr Uint64 kVisitorDwellMs = 3000;

enum class VisitPhase : std::uint8_t {
    ticket_approaching,
    ticketing,
    approaching,
    entering,
    aligning,
    inside,
    completed_here,
};

struct VisitState {
    // Final activity owner: a shop interior or a ticketed attraction.
    std::uint64_t building_instance_id = 0;
    // Non-zero only while this visit must pass through a paired Park booth.
    std::uint64_t ticket_booth_instance_id = 0;
    int ticket_x = 0;
    int ticket_y = 0;
    GridDirection ticket_facing = GridDirection::south;
    int approach_x = 0;
    int approach_y = 0;
    int door_x = 0;
    int door_y = 0;
    GridDirection door_facing = GridDirection::south;
    Uint64 last_tick_ms = 0;
    Uint64 elapsed_inside_ms = 0;
    VisitPhase phase = VisitPhase::approaching;
};

struct EntranceRoute {
    std::uint64_t building_instance_id = 0;
    NavigationTile approach;
    NavigationTile door;
    GridDirection door_facing = GridDirection::south;
    std::size_t route_tiles = 0;
};

struct TicketedAttractionRoute {
    std::uint64_t booth_instance_id = 0;
    std::uint64_t attraction_instance_id = 0;
    NavigationTile booth_service;
    GridDirection booth_facing = GridDirection::south;
    EntranceRoute attraction_entrance;
    std::size_t route_tiles = 0;
};

[[nodiscard]] inline std::unordered_map<std::uint64_t, VisitState>& states() {
    static std::unordered_map<std::uint64_t, VisitState> runtime_states;
    return runtime_states;
}

[[nodiscard]] inline std::pair<int, int> access_offset(const GridDirection direction) {
    switch (direction) {
        case GridDirection::north: return {0, -1};
        case GridDirection::east: return {1, 0};
        case GridDirection::south: return {0, 1};
        case GridDirection::west: return {-1, 0};
    }
    return {0, 0};
}

[[nodiscard]] inline CardinalDirection inward_direction(const GridDirection outward) {
    switch (outward) {
        case GridDirection::north: return CardinalDirection::south;
        case GridDirection::east: return CardinalDirection::west;
        case GridDirection::south: return CardinalDirection::north;
        case GridDirection::west: return CardinalDirection::east;
    }
    return CardinalDirection::north;
}

[[nodiscard]] inline MobileEntityDirection inward_mobile_direction(const GridDirection outward) {
    switch (outward) {
        case GridDirection::north: return MobileEntityDirection::south;
        case GridDirection::east: return MobileEntityDirection::west;
        case GridDirection::south: return MobileEntityDirection::north;
        case GridDirection::west: return MobileEntityDirection::east;
    }
    return MobileEntityDirection::north;
}

// Explicit accessPoints are authoritative visitor doors. Legacy/front-edge
// definitions receive one central fallback door only; the whole facade is never
// treated as an entrance. For an even-width facade the higher index is chosen,
// matching the current small-commercial right-hand front entrance convention.
[[nodiscard]] inline std::vector<BuildingAccessPoint> visitor_access_points(
    const BuildingDefinition& definition, const BuildingRotation rotation) {
    if (!definition.access_points.empty()) {
        return rotated_access_points(definition, rotation);
    }
    if (!definition.front_edge) return {};

    const std::vector<BuildingAccessPoint> front = front_edge_access_points(definition, rotation);
    if (front.empty()) return {};
    return {front[front.size() / 2]};
}

// Ordinary interior visits deliberately exclude residences, outdoor vendors,
// ticket booths and ticket-gated rides. A data-driven service/activity building
// becomes enterable only when it also declares an actual visitor entrance.
[[nodiscard]] inline bool supports_customer_visit(const BuildingDefinition& definition) {
    if (definition.category == "residential" || definition.is_park_ticket_booth ||
        definition.requires_ticket_booth) {
        return false;
    }
    if (definition.access_points.empty() && !definition.front_edge) return false;
    const bool activity = definition.activity_overlay && definition.activity_overlay->enabled;
    return !definition.service_name.empty() || activity;
}

[[nodiscard]] inline std::optional<EntranceRoute> reachable_entrance_for_instance(
    const NavigationTile start, const BuildingInstance& instance,
    const BuildingDefinition& definition, const NavigationNetwork& network) {
    std::optional<EntranceRoute> best;
    std::size_t best_route_tiles = std::numeric_limits<std::size_t>::max();

    for (const BuildingAccessPoint& access : visitor_access_points(definition, instance.rotation)) {
        const auto [offset_x, offset_y] = access_offset(access.facing);
        const NavigationTile door{
            instance.tile_x + access.local_x + offset_x,
            instance.tile_y + access.local_y + offset_y,
        };
        if (!network.is_navigable(door)) continue;

        // Prefer a true straight-in final hop when the map supplies a second
        // walkable tile outside the door. This naturally leaves the walking
        // sprite facing inward.
        const NavigationTile straight_approach{door.x + offset_x, door.y + offset_y};
        if (network.is_navigable(straight_approach) &&
            network.can_move(straight_approach, inward_direction(access.facing))) {
            const NavigationPathResult route = find_navigation_path(network, start, straight_approach);
            if (route.status == NavigationPathStatus::found && !route.tiles.empty()) {
                const std::size_t cost = route.tiles.size() + 1;
                if (cost < best_route_tiles) {
                    best_route_tiles = cost;
                    best = EntranceRoute{instance.instance_id, straight_approach, door, access.facing, cost};
                }
                continue;
            }
        }

        // A building placed flush to a one-tile road/path may have no second
        // perpendicular tile. Route to the authored access tile by the normal
        // graph, then explicitly face inward before entry/boarding.
        const NavigationPathResult route = find_navigation_path(network, start, door);
        if (route.status != NavigationPathStatus::found || route.tiles.empty()) continue;
        const std::size_t cost = route.tiles.size();
        if (cost >= best_route_tiles) continue;
        best_route_tiles = cost;
        best = EntranceRoute{instance.instance_id, door, door, access.facing, cost};
    }
    return best;
}

[[nodiscard]] inline std::optional<EntranceRoute> best_reachable_entrance(
    const NavigationTile start, const BuildingManager& buildings,
    const BuildingCatalog& catalog, const NavigationNetwork& network) {
    std::optional<EntranceRoute> best;
    std::size_t best_route_tiles = std::numeric_limits<std::size_t>::max();

    for (const BuildingInstance& instance : buildings.instances()) {
        if (!instance.operational) continue;
        const BuildingDefinition* definition = catalog.find(instance.definition_id);
        if (definition == nullptr || !supports_customer_visit(*definition)) continue;
        const auto entrance = reachable_entrance_for_instance(start, instance, *definition, network);
        if (!entrance || entrance->route_tiles >= best_route_tiles) continue;
        best_route_tiles = entrance->route_tiles;
        best = *entrance;
    }
    return best;
}

// A ticket booth is an outdoor service point, not an interior. The pedestrian
// stands on whichever adjacent path/road tile is actually connected, faces the
// booth briefly, and then continues to the linked attraction. This deliberately
// needs no activity overlay on the booth itself.
[[nodiscard]] inline std::optional<TicketedAttractionRoute> best_reachable_ticketed_attraction(
    const NavigationTile start, const BuildingManager& buildings,
    const BuildingCatalog& catalog, const NavigationNetwork& network) {
    std::optional<TicketedAttractionRoute> best;
    std::size_t best_route_tiles = std::numeric_limits<std::size_t>::max();
    constexpr std::array<GridDirection, 4> sides = {
        GridDirection::north, GridDirection::east, GridDirection::south, GridDirection::west,
    };

    for (const BuildingInstance& booth : buildings.instances()) {
        if (!booth.operational) continue;
        const BuildingDefinition* booth_definition = catalog.find(booth.definition_id);
        if (booth_definition == nullptr || !booth_definition->is_park_ticket_booth) continue;

        const std::optional<std::uint64_t> attraction_id =
            buildings.linked_attraction_for_ticket_booth(booth.instance_id);
        if (!attraction_id) continue;
        const BuildingInstance* attraction = buildings.find_by_id(*attraction_id);
        if (attraction == nullptr || !attraction->operational) continue;
        const BuildingDefinition* attraction_definition = catalog.find(attraction->definition_id);
        if (attraction_definition == nullptr || !attraction_definition->requires_ticket_booth) continue;
        if (visitor_access_points(*attraction_definition, attraction->rotation).empty()) continue;

        // The current booth is 1x1; using its rotated footprint here keeps the
        // service-point rule safe if a wider booth family is introduced later.
        const BuildingFootprint booth_footprint = rotated_footprint(*booth_definition, booth.rotation);
        for (const GridDirection side : sides) {
            const auto [dx, dy] = access_offset(side);
            const int local_x = side == GridDirection::west ? 0 :
                                side == GridDirection::east ? booth_footprint.width - 1 :
                                booth_footprint.width / 2;
            const int local_y = side == GridDirection::north ? 0 :
                                side == GridDirection::south ? booth_footprint.height - 1 :
                                booth_footprint.height / 2;
            const NavigationTile service{
                booth.tile_x + local_x + dx,
                booth.tile_y + local_y + dy,
            };
            if (!network.is_navigable(service)) continue;

            const NavigationPathResult to_booth = find_navigation_path(network, start, service);
            if (to_booth.status != NavigationPathStatus::found || to_booth.tiles.empty()) continue;
            const auto attraction_entrance = reachable_entrance_for_instance(
                service, *attraction, *attraction_definition, network);
            if (!attraction_entrance) continue;

            const std::size_t cost = to_booth.tiles.size() + attraction_entrance->route_tiles;
            if (cost >= best_route_tiles) continue;
            best_route_tiles = cost;
            best = TicketedAttractionRoute{
                booth.instance_id,
                attraction->instance_id,
                service,
                side,
                *attraction_entrance,
                cost,
            };
        }
    }
    return best;
}

inline void cancel_visit(const std::uint64_t pedestrian_id, VisitState& state,
                         PedestrianSystem& pedestrians, BuildingManager& buildings) {
    if (state.phase == VisitPhase::inside) {
        (void)buildings.end_activity(state.building_instance_id);
    }
    if (state.phase == VisitPhase::ticketing || state.phase == VisitPhase::aligning ||
        state.phase == VisitPhase::inside) {
        (void)pedestrians.set_visiting(pedestrian_id, false);
    }
}

[[nodiscard]] inline bool is_expected_destination(const PedestrianInstance& pedestrian,
                                                  const VisitState& state) {
    int expected_x = state.door_x;
    int expected_y = state.door_y;
    if (state.phase == VisitPhase::ticket_approaching || state.phase == VisitPhase::ticketing) {
        expected_x = state.ticket_x;
        expected_y = state.ticket_y;
    } else if (state.phase == VisitPhase::approaching) {
        expected_x = state.approach_x;
        expected_y = state.approach_y;
    }
    return pedestrian.destination.x == expected_x && pedestrian.destination.y == expected_y;
}

[[nodiscard]] inline bool begin_alignment(const std::uint64_t pedestrian_id, VisitState& state,
                                          PedestrianSystem& pedestrians, const Uint64 now) {
    if (!pedestrians.face_pedestrian(pedestrian_id, inward_mobile_direction(state.door_facing))) return false;
    if (!pedestrians.set_visiting(pedestrian_id, true)) return false;
    state.last_tick_ms = now;
    state.elapsed_inside_ms = 0;
    state.phase = VisitPhase::aligning;
    return true;
}

[[nodiscard]] inline bool begin_ticket_service(const std::uint64_t pedestrian_id, VisitState& state,
                                               PedestrianSystem& pedestrians, const Uint64 now) {
    if (!pedestrians.face_pedestrian(pedestrian_id, inward_mobile_direction(state.ticket_facing))) return false;
    if (!pedestrians.set_visiting(pedestrian_id, true)) return false;
    state.last_tick_ms = now;
    state.elapsed_inside_ms = 0;
    state.phase = VisitPhase::ticketing;
    return true;
}

// Called from the runtime frame bridge. Autonomous visits are started only for
// production pedestrian mode; manual F7/F8 route tests are not hijacked. All
// alignment, booth-service and dwell timers pause with the simulation.
inline void sync(PedestrianSystem& pedestrians, BuildingManager& buildings,
                 const BuildingCatalog& catalog, const NavigationNetwork& network,
                 const bool simulation_running, const bool allow_autonomous_visits) {
    const Uint64 now = SDL_GetTicks();
    auto& runtime_states = states();

    for (const PedestrianInstance& pedestrian_snapshot : pedestrians.instances()) {
        const std::uint64_t pedestrian_id = pedestrian_snapshot.id;
        auto current = runtime_states.find(pedestrian_id);

        if (current != runtime_states.end()) {
            VisitState& state = current->second;

            if (buildings.find_by_id(state.building_instance_id) == nullptr ||
                (state.ticket_booth_instance_id != 0 &&
                 buildings.find_by_id(state.ticket_booth_instance_id) == nullptr)) {
                cancel_visit(pedestrian_id, state, pedestrians, buildings);
                runtime_states.erase(current);
                continue;
            }

            if ((state.phase == VisitPhase::ticket_approaching || state.phase == VisitPhase::approaching ||
                 state.phase == VisitPhase::entering) && !is_expected_destination(pedestrian_snapshot, state)) {
                cancel_visit(pedestrian_id, state, pedestrians, buildings);
                runtime_states.erase(current);
                continue;
            }

            if (state.phase == VisitPhase::ticketing) {
                const Uint64 delta = now >= state.last_tick_ms ? now - state.last_tick_ms : 0;
                state.last_tick_ms = now;
                if (simulation_running) state.elapsed_inside_ms += delta;
                if (state.elapsed_inside_ms >= kTicketServiceMs) {
                    // The one-to-one booth/ride link must still be valid at the
                    // moment the ticket interaction completes.
                    const auto linked = buildings.linked_attraction_for_ticket_booth(
                        state.ticket_booth_instance_id);
                    (void)pedestrians.set_visiting(pedestrian_id, false);
                    if (!linked || *linked != state.building_instance_id) {
                        runtime_states.erase(current);
                        continue;
                    }
                    const NavigationTile service{state.ticket_x, state.ticket_y};
                    const NavigationTile approach{state.approach_x, state.approach_y};
                    if (!pedestrians.send_pedestrian(service, approach, network)) {
                        runtime_states.erase(current);
                        continue;
                    }
                    state.phase = VisitPhase::approaching;
                }
                continue;
            }

            if (state.phase == VisitPhase::aligning) {
                const Uint64 delta = now >= state.last_tick_ms ? now - state.last_tick_ms : 0;
                state.last_tick_ms = now;
                if (simulation_running) state.elapsed_inside_ms += delta;
                if (state.elapsed_inside_ms >= kDoorAlignMs) {
                    if (buildings.begin_activity(state.building_instance_id)) {
                        state.elapsed_inside_ms = 0;
                        state.phase = VisitPhase::inside;
                    } else {
                        (void)pedestrians.set_visiting(pedestrian_id, false);
                        runtime_states.erase(current);
                    }
                }
                continue;
            }

            if (state.phase == VisitPhase::inside) {
                const Uint64 delta = now >= state.last_tick_ms ? now - state.last_tick_ms : 0;
                state.last_tick_ms = now;
                if (simulation_running) state.elapsed_inside_ms += delta;
                if (state.elapsed_inside_ms >= kVisitorDwellMs) {
                    (void)buildings.end_activity(state.building_instance_id);
                    (void)pedestrians.set_visiting(pedestrian_id, false);
                    state.phase = VisitPhase::completed_here;
                }
                continue;
            }

            if (state.phase == VisitPhase::completed_here) {
                // Keep the guard until ordinary autonomous movement assigns a
                // different trip, preventing instant re-entry at the same door.
                if (pedestrian_snapshot.state == PedestrianState::walking &&
                    !is_expected_destination(pedestrian_snapshot, state)) {
                    runtime_states.erase(current);
                }
                continue;
            }

            if (pedestrian_snapshot.state == PedestrianState::walking) continue;

            const NavigationTile current_tile{
                pedestrian_snapshot.spatial.logical_tile_x,
                pedestrian_snapshot.spatial.logical_tile_y,
            };

            if (state.phase == VisitPhase::ticket_approaching) {
                const NavigationTile ticket{state.ticket_x, state.ticket_y};
                if (!(current_tile == ticket) ||
                    !begin_ticket_service(pedestrian_id, state, pedestrians, now)) {
                    runtime_states.erase(current);
                }
                continue;
            }

            if (state.phase == VisitPhase::approaching) {
                const NavigationTile approach{state.approach_x, state.approach_y};
                const NavigationTile door{state.door_x, state.door_y};
                if (!(current_tile == approach)) {
                    runtime_states.erase(current);
                    continue;
                }
                if (approach == door) {
                    if (!begin_alignment(pedestrian_id, state, pedestrians, now)) {
                        runtime_states.erase(current);
                    }
                } else if (network.is_navigable(door) &&
                           pedestrians.send_pedestrian(approach, door, network)) {
                    state.phase = VisitPhase::entering;
                } else {
                    runtime_states.erase(current);
                }
                continue;
            }

            if (state.phase == VisitPhase::entering) {
                const NavigationTile door{state.door_x, state.door_y};
                if (!(current_tile == door) ||
                    !begin_alignment(pedestrian_id, state, pedestrians, now)) {
                    runtime_states.erase(current);
                }
                continue;
            }
        }

        if (!allow_autonomous_visits || pedestrian_snapshot.state != PedestrianState::idle) continue;

        const NavigationTile start{
            pedestrian_snapshot.spatial.logical_tile_x,
            pedestrian_snapshot.spatial.logical_tile_y,
        };
        const auto entrance = best_reachable_entrance(start, buildings, catalog, network);
        const auto ticketed = best_reachable_ticketed_attraction(start, buildings, catalog, network);

        if (ticketed && (!entrance || ticketed->route_tiles <= entrance->route_tiles)) {
            if (!pedestrians.send_pedestrian(start, ticketed->booth_service, network)) continue;
            runtime_states[pedestrian_id] = VisitState{
                ticketed->attraction_instance_id,
                ticketed->booth_instance_id,
                ticketed->booth_service.x,
                ticketed->booth_service.y,
                ticketed->booth_facing,
                ticketed->attraction_entrance.approach.x,
                ticketed->attraction_entrance.approach.y,
                ticketed->attraction_entrance.door.x,
                ticketed->attraction_entrance.door.y,
                ticketed->attraction_entrance.door_facing,
                now,
                0,
                VisitPhase::ticket_approaching,
            };
            continue;
        }

        if (!entrance) continue;
        if (!pedestrians.send_pedestrian(start, entrance->approach, network)) continue;
        runtime_states[pedestrian_id] = VisitState{
            entrance->building_instance_id,
            0,
            0,
            0,
            GridDirection::south,
            entrance->approach.x,
            entrance->approach.y,
            entrance->door.x,
            entrance->door.y,
            entrance->door_facing,
            now,
            0,
            VisitPhase::approaching,
        };
    }
}

[[nodiscard]] inline bool is_inside(const std::uint64_t pedestrian_id) {
    const auto found = states().find(pedestrian_id);
    return found != states().end() && found->second.phase == VisitPhase::inside;
}

// main_runtime_impl appends pedestrian render data after service vehicles.
// Preserve that ordering while removing only visitors physically inside/on an
// attraction. Ticket-window and door-alignment phases deliberately remain
// visible for captures/gameplay.
inline void filter_inside_pedestrians(std::vector<MobileEntityRenderData>& entities,
                                      const PedestrianSystem& pedestrians) {
    const auto& instances = pedestrians.instances();
    if (instances.empty() || instances.size() > entities.size()) return;

    const std::size_t pedestrian_start = entities.size() - instances.size();
    std::size_t write_index = pedestrian_start;
    for (std::size_t index = 0; index < instances.size(); ++index) {
        if (is_inside(instances[index].id) || instances[index].state == PedestrianState::resting) continue;
        if (write_index != pedestrian_start + index) {
            entities[write_index] = std::move(entities[pedestrian_start + index]);
        }
        ++write_index;
    }
    entities.resize(write_index);
}

inline void clear(PedestrianSystem& pedestrians, BuildingManager& buildings) {
    for (auto& [pedestrian_id, state] : states()) {
        cancel_visit(pedestrian_id, state, pedestrians, buildings);
    }
    states().clear();
}

}  // namespace ch::building_visit_runtime
