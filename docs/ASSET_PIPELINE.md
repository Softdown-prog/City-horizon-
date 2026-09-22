# Asset Pipeline — City Horizon

This document describes the production path for visual assets. It is intentionally repository-first so a new agent can continue the project without relying on chat history.

## Goal

City Horizon ships **2D PNG sprites**. Blender is an offline authoring/render tool used to keep scale, perspective, lighting and rotation consistent across the game.

The current style contract is `CH_STYLIZED_PRERENDER_V1`. The target is a readable stylized pre-rendered city-builder look. Classic Tycoon games guide readability, miniature composition and nostalgia; they are not a requirement to literally reproduce early-2000s rendering limitations.

## Shared frozen contracts

- camera: `CH_CAMERA_V1`
- studio: `CH_TYCOON_STUDIO_V1`
- bake: `TYCOON_ASSET_BAKE_V1`
- style: `CH_STYLIZED_PRERENDER_V1`
- optional color mask: `CH_COLOR_MASK_V1`
- grid reference: 128×64, 2:1
- camera: orthographic, 45° yaw, 30° elevation
- directions: SOUTH / EAST / WEST / NORTH
- production Blender in Actions: 4.2.3 LTS

The camera and lights stay fixed. The asset root rotates.

## Pick the authoring path first

There are two normal paths into the same Blender/bake pipeline.

### Path A — design from zero with procedural structure

Use a compact procedural recipe/plan when the user explicitly asks to design something new from scratch and a procedural representation makes authoring easier or more reproducible.

Typical good candidates:
- building families with reusable grammar;
- trees/vegetation recipes;
- carousels and Ferris wheels;
- modular attraction pieces;
- roller-coaster track families;
- repeatable props or architecture.

```text
1. Design intent
   ↓
2. Compact procedural recipe / plan
   ↓
3. Deterministic expander if needed
   ↓
4. TYCOON_ASSET_SOURCE_V1
   ↓
5. Blender headless / frozen studio
   ↓
6. four-direction source renders
   ↓
7. postprocess/downsample
   ↓
8. review artifacts
   ↓
9. human approval
   ↓
10. classification/runtime promotion
```

Procedural authoring is a convenience and reproducibility tool. **Do not insert a procedural stage merely because it exists.**

### Path B — usable source already exists

If a `.blend`, imported mesh or other usable geometry source already exists, use/import that source directly in the canonical Blender pipeline. Do not recreate it procedurally unless there is a concrete reason.

The same frozen camera, lights, four rotations, post-process and review rules still apply.

A raster image can be used as an art/reference target, but one image is not guaranteed to contain enough information to reconstruct perfect hidden 3D geometry. Do not promise automatic exact reconstruction from a single PNG.

## Blender bake

`tools/tycoon_photo_studio/build_scene.py` is the canonical Blender baker for compatible sources.

The studio remains frozen:
- orthographic projection;
- 45° yaw;
- 30° elevation;
- fixed world lighting;
- consistent scale relative to the 128×64 runtime grid;
- transparent RGBA output;
- SOUTH/EAST/WEST/NORTH produced by rotating the asset root.

Do not move the camera or lights independently for each direction.

## Optional building/prop color masks

Recolorable assets may opt into `CH_COLOR_MASK_V1`. Do not generate a mask for every asset by default.

A mask-enabled `TYCOON_ASSET_SOURCE_V1` declares semantic channels such as:

```json
"colorMask": {
  "contract": "CH_COLOR_MASK_V1",
  "enabled": true,
  "channels": {
    "R": "wall",
    "G": "roof",
    "B": "trim"
  },
  "alpha": "coverage"
}
```

Recolorable source materials then declare `maskRole` using one of those semantic names. Imported `.blend` materials may instead carry the custom property `ch_color_mask_role`; a whole imported part may use `maskRole` as a coarse override.

V1 intentionally reserves alpha for object coverage rather than using it as a fourth tint group. This keeps the packed PNG inspectable and avoids conflating transparency with recolor data. If more than three independently tintable regions are genuinely required, define a later contract rather than silently changing V1.

When enabled, Blender emits an aligned mask source for every canonical direction and post-process emits gameplay-scale mask PNGs plus a four-view and review sheet. Masks share the color sprite's camera, AssetRoot rotation, frame resolution and pivot.

Mask data must not receive lighting, AO, cast shadows, palette reduction, dithering, edge outlines or background/halo removal. Unassigned visible surfaces stay RGB black and are therefore not recolored.

Use masks where variation is valuable: houses, shops, apartment blocks, warehouses and modular buildings. Avoid automatic masks for landmarks, unique hero buildings, glass-heavy assets, terrain and authored identity colors unless the design explicitly requires recoloring.

Authoring support does not imply runtime tinting is already implemented. The SDL runtime must separately sample `CH_COLOR_MASK_V1` and combine selected colors with the original sprite while preserving its lighting/value structure.

