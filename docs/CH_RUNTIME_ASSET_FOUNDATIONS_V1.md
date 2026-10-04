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

## 4. Shared resource cache foundation

Header: `src/ch_core/resource_cache.h`

`ch::ResourceCache<Key, Value>` is an ownership-neutral cache primitive for runtime resources. It provides:

- lookup by stable key;
- reuse of already-loaded values;
- `get_or_load()` for load-on-first-use behavior;
- failed-load handling without inserting invalid values;
- deterministic telemetry for lookups, hits, misses, insertions, load attempts and load failures.

The cache deliberately does not destroy resources by itself. SDL textures, audio buffers and other backend resources keep their existing ownership/destruction rules while sharing the same lookup and on-demand loading contract.

The first concrete integration replaces the two ad-hoc texture maps inside `MapForgeNativeViewport` with `ResourceCache<std::string, TextureAsset>`. Existing texture creation, blend/scale setup and `SDL_DestroyTexture` cleanup remain unchanged, so this migration changes cache infrastructure without changing approved visuals or GPU ownership.

This is the foundation for later unifying the live game texture cache, actor recolour variants and other reusable runtime resources. A residency/eviction policy is intentionally deferred until City Horizon has measured memory pressure and a safe frame-boundary release strategy.

## 5. First concrete asset consumer: water

Header: `src/ch_render/water_surface_runtime.h`

`WaterSurfaceRuntimeCatalog` is the first bridge from these foundations into an existing City Horizon asset contract. It reads the project's own `CH_WATER_SURFACE_V1` manifest and:

- preserves `water_shallow` and `water_deep` as semantic runtime IDs;
- registers their base, original overlay, indexed overlay and approved RGBA animation atlas through `AssetRegistry`;
- exposes the seam-coverage colours through named `PaletteBank` ranges rather than creating a second water-specific colour container;
- takes the animation cadence from the manifest (`16` frames at `125 ms` each) and resolves the current frame deterministically;
- validates that the manifest still matches the currently supported 4x4/256px/1px-gutter atlas geometry before accepting it.

This does **not** replace the approved RGBA atlas with runtime per-pixel recolouring. The existing atlas already bakes the subtle palette-intensity cycle plus glint drift and is intentionally retained so SDL backends do not require indexed-texture support. The semantic palette is currently used for runtime coverage/fallback colour ownership and remains available for future indexed consumers where there is a measured benefit.

## 6. Relationship to existing City Horizon systems

These primitives are foundations, not competing replacements.

- `MobileAnimationCatalog` remains the active actor animation catalog.
- `CH_ANIMATED_PROP_V1` / `AnimatedPropCatalog` remains the active animated-prop contract.
- the approved water PNGs and RGBA animation atlas remain the visual source of truth.
- existing ride and overlay runtimes continue to work unchanged until individually migrated.

New integrations should migrate incrementally when a visible gameplay use requires them. Shared low-level behavior can move onto these primitives without invalidating already approved asset definitions.

After water, the highest-value consumers are animated rides and visitor directional sprites.

## 7. Non-goals for V1

This contract does not introduce:

- a new archive/package file format;
- automatic mirroring of every asset;
- a replacement for the existing Asset Editor;
- a GPU texture residency/eviction policy;
- legacy game-format compatibility;
- a mass conversion of approved PNG assets.

Those remain separate decisions and should only be added when City Horizon has a demonstrated runtime need.

## 8. Validation

The existing `mobile_animation_test` also exercises these foundations so the normal CMake/CTest path checks:

- typed registration and duplicate-ID rejection;
- load-on-first-use resource caching, cache hits and failed-load telemetry;
- semantic palette ranges, remapping and cycling;
- loading the canonical `CH_WATER_SURFACE_V1` manifest;
- preservation of water IDs, build costs and stable asset paths;
- the approved 16-frame / 125 ms water cadence and deterministic two-second loop;
- semantic shallow/deep coverage colours;
- trimmed frame metadata;
- explicit direction aliases and mirroring;
- refusal to invent undeclared directional fallbacks;
- deterministic frame advancement and anchor retention.

Contract ID: `CH_RUNTIME_ASSET_FOUNDATIONS_V1`.
