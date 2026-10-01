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
// 19. Viking-ship rope creaks start only while the ride moves, with a small
//     presentation-only speed-of-sound propagation delay.

#include "audio_manager.h"
#include "building_system.h"
#include "building_visit_runtime.h"
#include "economy_system.h"
#include "land_system.h"
#include "park_fence_runtime.h"
#include "park_fence_save_manager.h"
#include "simulation_clock.h"
#include "src/runtime_view_state.h"
#include "src/runtime_map_renderer.h"
#include "src/runtime_game_state.h"
#include "src/runtime_game_ui.h"

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
        if (instance.definition_id != "ferris_wheel_01" || !instance.activity_active()) continue;
        const BuildingDefinition* definition = catalog.find(instance.definition_id);
        if (definition != nullptr && ch_attraction_visible_in_current_view(instance, *definition)) {
            return true;
        }
    }
    return false;
}

[[nodiscard]] inline std::optional<std::uint32_t> ch_viking_ship_sound_delay_ms(
    const BuildingManager& buildings, const BuildingCatalog& catalog) {
    const ch::runtime_view::ViewSnapshot view = ch::runtime_view::snapshot();
    if (!view.valid) return std::nullopt;

    const ch::WorldPoint listener = ch::screen_to_world_point(
        view.viewport_width * 0.5F, view.viewport_height * 0.5F,
        view.camera, view.viewport_width, view.viewport_height);
    float nearest_distance_tiles = -1.0F;

    for (const BuildingInstance& instance : buildings.instances()) {
        if (instance.definition_id != "viking_ship_01" || !instance.activity_active()) continue;
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

struct ChVikingShipAudioDelayState {
    bool waiting_or_playing = false;
    std::uint64_t ready_at_ms = 0;
};

inline void ch_sync_park_ride_audio_visibility(
    AudioManager& audio, const BuildingManager& buildings, const BuildingCatalog& catalog,
    const bool simulation_running) {
    static ChVikingShipAudioDelayState viking_audio;
    const std::optional<std::uint32_t> viking_delay = simulation_running
        ? ch_viking_ship_sound_delay_ms(buildings, catalog)
        : std::nullopt;
    const std::uint64_t now_ms = SDL_GetTicks();

    if (viking_delay) {
        if (!viking_audio.waiting_or_playing) {
            viking_audio.waiting_or_playing = true;
            viking_audio.ready_at_ms = now_ms + *viking_delay;
        }
        if (now_ms >= viking_audio.ready_at_ms) {
            (void)audio.set_looping(SoundEvent::viking_ship_running, true);
            return;
        }
    } else {
        viking_audio = {};
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
    const Camera& camera, const float viewport_width, const float viewport_height) {
    constexpr float kPickRadiusPx = 28.0F;
    constexpr float kPickRadiusSquared = kPickRadiusPx * kPickRadiusPx;
    std::optional<std::uint64_t> best;
    float best_distance_squared = kPickRadiusSquared;
    for (const PedestrianInstance& pedestrian : pedestrians.instances()) {
        if (pedestrian.state == PedestrianState::resting || pedestrian.state == PedestrianState::visiting) continue;
        const SDL_FPoint screen = world_to_screen(
            pedestrian.spatial.visual_world_x + pedestrian.spatial.ground_anchor_x,
            pedestrian.spatial.visual_world_y + pedestrian.spatial.ground_anchor_y,
            camera, viewport_width, viewport_height);
        const float dx = mouse_x - screen.x;
        const float dy = mouse_y - (screen.y - 16.0F * camera.zoom);
        const float distance_squared = dx * dx + dy * dy;
        if (distance_squared <= best_distance_squared) {
            best_distance_squared = distance_squared;
            best = pedestrian.id;
        }
    }
    return best;
}

class ChRuntimeSelectableGameplayUi : public ChRuntimeGameplayUi {
public:
    using ChRuntimeGameplayUi::ChRuntimeGameplayUi;

    void bind_selection_context(const PedestrianSystem* pedestrians,
                                const Camera* camera,
                                const int viewport_width,
                                const int viewport_height,
                                std::optional<std::uint64_t>* selected_pedestrian_id,
                                const bool world_selection_enabled) {
        pedestrians_ = pedestrians;
        camera_ = camera;
        viewport_width_ = viewport_width;
        viewport_height_ = viewport_height;
        selected_pedestrian_id_ = selected_pedestrian_id;
        world_selection_enabled_ = world_selection_enabled;
    }

    [[nodiscard]] UiInputResult handle_mouse_button_down(const float mouse_x,
                                                         const float mouse_y,
                                                         const bool primary_button) {
        UiInputResult result = ChRuntimeGameplayUi::handle_mouse_button_down(mouse_x, mouse_y, primary_button);
        if (result.consumed || !primary_button || !world_selection_enabled_ || pedestrians_ == nullptr ||
            camera_ == nullptr || selected_pedestrian_id_ == nullptr) {
            return result;
        }
        const std::optional<std::uint64_t> picked = ch_pick_pedestrian_at_screen(
            *pedestrians_, mouse_x, mouse_y, *camera_,
            static_cast<float>(viewport_width_), static_cast<float>(viewport_height_));
        if (!picked) return result;
        *selected_pedestrian_id_ = *picked;
        result.consumed = true;
        return result;
    }

private:
    const PedestrianSystem* pedestrians_ = nullptr;
    const Camera* camera_ = nullptr;
    int viewport_width_ = 1;
    int viewport_height_ = 1;
    std::optional<std::uint64_t>* selected_pedestrian_id_ = nullptr;
    bool world_selection_enabled_ = false;
};

#define parcels() world_parcels()
#define PedestrianLaneNavigationNetwork ParkFencePedestrianNavigationNetwork
#define SaveManager ParkFenceSaveManager
#define CityEconomy ChCityEconomy
#define SimulationClock ChSimulationClock

#define set_service_price(instance_id, definition, service_price) \
    set_service_price((instance_id), (definition), (service_price)) && \
    ch_sync_service_price_after_ui_edit(buildings, catalog, (instance_id), (definition))

#define mobile_render_entities() \
    ([&]() { \
        const auto ch_budget_date = simulation_clock.date(); \
        pedestrians.sync_monthly_budget_cycle(ch_budget_date.month, ch_budget_date.year); \
        ch_sync_park_ride_audio_visibility( \
            audio, buildings, catalog, simulation_clock.speed() != SimulationSpeed::paused); \
        const PedestrianSurfaceNavigationNetwork ch_visit_surfaces{roads, sidewalks}; \
        ch::building_visit_runtime::sync( \
            pedestrians, buildings, catalog, ch_visit_surfaces, \
            simulation_clock.speed() != SimulationSpeed::paused, automatic_pedestrian); \
        pedestrians.update_animation(0.0F, mobile_animations); \
        auto ch_mobile_entities = mobile_render_entities(); \
        ch::building_visit_runtime::filter_inside_pedestrians(ch_mobile_entities, pedestrians); \
        return ch_mobile_entities; \
    }())

#define play_sound(sound_event) \
    ([&]() { \
        const SoundEvent ch_sound_event = (sound_event); \
        if (ch_sound_event == SoundEvent::building_place) { \
            placement_definition_id.clear(); \
        } \
        return play_sound(ch_sound_event); \
    }())

#define rotate_placement(clockwise) \
    ([&]() { \
        const bool ch_camera_clockwise = static_cast<bool>(clockwise); \
        if (!placement_definition_id.empty()) { \
            rotate_placement(ch_camera_clockwise); \
            return; \
        } \
        const float ch_half_tile_width = kTileWidth * 0.5F * camera.zoom; \
        const float ch_half_tile_height = kTileHeight * 0.5F * camera.zoom; \
        if (ch_half_tile_width <= 0.0F || ch_half_tile_height <= 0.0F) return; \
        const float ch_axis_x = -camera.pan_x / ch_half_tile_width; \
        const float ch_axis_y = -camera.pan_y / ch_half_tile_height; \
        const CameraWorldPoint ch_focus = logical_world_point( \
            (ch_axis_y + ch_axis_x) * 0.5F, \
            (ch_axis_y - ch_axis_x) * 0.5F, \
            camera.rotation); \
        const CameraRotation ch_next_rotation = ch_camera_clockwise \
            ? rotate_camera_clockwise(camera.rotation) \
            : rotate_camera_counter_clockwise(camera.rotation); \
        const CameraWorldPoint ch_focus_in_new_view = camera_view_point( \
            ch_focus.x, ch_focus.y, ch_next_rotation); \
        camera.rotation = ch_next_rotation; \
        camera.pan_x = -(ch_focus_in_new_view.x - ch_focus_in_new_view.y) * ch_half_tile_width; \
        camera.pan_y = -(ch_focus_in_new_view.x + ch_focus_in_new_view.y) * ch_half_tile_height; \
        camera.pan_velocity_x = 0.0F; \
        camera.pan_velocity_y = 0.0F; \
        status = std::string("CAMERA FACING ") + camera_rotation_label(camera.rotation) + " | Z/X ROTATE"; \
        (void)play_sound(SoundEvent::ui_click); \
    }())

#define MapRenderer RuntimeMapRenderer
#define GameplayUi ChRuntimeSelectableGameplayUi
#define update_layout(viewport_width, viewport_height, model) \
    ([&]() { \
        auto ch_ui_model = (model); \
        ch_fill_citizen_status(ch_ui_model, pedestrians, selected_pedestrian_id); \
        gameplay_ui.bind_selection_context( \
            &pedestrians, &camera, (viewport_width), (viewport_height), &selected_pedestrian_id, \
            placement_definition_id.empty() && !road_mode && !sidewalk_mode && !land_mode && \
            !agriculture_mode && !decoration_mode && active_overlay == UiOverlay::none); \
        update_layout((viewport_width), (viewport_height), ch_ui_model); \
    }())

#define selected_instance_id selected_instance_id; std::optional<std::uint64_t> selected_pedestrian_id

#include "main_runtime_impl.cpp"

#undef selected_instance_id
#undef update_layout
#undef GameplayUi
#undef MapRenderer
#undef rotate_placement
#undef play_sound
#undef mobile_render_entities
#undef set_service_price
#undef SimulationClock
#undef CityEconomy
#undef SaveManager
#undef PedestrianLaneNavigationNetwork
#undef parcels
