# CH_ASSET_EDITOR_FOUNDATION_V1

Status: ACTIVE FOUNDATION

## Purpose

MapForge2 evolves into a deterministic 2D/2.5D asset authoring environment for City Horizon. The target is a focused combination of raster editor, vector editor, 2.5D scene composer, animation editor and AI-operated authoring pipeline.

The AI does **not** own the final pixels as its primary operation. AI actions create or modify deterministic document state. MapForge2 renderers produce the final PNG, spritesheet, atlas or runtime package from that state.

## Frozen/reused foundation

The following existing work is preserved and should be reused rather than rewritten without a concrete architectural reason:

- `CH_CAMERA_V1` and the canonical runtime projection path.
- `ch::world_to_screen_point()` and runtime camera/depth semantics.
- Building Composer footprint, facade, roof, material and export work.
- Animation Core hierarchy, pivots, keyframes, draw order and visual variants.
- Asset Browser and persistent content IDs.
- PNG RGBA, spritesheet and manifest export paths.
- Camera, projection, LOD, integration and visual QA gates.
- Classic Tycoon material/style contracts already created for City Horizon.

Prototype procedural artwork may remain as debug/reference material, but it is not a production-art authority.

## New universal authoring document

`CH_ASSET_DOCUMENT_V1` is the first common document contract. The authoring file extension is `.chasset`.

A document stores:

- stable asset ID and display metadata;
- canvas dimensions;
- camera contract;
- style preset;
- normalized runtime anchor;
- ordered layer stack;
- layer hierarchy;
- visibility, lock, opacity and blend state;
- deterministic 2D transforms and pivots;
- external raster/reference source paths;
- structured per-layer payloads for specialized capabilities;
- document metadata.

The first supported layer families are:

- `group`
- `raster`
- `vector`
- `mask`
- `adjustment`
- `reference`
- `object_2_5d`

This is intentionally a document foundation, not yet the final raster/vector renderer.

## Persistence invariant

Opening and saving a `.chasset` must reconstruct the same authored state. Random or procedural operations added later must store their seed and parameters in the document.

Saving is atomic. The document is validated before writing.

## History invariant

All future user and AI edits must pass through document operations that can be grouped into undoable transactions.

`AssetHistory` stores before/after deterministic snapshots. `AssetEditTransaction` groups a set of changes under one human-readable operation label. This is the base contract for future Ctrl+Z/Ctrl+Y and for undoing an AI request as one operation.

## Layer invariant

Layer IDs are persistent structural references. They follow the same lowercase/digit/dot/underscore/dash discipline as other City Horizon persistent IDs.

Layer hierarchy must not contain missing parents or cycles. Removing a parent removes its descendants from the document. Layer order is explicit and deterministic.

## Camera invariant

2.5D authoring state references `CH_CAMERA_V1`. Specialized 2.5D renderer work must use the canonical runtime projection instead of reproducing projection math inside the editor.

## AI invariant

Future AI integration receives a validated command surface such as:

- create layer;
- place component;
- set transform;
- set material;
- set mask;
- create keyframe;
- request preview/export.

The AI must not silently replace the document with an independently generated final image.

## Foundation gate

`MapForge2AssetDocumentGate` creates a representative document containing group, raster, vector, mask, adjustment, reference and 2.5D object layers. It verifies:

1. document validation;
2. `.chasset` save/load round-trip equality;
3. camera/style contract persistence;
4. grouped undo;
5. grouped redo.

GitHub Actions must run this gate before visual composer gates.

## Next implementation tranche

After this foundation is green, the next priority is the visible editor layer:

1. Layers panel and selection model.
2. Canvas selection/move/resize/rotate gizmos.
3. Raster layer storage and non-destructive masks.
4. Vector primitives and paths.
5. 2.5D world gizmos backed by `CH_CAMERA_V1`.
6. Structured AI command schema operating on the same document and history system.

No production-art expansion should force a second incompatible document model.
