# CH_STUDIO_CANONICAL_VIEWPORT_V1

Status: **PILOT / NOT YET FROZEN**

## Purpose

Make City Horizon Studio display real City Horizon world art through the canonical C++/SDL3 renderer instead of asking Qt to imitate game visuals.

This milestone is intentionally an inspection gate before lossless native authoring. It proves ownership, embedding, camera/DPR handling and renderer reuse first. Production scenario mutation and Save remain disabled.

## Camera contract

Projection geometry is no longer implicit in this viewport document. The canonical visual camera is defined separately by `CH_CAMERA_CONTRACT_V1` / `CH_CAMERA_V1`.

That contract fixes the City Horizon classic-tycoon camera to orthographic 2:1 dimetric geometry: 45-degree world yaw, 30-degree camera elevation, 26.565-degree ground screen axes, 128×64 logical tiles at zoom 1 and no perspective.

The viewport itself remains PILOT because embedding/DPR/scene-parity behavior still needs final human approval. This does not authorize the viewport, Building Composer or Animation Composer to substitute a different projection.

## Ownership contract

- **Qt6 owns:** the main window, native child viewport HWND, menus, docks, keyboard/mouse input, focus, resize notifications and the application event loop.
- **SDL3 owns:** the rendering context attached to the existing Qt-owned HWND.
- **ch_render owns:** terrain, road and building presentation rules used by the Studio viewport.
- **ch_core owns:** `CH_GRID_V1`, `CH_CAMERA_V1`, canonical projection, map parsing and coordinate transforms.
- SDL does not run a competing editor input loop.
- The Qt-owned HWND must outlive the SDL wrapper.

## Render scheduling

Qt is the single scheduling authority. A precise ~16 ms timer requests QWidget updates while canonical inspection mode is active. `paintEvent` performs one canonical frame. Hiding the widget naturally suppresses scheduled frame work through the visibility gate.

## DPR contract

Qt pointer positions are logical pixels. The canonical C++ camera/render path uses physical pixels. Studio therefore converts logical mouse positions, pan deltas and viewport dimensions by `devicePixelRatioF()` before calling canonical projection/render code.

No renderer-specific camera offset is allowed to compensate for DPI errors.

## Scenario modes

### Scratch mode

The Phase-1 diagnostic QPainter canvas remains available for interaction/command experiments. Terrain/Road/Erase and undo/redo remain enabled there.

### Canonical scenario mode

Opening a real City Horizon scenario switches the viewport to SDL3 + `ch_render`. The scenario is read through `ch::MapDocument`; terrain textures, connectivity-aware roads and building definitions are rendered from game data/assets.

Canonical scenario mode is **inspection-only in this pilot**. Inspect, pan, zoom, hover and center are allowed. Terrain/Road/Erase are disabled. This avoids a false editor in which Qt mutates an editor-only model while the canonical renderer shows something different.

## Asset rule

The Windows artifact carries the repository `assets` directory next to `MapForge2.exe`. The canonical adapter resolves textures relative to the executable directory, so IDE working-directory differences do not decide visual output.

Any raster art representing a 3D world object must be authored for `CH_CAMERA_V1`; matching a tile footprint numerically is not sufficient if the object itself visually uses another camera.

## Negative coordinates

Editor scenario bounds preserve real negative and positive coordinates. Camera centering uses actual loaded content bounds rather than assuming a 0..63-only document.

## Frozen systems

This pilot does **not** rewrite `MapRenderer`, terrain semantics, masks, overlays or animation contracts. It consumes game-side code. Camera projection geometry is frozen separately in `CH_CAMERA_V1`.

## Gates before freezing viewport V1

1. Windows CI compiles the Qt6 + SDL3 + ch_render Studio target.
2. Packaged artifact launches with Qt and SDL3 dependencies plus canonical assets.
3. Opening `assets/scenarios/initial_city.json` produces visible canonical terrain/roads/buildings.
4. Pan, zoom, hover and Center remain aligned at 100%, 125% and 150% Windows display scaling.
5. No black viewport after resize/minimize/restore.
6. Qt remains the only input/event-loop authority.
7. A parity capture compares the same scenario/camera against runtime output before this viewport contract is marked FROZEN.
8. The parity capture must use `CH_CAMERA_V1`; no generic true-isometric substitute is accepted.

## Next milestone

`CH_STUDIO_AUTHORING_DOCUMENT_V1`: introduce a lossless mutable canonical document/command layer. Only after round-trip preservation and renderer synchronization pass may canonical Terrain/Road/Place/Rotate/Erase authoring and production Save be enabled.
