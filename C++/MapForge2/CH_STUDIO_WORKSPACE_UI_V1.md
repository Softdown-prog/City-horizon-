# CH_STUDIO_WORKSPACE_UI_V1

Status: ACTIVE DIRECTION / UI FOUNDATION

## Goal

City Horizon Studio must be a production workspace first, not a panel showcase. The map/asset editing viewport owns the majority of the window. Tools appear around it only when needed.

## Layout contract

- Center: canonical editing viewport; maximum practical area.
- Top: high-frequency tools and mode switches (Inspect, Terrain, Road, Erase, material/tile selection, brush, Center, panels).
- Right/left/bottom: contextual panels only; dockable, movable, collapsible, hideable.
- Studio panels are hidden by default when a scenario opens so the map remains the visual focus.
- `Tab` toggles Studio Panels.
- No workflow should require a permanently open wide inspector.

## Functional priority

Do not add more placeholder tabs before the first complete production loops exist.

1. Lossless mutable authoring document for real scenario edits + Save/Save As.
2. Tile/terrain authoring with already-approved isometric tiles.
3. Material Mask Composer: approved base + reusable mask + extracted material/texture + deterministic preview/export.
4. Asset Calibration: alpha bounds, canonical scale, ground anchor, footprint, rotation/direction coverage.
5. Asset Library: catalog, provenance, tags, preview, pack grouping.
6. Animation: typed presets and frame/mirror preview using existing CH_ANIMATED_PROP_V1/actor rules.
7. Export: PNG RGBA, masks, recipes, metadata, thumbnails and CH_CONTENT_PACK_V1 definitions.

## Tile/material rule

Approved geometry is immutable. A tile already homologated for the game is not redrawn merely to create another surface.

Production composition is:

`approved base geometry + mask shape + source material/texture + semantic policy -> deterministic result`

Examples include full fill, half-tile, narrow center path, edge band, inner/outer corner and custom mask.

Visual-only edits must not silently change terrain semantics. Semantic changes remain explicit.

## Python integration rule

Existing Python tools are not rewritten merely for language uniformity.

Keep Python where it is already the best fit: Pillow/image processing, mask generation, batch conversion, Blender automation, offline validators/generators and specialized background-removal adapters.

City Horizon Studio invokes such tools through explicit adapters (normally `QProcess` + file/JSON contracts). The native Qt/C++ UI owns the user workflow; Python remains an implementation backend for offline/specialized operations.

A Python adapter must:

- declare inputs/outputs;
- never overwrite the source unless explicitly requested;
- return machine-readable success/error diagnostics where practical;
- write outputs to a staging/export path;
- be callable without UI automation.

## Production-tool candidates

Background cleanup/removal, alpha/matte inspection, halo cleanup, crop/normalize, RGBA conversion, mask authoring/generation, material extraction, texture tiling/seam checks, palette/contrast tools, sprite/frame slicing, thumbnail/pack export, Blender headless renders, provenance metadata and validation.

## Non-goal

The Studio is not a generic Photoshop/Unity replacement. It is a City Horizon-aware 2D/isometric production environment. Tools should encode the game's camera, tile, anchor, mask, semantic, animation and export rules so repeated content work requires less guessing.
