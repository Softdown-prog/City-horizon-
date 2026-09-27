// CITY HORIZON runtime entry point.
//
// The implementation remains in main_runtime_impl.cpp.  This narrow wrapper
// carries eleven compatibility/runtime fixes without duplicating the runtime loop:
//
// 1. Building placement is one-shot: after a successful building is placed
//    and its BuildingPlace sound is emitted, the active placement id is cleared
//    before the next frame.
// 2. Camera/cursor world bounds use every generated parcel, not only purchased
//    parcels.  Placement/economy ownership still goes through LandManager's
//    is_tile_owned()/is_area_owned(), so locked land remains locked until bought.
// 3. Pedestrian lane navigation is wrapped by the Park fence barrier graph, so
//    closed fence segments block crossings while open gates remain walkable.
// 4. Runtime SaveManager is replaced by its Park-fence-aware drop-in wrapper,
//    preserving the existing city JSON while persisting the fence network next
//    to the same save slot.
// 5. Service-price clicks use each definition's authored price step. A direct
//    price edit on a ticketed ride is mirrored into its linked booth before the
//    economy refresh, keeping the booth authoritative without making the ride
//    panel appear frozen.
// 6. Ferris-wheel audio is frame-synchronized with both ride activity and the
//    canonical visible viewport. An active wheel is audible only while its
//    logical footprint intersects the current camera view.
// 7. Runtime rendering builds a conservative camera-visible working set before
//    terrain traversal, road/building sorting and per-tile geometry.  The
//    canonical MapRenderer remains unchanged for Map Forge and render-contract
//    verification.
// 8. Z/X become production camera-rotation controls whenever no building is
//    being placed. The view turns in exact 90-degree steps across all four
//    cardinal facings while preserving the logical point at screen centre.
// 9. GameplayUi is wrapped by two top-bar camera buttons that emit the same
//    rotate actions. Their final presentation is supplied by CH Blender RGBA
//    assets, with hover/press animation and a safe fallback before promotion.
// 10. A pedestrian that finishes a route on an activity-building entrance is
//     hidden for a short interior visit while the building activity counter is
//     held. This is the first CH_VISITOR_MVP_V1 enter/leave vertical slice.
// 11. Building visits use the live pedestrian surface graph and a two-tile
//     front-door approach. The final visible hop is always toward the authored
//     front door; side/back entry and off-surface shortcuts are rejected.

#include "audio_manager.h"
#include "building_system.h"
#include "building_visit_runtime.h"
#include "land_system.h"
#include "park_fence_runtime.h"
#include "park_fence_save_manager.h"
#include "src/runtime_view_state.h"
#include "src/runtime_map_renderer.h"
#include "src/camera_rotation_ui.h"

#include <algorithm>

namespace ch {

// main_runtime_impl.cpp expresses a UI click as `current_price + delta`, where
// delta is +1 or -1.  ServicePrice may represent cents and carries its own
// authored click step (for example 25 cents). Resolve that intent here before
// the absolute-price setter receives it.
[[nodiscard]] inline std::int64_t operator+(const ServicePrice& price,
                                            const std::int64_t delta) noexcept {
    const std::int64_t step = price.step_minor_units > 0 ? price.step_minor_units : 1;
    if (delta == 1) return price.minor_units + step;
    if (delta == -1) return price.minor_units - step;
    return price.minor_units + delta;
}

}  // namespace ch

// Ticket booths remain the canonical owner of a Park ride's ticket price.  The
// ride panel may still expose the shared value for convenience; if the player
// changes it there, mirror the resulting (already clamped) price into the linked
// booth before CityEconomy synchronizes booth -> ride.
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

// Audio visibility follows the same canonical camera snapshot populated by the
// projection layer.  No independent audio camera or distance heuristic exists.
// The footprint is projected as the same isometric diamond used by the world;
// when that projected envelope no longer intersects the viewport, the ride is
// considered outside the visible set and must be silent.
[[nodiscard]] inline bool ch_ferris_wheel_visible_in_current_view(
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
        if (definition != nullptr && ch_ferris_wheel_visible_in_current_view(instance, *definition)) {
            return true;
        }
    }
    return false;
}

