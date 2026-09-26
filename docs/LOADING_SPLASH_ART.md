# City Horizon loading splash art

The loading-screen background is **key art / splash art**, not a gameplay asset, not a MapForge scene capture, and not a promise that every visible object exists in the runtime.

## Contract

Current direction: `CH_LOADING_SPLASH_ART_V1`.

A loading illustration MAY deliberately ignore gameplay-production constraints when doing so improves the image. In particular it may use:

- perspective, frontal, isometric, oblique or otherwise art-directed cameras;
- camera rotation, lens exaggeration and non-gameplay framing;
- cartoon, painterly, miniature, graphic, exaggerated or anti-realistic proportions;
- buildings, vehicles, attractions, scenery, weather and skyline elements that do not exist as runtime assets;
- unique geometry authored only for the illustration;
- larger-than-life landmarks and impossible staging;
- frame sequences, camera motion, parallax or other loading-only animation;
- lighting and color grading that are intentionally different from gameplay.

It MUST NOT be rejected because it violates `CH_CAMERA_V1`, `CH_GRID_V1`, gameplay footprints, canonical four-direction asset rotation, current runtime asset inventory, or MapForge placement rules. Those contracts apply to gameplay assets, not to key art.

## What remains constrained

The splash still has production requirements:

- fit the target screen aspect ratio cleanly;
- preserve UI-safe regions for logo, loading text and progress indicators;
- remain readable at the actual loading-screen size;
- avoid copyrighted third-party designs or direct copies of another game's artwork;
- be reproducible from repository-owned source/scripts when generated procedurally;
- render to ordinary 2D image/frame outputs consumed by SDL.

## Pipeline

For procedural 3D splash art the preferred path is intentionally different from the gameplay asset pipeline:

```text
art direction / composition recipe
  -> loading-only Blender scene
  -> artistic camera + lighting + original geometry
  -> 16:9 review render
  -> human art review
  -> final 2D PNG or frame sequence
  -> SDL loading-screen presentation
```

Do **not** route this through the gameplay asset preflight merely to satisfy `CH_CAMERA_V1` or footprint gates. A normal `CH_BLENDER_AGENT_JOB_V1` `blender_script` job is appropriate because this output is presentation art rather than an authored gameplay asset.

## Superseded experiment

`CITY_HORIZON_LOADING_HERO_V1` / `build_loading_hero_guarded.py` proved that the repository can assemble and render a loading image, but its diorama/map-like composition is only a technical experiment. It is not the visual target for production loading art.
