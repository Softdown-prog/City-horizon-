#pragma once

#include <SDL3/SDL.h>

#include "amusement_ride_contract.h"
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

namespace ch::building_visit_runtime {

constexpr Uint64 kDoorAlignMs = 180;
constexpr Uint64 kTicketServiceMs = 450;
constexpr Uint64 kVisitorDwellMs = 3000;

enum class VisitPhase : std::uint8_t {
    ticket_approaching,
    ticketing,
    queued,
    approaching,
    entering,
    aligning,
    inside,
    returning_to_booth,
    completed_here,
};

struct VisitState {
    std::uint64_t building_instance_id = 0;
    std::uint64_t ticket_booth_instance_id = 0;
    int ticket_x = 0;
    int ticket_y = 0;
    GridDirection ticket_facing = GridDirection::south;
    int approach_x = 0;
    int approach_y = 0;
    int door_x = 0;
    int door_y = 0;
    GridDirection door_facing = GridDirection::south;
    std::int64_t charge_cents = 0;
    Uint64 last_tick_ms = 0;
    Uint64 elapsed_inside_ms = 0;
    int ride_seat_index = -1;
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

// CH_AMUSEMENT_RIDE_QUEUE_V1 runtime side. The queue is ordered by successful
// ticket service. A running batch owns explicit seat indexes so the passenger
// overlay can later draw exactly the riders that actually boarded.
struct RideQueueState {
    std::vector<std::uint64_t> waiting;
    std::vector<std::uint64_t> riding;
    Uint64 last_tick_ms = 0;
    Uint64 boarding_elapsed_ms = 0;
    Uint64 cycle_elapsed_ms = 0;
};

[[nodiscard]] inline std::unordered_map<std::uint64_t, VisitState>& states() {
    static std::unordered_map<std::uint64_t, VisitState> runtime_states;
    return runtime_states;
}

[[nodiscard]] inline std::unordered_map<std::uint64_t, RideQueueState>& ride_queues() {
    static std::unordered_map<std::uint64_t, RideQueueState> runtime_queues;
    return runtime_queues;
}

[[nodiscard]] inline const ch::amusement_ride::RuntimeDefinition* managed_ride_definition(
    const BuildingDefinition& definition) {
    return ch::amusement_ride::find(definition);
}

[[nodiscard]] inline std::uint32_t managed_ride_capacity(const BuildingDefinition& definition) {
    const ch::amusement_ride::RuntimeDefinition* ride = managed_ride_definition(definition);
    return ride == nullptr ? 0U : std::min(ride->capacity, ride->seat_count);
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

[[nodiscard]] inline std::int64_t service_price_cents(const BuildingInstance& instance,
                                                       const BuildingDefinition& definition) {
    const ch::ServicePrice price = instance.service_price.minor_units > 0
        ? instance.service_price
        : definition.default_service_price;
    if (price.minor_units <= 0) return 0;
    const std::int64_t scale = price.units_per_dollar > 0 ? price.units_per_dollar : 1;
    if (scale == 100) return price.minor_units;
    if (scale == 1) return price.minor_units * 100;
    return (price.minor_units * 100 + scale - 1) / scale;
}

[[nodiscard]] inline bool is_essential_service(const BuildingDefinition& definition) {
    return definition.id == "bakery_01" || definition.id == "mini_market_01";
}

[[nodiscard]] inline bool satisfies_need(const BuildingDefinition& definition,
                                         const PedestrianNeed need) {
    switch (need) {
        case PedestrianNeed::hunger: return definition.needs_effect.hunger > 0.0F;
        case PedestrianNeed::thirst: return definition.needs_effect.thirst > 0.0F;
        case PedestrianNeed::fun: return definition.needs_effect.fun > 0.0F;
    }
    return false;
}

inline void apply_need_effects(const std::uint64_t pedestrian_id,
                               const BuildingDefinition& definition,
                               PedestrianSystem& pedestrians) {
    if (definition.needs_effect.hunger > 0.0F)
        (void)pedestrians.restore_need(pedestrian_id, PedestrianNeed::hunger, definition.needs_effect.hunger);
    if (definition.needs_effect.thirst > 0.0F)
        (void)pedestrians.restore_need(pedestrian_id, PedestrianNeed::thirst, definition.needs_effect.thirst);
    if (definition.needs_effect.fun > 0.0F)
        (void)pedestrians.restore_need(pedestrian_id, PedestrianNeed::fun, definition.needs_effect.fun);
}

[[nodiscard]] inline std::vector<BuildingAccessPoint> visitor_access_points(
    const BuildingDefinition& definition, const BuildingRotation rotation) {
    if (!definition.access_points.empty()) return rotated_access_points(definition, rotation);
    if (!definition.front_edge) return {};
    const std::vector<BuildingAccessPoint> front = front_edge_access_points(definition, rotation);
    if (front.empty()) return {};
    return {front[front.size() / 2]};
}

[[nodiscard]] inline bool supports_customer_visit(const BuildingDefinition& definition) {
    if (definition.category == "residential" || definition.is_park_ticket_booth ||
        definition.requires_ticket_booth) return false;
    if (definition.access_points.empty() && !definition.front_edge) return false;
    const bool activity = definition.activity_overlay && definition.activity_overlay->enabled;
    return !definition.service_name.empty() || activity || definition.needs_effect.any();
}

[[nodiscard]] inline std::optional<EntranceRoute> reachable_entrance_for_instance(
    const NavigationTile start, const BuildingInstance& instance,
    const BuildingDefinition& definition, const NavigationNetwork& network) {
    std::optional<EntranceRoute> best;
    std::size_t best_route_tiles = std::numeric_limits<std::size_t>::max();
    for (const BuildingAccessPoint& access : visitor_access_points(definition, instance.rotation)) {
        const auto [offset_x, offset_y] = access_offset(access.facing);
        const NavigationTile door{instance.tile_x + access.local_x + offset_x,
                                  instance.tile_y + access.local_y + offset_y};
        if (!network.is_navigable(door)) continue;
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
    const BuildingCatalog& catalog, const NavigationNetwork& network,
    const std::int64_t budget_cents, const PedestrianNeed need,
    const bool essential_only = false) {
    std::optional<EntranceRoute> best;
    std::size_t best_route_tiles = std::numeric_limits<std::size_t>::max();
    for (const BuildingInstance& instance : buildings.instances()) {
        if (!instance.operational) continue;
        const BuildingDefinition* definition = catalog.find(instance.definition_id);
        if (definition == nullptr || !supports_customer_visit(*definition)) continue;
        if (!satisfies_need(*definition, need)) continue;
        if (essential_only && !is_essential_service(*definition)) continue;
        if (service_price_cents(instance, *definition) > budget_cents) continue;
        const auto entrance = reachable_entrance_for_instance(start, instance, *definition, network);
        if (!entrance || entrance->route_tiles >= best_route_tiles) continue;
        best_route_tiles = entrance->route_tiles;
        best = *entrance;
    }
    return best;
}

[[nodiscard]] inline std::optional<TicketedAttractionRoute> best_reachable_ticketed_attraction(
    const NavigationTile start, const BuildingManager& buildings,
    const BuildingCatalog& catalog, const NavigationNetwork& network,
    const std::int64_t budget_cents, const PedestrianNeed need) {
    std::optional<TicketedAttractionRoute> best;
    std::size_t best_route_tiles = std::numeric_limits<std::size_t>::max();
    for (const BuildingInstance& booth : buildings.instances()) {
        if (!booth.operational) continue;
        const BuildingDefinition* booth_definition = catalog.find(booth.definition_id);
        if (booth_definition == nullptr || !booth_definition->is_park_ticket_booth) continue;
        if (service_price_cents(booth, *booth_definition) > budget_cents) continue;
        const std::optional<std::uint64_t> attraction_id = buildings.linked_attraction_for_ticket_booth(booth.instance_id);
        if (!attraction_id) continue;
        const BuildingInstance* attraction = buildings.find_by_id(*attraction_id);
        if (attraction == nullptr || !attraction->operational) continue;
        const BuildingDefinition* attraction_definition = catalog.find(attraction->definition_id);
        if (attraction_definition == nullptr || !attraction_definition->requires_ticket_booth ||
            !satisfies_need(*attraction_definition, need)) continue;
        if (visitor_access_points(*attraction_definition, attraction->rotation).empty()) continue;

        const std::vector<BuildingAccessPoint> booth_access =
            visitor_access_points(*booth_definition, booth.rotation);
        if (booth_access.empty()) continue;
        for (const BuildingAccessPoint& access : booth_access) {
            const auto [dx, dy] = access_offset(access.facing);
            const NavigationTile service{booth.tile_x + access.local_x + dx,
                                         booth.tile_y + access.local_y + dy};
            if (!network.is_navigable(service)) continue;
            const NavigationPathResult to_booth = find_navigation_path(network, start, service);
            if (to_booth.status != NavigationPathStatus::found || to_booth.tiles.empty()) continue;
            const auto attraction_entrance = reachable_entrance_for_instance(
                service, *attraction, *attraction_definition, network);
            if (!attraction_entrance) continue;
            const std::size_t cost = to_booth.tiles.size() + attraction_entrance->route_tiles;
            if (cost >= best_route_tiles) continue;
            best_route_tiles = cost;
            best = TicketedAttractionRoute{booth.instance_id, attraction->instance_id, service,
                                           access.facing, *attraction_entrance, cost};
        }
    }
    return best;
}

inline void erase_rider_id(std::vector<std::uint64_t>& ids, const std::uint64_t pedestrian_id) {
    ids.erase(std::remove(ids.begin(), ids.end(), pedestrian_id), ids.end());
}

inline void remove_from_ride_runtime(const std::uint64_t pedestrian_id, const std::uint64_t ride_id) {
    const auto found = ride_queues().find(ride_id);
    if (found == ride_queues().end()) return;
    erase_rider_id(found->second.waiting, pedestrian_id);
    erase_rider_id(found->second.riding, pedestrian_id);
    if (found->second.waiting.empty() && found->second.riding.empty()) ride_queues().erase(found);
}

inline void cancel_visit(const std::uint64_t pedestrian_id, VisitState& state,
                         PedestrianSystem& pedestrians, BuildingManager& buildings) {
    if (state.phase == VisitPhase::inside) (void)buildings.end_activity(state.building_instance_id);
    if (state.phase == VisitPhase::queued || state.phase == VisitPhase::inside)
        remove_from_ride_runtime(pedestrian_id, state.building_instance_id);
    if (state.phase == VisitPhase::ticketing || state.phase == VisitPhase::queued ||
        state.phase == VisitPhase::aligning || state.phase == VisitPhase::inside)
        (void)pedestrians.set_visiting(pedestrian_id, false);
}

[[nodiscard]] inline bool is_expected_destination(const PedestrianInstance& pedestrian,
                                                   const VisitState& state) {
    int expected_x = state.door_x;
    int expected_y = state.door_y;
    if (state.phase == VisitPhase::ticket_approaching || state.phase == VisitPhase::ticketing ||
        state.phase == VisitPhase::queued || state.phase == VisitPhase::returning_to_booth) {
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

inline void enqueue_managed_rider(const std::uint64_t pedestrian_id, VisitState& state,
                                  const Uint64 now) {
    RideQueueState& queue = ride_queues()[state.building_instance_id];
    if (queue.last_tick_ms == 0) queue.last_tick_ms = now;
    if (std::find(queue.waiting.begin(), queue.waiting.end(), pedestrian_id) == queue.waiting.end() &&
        std::find(queue.riding.begin(), queue.riding.end(), pedestrian_id) == queue.riding.end()) {
        queue.waiting.push_back(pedestrian_id);
    }
    state.ride_seat_index = -1;
    state.last_tick_ms = now;
    state.elapsed_inside_ms = 0;
    state.phase = VisitPhase::queued;
}

inline void finish_managed_ride_batch(const std::uint64_t ride_id, RideQueueState& queue,
                                      PedestrianSystem& pedestrians, BuildingManager& buildings,
                                      const BuildingCatalog& catalog, const Uint64 now) {
    const BuildingInstance* ride = buildings.find_by_id(ride_id);
    const BuildingDefinition* definition = ride == nullptr ? nullptr : catalog.find(ride->definition_id);
    for (const std::uint64_t pedestrian_id : queue.riding) {
        auto found = states().find(pedestrian_id);
        if (found == states().end()) continue;
        VisitState& state = found->second;
        if (state.phase != VisitPhase::inside || state.building_instance_id != ride_id) continue;
        (void)buildings.end_activity(ride_id);
        if (definition != nullptr) apply_need_effects(pedestrian_id, *definition, pedestrians);
        (void)pedestrians.set_visiting(pedestrian_id, false);
        state.ride_seat_index = -1;
        state.last_tick_ms = now;
        state.elapsed_inside_ms = 0;
        // The logical actor never left the booth service tile. Unhiding it here
        // therefore makes the visitor reappear exactly where the ticket/queue
        // flow started, ready for the normal pedestrian decision system.
        state.phase = VisitPhase::completed_here;
    }
    queue.riding.clear();
    queue.cycle_elapsed_ms = 0;
    queue.boarding_elapsed_ms = 0;
}

inline void sync_managed_rides(PedestrianSystem& pedestrians, BuildingManager& buildings,
                               const BuildingCatalog& catalog, const bool simulation_running,
                               const Uint64 now) {
    auto& queues = ride_queues();
    for (auto iterator = queues.begin(); iterator != queues.end();) {
        const std::uint64_t ride_id = iterator->first;
        RideQueueState& queue = iterator->second;
        const BuildingInstance* ride = buildings.find_by_id(ride_id);
        const BuildingDefinition* definition = ride == nullptr ? nullptr : catalog.find(ride->definition_id);
        const ch::amusement_ride::RuntimeDefinition* ride_definition =
            definition == nullptr ? nullptr : managed_ride_definition(*definition);
        const std::uint32_t capacity = ride_definition == nullptr
            ? 0U : std::min(ride_definition->capacity, ride_definition->seat_count);

        if (ride == nullptr || definition == nullptr || ride_definition == nullptr || capacity == 0U) {
            for (const std::uint64_t pedestrian_id : queue.waiting) {
                if (auto found = states().find(pedestrian_id); found != states().end()) {
                    (void)pedestrians.set_visiting(pedestrian_id, false);
                    found->second.phase = VisitPhase::completed_here;
                    found->second.ride_seat_index = -1;
                }
            }
            for (const std::uint64_t pedestrian_id : queue.riding) {
                if (auto found = states().find(pedestrian_id); found != states().end()) {
                    (void)pedestrians.set_visiting(pedestrian_id, false);
                    found->second.phase = VisitPhase::completed_here;
                    found->second.ride_seat_index = -1;
                }
            }
            iterator = queues.erase(iterator);
            continue;
        }

        queue.waiting.erase(std::remove_if(queue.waiting.begin(), queue.waiting.end(),
            [ride_id](const std::uint64_t pedestrian_id) {
                const auto found = states().find(pedestrian_id);
                return found == states().end() || found->second.phase != VisitPhase::queued ||
                       found->second.building_instance_id != ride_id;
            }), queue.waiting.end());

        const Uint64 delta = queue.last_tick_ms == 0 || now < queue.last_tick_ms ? 0 : now - queue.last_tick_ms;
        queue.last_tick_ms = now;

        if (!queue.riding.empty()) {
            if (simulation_running) queue.cycle_elapsed_ms += delta;
            if (queue.cycle_elapsed_ms >= static_cast<Uint64>(ride_definition->cycle_duration_ms))
                finish_managed_ride_batch(ride_id, queue, pedestrians, buildings, catalog, now);
            ++iterator;
            continue;
        }

        if (queue.waiting.empty()) {
            queue.boarding_elapsed_ms = 0;
            ++iterator;
            continue;
        }

        if (simulation_running) queue.boarding_elapsed_ms += delta;
        const bool dispatch = queue.waiting.size() >= static_cast<std::size_t>(capacity) ||
                              queue.boarding_elapsed_ms >= static_cast<Uint64>(ride_definition->boarding_timeout_ms);
        if (!dispatch) {
            ++iterator;
            continue;
        }

        const std::size_t batch_size = std::min<std::size_t>(queue.waiting.size(), capacity);
        std::vector<std::uint64_t> batch(queue.waiting.begin(), queue.waiting.begin() + batch_size);
        queue.waiting.erase(queue.waiting.begin(), queue.waiting.begin() + batch_size);
        queue.boarding_elapsed_ms = 0;
        queue.cycle_elapsed_ms = 0;

        int seat_index = 0;
        for (const std::uint64_t pedestrian_id : batch) {
            auto found = states().find(pedestrian_id);
            if (found == states().end() || found->second.phase != VisitPhase::queued ||
                found->second.building_instance_id != ride_id) continue;
            if (!buildings.begin_activity(ride_id)) {
                (void)pedestrians.set_visiting(pedestrian_id, false);
                found->second.phase = VisitPhase::completed_here;
                continue;
            }
            found->second.ride_seat_index = seat_index++;
            found->second.last_tick_ms = now;
            found->second.elapsed_inside_ms = 0;
            found->second.phase = VisitPhase::inside;
            queue.riding.push_back(pedestrian_id);
        }
        ++iterator;
    }
}

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
                (state.ticket_booth_instance_id != 0 && buildings.find_by_id(state.ticket_booth_instance_id) == nullptr)) {
                cancel_visit(pedestrian_id, state, pedestrians, buildings);
                runtime_states.erase(current);
                continue;
            }
            if ((state.phase == VisitPhase::ticket_approaching || state.phase == VisitPhase::approaching ||
                 state.phase == VisitPhase::entering || state.phase == VisitPhase::returning_to_booth) &&
                !is_expected_destination(pedestrian_snapshot, state)) {
                cancel_visit(pedestrian_id, state, pedestrians, buildings);
                runtime_states.erase(current);
                continue;
            }

            if (state.phase == VisitPhase::ticketing) {
                const Uint64 delta = now >= state.last_tick_ms ? now - state.last_tick_ms : 0;
                state.last_tick_ms = now;
                if (simulation_running) state.elapsed_inside_ms += delta;
                if (state.elapsed_inside_ms >= kTicketServiceMs) {
                    const auto linked = buildings.linked_attraction_for_ticket_booth(state.ticket_booth_instance_id);
                    if (!linked || *linked != state.building_instance_id) {
                        (void)pedestrians.set_visiting(pedestrian_id, false);
                        runtime_states.erase(current);
                        continue;
                    }

                    const BuildingInstance* attraction = buildings.find_by_id(state.building_instance_id);
                    const BuildingDefinition* attraction_definition =
                        attraction == nullptr ? nullptr : catalog.find(attraction->definition_id);
                    if (attraction_definition != nullptr && managed_ride_capacity(*attraction_definition) > 0U) {
                        // The ticket is purchased at the booth, before a seat is
                        // reserved. The queue then owns this visitor until a batch
                        // is dispatched or the visit is cancelled.
                        if (state.charge_cents > 0 &&
                            !pedestrians.spend_monthly_budget(pedestrian_id, state.charge_cents)) {
                            (void)pedestrians.set_visiting(pedestrian_id, false);
                            runtime_states.erase(current);
                            continue;
                        }
                        state.charge_cents = 0;
                        enqueue_managed_rider(pedestrian_id, state, now);
                        continue;
                    }

                    (void)pedestrians.set_visiting(pedestrian_id, false);
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

            if (state.phase == VisitPhase::queued) continue;

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
                const BuildingInstance* destination = buildings.find_by_id(state.building_instance_id);
                const BuildingDefinition* definition =
                    destination == nullptr ? nullptr : catalog.find(destination->definition_id);
                if (definition != nullptr && managed_ride_capacity(*definition) > 0U) {
                    // Managed rides complete as one synchronized batch below.
                    continue;
                }

                const Uint64 delta = now >= state.last_tick_ms ? now - state.last_tick_ms : 0;
                state.last_tick_ms = now;
                if (simulation_running) state.elapsed_inside_ms += delta;
                if (state.elapsed_inside_ms >= kVisitorDwellMs) {
                    (void)buildings.end_activity(state.building_instance_id);
                    (void)pedestrians.spend_monthly_budget(pedestrian_id, state.charge_cents);
                    if (definition != nullptr) apply_need_effects(pedestrian_id, *definition, pedestrians);
                    (void)pedestrians.set_visiting(pedestrian_id, false);
                    if (state.ticket_booth_instance_id != 0) {
                        const NavigationTile ride_exit{state.door_x, state.door_y};
                        const NavigationTile booth_return{state.ticket_x, state.ticket_y};
                        if (network.is_navigable(ride_exit) && network.is_navigable(booth_return) &&
                            pedestrians.send_pedestrian(ride_exit, booth_return, network)) {
                            state.phase = VisitPhase::returning_to_booth;
                        } else {
                            state.phase = VisitPhase::completed_here;
                        }
                    } else {
                        state.phase = VisitPhase::completed_here;
                    }
                }
                continue;
            }

            if (state.phase == VisitPhase::completed_here) {
                if (pedestrian_snapshot.state == PedestrianState::walking && !is_expected_destination(pedestrian_snapshot, state))
                    runtime_states.erase(current);
                continue;
            }

            if (pedestrian_snapshot.state == PedestrianState::walking) continue;
            const NavigationTile current_tile{pedestrian_snapshot.spatial.logical_tile_x,
                                              pedestrian_snapshot.spatial.logical_tile_y};
            if (state.phase == VisitPhase::returning_to_booth) {
                runtime_states.erase(current);
                continue;
            }
            if (state.phase == VisitPhase::ticket_approaching) {
                const NavigationTile ticket{state.ticket_x, state.ticket_y};
                if (!(current_tile == ticket) || !begin_ticket_service(pedestrian_id, state, pedestrians, now))
                    runtime_states.erase(current);
                continue;
            }
            if (state.phase == VisitPhase::approaching) {
                const NavigationTile approach{state.approach_x, state.approach_y};
                const NavigationTile door{state.door_x, state.door_y};
                if (!(current_tile == approach)) { runtime_states.erase(current); continue; }
                if (approach == door) {
                    if (!begin_alignment(pedestrian_id, state, pedestrians, now)) runtime_states.erase(current);
                } else if (network.is_navigable(door) && pedestrians.send_pedestrian(approach, door, network)) {
                    state.phase = VisitPhase::entering;
                } else runtime_states.erase(current);
                continue;
            }
            if (state.phase == VisitPhase::entering) {
                const NavigationTile door{state.door_x, state.door_y};
                if (!(current_tile == door) || !begin_alignment(pedestrian_id, state, pedestrians, now))
                    runtime_states.erase(current);
                continue;
            }
        }

        if (!allow_autonomous_visits || pedestrian_snapshot.state != PedestrianState::idle ||
            !pedestrian_snapshot.outing_intent.active || pedestrian_snapshot.monthly_budget_cents <= 0) continue;

        const NavigationTile start{pedestrian_snapshot.spatial.logical_tile_x,
                                   pedestrian_snapshot.spatial.logical_tile_y};
        const std::int64_t budget = pedestrian_snapshot.monthly_budget_cents;
        const PedestrianNeed need = pedestrian_snapshot.outing_intent.priority_need;
        const auto entrance = best_reachable_entrance(start, buildings, catalog, network, budget, need, false);
        const auto essential = best_reachable_entrance(start, buildings, catalog, network, budget, need, true);
        const auto ticketed = best_reachable_ticketed_attraction(start, buildings, catalog, network, budget, need);

        bool choose_ticketed = false;
        std::optional<EntranceRoute> chosen_entrance;
        switch (pedestrian_snapshot.outing_intent.preference) {
            case PedestrianOutingPreference::outdoor_leisure:
                choose_ticketed = ticketed.has_value();
                if (!choose_ticketed) chosen_entrance = entrance;
                break;
            case PedestrianOutingPreference::covered_commerce:
                chosen_entrance = entrance;
                break;
            case PedestrianOutingPreference::essential_commerce:
                chosen_entrance = essential ? essential : entrance;
                break;
            case PedestrianOutingPreference::balanced:
                if (ticketed && (!entrance || ticketed->route_tiles <= entrance->route_tiles)) choose_ticketed = true;
                else chosen_entrance = entrance;
                break;
        }

        if (choose_ticketed && ticketed) {
            const BuildingInstance* booth = buildings.find_by_id(ticketed->booth_instance_id);
            const BuildingDefinition* booth_definition = booth == nullptr ? nullptr : catalog.find(booth->definition_id);
            if (booth == nullptr || booth_definition == nullptr) continue;
            const std::int64_t charge = service_price_cents(*booth, *booth_definition);
            if (!pedestrians.send_pedestrian(start, ticketed->booth_service, network)) continue;
            pedestrians.clear_outing_intent(pedestrian_id);
            runtime_states[pedestrian_id] = VisitState{ticketed->attraction_instance_id,
                ticketed->booth_instance_id, ticketed->booth_service.x, ticketed->booth_service.y,
                ticketed->booth_facing, ticketed->attraction_entrance.approach.x,
                ticketed->attraction_entrance.approach.y, ticketed->attraction_entrance.door.x,
                ticketed->attraction_entrance.door.y, ticketed->attraction_entrance.door_facing,
                charge, now, 0, -1, VisitPhase::ticket_approaching};
            continue;
        }

        if (!chosen_entrance) continue;
        const BuildingInstance* destination = buildings.find_by_id(chosen_entrance->building_instance_id);
        const BuildingDefinition* destination_definition = destination == nullptr ? nullptr : catalog.find(destination->definition_id);
        if (destination == nullptr || destination_definition == nullptr) continue;
        const std::int64_t charge = service_price_cents(*destination, *destination_definition);
        if (!pedestrians.send_pedestrian(start, chosen_entrance->approach, network)) continue;
        pedestrians.clear_outing_intent(pedestrian_id);
        runtime_states[pedestrian_id] = VisitState{chosen_entrance->building_instance_id, 0, 0, 0,
            GridDirection::south, chosen_entrance->approach.x, chosen_entrance->approach.y,
            chosen_entrance->door.x, chosen_entrance->door.y, chosen_entrance->door_facing,
            charge, now, 0, -1, VisitPhase::approaching};
    }

    sync_managed_rides(pedestrians, buildings, catalog, simulation_running, now);
}

[[nodiscard]] inline bool is_inside(const std::uint64_t pedestrian_id) {
    const auto found = states().find(pedestrian_id);
    return found != states().end() && found->second.phase == VisitPhase::inside;
}

[[nodiscard]] inline std::optional<int> ride_seat_index_for(const std::uint64_t pedestrian_id) {
    const auto found = states().find(pedestrian_id);
    if (found == states().end() || found->second.phase != VisitPhase::inside ||
        found->second.ride_seat_index < 0) return std::nullopt;
    return found->second.ride_seat_index;
}

[[nodiscard]] inline std::size_t ride_queue_size(const std::uint64_t attraction_instance_id) {
    const auto found = ride_queues().find(attraction_instance_id);
    return found == ride_queues().end() ? 0U : found->second.waiting.size();
}

[[nodiscard]] inline std::size_t ride_occupancy(const std::uint64_t attraction_instance_id) {
    const auto found = ride_queues().find(attraction_instance_id);
    return found == ride_queues().end() ? 0U : found->second.riding.size();
}

inline void filter_inside_pedestrians(std::vector<MobileEntityRenderData>& entities,
                                      const PedestrianSystem& pedestrians) {
    const auto& instances = pedestrians.instances();
    if (instances.empty() || instances.size() > entities.size()) return;
    const std::size_t pedestrian_start = entities.size() - instances.size();
    std::size_t write_index = pedestrian_start;
    for (std::size_t index = 0; index < instances.size(); ++index) {
        if (is_inside(instances[index].id) || instances[index].state == PedestrianState::resting) continue;
        if (write_index != pedestrian_start + index)
            entities[write_index] = std::move(entities[pedestrian_start + index]);
        ++write_index;
    }
    entities.resize(write_index);
}

inline void clear(PedestrianSystem& pedestrians, BuildingManager& buildings) {
    for (auto& [pedestrian_id, state] : states()) cancel_visit(pedestrian_id, state, pedestrians, buildings);
    states().clear();
    ride_queues().clear();
}

}  // namespace ch::building_visit_runtime
