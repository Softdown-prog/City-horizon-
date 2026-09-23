# City Horizon

City Horizon is a modern **2D isometric city-builder** written primarily in C++20 with SDL3. The runtime consumes pre-rendered PNG assets. Blender is an offline production tool used to generate consistent 2D game sprites; the game itself remains 2D.

This README is the fast project reset point for a new chat/session. Read it together with [`AGENTS.md`](AGENTS.md) before changing code, assets, camera, Blender settings or project structure.

## Non-negotiable world contract

Use the existing canonical world. Do not reinterpret it per asset.

- camera contract: `CH_CAMERA_V1`
- projection: orthographic/dimetric 2:1
- world yaw: 45°
- elevation: 30°
- reference tile: 128×64
- canonical directions: SOUTH / EAST / WEST / NORTH
- Blender studio: `CH_TYCOON_STUDIO_V1`
- bake contract: `TYCOON_ASSET_BAKE_V1`
- current visual contract: `CH_STYLIZED_PRERENDER_V1`

The camera and lighting stay fixed. The **asset root rotates** to generate the four directions. Never move the camera or lights per direction just to make one side prettier.

## Visual target

City Horizon intentionally uses a restrained pre-rendered look that reads as 2D game art at gameplay scale. Classic Tycoon games are references for readability, miniature composition, path logic, density and nostalgia, but the project is not trying to reproduce old hardware limitations literally.

The Blender source render may be detailed, but the final asset is deliberately reduced/downsampled and stylized. This is intentional: it suppresses the glossy/plastic standalone-3D look and helps the asset belong to a 2D isometric game world.

Do not increase Blender scale, render drama, PBR intensity or microscopic detail merely because Blender can render it. Preserve the lower-scale restrained setup when it produces the approved gameplay look.

## Decide how to author the asset before touching Blender

There are two normal authoring paths.

### A. New asset designed from zero

When the user explicitly asks to design something new from scratch and a procedural description is convenient, use a compact procedural recipe/plan first. This is especially useful for repeatable families or geometry-heavy objects such as attractions, modular architecture, trees and track pieces.

```text
Design intent
  -> compact procedural recipe / plan
  -> deterministic expander when needed
  -> TYCOON_ASSET_SOURCE_V1
  -> Blender headless
  -> four-direction bake
  -> post-process/downsample
  -> review artifacts
  -> human approval
  -> classify/promote to runtime assets
```

Do **not** force a procedural stage when it adds no value.

### B. Geometry / image source already exists

If the visual source is already available as a `.blend`, imported mesh or other usable source, do not redesign it procedurally just for ceremony. Import/use that source in the existing Blender pipeline, keep the frozen camera/light setup, render the four directions, then run the normal post-process and review stages.

A supplied raster image is not automatically a valid 3D source. If only a reference image exists, use it as reference for authoring; do not pretend Blender can reconstruct hidden geometry perfectly from one PNG.

## Canonical production pipeline

```text
approved source / recipe
        ↓
Blender 4.2.3 LTS in the frozen studio
        ↓
source color + shadow passes
        ↓
SOUTH / EAST / WEST / NORTH
        ↓
postprocess.py
        ↓
downsample + alpha/edge treatment + pivots + atlas/review boards
        ↓
GitHub Actions artifact / visual capture
        ↓
human gameplay-scale approval
        ↓
CityHorizonAssetEditor classification
        ↓
runtime-facing asset folder / definition
        ↓
MapForge/runtime validation
```

The current pipeline already handles RGBA output, transparent background, downsampling, edge cleanup, common pivot handling and trimmed atlas generation. Do not add a separate background-removal/cropping tool by default. Add extra cleanup only when an actual final PNG shows a defect.

## Visual approval gate

A successful GitHub Actions run proves only that the pipeline executed. It does **not** approve the art.

For a new visual asset, inspect at minimum:

- individual SOUTH / EAST / WEST / NORTH PNGs;
- 4-view/review board;
- context board at gameplay scale;
- footprint/pivot alignment;
- MapForge/runtime placement when integration matters.

When using Actions, surface a review/capture artifact before declaring the asset finished. A visual task is not complete because code compiled or a workflow turned green.

Once an asset is approved, freeze it. Do not reopen an approved asset for speculative polish unless a concrete in-game defect appears.

## Roads, sidewalks, paths and buildings

The runtime grid is authoritative. Roads, sidewalks and pedestrian paths must visually and logically connect on the isometric grid.

Buildings must sit correctly on their footprint and align to the road/sidewalk system. Do not leave unexplained strips of grass between a road/sidewalk and a building when the intended placement is flush to the street edge.

Roads and pedestrian paths can share topology concepts, but their gameplay semantics remain different.

## Terrain and tiles

Reference tile size is always 128×64 at base scale. Ground assets must be tested as repeated/connected tiles, not judged only as isolated PNGs.

The current project already contains canonical grass and connected path/autotile work. Water is not a prerequisite for the first playable city slice and does not need to block city construction.

## MapForge2

`MapForge2` is the project-side map/editor environment. Use it to:

- test assets on the real grid;
- verify footprint, anchor and placement;
- inspect roads/paths/terrain in context;
- create controlled captures;
- validate that an asset belongs to the gameplay world rather than only looking good in an isolated render.

Do not use legacy visual assets visible in MapForge as art references for new production.

## CityHorizonAssetEditor

