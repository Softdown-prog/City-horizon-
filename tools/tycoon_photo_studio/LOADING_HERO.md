# Loading hero art — CH Blender

City Horizon loading-screen backgrounds are authored as deterministic offline
presentation art. The runtime still receives a static 2D PNG; Blender is never a
runtime dependency.

## Current candidate

`CITY_HORIZON_LOADING_HERO_V1` is implemented by:

- `assets/loading_hero_city_park_01.loading.json`
- `build_loading_hero_guarded.py`
- CH Blender jobs under `tools/ch_blender/jobs/ui.loading_hero_city_park.*.job.json`

The first composition reuses current project systems where practical: the Ferris
wheel builder, the shared attraction ticket entry, current small-commercial
recipes, the frozen studio/camera/light language, and deterministic procedural
scenery authored inside the loading composition.

## Presentation contract

- target aspect ratio: 16:9;
- proxy review: 1280x720;
- final candidate: 2560x1440;
- the CH camera yaw/elevation and studio lighting remain the project source of
  perspective and material language;
- framing is loading-screen presentation only and must not be treated as a
  gameplay-camera contract change;
- the upper-left title area and lower progress-bar band are declared as safe
  areas in the recipe;
- logo, loading text, progress and hints are not baked into the background;
- no gameplay HUD or visible placement grid belongs in this art.

## Quality gate

The same guarded rule applies as other agent-authored Blender work:

`preflight -> 16:9 SOUTH proxy -> explicit human visual review -> final PNG`

A passing workflow only proves the scene/package contract. It does not approve
the artwork. Do not promote the generated PNG into `assets/ui` or wire it into
the SDL loading screen until the proxy has been visually reviewed.

The final stage requires the exact SHA-256 of the reviewed proxy through the
standard `CH_PROXY_APPROVAL_V1` gate.
