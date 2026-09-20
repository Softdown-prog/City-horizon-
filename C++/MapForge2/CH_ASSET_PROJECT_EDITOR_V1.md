# CH_ASSET_PROJECT_EDITOR_V1

Status: ACTIVE PROTOTYPE

## Why this exists

City Horizon needs a first-party content editor in the same spirit as classic game-specific development tools such as Zoo Tycoon's APE: one place where a creator can edit the data that makes an object belong to the game instead of manually coordinating unrelated JSON files, PNG folders and runtime code.

This is not an attempt to clone Zoo Tycoon or reverse-engineer APE. The useful design lesson is the workflow: **game object properties + visuals + metadata + validation in one dedicated editor**.

The executable is:

```text
CityHorizonAssetEditor
```

It reuses the existing `CH_ASSET_DOCUMENT_V1` / `.chasset` foundation and `AssetHistory`; it does not introduce a second incompatible asset format.

## Phase 1 capabilities

The first editor shell is deliberately small but functional.

### General

- persistent asset ID;
- display name;
- category;
- canvas size;
- camera contract;
- style preset;
- default new-asset style: `CH_TYCOON_MINIATURE_V1`.

### Gameplay

The editor stores common park-object gameplay metadata in the `.chasset` document:

- build cost;
- upkeep;
- income;
- footprint width/depth in tiles;
- path-connection requirement;
- free-form tags.

These fields are metadata at this stage. Runtime adapters can consume them later without changing the authoring format.

### Four canonical directions

The editor can assign and preview SOUTH, EAST, WEST and NORTH PNGs. Paths are stored relative to the `.chasset` file when practical so project folders remain movable.

### Layers and references

The existing universal document supports structured layers. The editor can already add:

- raster layers;
- reference layers;
- remove layers;
- preview selected raster/reference content.

The full vector/mask/2.5D UI is a later tranche; the document contract already supports those layer families.

### Persistence and history

- new/open/save/save-as `.chasset`;
- deterministic document validation;
- undo/redo through existing `AssetHistory` transactions;
- advanced raw metadata JSON editing for fields that do not yet have dedicated controls.

## UI layout

The first shell uses three zones:

```text
Layers / object structure | canonical preview | APE-like property tabs
```

Property tabs begin with:

1. General
2. Gameplay
3. 4 Directions
4. Advanced

The preview is intentionally central. A valid data file is not enough for visual approval.

## What this editor should become

The long-term goal is a **City Horizon Project Editor** for every authored content type, not only buildings:

- park buildings and kiosks;
- attractions;
- scenery and props;
- trees and vegetation;
- paths and path-connected objects;
- characters/visitors;
- animation clips;
- icons and UI thumbnails;
- gameplay/economy properties;
- placement rules;
- runtime packaging/export.

Future tabs can be type-specific while the `.chasset` document remains common.

## Recommended next tranche

Do not turn this into a generic Photoshop/Blender replacement. Add game-specific authoring first:

1. true four-direction sprite board instead of single-image preview;
2. footprint/grid preview using `CH_CAMERA_V1`;
3. path connector and entrance/exit gizmos;
4. building/service/attraction property schemas;
5. icon/thumbnail generation;
6. animation clip editor backed by Animation Core;
7. runtime package/export button;
8. direct test-in-MapForge action;
9. asset catalog browser and clone/variant workflow;
10. structured AI commands that edit the same `.chasset` state.

## Important rule

The editor is the authoring/control center; Blender, image tools and procedural generators may feed it, but they must not bypass the project's canonical asset metadata and validation contracts.
