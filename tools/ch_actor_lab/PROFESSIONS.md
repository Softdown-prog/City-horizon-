# CH Actor professions

The approved `ch_actor_green_01` walk cycle is the shared human locomotion base. Professions must not fork or redraw that locomotion unless a future animation review explicitly replaces the base actor.

## Cleaner pilot

The first automatic production CH Actor is assigned `PedestrianProfession::cleaner`.

- Uniform: existing runtime clothing mask, with a fixed teal jacket and dark navy trousers.
- Equipment: `ch_actor_broom_01`, rendered as a second transparent 48x64 mobile layer with the exact same ground anchor and animation frame index as the actor.
- Camera rotation: the broom has its own four-direction animation set, so `camera_relative_mobile_entity()` resolves the correct visual direction exactly like the actor.
- Rain: the broom is hidden while raining and the existing umbrella remains active, avoiding two hand-held props at once.
- Visiting/resting: the broom is hidden while the pedestrian is visiting; resting pedestrians are already not rendered.

The broom overlays live under `assets/characters/ch_actor_green_01/equipment/broom/frames/` and are reproducible with:

```bash
python tools/ch_actor_lab/build_profession_equipment.py
```

The tool derives hand positions from the same `CH_CAMERA_V1` projection and arm kinematics used by `software_render.py`; it does not modify the approved actor PNGs.

## Extension rule

Future professions should reuse the same pattern:

1. Keep `ch_actor_green_01` as the locomotion/body layer.
2. Select a profession-specific clothing palette through the existing mask.
3. Add frame-aligned equipment as a separate animation set when needed.
4. Assign the profession in simulation state with `PedestrianSystem::set_profession()`.

This keeps walking, foot anchor, pathfinding and camera behavior independent from jobs such as gardener, mechanic, electrician or maintenance worker.
