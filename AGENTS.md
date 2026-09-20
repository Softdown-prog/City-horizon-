# AGENTS.md — City Horizon onboarding contract

This file is the fast onboarding document for AI agents and human contributors. Read it before changing the project.

## 1. What City Horizon is

City Horizon is now a **small-scope 2D isometric park-management / tycoon project**, pivoted away from the previous full modern city-builder scope.

The runtime remains SDL3/C++, and the existing engine, MapForge, placement systems, grid, camera, connected paths/roads, economy foundations, audio and asset pipeline should be reused wherever they fit.

The project is developed by a solo programmer. Preserve continuity: prefer documenting durable decisions in the repository instead of relying on chat/session memory.

### Scope rule

Do **not** silently re-expand the project back into a full city-builder or RollerCoaster-Tycoon-scale simulation.

The first playable target is intentionally small:
- one compact park map;
- connected pedestrian paths;
- a limited set of reusable trees and props;
- benches, lighting, toilets and basic service objects;
- a cafeteria / kiosk and a few small attractions;
- simple money / upkeep / income loops;
- simple park quality metrics such as cleanliness, beauty, services and fun;
- land expansion only after the core loop works;
- visitors may start as simplified agents/markers before full character animation.

Large systems such as full urban zoning, traffic simulation, vehicle networks, dozens of building categories, airports, ports, skyscraper progression and city-scale infrastructure are **out of scope** unless explicitly re-approved later.

## 2. Current art direction

The authoritative style contract is `CH_STYLIZED_PRERENDER_V1`.

Target:
- stylized pre-rendered 2D sprites;
- strong gameplay readability;
- clean, coherent material separation;
- controlled detail and soft contact/shadow structure;
- one coherent visual universe across park buildings, vegetation, paths, attractions and props;
- a miniature / diorama-like presentation is acceptable and may be embraced intentionally;
- modern tooling is allowed and expected.

Do not interpret classic Tycoon references as an instruction to reproduce year-2000 hardware limitations. Zoo Tycoon / RollerCoaster Tycoon are useful references for readability, miniature composition, path logic and information density only.

### Visual proof rule

For visual tasks, code completion is not evidence of success. A visual approach is only considered successful after its generated PNG/artifact has been inspected at gameplay scale.

Do not keep escalating a failed visual technique with endless new procedural revisions. If repeated generated outputs do not approach the requested target, stop and report the limitation instead of presenting another speculative pipeline change as a likely solution.

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

For the park pivot, prefer **reusable modular assets** over large catalog breadth. One good tree, bench, lamp, kiosk or attraction may appear many times and is more valuable than many one-off building types.

## 5. Blender's role

Blender is a deterministic renderer/baker and geometry/material execution environment. It is not the place where undocumented art direction should live.

Keep design intent in recipes/contracts where possible. Blender receives canonical source, uses the frozen studio, rotates the asset root for four directions and exports source passes. The final game still uses 2D PNGs.

Pinned production Blender version in Actions is currently 4.2.3 LTS.

Blender is not assumed to solve every visual problem automatically. New procedural material or asset-generation approaches must be validated with a real rendered artifact before being promoted as production direction.

## 6. Material rules

The material library lives in `tools/tycoon_photo_studio/tycoon_material_library.py` and supports procedural recipes such as plaster, brick, concrete, timber, stone, metal panel and glass.

Use material response to communicate matter at gameplay scale. Avoid:
- plastic CG look;
- high-frequency texture noise that disappears at final size;
- photoreal microdetail;
- flat vector surfaces with no material read;
- treating technical correctness as sufficient visual approval.

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

Park buildings and props should align to the grid and pedestrian paths without unexplained grass gaps. Footprint, pivot and anchor correctness are part of the asset contract.

Connected pedestrian paths are a primary gameplay system. Existing road/path topology code should be reused where practical, while keeping pedestrian-path semantics independent from vehicle-road semantics.

## 9. Engineering workflow

Prefer edits to canonical files. Do not create duplicate EXEs, backup copies or alternate source trees unless a task explicitly requires them.

The solo-development workflow intentionally avoids a full rebuild/ctest cycle after every tiny edit. Use focused validation while iterating. Full compile/test is appropriate for milestones, architecture changes or when there is a concrete reason to validate the whole system.

When changing a GitHub file, read the current version first. Avoid concurrent writes to the same path.

### Vertical-slice priority

Before adding broad new systems, prove the park loop with a minimal vertical slice using mostly existing technology:

```text
compact map
  -> place connected paths
  -> place a few reusable park objects / services
  -> place one or two small attractions
  -> spend money / receive income
  -> observe simple park metrics
  -> expand only after the loop is playable
```

Do not build large infrastructure ahead of visible gameplay need.

## 10. Source hierarchy

For visual work, trust in this order:
1. current contracts under `tools/tycoon_photo_studio/contracts/`;
2. approved procedural recipes/source configs;
3. frozen studio/camera configuration;
4. generated bake artifacts;
5. runtime integration.

Do not infer art direction from old asset folders.

For game scope, this `AGENTS.md` pivot is authoritative over older city-builder descriptions unless a newer explicit contract supersedes it.

## 11. Where to learn more

- project overview: `README.md`
- visual/runtime asset notes: `assets/README.md`
- asset pipeline: `docs/ASSET_PIPELINE.md`
- Tycoon Photo Studio: `tools/tycoon_photo_studio/README.md`
- MapForge documentation: `docs/map_forge/`

If a new system introduces a durable contract or workflow, update the relevant README/docs in the same change. The repository should carry enough context that a new agent can continue the project without the user re-explaining the fundamentals.
