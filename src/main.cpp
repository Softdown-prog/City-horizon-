// CITY HORIZON runtime entry point.
//
// The implementation remains in main_runtime_impl.cpp.  This narrow wrapper
// carries runtime compatibility/features without duplicating the runtime loop:
//
// 1. Building placement is one-shot after a successful placement.
// 2. Camera/cursor geometry spans every generated parcel while ownership rules stay authoritative.
// 3. Pedestrian navigation respects Park fence barriers and gates.
// 4. SaveManager persists the Park fence network alongside the canonical city save.
// 5. Service-price clicks respect authored price steps and linked Park booths.
// 6. Park attraction audio follows activity plus current camera visibility.
// 7. Runtime rendering uses a conservative camera-visible working set.
// 8. Z/X rotate the production camera when no building is being placed.
// 9. Runtime UI adds camera controls and lightweight procedural overlays.
// 10. Interior visits use authored front doors and the live pedestrian graph.
// 11. Visitor eligibility remains explicit for residences/vendors/booths/rides.
// 12. Ticketed Park rides use the booth -> boarding sequence.
// 13. Citizen monthly spending budgets reset exactly once per game month.
// 14. Bankruptcy state is bridged into a blocking Game Over presentation after
//     three consecutive negative-treasury month closes.
// 15. Once bankrupt, the simulation clock is frozen while ESC remains available
//     for the existing menu flow.
// 16. The runtime UI receives a compact citizen inspection snapshot for needs/budget bars.
// 17. Normal world clicks can select the nearest visible pedestrian for that panel.
// 18. Citizen status remains hidden until the player explicitly selects a pedestrian.
// 19. Pirate-ship rope creaks start only while the ride moves, with a small
//     presentation-only speed-of-sound propagation delay.
// 20. Aggregate residential population materializes bounded, persistent citizen
//     actors whose autonomous decisions are sharded across simulation ticks.
// 21. The shared procedural railway graph is authorable and rendered by the live runtime.

#include "audio_manager.h"
#include "building_system.h"
#include "building_visit_runtime.h"
#include "economy_system.h"
#include "land_system.h"
#include "mission_system.h"
#include "park_fence_runtime.h"
#include "park_fence_save_manager.h"
#include "pedestrian_decision.h"
#include "population_system.h"
#include "ride_runtime_registry.h"
#include "simulation_clock.h"
#include "src/ch_core/projection.h"
#include "src/runtime_view_state.h"
#include "src/runtime_map_renderer.h"
#include "src/runtime_game_state.h"
#include "src/runtime_game_ui.h"
#include "src/rail_runtime_bridge.h"

#include <algorithm>
#include <cmath>
#include <optional>

namespace ch {

[[nodiscard]] inline std::int64_t operator+(const ServicePrice& price,
                                            const std::int64_t delta) noexcept {
    const std::int64_t step = price.step_minor_units > 0 ? price.step_minor_units : 1;
    if (delta == 1) return price.minor_units + step;
    if (delta == -1) return price.minor_units - step;
    return price.minor_units + delta;
}

}  // namespace ch

class ChCityEconomy : public CityEconomy {
public:
    using CityEconomy::CityEconomy;

    void restore_funds(const std::int64_t funds) {
        CityEconomy::restore_funds(funds);
        ch::runtime_game_state::reset();
        ch::rail_runtime::reset();
        ch::ride_runtime::reset();
    }

    void on_month_closed(const BuildingManager& buildings, const BuildingCatalog& catalog,
                         const PopulationSystem& population, const GameDate& closing_date,
                         const ServiceVehicleCatalog* vehicle_catalog = nullptr,
                         const ServiceVehicleManager* vehicles = nullptr,
                         FarmingSystem* farming = nullptr) {
        CityEconomy::on_month_closed(buildings, catalog, population, closing_date,
                                     vehicle_catalog, vehicles, farming);
        ch::runtime_game_state::update(bankrupt(), consecutive_negative_months());
    }

    void process_month(const BuildingManager& buildings, const BuildingCatalog& catalog,
                       const PopulationSystem& population, const GameDate& closing_date,
                       const ServiceVehicleCatalog* vehicle_catalog = nullptr,
                       const ServiceVehicleManager* vehicles = nullptr,
                       FarmingSystem* farming = nullptr) {
        CityEconomy::process_month(buildings, catalog, population, closing_date,
                                   vehicle_catalog, vehicles, farming);
        ch::runtime_game_state::update(bankrupt(), consecutive_negative_months());
    }
};

