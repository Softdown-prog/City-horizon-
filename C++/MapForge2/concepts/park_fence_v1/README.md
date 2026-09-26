# City Park fence V1 — procedural 2D reference

This is the first reusable fence family for the City Horizon amusement-park asset set.

The `city_park` classification is content organization only. The fence is **not** restricted to an amusement-park zone at runtime: it is a free construction piece that the player may place anywhere allowed by the normal placement rules.

## Visual intent

- classic dark-green painted metal / wrought-iron language;
- low-to-medium height, readable at gameplay scale;
- stronger square posts with restrained round finials;
- two horizontal rails and repeated vertical pickets;
- small spear tips, broad enough to survive final gameplay scale;
- no text, logos, baked ground, or theme-specific signage;
- transparent RGBA output with the canonical 128x64 2:1 projection.

## Canonical modules

V1 establishes four reusable modules instead of authoring a closed park perimeter:

1. `Straight` — one tile-length fence run;
2. `Corner` — one 90-degree connection;
3. `End` — half-run termination for open boundaries;
4. `Gate` — visitor passage with two stronger gate posts and two short leaves permanently shown swung open.

The gate must never render as a closed fence span across the visitor route. The center passage remains physically and visually clear so visitors can enter through it without requiring a gate animation in V1.

Each module is rendered from one physical definition under the four canonical quarter-turns. No screen-space mirroring or hand-painted direction is allowed.

## Gameplay contract

The fence does not create a mandatory park boundary and does not define ownership of the enclosed area. It is a freely placeable delimiting/decorative object, comparable to general-purpose fences in classic tycoon builders.

After visual approval, runtime promotion should live under `assets/city_park/fences/` while remaining placeable outside amusement-park layouts.

## Source

- `src/park_fence_renderer.h`
- `src/park_fence_renderer.cpp`
- `src/park_fence_preview_main.cpp`

The renderer deliberately consumes `procedural_2d_primitives` so future agents can vary posts, rails, picket spacing, colors, height, gate width, and ornament without redrawing individual PNGs.