Agent instructions: `tools/ch_blender/COLOR_MASK_AGENTS.md`.

## Why the final asset is reduced

The source bake may be supersampled and more detailed than the final game sprite. `postprocess.py` downsamples to gameplay scale.

This is intentional. The project currently favors a restrained, slightly pixel-like pre-rendered result because it integrates better with a 2D isometric world and suppresses an overly glossy/plastic 3D-render appearance.

Do not increase source/detail scale just to make an isolated Blender image look more impressive if the current downsampled result reads better in gameplay.

## Post-processing

`postprocess.py` is part of the production path, not an optional external cleanup stage. It already handles relevant work including:
- runtime-scale downsample;
- RGBA/alpha preservation;
- edge cleanup;
- shadow composition;
- shared pivot packaging;
- fixed four-view sheet;
- trimmed atlas generation;
- review/context boards;
- opt-in `CH_COLOR_MASK_V1` downsample/review packaging.

Therefore, do **not** automatically send every Blender render through a second background remover, halo remover or manual cropper. The Blender color pass is already intended to use a transparent background. Add an extra cleanup step only when inspection of the final PNG shows an actual defect.

## Review through GitHub Actions

For repository-driven asset production, Actions may perform the Blender bake and package review artifacts.

Expected building-like outputs commonly include:
- `<asset>_south.png`
- `<asset>_east.png`
- `<asset>_west.png`
- `<asset>_north.png`
- `<asset>_4view.png`
- `<asset>_review.png`
- `<asset>_4dir_context.png`
- atlas + manifest

Mask-enabled assets additionally include:
- `<asset>_<direction>_mask.png`
- `<asset>_mask_4view.png`
- `<asset>_mask_review.png`

When a visual asset is generated through Actions, surface the review/capture artifact so the human can inspect the result before promotion.

A green workflow means **execution succeeded**, not that the art was approved.

## Gameplay-scale gate

Every asset must be evaluated where the player will actually see it.

Review at minimum:
- all four individual direction PNGs;
- 4-view/review board;
- context board;
- footprint and pivot consistency;
- alpha/edge quality on representative backgrounds;
- color-mask review when the asset opts into `CH_COLOR_MASK_V1`;
- MapForge/runtime placement when integration matters.

Once an asset is approved, freeze it. Do not reopen it for speculative polishing unless a concrete in-game problem appears.

## Classification after approval

After a visual asset passes review, use the first-party `CityHorizonAssetEditor` in `C++/MapForge2/` to classify/control its game metadata rather than inventing another classifier.

The editor already supports categories such as building, attraction, service, scenery, tree, prop, path, character and UI, plus footprint, costs, upkeep/income, `requiresPath`, tags, four canonical PNGs, grid preview and `.chasset` persistence.

Typical flow:

```text
approved four-direction PNGs
  -> CityHorizonAssetEditor
  -> category / ID / footprint / gameplay metadata
  -> runtime-facing asset organization
  -> MapForge/runtime validation
```

## MapForge and street alignment

MapForge2 is the integration environment for testing assets on the actual isometric grid.

Buildings must sit correctly on their footprint. When the intended design is street-facing, the building/sidewalk relationship should be visually flush and should not leave unexplained grass strips between the road/sidewalk and the building.

Ground tiles and paths must be tested as connected/repeated systems, not only as isolated PNGs.

## Vegetation

Trees may use deterministic procedural recipes and dedicated generators. Solve silhouette, gameplay read and material language before scaling a family.

Useful files include:
- `build_classic_tree.py`
- `generate_fractal_tree_asset.py`
- tree recipes under `tools/tycoon_photo_studio/assets/`
- `stylize_foliage_2d.py`

Vegetation still ends in the same frozen four-direction studio/review flow.

## Materials

Procedural material recipes live in `tycoon_material_library.py`. Typical recipes include:
- plaster
- brick
- concrete
- timber
- stone
- metal_panel
- glass
- solid fallback

Material detail must survive final gameplay scale. Avoid high-frequency noise, photoreal microdetail and plastic CG response that only looks good in close-up.

## Attractions later

Complex attractions do not block the first playable city.

When implemented, procedural structural descriptions are appropriate for attractions where geometry and gameplay benefit from sharing a definition. Examples include carousel radial structure, Ferris-wheel radius/cabin count and modular roller-coaster track pieces.

Those definitions should still feed the same Blender → four-direction bake → post-process → classification/runtime pipeline rather than creating a separate visual pipeline.

## Legacy assets

Old/current runtime sprites are not visual references for new production. They may remain temporarily for functionality, but new production art should derive from the current pipeline and approved current-pipeline examples.

## Production stop rule

Do not generate dozens of variants before one exemplar has been visually accepted.

Likewise, do not keep redesigning an accepted exemplar indefinitely. Once it is good enough in gameplay context, promote it and move on.