class ChSimulationClock : public SimulationClock {
public:
    using SimulationClock::SimulationClock;

    [[nodiscard]] SimulationSpeed speed() const {
        return ch::runtime_game_state::game_over
            ? SimulationSpeed::paused
            : SimulationClock::speed();
    }

    void set_speed(const SimulationSpeed speed) {
        if (!ch::runtime_game_state::game_over) SimulationClock::set_speed(speed);
    }

    void toggle_pause() {
        if (!ch::runtime_game_state::game_over) SimulationClock::toggle_pause();
    }

    [[nodiscard]] SimulationAdvance advance_seconds(const double real_seconds) {
        if (ch::runtime_game_state::game_over) return {};
        return SimulationClock::advance_seconds(real_seconds);
    }
};

// Runtime-only bridge: there is one authoritative population simulation in a
// City Horizon session. The compatibility wrapper registers that instance so
// the legacy runtime call site can feed it to the scalable citizen controller
// without duplicating or rewriting main_runtime_impl.cpp.
class ChPopulationSystem : public PopulationSystem {
public:
    ChPopulationSystem() { active_instance_ = this; }
    ~ChPopulationSystem() {
        if (active_instance_ == this) active_instance_ = nullptr;
    }

    [[nodiscard]] static ChPopulationSystem* active_instance() { return active_instance_; }

private:
    inline static ChPopulationSystem* active_instance_ = nullptr;
};

class ChPedestrianDecisionNode {
public:
    void reset() {
        scalable_.reset();
        legacy_.reset();
    }

    void update(const float seconds, PedestrianSystem& pedestrians, const NavigationNetwork& network,
                const BuildingManager& buildings, const BuildingCatalog& catalog,
                const RoadManager& roads, const SidewalkManager& sidewalks, const bool raining = false) {
        if (ChPopulationSystem* population = ChPopulationSystem::active_instance()) {
            scalable_.update(seconds, *population, pedestrians, network,
                             buildings, catalog, roads, sidewalks, raining);
            return;
        }
        legacy_.update(seconds, pedestrians, network, buildings, catalog, roads, sidewalks, raining);
    }

private:
    PedestrianDecisionSystem scalable_;
    PedestrianDecisionNode legacy_;
};

[[nodiscard]] inline bool ch_sync_service_price_after_ui_edit(
    BuildingManager& buildings, const BuildingCatalog& catalog,
    const std::uint64_t edited_instance_id, const BuildingDefinition& edited_definition) {
    if (!edited_definition.requires_ticket_booth) return true;

    const std::optional<std::uint64_t> booth_id =
        buildings.linked_ticket_booth_for_attraction(edited_instance_id);
    if (!booth_id) return true;

    const BuildingInstance* edited = buildings.find_by_id(edited_instance_id);
    const BuildingInstance* booth = buildings.find_by_id(*booth_id);
    const BuildingDefinition* booth_definition =
        booth == nullptr ? nullptr : catalog.find(booth->definition_id);
    if (edited == nullptr || booth == nullptr || booth_definition == nullptr ||
        !booth_definition->is_park_ticket_booth || edited->service_price <= 0) {
        return false;
    }

    return buildings.set_service_price(
        booth->instance_id, *booth_definition,
        static_cast<std::int64_t>(edited->service_price));
}

