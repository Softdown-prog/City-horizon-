# AGENTS.md — City Horizon onboarding contract

This file is the fast onboarding document for AI agents and human contributors. Read it before changing the project. Also read the root [`README.md`](README.md), which is now the main cross-chat project reset point.

## 0. Parallel work and Git safety — mandatory

City Horizon is commonly edited by multiple chats, agents, Actions jobs and worker-pool jobs at the same time. `main` is therefore an **integration branch**, not a shared mutable working branch.

Before any repository change, also read [`docs/PARALLEL_GIT_WORKFLOW.md`](docs/PARALLEL_GIT_WORKFLOW.md).

Hard rules:
- do **not** make normal development commits directly to `main`;
- create one isolated branch per chat/task from the latest `main`;
- workers may run in parallel inside a task, but must not race to rewrite the same canonical path;
- before integration, reconcile the task branch with the current `main` and preserve all already-landed changes;
- integrate through a pull request;
- never force-push, hard-reset, or move the `main` ref backwards;
- never replace a whole file from a stale snapshot when a localized edit is sufficient;
- if two tasks touch the same path, resolve the conflict on the task branch from current `main` plus the intended task delta;
- generated assets can be parallel artifacts, but promotion into shared runtime/catalog paths must be coordinated/serialized.

The previous direct-to-`main` solo rule is retired because it is unsafe when several chats and workers operate concurrently.

## 1. What City Horizon is

City Horizon is a **modern 2D isometric city-builder**.

The runtime remains SDL3/C++. The existing engine, MapForge, placement systems, grid, camera, connected roads/paths, economy foundations, audio and asset pipeline should be reused wherever they fit.

The project is developed by a solo programmer. Preserve continuity: prefer documenting durable decisions in the repository instead of relying on chat/session memory.

### Scope rule

Do not silently pivot City Horizon into a different genre. The project remains a city builder unless the user explicitly decides otherwise.

The city-builder scope may still be developed incrementally. Prefer proving one system at a time instead of expanding broad infrastructure ahead of visible gameplay need.

## 2. Current art direction

The authoritative visual contract is `CH_STYLIZED_PRERENDER_V1`.

Target:
- stylized pre-rendered 2D sprites;
- strong gameplay readability;
- clean, coherent material separation;
- controlled detail and soft contact/shadow structure;
- one coherent visual universe across buildings, vegetation, roads, props and characters;
- believable category-appropriate proportions and relative scale inside the canonical gameplay grid;
- modern tooling is allowed and expected.

Keep category proportions and relative scale coherent with the world grid and neighboring approved assets. Simplification for gameplay readability is allowed, but do not compress massing or exaggerate roofs, windows, doors or props without an asset-specific reason.

Blender remains an offline production tool. Its camera, lighting, scale relationships and material settings should stay controlled so the final result reads as a coherent 2D game asset rather than a standalone 3D showcase render.

Do not interpret classic Tycoon references as an instruction to reproduce year-2000 hardware limitations. Zoo Tycoon / RollerCoaster Tycoon are useful references for readability, path logic, information density, silhouette clarity and gameplay composition.

The current production direction intentionally accepts downsampled, slightly pixel-like pre-rendered assets when they integrate better with the 2D world. Do not undo that look merely to make the source render appear more modern or more detailed.

### Visual proof rule

For visual tasks, code completion is not evidence of success. A visual approach is only considered successful after its generated PNG/artifact has been inspected at gameplay scale.

Do not keep escalating a failed visual technique with endless new procedural revisions. If repeated generated outputs do not approach the requested target, stop and report the limitation instead of presenting another speculative pipeline change as a likely solution.

Once an asset has been visually approved, do not reopen it for speculative polish unless a concrete in-game defect appears.

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

The camera and lighting stay fixed. Rotate the asset root for the four canonical views.

## 4. Choose the correct authoring path

Do not force every asset through the same authoring method before Blender.

### New asset from zero

When the user explicitly asks to design a new asset from scratch and procedural structure is useful, prefer a compact procedural plan/recipe before Blender. This is especially suitable for repeatable families, attractions, modular geometry, trees and track pieces.

```text
Design intent / procedural plan
  -> deterministic expander when needed
  -> TYCOON_ASSET_SOURCE_V1
  -> build_scene.py in Blender headless
  -> TYCOON_ASSET_BAKE_V1
  -> postprocess.py
  -> four PNG directions + review/context boards
  -> gameplay-scale human review
  -> classification/runtime promotion
```

### Existing geometry/source

If a usable `.blend`, mesh or other geometric source already exists, do not recreate it procedurally by default. Import/use it in the canonical Blender pipeline, keep the frozen camera/light setup, bake the four directions and continue through the same post-process/review flow.

A raster reference image is not automatically reconstructable as perfect 3D geometry. Use it as a reference when needed; do not claim hidden geometry can be recovered exactly from one PNG.

## 5. Blender's role

Blender is a deterministic renderer/baker and geometry/material execution environment. The final game remains 2D and consumes PNG assets.

Pinned production Blender version in Actions is currently **4.2.3 LTS**.

Keep these stable unless the project explicitly changes contract:
- orthographic camera;
- 45° yaw;
- 30° elevation;
- canonical scale relative to the 128×64 tile;
- frozen world/studio lighting;
- RGBA PNG output with transparent film/background;
- shared projected ground-origin pivot across all four rotations;
- SOUTH/EAST/WEST/NORTH generated by rotating the asset root;
- restrained material/detail density that survives final downsample.

Keep Blender output intentionally controlled at the approved game scale. Do not increase camera drama, PBR intensity or detail density merely because Blender can render them, and do not reduce or distort an asset's proportions without a concrete gameplay or design reason. Preserve coherent relative scale with the world grid and neighboring approved assets.

