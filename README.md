# City Horizon

City Horizon is a modern 2D isometric city-builder written primarily in C++20 with SDL3. The runtime consumes pre-rendered PNG assets, but the visual source of truth is a procedural/Blender pipeline that keeps camera, scale, lighting and asset contracts consistent.

## Read this first

Agents and contributors should read [`AGENTS.md`](AGENTS.md) before changing code or assets. The project has strict camera, asset and workflow rules that are easy to break if a task is approached as an isolated image-generation problem.

## Core visual contracts

- `CH_CAMERA_V1`: orthographic/dimetric 2:1 camera, 45° yaw, 30° elevation.
- reference tile: 128×64.
- `CH_STYLIZED_PRERENDER_V1`: current art-direction contract. The target is a readable, stylized, pre-rendered City Horizon look. Classic Tycoon games are references for readability and miniature composition, not hardware limitations that must be emulated literally.
- `TYCOON_ASSET_BAKE_V1`: deterministic four-direction bake contract.
- `CH_TYCOON_STUDIO_V1`: frozen camera/light studio used by the Blender baker.

## Asset source of truth

Do **not** use old runtime sprites as visual references for new art. New visual assets must come from the procedural/Blender pipeline under `tools/tycoon_photo_studio/`.

Preferred building flow:

```text
human/agent design intent
        ↓
compact procedural plan / recipe
        ↓
pre-Blender expander
        ↓
TYCOON_ASSET_SOURCE_V1
        ↓
Blender headless + CH_TYCOON_STUDIO_V1
        ↓
TYCOON_ASSET_BAKE_V1 source renders
        ↓
post-process / stylization
        ↓
SOUTH / EAST / WEST / NORTH PNGs
        ↓
MapForge/runtime gameplay-scale review
        ↓
approved runtime asset
```

The first explicit residential example of this flow is:

- plan: `tools/tycoon_photo_studio/assets/suburban_house_simple_2x2_01.house.json`
- expander: `tools/tycoon_photo_studio/generate_suburban_house_asset.py`
- bake workflow: `.github/workflows/tycoon-suburban-house-bake.yml`

See [`docs/ASSET_PIPELINE.md`](docs/ASSET_PIPELINE.md) for the complete pipeline.

## Main areas of the repository

- `C++/`: game/editor C++ sources, including MapForge2.
- `src/`: runtime/game sources that are still organized outside the `C++/` subtree.
- `tools/tycoon_photo_studio/`: procedural authoring, Blender scene generation, post-processing and contracts.
- `assets/`: runtime-facing assets and asset notes. Legacy visuals are not art references.
- `docs/`: project architecture and workflow documentation.
- `.github/workflows/`: deterministic CI bakes/captures.

## Runtime camera/grid

The map projection uses a 2:1 isometric/dimetric grid. Conceptually:

```text
screenX = centerX + panX + (tileX - tileY) * tileWidth/2 * zoom
screenY = centerY + panY + (tileX + tileY) * tileHeight/2 * zoom
```

Pre-rendered building sprites already contain their view, lighting and perspective. Runtime code positions the sprite; it does not invent a different camera for it.

## Build

Typical Windows development requirements are CMake 3.24+, a C++20 compiler and SDL3 dependencies configured by the project.

```powershell
cmake -S . -B build
cmake --build build --config Debug
.\build\Debug\city_builder.exe
```

Do not perform full rebuilds/tests after every small edit by default. Prefer focused edits and validation; do a complete compile/test at meaningful milestones or when architecture-critical code changes.

## Approval rule

A green GitHub Actions run proves that the pipeline executed successfully. It does **not** prove that the art is visually approved. Final approval happens after inspecting the PNGs at gameplay scale and, when relevant, in MapForge/runtime context.