[[nodiscard]] inline bool ch_attraction_visible_in_current_view(
    const BuildingInstance& instance, const BuildingDefinition& definition) {
    const ch::runtime_view::ViewSnapshot view = ch::runtime_view::snapshot();
    if (!view.valid) return false;

    const BuildingFootprint footprint = rotated_footprint(definition, instance.rotation);
    const float x0 = static_cast<float>(instance.tile_x);
    const float y0 = static_cast<float>(instance.tile_y);
    const float x1 = x0 + static_cast<float>(footprint.width);
    const float y1 = y0 + static_cast<float>(footprint.height);

    const ch::ScreenPoint top = ch::world_to_screen_point(x0, y0, view.camera,
                                                          view.viewport_width, view.viewport_height);
    const ch::ScreenPoint right = ch::world_to_screen_point(x1, y0, view.camera,
                                                            view.viewport_width, view.viewport_height);
    const ch::ScreenPoint bottom = ch::world_to_screen_point(x1, y1, view.camera,
                                                             view.viewport_width, view.viewport_height);
    const ch::ScreenPoint left = ch::world_to_screen_point(x0, y1, view.camera,
                                                           view.viewport_width, view.viewport_height);

    const float min_x = std::min(std::min(top.x, right.x), std::min(bottom.x, left.x));
    const float max_x = std::max(std::max(top.x, right.x), std::max(bottom.x, left.x));
    const float min_y = std::min(std::min(top.y, right.y), std::min(bottom.y, left.y));
    const float max_y = std::max(std::max(top.y, right.y), std::max(bottom.y, left.y));

    return max_x > 0.0F && min_x < view.viewport_width &&
           max_y > 0.0F && min_y < view.viewport_height;
}

[[nodiscard]] inline bool ch_ferris_wheel_should_be_audible(
    const BuildingManager& buildings, const BuildingCatalog& catalog) {
    for (const BuildingInstance& instance : buildings.instances()) {
        if (instance.definition_id != "ferris_wheel_01" ||
            !ch::ride_runtime::is_moving(instance.instance_id)) continue;
        const BuildingDefinition* definition = catalog.find(instance.definition_id);
        if (definition != nullptr && ch_attraction_visible_in_current_view(instance, *definition)) {
            return true;
        }
    }
    return false;
}

[[nodiscard]] inline std::optional<std::uint32_t> ch_pirate_ship_sound_delay_ms(
    const BuildingManager& buildings, const BuildingCatalog& catalog) {
    const ch::runtime_view::ViewSnapshot view = ch::runtime_view::snapshot();
    if (!view.valid) return std::nullopt;

    const ch::WorldPoint listener = ch::screen_to_world_point(
        view.viewport_width * 0.5F, view.viewport_height * 0.5F,
        view.camera, view.viewport_width, view.viewport_height);
    float nearest_distance_tiles = -1.0F;

    for (const BuildingInstance& instance : buildings.instances()) {
        if (instance.definition_id != "pirate_ship_01" ||
            !ch::ride_runtime::is_moving(instance.instance_id)) continue;
        const BuildingDefinition* definition = catalog.find(instance.definition_id);
        if (definition == nullptr || !ch_attraction_visible_in_current_view(instance, *definition)) continue;

        const BuildingFootprint footprint = rotated_footprint(*definition, instance.rotation);
        const float source_x = static_cast<float>(instance.tile_x) + static_cast<float>(footprint.width) * 0.5F;
        const float source_y = static_cast<float>(instance.tile_y) + static_cast<float>(footprint.height) * 0.5F;
        const float dx = source_x - listener.x;
        const float dy = source_y - listener.y;
        const float distance_tiles = std::sqrt(dx * dx + dy * dy);
        if (nearest_distance_tiles < 0.0F || distance_tiles < nearest_distance_tiles) {
            nearest_distance_tiles = distance_tiles;
        }
    }

    if (nearest_distance_tiles < 0.0F) return std::nullopt;

    // Audio presentation scale only: one logical tile is treated as roughly 3 m.
    // Propagation uses 343 m/s and is capped so the effect stays responsive in a tycoon view.
    constexpr float kPresentationMetersPerTile = 3.0F;
    constexpr float kSpeedOfSoundMetersPerSecond = 343.0F;
    constexpr std::uint32_t kMaximumPropagationDelayMs = 140U;
    const float delay_ms = nearest_distance_tiles * kPresentationMetersPerTile /
                           kSpeedOfSoundMetersPerSecond * 1000.0F;
    return std::min(kMaximumPropagationDelayMs,
                    static_cast<std::uint32_t>(std::max(0L, std::lround(delay_ms))));
}

struct ChPirateShipAudioDelayState {
    bool waiting_or_playing = false;
    std::uint64_t ready_at_ms = 0;
};

