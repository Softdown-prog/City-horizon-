// CITY HORIZON runtime entry point.
//
// The implementation remains in main_runtime_impl.cpp.  The narrow wrapper
// below makes building placement one-shot: after a successful building is
// placed and its BuildingPlace sound is emitted, the active placement id is
// cleared before the next frame.  This prevents the translucent placement
// preview from continuing to follow the cursor after the real building has
// already been created.
//
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
