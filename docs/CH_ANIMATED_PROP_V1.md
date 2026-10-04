# CH_ANIMATED_PROP_V1

`CH_ANIMATED_PROP_V1` is the data contract for props whose visual motion is composed from a static base plus one or more animated layers. It is deliberately generic: ride, prop, tool, or MapForge code must not require an id-specific animation branch when the same motion can be described by data.

## Discovery

`AnimatedPropCatalog::load_directory()` scans the supplied root recursively. This allows each asset to live in its own subdirectory without requiring a central hard-coded list.

Only JSON files whose root `contract` is exactly `CH_ANIMATED_PROP_V1` are loaded. Other runtime manifests in the same directory tree are ignored.

## Base object

A manifest has a stable `id`, a `base_static` sprite, and optional `baseWidth` / `baseHeight` metadata. Animated layers are declared in a `layers` array. The original one-layer proof-of-concept shape remains accepted for backward compatibility.

```json
{
  "contract": "CH_ANIMATED_PROP_V1",
  "id": "example_ride",
  "base_static": "assets/props/example/base.png",
  "layers": []
}
```

## Layer contract

Each layer may define:

- `id`: stable layer name;
- `sprite` or `atlas`: runtime sprite path;
- `driver`: `time`, `rotation`, `oscillate`, `path`, `state`, or `distance`;
- `presentation`: `transform_rotation` or `atlas_phase`;
- `mountPointX` / `mountPointY`: attachment point in base-sprite coordinates;
- `pivotX` / `pivotY`: pivot inside one layer frame;
- `renderOrder`: ascending compositing order.

Layers are stable-sorted by `renderOrder`, so equal-order layers preserve authored order.

## Atlas phase presentation

`atlas_phase` means the source image contains discrete pre-rendered animation frames. It uses:

- `frameCount` — number of usable frames;
- `columns` — atlas columns;
- `rows` — atlas rows;
- `phaseOffset` — normalized phase offset added before frame selection;
- `loop` — whether phase wraps or clamps to the last frame.

The contract requires `frameCount <= columns * rows`. Invalid atlas metadata rejects the manifest instead of allowing an out-of-bounds source rectangle.

Frame selection is deterministic: normalized phase `[0,1)` maps uniformly across `frameCount`; a looping phase of `1.0` wraps to frame zero, while a non-looping phase at or beyond `1.0` clamps to the final frame. `animated_prop_runtime.h` owns this math so individual rides do not duplicate it.

## Runtime rule

Do not add concrete ride or prop ids to the generic animation resolver. Differences such as frame count, atlas layout, phase offset, motion driver, pivot, and render order belong in authored data.

Approved visual assets are not regenerated merely to adopt this contract. Existing validated PNGs should be referenced as-is when their layout already matches the manifest.

## Relationship to City Park rides

`CH_AMUSEMENT_RIDE_V1` owns gameplay behavior such as queue, capacity, dispatch, ride cycle, and passenger bindings. `CH_ANIMATED_PROP_V1` only describes composited visual motion. The two contracts may be used together without either one knowing a concrete attraction id.
