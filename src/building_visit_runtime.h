#pragma once

#include <SDL3/SDL.h>

#include "building_system.h"
#include "pedestrian_system.h"

#include <algorithm>
#include <cstdint>
#include <optional>
#include <unordered_map>
#include <utility>
#include <vector>

// First vertical slice of CH_VISITOR_MVP_V1 building entry.
//
// A pedestrian that finishes a route on an authored building access tile is
// considered to have entered that building. While inside, the pedestrian is
// omitted from the world render and the building's normal activity counter is
// held. The counter means overlapping visitors remain safe without coupling
// the renderer to visitor logic. The first consumer is Mini Mercado, but this
// bridge intentionally works for any definition that opts into
// CH_BUILDING_ACTIVITY_OVERLAY_V1 and has explicit/front-edge access points.
namespace ch::building_visit_runtime {

constexpr Uint64 kVisitorDwellMs = 3000;

struct VisitState {
    std::uint64_t building_instance_id = 0;
    int destination_x = 0;
    int destination_y = 0;
    Uint64 last_tick_ms = 0;
    Uint64 elapsed_inside_ms = 0;
    bool inside = false;
    bool completed_here = false;
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

[[nodiscard]] inline std::optional<std::uint64_t> activity_building_at(
    const int tile_x, const int tile_y,
    const BuildingManager& buildings, const BuildingCatalog& catalog) {
    for (const BuildingInstance& instance : buildings.instances()) {
        if (!instance.operational) continue;
        const BuildingDefinition* definition = catalog.find(instance.definition_id);
        if (definition == nullptr || !definition->activity_overlay ||
            !definition->activity_overlay->enabled) {
            continue;
        }

        for (const BuildingAccessPoint& access : road_access_candidates(*definition, instance.rotation)) {
            const auto [offset_x, offset_y] = access_offset(access.facing);
            if (instance.tile_x + access.local_x + offset_x == tile_x &&
                instance.tile_y + access.local_y + offset_y == tile_y) {
                return instance.instance_id;
            }
        }
    }
    return std::nullopt;
}

inline void cancel_visit(VisitState& state, BuildingManager& buildings) {
    if (state.inside) {
        (void)buildings.end_activity(state.building_instance_id);
    }
    state.inside = false;
}

// Called from the runtime frame bridge. The dwell timer advances only while
// simulation_running is true, so pause screens do not silently finish visits.
inline void sync(PedestrianSystem& pedestrians, BuildingManager& buildings,
                 const BuildingCatalog& catalog, const bool simulation_running) {
    const Uint64 now = SDL_GetTicks();
    auto& runtime_states = states();

    for (const PedestrianInstance& pedestrian : pedestrians.instances()) {
        auto current = runtime_states.find(pedestrian.id);
        if (current != runtime_states.end()) {
            VisitState& state = current->second;
            const bool destination_changed =
                state.destination_x != pedestrian.destination.x ||
                state.destination_y != pedestrian.destination.y;

            // The current test pedestrian may be reused for a new route. A new
            // trip cancels stale visit state before normal route processing.
            if (pedestrian.state == PedestrianState::walking || destination_changed) {
                cancel_visit(state, buildings);
                runtime_states.erase(current);
                current = runtime_states.end();
            } else if (state.inside) {
                // Demolition or replacement while a visitor is inside must not
                // leave hidden pedestrian state behind.
                if (buildings.find_by_id(state.building_instance_id) == nullptr) {
                    runtime_states.erase(current);
                    continue;
                }

                const Uint64 delta = now >= state.last_tick_ms ? now - state.last_tick_ms : 0;
                state.last_tick_ms = now;
                if (simulation_running) state.elapsed_inside_ms += delta;
                if (state.elapsed_inside_ms >= kVisitorDwellMs) {
                    (void)buildings.end_activity(state.building_instance_id);
                    state.inside = false;
                    state.completed_here = true;
                }
                continue;
            } else if (state.completed_here) {
                // Remain visible at the exit until another route is assigned;
                // otherwise an idle pedestrian would immediately re-enter.
                state.last_tick_ms = now;
                continue;
            }
        }

        if (pedestrian.state != PedestrianState::idle) continue;
        const auto building_id = activity_building_at(
            pedestrian.destination.x, pedestrian.destination.y, buildings, catalog);
        if (!building_id || !buildings.begin_activity(*building_id)) continue;

        runtime_states[pedestrian.id] = VisitState{
            *building_id,
            pedestrian.destination.x,
            pedestrian.destination.y,
            now,
            0,
            true,
            false,
        };
    }
}

[[nodiscard]] inline bool is_inside(const std::uint64_t pedestrian_id) {
    const auto found = states().find(pedestrian_id);
    return found != states().end() && found->second.inside;
}

// main_runtime_impl currently appends pedestrian render data after service
// vehicles. Preserve that ordering while removing only visitors that are
// physically inside a building. The logic remains valid when PedestrianSystem
// grows beyond the current single test pedestrian, provided it keeps one render
// record per instance in instance order (its current contract).
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

inline void clear(BuildingManager& buildings) {
    for (auto& [pedestrian_id, state] : states()) {
        (void)pedestrian_id;
        cancel_visit(state, buildings);
    }
    states().clear();
}

}  // namespace ch::building_visit_runtime
