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

V1 now establishes six reusable modules instead of authoring a closed park perimeter:

1. `Straight` — straight two-sided run;
2. `Corner` — 90-degree connection;
3. `End` — one-sided termination;
4. `Gate` — visitor passage with two stronger gate posts and two short leaves permanently shown swung open;
5. `Tee` — three-way junction;
6. `Cross` — four-way junction.

The gate must never render as a closed fence span across the visitor route. The center passage remains physically and visually clear so visitors can enter through it without requiring a gate animation in V1.

Each module is rendered from one physical definition under the four canonical quarter-turns. No screen-space mirroring or hand-painted direction is allowed.

## Automatic topology / classic tycoon behaviour

Runtime connectivity is defined by `src/fence_system.h/.cpp`. Fence nodes live on **grid vertices**, not inside terrain tiles, so the fence can delimit tile borders without consuming the buildable tile itself.

Every placed node receives the shared N/E/S/W `TileConnectionMask`. Whenever a node is placed or removed, that node and its four neighbours are refreshed immediately. The visible module and its logical rotation are then derived only from the neighbour mask:

- no neighbours -> isolated straight preview using the placement orientation hint;
- one neighbour -> `End`, pointing toward that neighbour;
- two opposite neighbours -> `Straight`;
- two adjacent neighbours -> `Corner`;
- three neighbours -> `Tee`, automatically rotated toward the missing side;
- four neighbours -> `Cross`;
- a valid gate request on a two-sided straight run -> `Gate`, automatically aligned to that run.

This means the player does not manually rotate each fence segment. Extending a run, creating a corner, attaching a third branch or deleting a neighbouring segment automatically changes the affected fence pieces, following the same general interaction expected from classic tycoon fence tools.

Dragging may place a run of grid vertices. The current deterministic route follows X first and then Y, so an L-shaped drag produces its corner from topology rather than from an explicitly selected corner asset.

## Gameplay contract

The fence does not create a mandatory park boundary and does not define ownership of the enclosed area. It is a freely placeable delimiting/decorative object, comparable to general-purpose fences in classic tycoon builders.

After visual approval, runtime promotion should live under `assets/city_park/fences/` while remaining placeable outside amusement-park layouts.

## Source

Procedural art:

- `C++/MapForge2/src/park_fence_renderer.h`
- `C++/MapForge2/src/park_fence_renderer.cpp`
- `C++/MapForge2/src/park_fence_preview_main.cpp`

Runtime topology:

- `src/fence_system.h`
- `src/fence_system.cpp`
- shared topology bits: `src/tile_topology.h`

The renderer deliberately consumes `procedural_2d_primitives` so future agents can vary posts, rails, picket spacing, colors, height, gate width, and ornament without redrawing individual PNGs.
