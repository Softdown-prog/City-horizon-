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

The authoritative production visual contract is now `CH_STYLIZED_3D_PRERENDER_V1`.

City Horizon intentionally uses **stylized 3D assets rendered offline and shipped as 2D RGBA PNG sprites**. Visible 3D rendering characteristics are allowed and desirable when they support a coherent stylized miniature/toy-like look.

Target:
- stylized 3D prerendered sprites used in a 2D runtime;
- strong gameplay readability;
- clean, coherent material separation;
- rounded/simple forms where appropriate;
- saturated but controlled colors;
- soft directional lighting;
- readable contact shadows and localized AO;
- large details that survive gameplay-scale reduction;
- one coherent visual universe across park buildings, vegetation, paths, attractions and props;
- miniature / diorama-like presentation is acceptable and may be embraced intentionally;
- modern Blender rendering characteristics are allowed and expected.

Do **not** try to hide the Blender origin of a good asset through aggressive posterization, forced dithering, palette reduction, fake pixel-art treatment or other destructive retro emulation.

Classic Zoo Tycoon / RollerCoaster Tycoon references remain useful for readability, composition, path logic and information density only. They are not the production-rendering target.

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
- fixed world lighting from `CH_TYCOON_STUDIO_V1` unless explicitly superseded;
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
  -> light corrective postprocess only when needed
  -> four PNG directions + review/context boards
  -> gameplay-scale human review
  -> runtime promotion
```

The design should be explicit before Blender when practical. A compact plan/recipe is preferred over hundreds of hand-authored primitive entries because it is easier to audit, vary and reproduce.

The Blender render should already be visually close to the final sprite. Post-processing is not expected to erase the 3D look.

### House-design reset

There is currently **no approved residential-house recipe, generator or geometry reference**.

The previous suburban-house and miniature-house pilots were retired because, although technically competent, they converged on the same unwanted house design language. They must not be recreated, copied, parameter-tweaked, or used as a silhouette/geometry starting point for future buildings.

For a future house, start from a genuinely new silhouette and grammar before materials or post-processing. It may reuse only the generic technical infrastructure: camera/grid contracts, frozen studio, generic material system, Blender bake, four-direction export and review tooling.

Vegetation uses its own procedural tree contracts but ends in the same frozen studio/bake review flow.

For the park pivot, prefer **reusable modular assets** over large catalog breadth. One good tree, bench, lamp, kiosk or attraction may appear many times and is more valuable than many one-off building types.

## 5. Blender's role

Blender is the primary deterministic authoring/rendering environment for suitable production assets.

Keep design intent in recipes/contracts where practical. Blender receives canonical source, uses the frozen studio, rotates the asset root for four directions and exports source/final passes. The game still consumes 2D PNGs.

Pinned production Blender version in Actions is currently 4.2.3 LTS.

Blender is expected to preserve a **stylized 3D rendered appearance** under the new visual contract. It is not a defect if a sprite visibly reads as a clean modern 3D prerender.

Use Blender for:
- consistent proportions and geometry;
- canonical camera;
- four-direction rendering;
- stylized materials;
- soft lighting;
- readable AO/contact shadows;
- deterministic export.

New procedural material or asset-generation approaches must still be validated with a real rendered artifact before being promoted as production direction.

## 6. Material rules

The material library lives in `tools/tycoon_photo_studio/tycoon_material_library.py` and supports procedural recipes such as plaster, brick, concrete, timber, stone, metal panel and glass.

Under `CH_STYLIZED_3D_PRERENDER_V1`, material response should communicate matter without chasing photorealism.

Prefer:
- broad readable color/value groups;
- restrained gloss;
- simplified specular response;
- smooth stylized gradients;
- clean bevel highlights;
- localized AO/contact darkening;
- simple signage/accent colors.

Avoid:
- photoreal architectural-visualization look;
- noisy high-frequency texture that disappears at final size;
- physically accurate PBR showcase rendering as an end goal;
- raw low-poly geometry with no art treatment;
- flat vector surfaces with no depth read;
- destructive retro filters used only to hide 3D rendering.

## 7. Visual approval rule

A successful CI workflow means the deterministic pipeline ran. It does NOT mean the asset is visually approved.

Always inspect:
- individual direction PNGs;
- 4-view board;
- context/review board;
- gameplay-scale result when available.

Do not claim an art target was achieved before inspecting the artifact.

Under the new style, do not reject an otherwise coherent asset merely because it visibly originated from Blender/3D. Judge whether it belongs to the same stylized visual universe.

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
1. `C++/MapForge2/CH_STYLIZED_3D_PRERENDER_V1.md`;
2. current contracts under `tools/tycoon_photo_studio/contracts/` that do not conflict with it;
3. approved procedural recipes/source configs;
4. frozen studio/camera configuration;
5. generated bake artifacts;
6. runtime integration.

`CH_CLASSIC_TYCOON_STYLE_V1` is historical/reference guidance only when it conflicts with `CH_STYLIZED_3D_PRERENDER_V1`.

Do not infer art direction from old asset folders. Retired house experiments are explicitly excluded as visual or geometric references.

For game scope, this `AGENTS.md` pivot is authoritative over older city-builder descriptions unless a newer explicit contract supersedes it.

## 11. Where to learn more

- project overview: `README.md`
- visual/runtime asset notes: `assets/README.md`
- asset pipeline: `docs/ASSET_PIPELINE.md`
- Tycoon Photo Studio: `tools/tycoon_photo_studio/README.md`
- MapForge documentation: `docs/map_forge/`
- authoritative production art direction: `C++/MapForge2/CH_STYLIZED_3D_PRERENDER_V1.md`

If a new system introduces a durable contract or workflow, update the relevant README/docs in the same change. The repository should carry enough context that a new agent can continue the project without the user re-explaining the fundamentals.
