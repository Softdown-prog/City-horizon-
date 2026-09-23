# CH_BUILDING_ACTIVITY_OVERLAY_V1

Status: runtime contract v1.

This contract defines transparent RGBA layers for temporary building activity:
window/light glow, steam, door motion, machinery, signs, or similar small effects.
The base building remains unchanged. Activity overlays are not color masks.

## Runtime order

1. Render the approved building sprite.
2. Apply normal building customization/state passes.
3. When `BuildingInstance::activity_count > 0`, render `activityOverlay`.
4. Continue with normal selection/debug presentation.

The activity counter is transient. Save restoration resets it to zero.

## Building definition

```json
"activityOverlay": {
  "contract": "CH_BUILDING_ACTIVITY_OVERLAY_V1",
  "enabled": true,
  "sprites": {
    "0": "assets/buildings/example/example_south_activity.png",
    "1": "assets/buildings/example/example_west_activity.png",
    "2": "assets/buildings/example/example_north_activity.png",
    "3": "assets/buildings/example/example_east_activity.png"
  },
  "animation": {
    "layout": "horizontal",
    "frameCount": 4,
    "frameDurationMs": 160,
    "playback": "loop"
  }
}
```

`animation` is optional. A static overlay is the preferred form for a simple
state such as an illuminated window. Animated overlays use the same horizontal
spritesheet timing model already used by building animations (`loop` or
`ambient_once`).

## Art rules

- PNG RGBA with transparent background.
- Draw only the temporary effect; do not duplicate the whole building.
- Provide one overlay for every rotation supported by the building.
- Each overlay frame must use the same canvas and ground anchor as the matching
  base-building frame. Runtime never mirrors, rotates, or invents alignment.
- All frames of an animated overlay use the same canvas dimensions.
- `CH_COLOR_MASK_V1` remains reserved for permanent wall/roof recoloring.

## Gameplay trigger

`BuildingManager::begin_activity(instance_id)` increments the per-instance
activity counter. `BuildingManager::end_activity(instance_id)` decrements it.
This means overlapping visitors are safe: the effect is removed only when the
last activity source leaves.

The renderer does not know why the building is active. A pedestrian/customer
system, production system, scripted event, or another gameplay system can use
the same trigger without coupling itself to rendering.
