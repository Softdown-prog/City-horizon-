# Phase E — Deterministic Placement Engine (CH_PLACEMENT_V1)

## Overview

Phase E establishes a single, deterministic placement evaluation authority inside `ch_core`. No entity enters the map because Python, Gemini, or Codex decided it fits; an entity enters the map **only** if `ch_core::can_place(...)` produces `PlacementResult::VALID`.

`can_place()` is a pure, side-effect-free evaluation function. It performs **zero state mutation** and zero auto-snapping.

---

## Contract Standard: `CH_PLACEMENT_V1`

### Placement Categories
- `Building`
- `Road`
- `Tree`
- `Decoration`
- `WaterStructure`

### Stable Violation Codes
- `CH_PLACE_BOUNDS`: Position or footprint extends outside map bounds (`-24..24`).
- `CH_PLACE_OCCUPIED`: One or more footprint tiles are already occupied by another building or structure.
- `CH_PLACE_TERRAIN`: Terrain type at target location is incompatible with object category (e.g. building on water).
- `CH_PLACE_ANCHOR`: Ground/contact anchor evaluation failed.
- `CH_PLACE_CONNECTOR`: Required semantic connector is missing or misaligned.
- `CH_PLACE_ROAD_REQUIRED`: Placement requires perimeter road/sidewalk access which is absent.
- `CH_PLACE_WATER_REQUIRED`: Water structure requires adjacent water source.
- `CH_PLACE_CATEGORY_RULE`: Category-specific placement rule violated.

---

## Architecture & Data Flow

```
AI / UI / Game Placement Request
               ↓
    PlacementRequest { object_id, category, origin, rotation }
               ↓
    ch_core::can_place(request, world_view, catalog_view)
               ↓
   ┌──────────────────────────────────────────────┐
   │ Evaluates:                                   │
   │ 1. Map Bounds (-24..24)                       │
   │ 2. Terrain Compatibility                      │
   │ 3. Footprint Occupancy                       │
   │ 4. Contact Anchor                             │
   │ 5. Road Access & Connectors                   │
   └──────────────────────────────────────────────┘
               ↓
   PlacementResult { state, violations, affected_tiles, resolved_origin }
               ↓
   ┌───────────────────────┬──────────────────────┐
   │                       │                      │
   VALID                   INVALID                NOT_DECLARED
   (Green Preview)         (Red Preview +         (Fallback to default
                           CH_PLACEMENT_REJECTED)  1x1 footprint)
```

---

## Rejection Format Example (`CH_PLACEMENT_REJECTED`)

```
CH_PLACEMENT_REJECTED
object: residence_01
origin: 8,12
violation: CH_PLACE_OCCUPIED
conflicting_tile: 9,13
```

---

## Phase E Gate Checklist

- [x] Contract `CH_PLACEMENT_V1` declared in `ch_core`.
- [x] Single placement authority `can_place(...)` in `ch_core`.
- [x] Map Forge uses `can_place(...)` for native preview.
- [x] City Builder (`main.cpp`) uses `can_place(...)` for game placement.
- [x] Bounds, footprint, occupancy, terrain, anchors, connectors enforced.
- [x] Invalid placement produces structured `CH_PLACEMENT_REJECTED` output.
- [x] `can_place(...)` performs zero mutation.
- [x] Zero silent position snapping/correction.
- [x] GAME == FORGE geometry signature hash gate passes.
- [x] All 15 C++ unit tests and 16+ Python unit tests pass green.
- [x] No Phase F+ feature (transactions, autotiling, procedural solver) implemented.