inline void ch_sync_park_ride_audio_visibility(
    AudioManager& audio, const BuildingManager& buildings, const BuildingCatalog& catalog,
    const bool simulation_running) {
    static ChPirateShipAudioDelayState pirate_audio;
    const std::optional<std::uint32_t> pirate_delay = simulation_running
        ? ch_pirate_ship_sound_delay_ms(buildings, catalog)
        : std::nullopt;
    const std::uint64_t now_ms = SDL_GetTicks();

    if (pirate_delay) {
        if (!pirate_audio.waiting_or_playing) {
            pirate_audio.waiting_or_playing = true;
            pirate_audio.ready_at_ms = now_ms + *pirate_delay;
        }
        if (now_ms >= pirate_audio.ready_at_ms) {
            (void)audio.set_looping(SoundEvent::pirate_ship_running, true);
            return;
        }
    } else {
        pirate_audio = {};
    }

    const bool ferris_audible = simulation_running &&
        ch_ferris_wheel_should_be_audible(buildings, catalog);
    (void)audio.set_looping(SoundEvent::ferris_wheel_running, ferris_audible);
}

[[nodiscard]] inline const char* ch_pedestrian_activity_label(const PedestrianState state) {
    switch (state) {
        case PedestrianState::resting: return "EM CASA";
        case PedestrianState::walking: return "CAMINHANDO";
        case PedestrianState::visiting: return "CONSUMINDO / VISITANDO";
        case PedestrianState::idle: return "AGUARDANDO DECISAO";
    }
    return "AGUARDANDO";
}

[[nodiscard]] inline const PedestrianInstance* ch_find_pedestrian(
    const PedestrianSystem& pedestrians, const std::optional<std::uint64_t> selected_id) {
    if (!selected_id) return nullptr;
    for (const PedestrianInstance& pedestrian : pedestrians.instances()) {
        if (pedestrian.id == *selected_id) return &pedestrian;
    }
    return nullptr;
}

inline std::optional<std::uint64_t> ch_selected_pedestrian_id;

inline void ch_fill_citizen_status(GameplayUiModel& model, const PedestrianSystem& pedestrians,
                                   const std::optional<std::uint64_t> selected_id) {
    const PedestrianInstance* pedestrian = ch_find_pedestrian(pedestrians, selected_id);
    if (pedestrian == nullptr) {
        model.citizen_status.reset();
        return;
    }
    const PedestrianNeeds needs = pedestrian->needs;
    UiCitizenStatus status;
    status.citizen_id = pedestrian->id;
    status.title = "CIDADAO #" + std::to_string(pedestrian->id);
    status.activity = ch_pedestrian_activity_label(pedestrian->state);
    status.money = "$" + std::to_string(pedestrian->monthly_budget_cents / 100) +
                   " / $" + std::to_string(pedestrian->monthly_budget_capacity_cents / 100);
    status.hunger = std::clamp(static_cast<int>(std::lround(needs.hunger)), 0, 100);
    status.thirst = std::clamp(static_cast<int>(std::lround(needs.thirst)), 0, 100);
    status.fun = std::clamp(static_cast<int>(std::lround(needs.fun)), 0, 100);
    model.citizen_status = std::move(status);
}

[[nodiscard]] inline std::optional<std::uint64_t> ch_pick_pedestrian_at_screen(
    const PedestrianSystem& pedestrians, const float mouse_x, const float mouse_y,
    const ch::CameraState& camera, const float viewport_width, const float viewport_height) {
    constexpr float kPickRadiusPx = 28.0F;
    constexpr float kPickRadiusSquared = kPickRadiusPx * kPickRadiusPx;
    std::optional<std::uint64_t> best;
    float best_distance_squared = kPickRadiusSquared;
    for (const PedestrianInstance& pedestrian : pedestrians.instances()) {
        if (pedestrian.state == PedestrianState::resting || pedestrian.state == PedestrianState::visiting) continue;
        const ch::ScreenPoint screen = ch::world_to_screen_point(
            pedestrian.map_x, pedestrian.map_y, camera, viewport_width, viewport_height);
        const float dx = screen.x - mouse_x;
        const float dy = screen.y - mouse_y;
        const float distance_squared = dx * dx + dy * dy;
        if (distance_squared <= best_distance_squared) {
            best_distance_squared = distance_squared;
            best = pedestrian.id;
        }
    }
    return best;
}

#include "main_runtime_impl.cpp"
