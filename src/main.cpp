// CITY HORIZON runtime entry point.
//
// The implementation remains in main_runtime_impl.cpp.  This narrow wrapper
// carries three compatibility fixes without duplicating the runtime loop:
//
// 1. Building placement is one-shot: after a successful building is placed
//    and its BuildingPlace sound is emitted, the active placement id is cleared
//    before the next frame.
// 2. Camera/cursor world bounds use every generated parcel, not only purchased
//    parcels.  Placement/economy ownership still goes through LandManager's
//    is_tile_owned()/is_area_owned(), so locked land remains locked until bought.
// 3. Pedestrian lane navigation is wrapped by the Park fence barrier graph, so
//    closed fence segments block crossings while open gates remain walkable.

#include "land_system.h"
#include "park_fence_runtime.h"

// main_runtime_impl.cpp has two geometry-only parcels() reads: one for camera
// clamping and one for cursor roaming.  Redirect those reads to the complete
// world geometry.  land_system.h is included above so its public declaration is
// not rewritten by this compatibility macro.
#define parcels() world_parcels()

// The runtime currently constructs PedestrianLaneNavigationNetwork inline at
// its call sites. Redirect that exact type to the fence-aware drop-in wrapper
// without changing road topology or vehicle routing.
#define PedestrianLaneNavigationNetwork ParkFencePedestrianNavigationNetwork

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
#undef PedestrianLaneNavigationNetwork
#undef parcels
