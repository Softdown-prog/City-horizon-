# Asset Pipeline — City Horizon

This document describes the production path for visual assets. It is intentionally procedural and repository-first so a new agent can continue the project without relying on chat history.

## Goal

City Horizon ships 2D PNG sprites, but they are generated from controlled procedural/3D sources so scale, perspective, lighting and rotation remain consistent across the entire game.

The current style contract is `CH_STYLIZED_PRERENDER_V1`. It defines a stylized pre-rendered look optimized for city-builder readability. It does not require literal emulation of early-2000s rendering limitations.

## Shared frozen contracts

- camera: `CH_CAMERA_V1`
- studio: `CH_TYCOON_STUDIO_V1`
- bake: `TYCOON_ASSET_BAKE_V1`
- style: `CH_STYLIZED_PRERENDER_V1`
- grid reference: 128×64, 2:1
- camera: orthographic, 45° yaw, 30° elevation
- directions: SOUTH / EAST / WEST / NORTH

## Building pipeline

New buildings should normally be designed before Blender as a compact procedural plan.

```text
1. Design intent
   ↓
2. Procedural recipe / plan
   ↓
3. Pre-Blender expander
   ↓
4. TYCOON_ASSET_SOURCE_V1
   ↓
5. build_scene.py (Blender headless)
   ↓
6. source color + shadow passes for 4 rotations
   ↓
7. postprocess.py
   ↓
8. building stylizer
   ↓
9. SOUTH/EAST/WEST/NORTH + 4view/review/context
   ↓
10. Human gameplay-scale approval
   ↓
11. Runtime promotion
```

### Why a pre-Blender plan exists

The plan keeps architectural intent auditable. Agents should be able to answer questions such as "why is this porch here?", "how wide is this window family?" or "what detail level is intended?" without reverse-engineering a large Blender scene.

The expander resolves that plan into simple canonical primitives. Blender executes the geometry/material instructions and renders them under the frozen studio.

### First canonical residential example

Plan:
`tools/tycoon_photo_studio/assets/suburban_house_simple_2x2_01.house.json`

Expander:
`tools/tycoon_photo_studio/generate_suburban_house_asset.py`

Workflow:
`.github/workflows/tycoon-suburban-house-bake.yml`

The plan uses contract `CITY_HORIZON_SUBURBAN_HOUSE_V1` and expands into `TYCOON_ASSET_SOURCE_V1` before Blender runs.

## Vegetation pipeline

Trees use deterministic procedural tree recipes and a dedicated generator. The approved broadleaf work demonstrates the desired rule: solve silhouette, gameplay read and material language before producing large families.

Important files include:
- `build_classic_tree.py`
- `generate_fractal_tree_asset.py`
- tree recipes under `tools/tycoon_photo_studio/assets/`
- `stylize_foliage_2d.py`

Tree recipes still end in the same four-direction studio and review workflow.

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

Material detail should survive final gameplay scale. Avoid expensive/high-frequency noise that becomes invisible or turns into pixel grit after downsampling.

## Rotations and lighting

The camera and lights stay fixed. The asset root rotates for SOUTH/EAST/WEST/NORTH. This ensures all assets belong to the same world lighting and projection.

Do not render each direction with a different camera or move lights to make a face prettier.

## Post-processing

Post-processing exists to support readability and stylization, not to fake a historical GPU.

Useful operations can include:
- controlled tonal compression;
- palette discipline;
- alpha cleanup;
- restrained edge reinforcement;
- material-specific conventions;
- shadow simplification.

Do not globally destroy useful material information just to make a sprite look "older".

## Gameplay-scale gate

Every asset must be evaluated at the scale where the player sees it. Close-up screenshots are diagnostic only.

Review at minimum:
- each direction PNG;
- 4-view board;
- context board;
- footprint/pivot consistency;
- MapForge/runtime placement when integration matters.

A green workflow is an execution gate, not an art approval gate.

## Legacy assets

Old/current runtime sprites are not visual references for new production. They can remain temporarily for functionality, but new assets must derive their appearance from the current procedural pipeline and approved new-pipeline examples.

## Adding a new procedural building family

When a new building category is introduced:

1. define a small human-readable plan contract;
2. create a deterministic expander into `TYCOON_ASSET_SOURCE_V1`;
3. use procedural material recipes;
4. add a focused Actions workflow;
5. export all four directions and review boards;
6. approve one exemplar before scaling the family;
7. document any durable design/technical rule in this file or `AGENTS.md`.

Do not jump directly into producing dozens of variants before the first exemplar is visually accepted.