inline void ch_sync_ferris_wheel_audio_visibility(
    AudioManager& audio, const BuildingManager& buildings, const BuildingCatalog& catalog) {
    (void)audio.set_looping(
        SoundEvent::ferris_wheel_running,
        ch_ferris_wheel_should_be_audible(buildings, catalog));
}

// main_runtime_impl.cpp has two geometry-only parcels() reads: one for camera
// clamping and one for cursor roaming.  Redirect those reads to the complete
// world geometry.  land_system.h is included above so its public declaration is
// not rewritten by this compatibility macro.
#define parcels() world_parcels()

// These headers are already included above, so the substitutions apply only to
// runtime call sites/declarations inside main_runtime_impl.cpp, never to the
// canonical class declarations themselves.
#define PedestrianLaneNavigationNetwork ParkFencePedestrianNavigationNetwork
#define SaveManager ParkFenceSaveManager

// The runtime has one player-facing service-price setter call. Preserve that
// existing action path, then synchronize a linked ticket booth when the edited
// instance is a Park ride. Ordinary shops simply return true from the helper.
#define set_service_price(instance_id, definition, service_price) \
    set_service_price((instance_id), (definition), (service_price)) && \
    ch_sync_service_price_after_ui_edit(buildings, catalog, (instance_id), (definition))

// `mobile_render_entities()` is evaluated in the normal frame path immediately
// before world entities are rendered (and may also be queried by debug UI).
// The visit bridge consumes the exact same road/path/floor surface contract as
// normal pedestrian routing. It may start autonomous visits only while the
// production automatic-pedestrian mode is active.
#define mobile_render_entities() \
    ([&]() { \
        ch_sync_ferris_wheel_audio_visibility(audio, buildings, catalog); \
        const PedestrianSurfaceNavigationNetwork ch_visit_surfaces{roads, sidewalks}; \
        ch::building_visit_runtime::sync( \
            pedestrians, buildings, catalog, ch_visit_surfaces, \
            simulation_clock.speed() != SimulationSpeed::paused, automatic_pedestrian); \
        auto ch_mobile_entities = mobile_render_entities(); \
        ch::building_visit_runtime::filter_inside_pedestrians(ch_mobile_entities, pedestrians); \
        return ch_mobile_entities; \
    }())

// `play_sound` is a local lambda inside the implementation.  A function-like
// macro is used here only around its call sites; its declaration is untouched.
#define play_sound(sound_event) \
    ([&]() { \
        const SoundEvent ch_sound_event = (sound_event); \
        if (ch_sound_event == SoundEvent::building_place) { \
            placement_definition_id.clear(); \
        } \
        return play_sound(ch_sound_event); \
    }())

// The implementation already has one placement-rotation lambda and complete
// four-way projection/render support. Function-like macro expansion leaves that
// lambda declaration untouched, but intercepts its call sites. During ordinary
// gameplay Z/X now rotate the camera; while placing a rotatable building they
// retain their original building-rotation behaviour.
//
// Camera pan is screen-space. Before changing the facing, recover the exact
// logical world point under the viewport centre, rotate that point into the new
// camera basis, then solve the new pan that puts it back at the same centre.
// This prevents the city from jumping around the screen on every 90-degree turn.
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

// Redirect only runtime call sites. These class declarations are already parsed
// above, so canonical Map Forge rendering and the established GameplayUi remain
// untouched outside the executable translation unit.
#define MapRenderer RuntimeMapRenderer
#define GameplayUi ChGameplayUi

#include "main_runtime_impl.cpp"

#undef GameplayUi
#undef MapRenderer
#undef rotate_placement
#undef play_sound
#undef mobile_render_entities
#undef set_service_price
#undef SaveManager
#undef PedestrianLaneNavigationNetwork
#undef parcels
