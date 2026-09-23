# CH_SPRITE_WORKSHOP_EDITOR_LINK_V1

Status: ACTIVE

## Purpose

`CityHorizonAssetEditor` can launch `CityHorizonSpriteWorkshop` directly for the direction currently selected in the canonical preview: SOUTH, EAST, WEST or NORTH.

The link does not create a new asset format. It reads the active `CH_ASSET_DOCUMENT_V1` / `.chasset` state and passes an inspection session to the workshop.

## Launch behavior

The `4 Directions` tab exposes:

```text
Edit selected direction in Sprite Workshop
```

The launcher passes:

- the selected direction PNG;
- the document normalized anchor;
- base horizontal animation frame count and frame duration when metadata is present;
- direction-specific animation overrides from `directionAnimations` when present;
- the matching `CH_BUILDING_ACTIVITY_OVERLAY_V1` PNG when metadata is present;
- activity-overlay frame count and duration independently from the base animation;
- asset display name and direction label for workshop context.

Relative PNG paths are resolved against the `.chasset` file directory.

## Metadata compatibility

Base animation may be authored as:

```json
"animation": {
  "frameCount": 12,
  "frameDurationMs": 125
}
```

A direction-specific override may be authored as:

```json
"directionAnimations": {
  "south": { "frameCount": 12, "frameDurationMs": 125 }
}
```

Activity overlay follows the runtime contract shape and accepts either direction names or runtime rotation indexes in `sprites`:

```json
"activityOverlay": {
  "contract": "CH_BUILDING_ACTIVITY_OVERLAY_V1",
  "sprites": {
    "south": "south_activity.png",
    "west": "west_activity.png",
    "north": "north_activity.png",
    "east": "east_activity.png"
  },
  "animation": {
    "frameCount": 4,
    "frameDurationMs": 160
  }
}
```

The launcher also understands runtime-style numeric sprite keys `0/1/2/3` using the canonical SOUTH/WEST/NORTH/EAST mapping.

## Workshop V1.1 session model

Base and activity overlay now have independent:

- horizontal frame counts;
- current frame selection;
- frame durations;
- animation timers.

This is required for the common City Horizon case where a building is static while only an overlay object animates, for example a rotating popsicle sign or barber pole.

The workshop remains a QA/inspection tool. It does not silently rewrite the `.chasset` or source PNGs.
