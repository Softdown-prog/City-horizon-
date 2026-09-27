#pragma once

#include <SDL3/SDL.h>

#include "building_system.h"
#include "pedestrian_system.h"

#include <algorithm>
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
// door. All visible movement stays on the pedestrian surface graph. When a
// straight perpendicular approach exists it is preferred; otherwise the actor
// may reach the front-door tile from the connected path/road and turns to face
// inward before disappearing. A visitor can never enter from a side or rear
// facade merely because that tile happens to be reachable.
namespace ch::building_visit_runtime {

constexpr Uint64 kDoorAlignMs = 180;
constexpr Uint64 kVisitorDwellMs = 3000;

enum class VisitPhase : std::uint8_t {
    approaching,
    entering,
    aligning,
    inside,
    completed_here,
};

struct VisitState {
    std::uint64_t building_instance_id = 0;
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

[[nodiscard]] inline bool supports_customer_visit(const BuildingDefinition& definition) {
    const bool activity = definition.activity_overlay && definition.activity_overlay->enabled;
    return !definition.service_name.empty() || activity;
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

        for (const BuildingAccessPoint& access : visitor_access_points(*definition, instance.rotation)) {
            const auto [offset_x, offset_y] = access_offset(access.facing);
            const NavigationTile door{
                instance.tile_x + access.local_x + offset_x,
                instance.tile_y + access.local_y + offset_y,
            };
            if (!network.is_navigable(door)) continue;

            // Prefer a true straight-in final hop when the map supplies a
            // second walkable tile outside the door (for example sidewalk ->
            // apron). This naturally leaves the walking sprite facing inward.
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

            // A shop placed flush to a one-tile road often has no second tile
            // perpendicular to its facade. Route to the authored door tile by
            // the normal graph instead; the alignment phase below turns the
            // actor to face inward before entry, without moving off-surface.
            const NavigationPathResult route = find_navigation_path(network, start, door);
            if (route.status != NavigationPathStatus::found || route.tiles.empty()) continue;
            const std::size_t cost = route.tiles.size();
            if (cost >= best_route_tiles) continue;
            best_route_tiles = cost;
            best = EntranceRoute{instance.instance_id, door, door, access.facing, cost};
        }
    }
    return best;
}

inline void cancel_visit(const std::uint64_t pedestrian_id, VisitState& state,
                         PedestrianSystem& pedestrians, BuildingManager& buildings) {
    if (state.phase == VisitPhase::inside) {
        (void)buildings.end_activity(state.building_instance_id);
    }
    if (state.phase == VisitPhase::aligning || state.phase == VisitPhase::inside) {
        (void)pedestrians.set_visiting(pedestrian_id, false);
    }
}

[[nodiscard]] inline bool is_expected_destination(const PedestrianInstance& pedestrian,
                                                  const VisitState& state) {
    const int expected_x = state.phase == VisitPhase::approaching ? state.approach_x : state.door_x;
    const int expected_y = state.phase == VisitPhase::approaching ? state.approach_y : state.door_y;
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

// Called from the runtime frame bridge. Autonomous visits are started only for
// production pedestrian mode; manual F7/F8 route tests are not hijacked. Both
// alignment and dwell timers pause with the simulation.
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

            if (buildings.find_by_id(state.building_instance_id) == nullptr) {
                cancel_visit(pedestrian_id, state, pedestrians, buildings);
                runtime_states.erase(current);
                continue;
            }

            if ((state.phase == VisitPhase::approaching || state.phase == VisitPhase::entering) &&
                !is_expected_destination(pedestrian_snapshot, state)) {
                cancel_visit(pedestrian_id, state, pedestrians, buildings);
                runtime_states.erase(current);
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
        if (!entrance) continue;

        if (!pedestrians.send_pedestrian(start, entrance->approach, network)) continue;
        runtime_states[pedestrian_id] = VisitState{
            entrance->building_instance_id,
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
// Preserve that ordering while removing only visitors physically inside. The
// short door-alignment phase deliberately remains visible for captures/gameplay.
inline void filter_inside_pedestrians(std::vector<MobileEntityRenderData>& entities,
                                      const PedestrianSystem& pedestrians) {
    const auto& instances = pedestrians.instances();
    if (instances.empty() || instances.size() > entities.size()) return;

    const std::size_t pedestrian_start = entities.size() - instances.size();
    std::size_t write_index = pedestrian_start;
    for (std::size_t index = 0; index < instances.size(); ++index) {
        if (is_inside(instances[index].id)) continue;
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
