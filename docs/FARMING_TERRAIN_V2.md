# City Horizon — Farming Terrain V2

Status: **approved design direction / implementation pilot**

This document replaces the old visual model where every prepared farm cell was rendered as a complete pre-rendered soil tile.

## Goal

Farming areas must read as a **single continuous field**, not as a mosaic of repeated isometric diamonds.

The simulation may continue using the canonical tile grid for ownership, placement, saving, crop state and collisions, but the player should not visually perceive the grid boundaries inside a field.

## Non-goals for the first pilot

The first implementation must NOT add:

- crops;
- tractors;
- irrigation;
- fences;
- hay bales or decorative props;
- automatic farm buildings;
- new gameplay rules.

Those systems are layered later only after the ground presentation is visually approved.

## CH_FARM_GROUND_V2

The field presentation is split into independent layers.

### Layer 1 — continuous prepared soil

Prepared farm cells are rendered using one continuous soil material.

Rules:

- no visible per-tile border;
- no outline around internal tile edges;
- no full soil PNG repeated once per logical cell;
- adjacent farm cells must share exactly the same soil appearance at their common edge;
- logical tile ownership remains unchanged;
- soil rendering must stay aligned with `CH_CAMERA_V1` and the canonical 128x64 grid.

A flat color/material is acceptable for the first pilot. A world-space seamless soil texture can replace it later without changing the gameplay contract.

### Layer 2 — furrows

Furrows are an overlay independent from the soil material.

They must be defined in **world coordinates**, not baked into a per-tile soil sprite.

For the initial pilot:

- use one field orientation only;
- furrows run along a canonical world axis;
- segments on neighbouring farm cells must join at their common edge;
- no line is drawn outside prepared/planted farm cells;
- camera rotation changes only projection, never the logical furrow direction.

A later version may allow X-axis or Y-axis field orientation per connected field.

### Layer 3 — crops

Crops are independent transparent overlays/instances placed above `CH_FARM_GROUND_V2`.

The soil must not contain crop-specific pixels.

Therefore there must be no separate ground asset such as:

- `soil_wheat`;
- `soil_corn`;
- `soil_tomato`;
- crop-specific prepared-soil tiles.

Crop growth stages may continue to use the existing `FarmingSystem` state machine while their presentation is migrated separately.

## Field boundary

Internal grid boundaries are never shown.

Only the external border between farm and non-farm terrain may receive a transition treatment.

The first pilot may use a clean hard boundary while validating continuity. The intended production solution is a reusable boundary mask/autotile that softly mixes prepared soil with the base terrain.

This transition belongs to the field perimeter, not to every tile.

## Rendering order

Recommended order:

1. base terrain / grass;
2. continuous farm soil;
3. farm boundary blend;
4. furrow overlay;
5. crop overlays;
6. props / buildings / vehicles according to normal depth sorting.

## Simulation contract

`FarmingSystem` remains responsible for logical cells and crop state.

The V2 work is initially a **presentation refactor**. Do not rewrite harvesting, growth days, inventory or save semantics merely to change how prepared soil is drawn.

A farm cell may remain represented internally by `FarmTile`. Multiple neighbouring `FarmTile` objects are visually interpreted as one field surface.

## Connected fields

A connected field is a group of farm cells connected by cardinal N/E/S/W neighbours.

The rendering system may later build connected components for:

- choosing furrow orientation;
- generating only the external perimeter;
- applying low-frequency visual variation per field;
- assigning field-level irrigation or ownership metadata.

Do not require connected-component storage for the first rendering pilot.

## Visual variation

Production fields should avoid obvious repetition, but variation must be subtle.

Preferred future method:

- seamless soil sampled in world space;
- low-frequency deterministic variation based on world coordinates or field id;
- no random per-tile tint that reveals the tile grid.

## Existing legacy art

The legacy prepared-soil full-tile PNG is not the canonical V2 ground solution.

It may remain temporarily in the repository only while migration is in progress, but new V2 rendering must not depend on repeating it once per farm cell.

Legacy crop composite sprites are likewise migration-only. Plant-only transparent overlays are the desired crop format.

## First implementation gate

Before adding crops again, validate a simple field such as 6x8 or 8x8 in the real game camera.

The pilot passes only if:

1. the player cannot see internal tile seams;
2. the soil reads as one continuous area;
3. furrows line up continuously across neighbouring cells;
4. camera rotation keeps the field coherent;
5. no crop/trator/decorative asset is required to hide defects in the ground;
6. placement/collision/save logic remains unchanged.

Only after this gate passes should crop artwork, irrigation and new tractors be rebuilt on top of the new field system.