The current pipeline already performs downsampling, alpha preservation, edge cleanup, pivot packaging, atlas/review generation and transparent-background handling. Do not add external background-removal, halo-removal or cropping stages by default. Add extra cleanup only if the final PNG demonstrates a real defect.

## 6. Materials

The material library lives in `tools/tycoon_photo_studio/tycoon_material_library.py` and supports procedural recipes such as plaster, brick, concrete, timber, stone, metal panel and glass.

Use material response to communicate matter at gameplay scale. Avoid:
- plastic CG look;
- high-frequency texture noise that disappears at final size;
- photoreal microdetail;
- flat vector surfaces with no material read;
- treating technical correctness as sufficient visual approval.

## 7. Visual approval and Actions

A successful CI workflow means the deterministic pipeline ran. It does **not** mean the asset is visually approved.

Always inspect:
- individual direction PNGs;
- 4-view board;
- context/review board;
- gameplay-scale result when available;
- footprint, pivot and anchor behavior.

When Actions is used for a new visual asset, provide/surface the review artifact or capture before declaring success. Do not claim an art target was achieved before inspecting the artifact.

## 8. Runtime / MapForge / street alignment

MapForge2 is the project-side environment for map/editor testing and deterministic captures. Use neutral or controlled captures when judging new assets; legacy assets visible in a scene are functional context only and must not become visual references.

Buildings should align to the grid and sidewalks without unexplained grass gaps. When a building is intended to meet a road/sidewalk, keep it visually flush to that street edge. Footprint, pivot and anchor correctness are part of the asset contract.

Connected roads and pedestrian paths remain primary gameplay systems. Reuse shared topology where practical while preserving their different semantics.

## 9. CityHorizonAssetEditor

`CityHorizonAssetEditor` is a separate executable inside `C++/MapForge2/`. It is the first-party APE-like classification/control tool for authored assets.

Use the existing editor rather than creating a competing classifier. It already supports persistent IDs, categories, gameplay metadata, footprint, `requiresPath`, tags, SOUTH/EAST/WEST/NORTH sprite assignment, gameplay-grid preview, raster/reference layers, tile/surface/autotile work, `.chasset` persistence, validation and undo/redo.

It is an active prototype rather than a finished universal tool. Entrance/exit gizmos, richer type schemas, animation editing, direct runtime export and deeper MapForge handoff remain future work.

## 10. Asset organization

Authoring sources and runtime products are different things.

- `tools/tycoon_photo_studio/` — procedural/Blender sources, materials, post-processing and contracts
- `assets/` — approved runtime-facing assets and data
- `C++/MapForge2/` — MapForge and CityHorizonAssetEditor tooling
- `.github/workflows/` — deterministic bakes/captures

After visual approval, classify/promote only the runtime-facing outputs the game needs while preserving the recipe/source that reproduces them.

## 11. Engineering workflow

Prefer edits to canonical files. Do not create duplicate EXEs, backup copies or alternate source trees unless a task explicitly requires them.

The solo-development workflow intentionally avoids a full rebuild/ctest cycle after every tiny edit. Use focused validation while iterating. Full compile/test is appropriate for milestones, architecture changes or when there is a concrete reason to validate the whole system.

When changing a GitHub file, read the current version first. Avoid concurrent writes to the same path.

For a localized fix, do not silently refactor or "improve" unrelated areas. If the requested change requires broader dependencies, report that before expanding scope.

### Git workflow

Always use the parallel-safe workflow defined in [`docs/PARALLEL_GIT_WORKFLOW.md`](docs/PARALLEL_GIT_WORKFLOW.md).

For every normal development task:
1. fetch/read the current `main`;
2. create a task-specific branch from that current `main`;
3. make only the task's intended changes there;
4. before integration, reconcile the branch with the newest `main`;
5. open/update a PR and require the `Main Integration Guard` to pass;
6. merge without rewriting `main` history.

Do not commit directly to `main` from a chat/agent. Do not use `update_ref(..., force=true)` or equivalent on `main`. If a worker/action must write generated results back, it must first synchronize with `origin/main`; shared canonical promotions should be serialized using the repository's common main-writer coordination policy.

### Vertical-slice priority

Before adding broad new systems, prove city-builder systems in small playable slices using mostly existing technology.

Do not build large infrastructure ahead of visible gameplay need. Water, large attractions and advanced simulation must not block a first small playable city.

## 12. Source hierarchy

For visual work, trust in this order:
1. current contracts under `tools/tycoon_photo_studio/contracts/`;
2. approved procedural recipes/source configs or approved imported geometry;
3. frozen studio/camera configuration;
4. generated bake artifacts;
5. human gameplay-scale approval;
6. runtime integration.

Do not infer art direction from old asset folders. Retired house experiments are explicitly excluded as visual or geometric references.

For game scope, this `AGENTS.md` and the root `README.md` are authoritative over older pivot notes unless a newer explicit contract supersedes them.

## 13. Where to learn more

- project reset / quick onboarding: `README.md`
- parallel Git integration: `docs/PARALLEL_GIT_WORKFLOW.md`
- visual/runtime asset notes: `assets/README.md`
- asset pipeline: `docs/ASSET_PIPELINE.md`
- Tycoon Photo Studio: `tools/tycoon_photo_studio/README.md`
- Asset Editor: `C++/MapForge2/CH_ASSET_PROJECT_EDITOR_V1.md`
- camera: `C++/MapForge2/CH_CAMERA_CONTRACT_V1.md`
- MapForge documentation: `docs/map_forge/`

If a new system introduces a durable contract or workflow, update the relevant README/docs in the same change. The repository should carry enough context that a new agent can continue the project without the user re-explaining the fundamentals.
