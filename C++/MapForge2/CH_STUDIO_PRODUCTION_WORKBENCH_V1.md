# City Horizon Studio — Production Workbench V1

Status: PILOT / ADDITIVE / NON-DESTRUCTIVE

## Purpose

Production Workbench V1 begins the transition from a map-only editor into a game-specific 2D/isometric production environment without removing or rewriting the systems already present in Map Forge 2 / City Horizon Studio.

The workbench is intentionally additive. Existing canonical rendering, terrain semantics, content-pack validation, scratch-map authoring, scenario inspection and frozen rendering/content contracts remain authoritative.

## First principle

> Existing City Horizon work is an input to the production pipeline, not disposable prototype code.

The workbench therefore does not replace `ch_render`, `CH_GRID_V1`, `CH_MASK_V1`, `CH_CONTENT_PACK_V1`, `CH_ANIMATED_PROP_V1`, the canonical scenario reader, or the existing Studio tabs.

## Production sectors

The V1 shell introduces dedicated sectors for:

- Project identity and production profile
- Art/base-asset inspection
- Masks/materials
- 2D modular assembly
- Animation
- Lighting/art finish
- Camera/projection discipline
- Asset library indexing
- Validation
- Export gating

These sectors are intentionally game-specific. The goal is not to recreate Photoshop, Blender or Unity. The goal is to make City Horizon content easier to author coherently and to make the same workflow useful for asset-pack production.

## Implemented in V1

### Canonical production profile

`CH_STUDIO_PROJECT_V1` records project identity while inheriting the already-homologated City Horizon camera/grid values directly from `src/ch_core/contracts.h`:

- `CH_GRID_V1`
- 128×64 diamond tile
- 2:1 ratio
- 45° world rotation
- 35.264° isometric inclination
- orthographic isometric projection

The profile can be saved and loaded independently from scenario Save. A mismatched grid/tile profile is rejected instead of silently creating a second projection.

### Read-only art intake

A base image can be selected and previewed. V1 reads metadata and pixels for preview/validation but never overwrites the source asset.

### Read-only asset library index

A source folder can be indexed recursively for common image formats. The Studio does not move, rename or rewrite indexed files. This provides a safe first step for cataloging the existing historical asset archive and identifying coherent packs.

### Basic validation

V1 reports:

- project identity presence
- source file existence/readability
- image decode success
- pixel dimensions
- alpha-channel availability
- PNG-vs-other source format

It deliberately does **not** claim perspective, footprint, anchor or artistic homologation yet.

## Explicitly gated in V1

V1 does not yet:

- paint or rewrite mask pixels
- destructively recolor assets
- author modular sockets
- deform sprites with 2D meshes
- rewrite canonical game definitions
- export commercial packs
- enable canonical scenario Save
- claim runtime/editor pixel-parity beyond the existing canonical viewport pilot

Those features are added only after their own contracts and validation gates exist.

## Planned next vertical slices

The preferred order is:

1. Asset Calibration: canvas, alpha bounds, ground anchor, footprint preview and real-world scale.
2. Mask Authoring: visual region painting that outputs `CH_MASK_V1` without modifying base RGBA.
3. Modular Assembly: named sockets/pieces (roof, door, window, sign, awning, props) with deterministic snapping.
4. World Preview: selected asset rendered inside the canonical City Horizon scene at actual scale.
5. Animation Workbench: typed drivers and directional/atlas inspection reusing existing animation contracts.
6. Catalog/Product Pack: provenance, tags, family grouping, thumbnails, validation and deterministic package export.

## Invariant

> AI may propose or operate production actions, but project rules, snapping, masks, camera, validation and export are deterministic.

The user directs the art. The Studio records the decisions. The runtime consumes the same definitions. No important production decision should need to be recreated from a screenshot or remembered manually.
