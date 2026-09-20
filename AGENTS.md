# AGENTS.md — City Horizon onboarding contract

This file is the fast onboarding document for AI agents and human contributors. Read it before changing the project.

## 1. What City Horizon is

City Horizon is a modern 2D isometric city-builder. The game runtime is SDL3/C++, but visual assets are primarily pre-rendered PNGs created by a deterministic procedural + Blender pipeline.

The project is developed by a solo programmer. Preserve continuity: prefer documenting durable decisions in the repository instead of relying on chat/session memory.

## 2. Current art direction

The authoritative style contract is `CH_STYLIZED_PRERENDER_V1`.

Target:
- stylized pre-rendered 2D sprites;
- strong gameplay readability;
- clean, coherent material separation;
- controlled detail and soft contact/shadow structure;
- one coherent visual universe across buildings, vegetation, roads, props and characters;
- modern tooling is allowed and expected.

Do not interpret classic Tycoon references as an instruction to reproduce year-2000 hardware limitations. Zoo Tycoon / RollerCoaster Tycoon are useful references for readability, miniature composition and information density only.

## 3. Camera and grid are non-negotiable

Use:
- `CH_CAMERA_V1`;
- orthographic/dimetric 2:1 projection;
- 45° yaw;
- 30° elevation;
- 128×64 reference tile;
- fixed world lighting from `CH_TYCOON_STUDIO_V1`;
- four canonical asset directions: SOUTH, EAST, WEST, NORTH.

Do not create top-down 90° art for this project. Do not silently change camera angle, tile ratio or light direction to make one asset look better.

## 4. New visual assets must use the pipeline

Do not use legacy/current runtime sprites as visual references. They may exist temporarily for functionality, but they are not the target art style.

Preferred building workflow:

```text
Design intent / procedural plan
  -> pre-Blender expander
  -> TYCOON_ASSET_SOURCE_V1
  -> build_scene.py in Blender headless
  -> TYCOON_ASSET_BAKE_V1
  -> postprocess.py
  -> category stylizer
  -> four PNG directions + review/context boards
  -> gameplay-scale human review
  -> runtime promotion
```

The design should be explicit before Blender when practical. A compact plan/recipe is preferred over hundreds of hand-authored primitive entries because it is easier to audit, vary and reproduce.

First residential example:
- `tools/tycoon_photo_studio/assets/suburban_house_simple_2x2_01.house.json`
- `tools/tycoon_photo_studio/generate_suburban_house_asset.py`
- `.github/workflows/tycoon-suburban-house-bake.yml`

Vegetation uses its own procedural tree contracts but ends in the same frozen studio/bake review flow.

## 5. Blender's role

Blender is a deterministic renderer/baker and geometry/material execution environment. It is not the place where undocumented art direction should live.

Keep design intent in recipes/contracts where possible. Blender receives canonical source, uses the frozen studio, rotates the asset root for four directions and exports source passes. The final game still uses 2D PNGs.

Pinned production Blender version in Actions is currently 4.2.3 LTS.

## 6. Material rules

The material library lives in `tools/tycoon_photo_studio/tycoon_material_library.py` and supports procedural recipes such as plaster, brick, concrete, timber, stone, metal panel and glass.

Use material response to communicate matter at gameplay scale. Avoid:
- plastic CG look;
- high-frequency texture noise that disappears at final size;
- photoreal microdetail;
- flat vector surfaces with no material read.

## 7. Visual approval rule

A successful CI workflow means the deterministic pipeline ran. It does NOT mean the asset is visually approved.

Always inspect:
- individual direction PNGs;
- 4-view board;
- context/review board;
- gameplay-scale result when available.

Do not claim an art target was achieved before inspecting the artifact.

## 8. Runtime / MapForge

MapForge2 is the project-side environment for map/editor testing and deterministic captures. Use neutral or controlled captures when judging new assets; legacy assets visible in a scene are functional context only and must not become visual references.

Buildings should align to the grid and sidewalks without unexplained grass gaps. Footprint, pivot and anchor correctness are part of the asset contract.

## 9. Engineering workflow

Prefer edits to canonical files. Do not create duplicate EXEs, backup copies or alternate source trees unless a task explicitly requires them.

The solo-development workflow intentionally avoids a full rebuild/ctest cycle after every tiny edit. Use focused validation while iterating. Full compile/test is appropriate for milestones, architecture changes or when there is a concrete reason to validate the whole system.

When changing a GitHub file, read the current version first. Avoid concurrent writes to the same path.

## 10. Source hierarchy

For visual work, trust in this order:
1. current contracts under `tools/tycoon_photo_studio/contracts/`;
2. approved procedural recipes/source configs;
3. frozen studio/camera configuration;
4. generated bake artifacts;
5. runtime integration.

Do not infer art direction from old asset folders.

## 11. Where to learn more

- project overview: `README.md`
- visual/runtime asset notes: `assets/README.md`
- asset pipeline: `docs/ASSET_PIPELINE.md`
- Tycoon Photo Studio: `tools/tycoon_photo_studio/README.md`
- MapForge documentation: `docs/map_forge/`

If a new system introduces a durable contract or workflow, update the relevant README/docs in the same change. The repository should carry enough context that a new agent can continue the project without the user re-explaining the fundamentals.
