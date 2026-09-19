# City Horizon Tycoon Asset Baker V1

Status: **golden static asset approved; studio recipe frozen as V1**

The City Horizon production path is now a deterministic asset baker rather than a one-off POC. One declarative asset source is rendered by Blender headless through one frozen studio preset and exported as four coherent 2D game rotations.

## Canonical four-direction rule

`CH_CAMERA_V1` and world lighting never rotate. The asset root rotates around world origin:

| Direction | Quarter turns | Asset Z rotation |
| --- | ---: | ---: |
| South | 0 | 0° |
| East | 1 | 90° |
| West | 3 | 270° |
| North | 2 | 180° |

Output order remains `south, east, west, north`, matching the existing `BuildingExportPipeline` / `BuildingComposer` contract.

## Frozen studio

`tools/tycoon_photo_studio/studio_presets/ch_tycoon_studio_v1.json` is the visual authority for this version. It owns camera, Cycles settings, lighting, shadow receiver, source/final resolution and post-processing values. New assets must reuse this preset unless a new studio version is explicitly reviewed and approved.

Current V1 recipe preserves the approved kiosk result:

- Blender 4.2.3 LTS;
- Cycles CPU, 24 samples + denoising;
- orthographic `CH_CAMERA_V1`, yaw 45°, elevation 30°, ortho scale 5.6;
- 1024×1024 source render → 256×256 final frame;
- fixed warm NW key + cool SE fill;
- Cycles shadow catcher;
- 128-color reduction;
- Floyd-Steinberg dithering;
- candidate post-process variant 03.

## Generic asset source

Assets are no longer hardcoded into `build_scene.py`. A source JSON uses `TYCOON_ASSET_SOURCE_V1` and declares:

- `assetId` and `assetType`;
- footprint / occupied cells;
- requested studio preset;
- materials;
- source parts.

The first source is `tools/tycoon_photo_studio/assets/park_kiosk_1x1.json`. The current declarative source supports boxes, pyramid roofs and UV spheres. The baker is intentionally structured so richer source modes can be added later without changing camera/export contracts.

## Golden Asset #1

`park_kiosk_1x1` is the approved Golden Asset #1. Its approved four-direction result is captured as a compact 16×16 RGBA perceptual fingerprint at:

`tools/tycoon_photo_studio/golden/park_kiosk_1x1_golden.json`

CI re-bakes the kiosk from the generic source config and compares all four final directions against that approved fingerprint with a small numeric tolerance. The fingerprint also records the original PNG SHA-256 values for diagnostics. This is a regression guard, not a replacement for human review of new assets.

## Export package

Each static asset emits:

- `<asset>_south.png`
- `<asset>_east.png`
- `<asset>_west.png`
- `<asset>_north.png`
- `<asset>_4view.png`
- `<asset>_atlas.png`
- `<asset>_manifest.json`
- `<asset>_review.png`
- `<asset>_style_matrix.png`
- `<asset>_4dir_context.png`

The pivot is always the projection of world origin `(0,0,0)`, never the alpha bounds, so asymmetric assets remain planted on the same tile through rotation.

## Reuse from MapForge2

The baker keeps the useful foundation already built:

- `CH_CAMERA_V1` and `CH_GRID_V1`;
- four-view direction naming/order;
- footprint and tile metadata;
- pivot/anchor concepts;
- PNG + JSON packaging;
- atlas/spritesheet concepts;
- Animation Core as the future `4 directions × N frames` extension;
- Asset Browser and validation systems as future consumers/orchestrators.

Blender is now the production pixel source. QPainter/procedural renderers remain useful for debug, composition and metadata, not as the final visual authority for this pipeline.

## Next gate

Do not mass-produce the library yet. The next validation is a second, visually different static asset using the same frozen studio. If it still reads as the same game, the baker has demonstrated cross-asset coherence rather than success on one kiosk only.
