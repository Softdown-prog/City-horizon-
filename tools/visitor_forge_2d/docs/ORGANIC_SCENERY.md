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
