# Render output classes

City Horizon keeps one visual language but now has two explicit render-output pipelines. This avoids forcing every asset through the same 256×256 runtime class.

## 1. Compact 256 — default

Use `compact_256` for normal buildings, props, scenery and assets whose silhouette/material read remains clean after downsample.

- source render: 1024×1024
- final output: 256×256
- preset: `tools/tycoon_photo_studio/render_pipelines/compact_256/studio.json`

This preserves the restrained pre-rendered look already used by the project and remains the default because it is cheaper in render time, storage, atlas size and runtime memory.

## 2. Large asset — landmarks and fine structures

Use `large_asset` when the compact path visibly destroys detail or when the object is genuinely large in the game world: major attractions, large/tall buildings, skyline landmarks, large civic buildings or assets with thin open structure such as spokes, trusses and railings.

Two sizes exist:

- 1024 final: source 2048×2048 -> final 1024×1024. This is the normal large-asset choice.
- 2048 final: source 4096×4096 -> final 2048×2048. This is exceptional and must be justified by gameplay-scale inspection.

Presets:

- `tools/tycoon_photo_studio/render_pipelines/large_asset/studio_1024.json`
- `tools/tycoon_photo_studio/render_pipelines/large_asset/studio_2048.json`

## What does not change

Both pipelines use the same City Horizon visual contracts:

- `CH_CAMERA_V1`
- `CH_TYCOON_STUDIO_V1`
- `CH_STYLIZED_PRERENDER_V1`
- `TYCOON_ASSET_BAKE_V1`
- transparent RGBA
- SOUTH / EAST / WEST / NORTH
- fixed camera and fixed lighting; rotate `AssetRoot`, not camera/lights

The larger pipeline is a resolution/output-class decision, not a different art style.

## Selection rule for agents

Start with `compact_256` unless the asset is obviously a landmark/large structure. Move to `large_asset_1024` when at least one of these is true:

- thin geometry becomes blurred or disappears at 256;
- the runtime scale requires a much larger on-screen sprite;
- a large/tall building loses window/facade structure at 256;
- MapForge/runtime comparison shows visible degradation caused by compact downsampling.

Use `large_asset_2048` only after a 1024 test is still insufficient. Do not upscale a 256 PNG. Re-render from the Blender/procedural source.

## Required validation

For large assets, always inspect the result in MapForge/runtime context before promotion. Check scale, pivot/footprint, lighting against terrain, alpha/halo, thin-structure readability and memory/atlas implications.

A green Blender workflow means the render executed; it does not approve the visual result.

## Machine-readable registry

`tools/tycoon_photo_studio/render_pipelines/ch_render_pipelines_v1.json`

This registry is also referenced from `tools/ch_blender/ch_blender_manifest.json` so agents can select the correct output class without relying on chat history.