`CityHorizonAssetEditor` is a separate executable inside `C++/MapForge2/`, inspired by the workflow of classic game-specific tools such as Zoo Tycoon's APE.

Use it as the first-party classification/control center for authored assets. It already supports:

- persistent asset ID and display name;
- categories such as `building`, `attraction`, `service`, `scenery`, `tree`, `prop`, `path`, `character`, `ui`;
- build cost, upkeep and income metadata;
- footprint width/depth;
- `requiresPath`;
- free-form tags;
- SOUTH / EAST / WEST / NORTH PNG assignment;
- canonical gameplay-grid preview;
- raster/reference layers;
- tile/surface preview and autotile mask assignment;
- `.chasset` save/load;
- validation and undo/redo.

The editor is usable for cataloging/classifying assets now, but is still an active prototype. Entrance/exit gizmos, richer type-specific schemas, animation editing, direct runtime export and deeper MapForge handoff remain future work.

Do not create a second competing asset-classification tool unless there is a concrete architectural reason.

## Asset organization

Keep authoring sources and runtime products separate.

- `tools/tycoon_photo_studio/` — Blender/procedural authoring, materials, post-processing and source contracts
- `assets/` — runtime-facing approved assets and game data
- `C++/MapForge2/` — MapForge, CityHorizonAssetEditor and related tooling
- `src/` — runtime/game systems still outside the `C++/` subtree
- `.github/workflows/` — deterministic Actions bakes/captures
- `docs/` — durable project/architecture/workflow documentation

When an asset is approved, classify it and promote only the runtime-facing files that the game needs. Keep recipe/source data in the authoring pipeline so the asset remains reproducible.

## Blender production rules

Pinned production Blender in Actions: **4.2.3 LTS**.

Keep these stable unless the project explicitly changes contract:

- orthographic camera;
- 45° yaw;
- 30° elevation;
- fixed studio/world lighting;
- canonical scale relative to the 128×64 grid;
- one shared projected ground-origin pivot across the four rotations;
- RGBA PNG output with transparent film/background;
- four canonical rotations generated by rotating the asset root;
- restrained materials and detail that survive final downsample.

Blender is the execution/render environment. It is not permission to change the project's camera, projection or visual scale asset-by-asset.

## Engineering workflow

This is a solo-development project. Preserve working systems and make narrow changes.

- inspect current files before editing them;
- prefer canonical files instead of duplicates/backups;
- do not refactor unrelated systems during a localized fix;
- if a requested change requires broader dependencies, report that before expanding scope;
- avoid full rebuild/ctest after every tiny change; use focused validation while iterating and full validation at meaningful milestones;
- do not treat a green build as proof that a visual change is correct.

### Git workflow for this repository

For the current solo workflow, **do not create a new branch unless the user explicitly asks for one**. Make requested repository commits directly to `main` after reading the current target files. Do not silently open PR branches or duplicate worktrees.

### GitHub Actions budget / trigger policy

GitHub Actions minutes are a finite project resource. Workflows must be path-scoped so an unrelated commit does not fan out into multiple expensive Windows/Blender jobs.

Durable rule for all future chats/agents:

- do **not** add a bare `push` trigger on `main` for heavy workflows;
- use `paths:` (or an equivalent narrow trigger) that names the files/subtrees the workflow actually validates;
- CH Blender agent jobs should trigger from `tools/ch_blender/jobs/*.job.json` only unless there is a concrete dependency requiring more;
- MapForge Windows builds should trigger only for MapForge/editor/runtime-asset inputs that can affect that build;
- MapForge capture should trigger only for capture request / capture worker inputs;
- atomic path tests should trigger only for their tile test source/tool/MapForge capture worker inputs;
- keep `workflow_dispatch` available where manual execution is useful;
- when adding a new workflow, document why each trigger path is required;
- before widening a trigger, prefer manual dispatch over making every commit pay the cost.

If a commit that only changes `tools/ch_blender/jobs/` starts MapForge Windows, MapForge Capture or unrelated tile workflows, treat that as a CI trigger regression and fix the workflow filters before continuing routine asset jobs.

## Current production priority

Build a small coherent playable city before chasing large content breadth.

Prefer using already-valid grass, roads/paths and approved buildings/props to assemble a small map. Add sidewalks, basic urban decoration, a few buildings and simple gameplay before tackling water, complex attractions or large simulation systems.

Complex attractions such as carousels, Ferris wheels and roller coasters can use procedural structural definitions later, then pass through the same Blender/four-direction runtime pipeline. Do not let them block the first playable city slice.

## Read next

- [`AGENTS.md`](AGENTS.md) — AI/contributor operating rules
- [`docs/ASSET_PIPELINE.md`](docs/ASSET_PIPELINE.md) — detailed visual production pipeline
- [`assets/README.md`](assets/README.md) — runtime asset policy
- [`tools/tycoon_photo_studio/README.md`](tools/tycoon_photo_studio/README.md) — Blender/bake implementation
- [`C++/MapForge2/CH_ASSET_PROJECT_EDITOR_V1.md`](C++/MapForge2/CH_ASSET_PROJECT_EDITOR_V1.md) — Asset Editor state and intent
- [`C++/MapForge2/CH_CAMERA_CONTRACT_V1.md`](C++/MapForge2/CH_CAMERA_CONTRACT_V1.md) — camera contract

If a future decision changes any durable rule above, update this README and the relevant specialized document in the same change so a new chat/session can continue without the user re-explaining the project.