# CH_RUNTIME_ASSET_FOUNDATIONS_V1

Status: active foundation contract.

This document defines small runtime primitives that City Horizon can reuse while keeping the existing city-builder architecture, camera contract, authored assets and current animation/catalog systems intact.

## Clean-room provenance rule

The implementation in this change is independently authored for City Horizon from general game-engine concepts only.

It does **not** include or reproduce third-party source code, assets, tests, binary layouts, file formats, constants or compatibility behavior from Zoo Tycoon, zt1-engine or any other external engine. In particular, City Horizon does not add support here for ZTD, ANI, Zoo Tycoon DLL resources, zoo.ini or other Zoo Tycoon-specific formats.

External projects may be studied to understand broad architectural problems, but implementation details must be designed against City Horizon's own contracts and needs.

## 1. Asset registry foundation

Header: `src/ch_core/asset_registry.h`

`ch::AssetRegistry` provides a small typed lookup layer for runtime-facing assets. Each `AssetDescriptor` has:

- a stable City Horizon ID;
- an `AssetKind`;
- a logical runtime path;
- an optional logical source group;
- an optional City Horizon contract name.

Registration rejects empty IDs, empty paths and duplicate IDs. `source_group` is only logical grouping metadata at this stage. It deliberately does **not** define a proprietary archive/container format yet.

This is intended to reduce direct path knowledge in gameplay/render code over time without forcing a one-shot migration of existing catalogs.

## 2. Palette foundation

Header: `src/ch_render/palette_bank.h`

`ch::PaletteBank` stores RGBA entries and named semantic ranges. A caller may define ranges such as:

- `primary`;
- `secondary`;
- `water_cycle`;
- future material-specific ramps.

The runtime can replace a complete named range or rotate only that range for palette-cycling effects. The palette object does not parse any legacy game palette format and makes no assumptions about third-party palette indices.

Primary/secondary color masks already used by City Horizon can migrate to semantic palette ranges only where that produces a concrete runtime or memory benefit. Existing approved assets do not need to be re-authored just to satisfy this foundation contract.

## 3. Sprite animation foundation

Header: `src/ch_render/sprite_animation_runtime.h`

The runtime keeps City Horizon's four canonical directions:

- SOUTH;
- EAST;
- WEST;
- NORTH.

A `SpriteFrame` contains:

- an asset path;
- a source rectangle;
- draw offsets relative to the logical untrimmed canvas;
- an anchor point;
- a per-frame duration.

This permits trimmed atlas frames while preserving stable placement and ground anchoring.

A `SpriteAnimationClip` stores authored directional tracks. Missing directions are **not** guessed. A different direction can reuse an authored track only when the asset explicitly defines a `DirectionAlias`. The alias also explicitly declares whether horizontal mirroring is allowed. This protects asymmetric assets, text, entrances, props and other direction-sensitive artwork from accidental flips.

`SpriteAnimationPlayer` advances by caller-supplied delta time, resets on clip/direction changes, supports looping and non-looping tracks, and exposes the current frame plus the explicit mirror flag. Large looped deltas are reduced by the clip cycle duration so a pause/debug stall does not require iterating once per missed cycle.

## 4. Relationship to existing City Horizon systems

These primitives are foundations, not competing replacements.

- `MobileAnimationCatalog` remains the active actor animation catalog.
- `CH_ANIMATED_PROP_V1` / `AnimatedPropCatalog` remains the active animated-prop contract.
- existing ride, water and overlay runtimes continue to work unchanged.

New integrations should migrate incrementally when a visible gameplay use requires them. Shared low-level behavior can move onto these primitives without invalidating already approved asset definitions.

Recommended first consumers are the systems that already need the same concepts: animated rides, visitor directional sprites and palette-cycled water/overlays.

## 5. Non-goals for V1

This contract does not introduce:

- a new archive/package file format;
- automatic mirroring of every asset;
- a replacement for the existing Asset Editor;
- GPU texture residency/eviction policy;
- legacy game-format compatibility;
- a mass conversion of approved PNG assets.

Those remain separate decisions and should only be added when City Horizon has a demonstrated runtime need.

## 6. Validation

The existing `mobile_animation_test` also exercises these foundations so the normal CMake/CTest path checks:

- typed registration and duplicate-ID rejection;
- semantic palette ranges, remapping and cycling;
- trimmed frame metadata;
- explicit direction aliases and mirroring;
- refusal to invent undeclared directional fallbacks;
- deterministic frame advancement and anchor retention.

Contract ID: `CH_RUNTIME_ASSET_FOUNDATIONS_V1`.
