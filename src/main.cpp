// CITY HORIZON runtime entry point.
//
// The implementation remains in main_runtime_impl.cpp.  This narrow wrapper
// carries five compatibility fixes without duplicating the runtime loop:
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

#include "building_system.h"
#include "land_system.h"
#include "park_fence_runtime.h"
#include "park_fence_save_manager.h"

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

#include "main_runtime_impl.cpp"

#undef play_sound
#undef set_service_price
#undef SaveManager
#undef PedestrianLaneNavigationNetwork
#undef parcels
