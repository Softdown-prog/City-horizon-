# Organic scenery 2D

`CH_2D_ORGANIC_SCENERY_V1` extends Visitor Forge 2D for foliage and other
organic props that do not read well as stacks of rigid polygons.

The renderer is `core/organic_scenery.py`. It is deterministic: the JSON recipe,
palette and integer `seed` reproduce the same PNG without an image model or a
hidden raster source.

## Why this path exists

`CH_2D_SHAPE_RECIPE_V1` remains the compact editor for signs, furniture and
simple props. Organic scenery needs a different vocabulary: tapered quadratic
brushes, feathered branch clusters, irregular foliage masses, broad 2D light
and deliberate front/back depth. Keeping that logic in Visitor Forge avoids
turning every tree recipe into hundreds of hand-authored triangles.

## Dense raster foliage pass

Organic scenery is still authored procedurally, but the final look is no longer
limited to clean vector-like masks. The renderer now builds a denser crown from
branch clusters plus irregular clumps, fuses nearby foliage masses at working
resolution and applies deterministic raster paint inside the authored masks.

The recipe can expose a `raster` object with three density controls:

- `shadowDabs` — small occlusion/color dabs inside the crown;
- `highlightDabs` — light paint variation on front foliage;
- `needleStrokes` — short directional strokes that break flat fills at 1x.

These passes are generated from the same integer seed, so repeated builds remain
byte-stable for the same renderer, recipe and Pillow version. They are not
external textures and do not use image generation. Work happens at 4x; final
RGBA is reduced through alpha-safe Lanczos filtering so the sprite gains a
raster-painted finish without introducing a background-removal step.

Use crown filling to remove large accidental holes, not to turn the tree into a
solid triangular cone. The final silhouette should preserve irregular branch
breaks while reading as one dense organism at gameplay scale.

## Camera gate

Gameplay scenery must declare `CH_CAMERA_V1` and the canonical `[128, 64]`
ground tile. The renderer exports an additional `*_isometric_review.png` with
the sprite anchor placed on the canonical 2:1 dimetric grid. This board is a
visual gate only; runtime projection remains authoritative.

For a tree, world height stays screen vertical. Rear/uphill boughs are painted
slightly higher and darker, while front/downhill boughs hang lower and expose
more of their top-facing surfaces. That gives the crown the 30-degree camera
read instead of a flat front-view Christmas-tree silhouette.

## Pine study

The canonical study is `examples/pine_tree_organic_v1.json`.

```bash
PYTHONPATH=tools/visitor_forge_2d/src python -m visitor_forge_2d.core.organic_scenery \
  --recipe tools/visitor_forge_2d/examples/pine_tree_organic_v1.json \
  --output out/visitor_forge_2d/pine_tree_v1
```

Review all three outputs before runtime promotion:

- `pine_tree_v1.png` — transparent gameplay sprite;
- `pine_tree_v1_review.png` — 1x / 2x art inspection;
- `pine_tree_v1_isometric_review.png` — camera/grid/anchor inspection.

Generated files under `out/` are review artifacts. Promote a PNG into `assets/`
only after the gameplay-size and isometric boards are visually approved.
