# CH_PROCEDURAL_ROAD_PLACEMENT_BRIDGE_V1

## Purpose

`CH_PROCEDURAL_ROAD_PLACEMENT_BRIDGE_V1` is the migration bridge between City Horizon's authoritative legacy tile roads and the experimental continuous procedural-road graph.

The bridge does not replace `RoadManager`. It mirrors accepted legacy road topology into `ProceduralRoadGraph` plus `ProceduralRoadClassCatalog`.

As of the runtime mirror integration, every production `RoadManager` owns one continuously synchronized `ProceduralRoadPlacementBridge`. Legacy occupancy, access, economy, save/load and traffic authority remain unchanged.

## Source

Implementation:

- `src/procedural_road_placement_bridge.h`
- `src/road_system.h`
- `src/road_system.cpp`

Focused gates:

- `src/procedural_road_placement_bridge_test.cpp`
- `src/procedural_road_runtime_mirror_test.cpp`

## V1 topology mapping

Every legacy road tile center becomes one explicit procedural graph node.

Adjacent legacy road tiles become one procedural graph segment each.

This V1 mapping intentionally favors exact topology over graph compression:

- a straight legacy run has degree-2 intermediate nodes;
- a second road crossing the same ground tile reuses that node and creates an explicit junction;
- repeated identical placement reuses existing nodes and edges rather than duplicating them.

Later graph simplification can merge degree-2 runs after persistence/render gates are stable. It must not change connectivity.

## Elevation rule

Node identity contains:

- legacy tile X;
- legacy tile Y;
- quantized procedural elevation.

Therefore two roads that occupy the same projected XY tile but have different elevations receive different graph nodes.

A ground road and an elevated road do not become connected merely because they cross visually. This preserves the core procedural-road topology contract required for bridges and viaducts.

## Construction class

New edges are created through `ProceduralRoadConstructionBuilder`.

The chosen `ProceduralRoadClass` therefore automatically supplies:

- road width;
- lane count;
- subdivisions;
- texture repeat;
- class catalog metadata.

`unspecified` is rejected as an authored placement class.

An existing procedural edge is never silently upgraded merely because a repeated mirror request names a different class. Explicit re-profiling is available through `set_existing_edge_class(...)`.

The production runtime mirror currently uses `Local` as its compatibility class because road class is not yet persisted in the legacy save format.

## Runtime synchronization

`RoadManager` remains the source of truth and owns the mirror as a subordinate migration layer.

### New placement

`RoadManager::place_tile(...)` now mirrors every accepted tile immediately.

The new tile receives one procedural node and is connected to every existing cardinal road neighbor. This also covers `RoadManager::place_segment(...)`, because segment placement already routes through `place_tile(...)`.

This incremental path means a player-authored crossing becomes an explicit graph junction without requiring a full-network rebuild after every placed tile.

### Save/load

`SaveManager` restores roads one tile at a time through `RoadManager::place_tile(...)`.

Because the mirror hook lives in `RoadManager`, save loading automatically reconstructs the procedural network regardless of tile restoration order. No separate main-runtime load patch is required.

### Demolition

`RoadManager::remove_tile(...)` removes the authoritative legacy tile first and then calls `rebuild_from_legacy_tiles(...)`.

The full rebuild is intentional for V1: it eliminates removed nodes and edges deterministically, preventing procedural ghost roads after demolition.

### Clear

`RoadManager::clear()` clears both the authoritative legacy road collection and its subordinate procedural mirror.

### Copy semantics

Copying a `RoadManager` copies the legacy road state and rebuilds an independent procedural mirror. The copied mirror does not alias the source.

## Full rebuild

`rebuild_from_legacy_tiles(...)` clears the procedural mirror and deterministically reconstructs it from the complete legacy `RoadTile` collection.

The rebuild:

1. creates/reuses one node for every legacy road tile;
2. scans only East and South neighbors after all nodes exist;
3. emits every undirected logical adjacency exactly once;
4. restores class/geometry through the canonical construction builder.

Because the legacy save format does not carry road class yet, a production rebuild uses `Local` as the compatibility class.

## Authority boundary

The mirror must not change whether a legacy road placement succeeds.

`RoadManager` remains authoritative for:

- logical occupancy;
- construction validity;
- building access;
- economy cost;
- legacy navigation and traffic;
- save/load persistence.

The procedural mirror is now available through `RoadManager::procedural_mirror()` for gated procedural rendering, routing and traffic experiments.

Collector/Arterial must not become durable player-facing runtime choices until class persistence exists. Otherwise a save could silently lose the authored road hierarchy.

## Validation

The bridge-level gate covers:

- node/edge creation for a cardinal tile run;
- explicit node reuse at a same-elevation four-way crossing;
- class preservation on Local and Collector edges;
- non-connection of an elevated crossing;
- idempotent repeated mirroring;
- rejection of non-adjacent input without mutation;
- explicit edge re-profiling to Arterial;
- complete rebuild of a four-way legacy topology;
- removal of a branch through rebuild after simulated demolition;
- rebuild at a non-zero elevation and with a supplied compatibility class.

The production `RoadManager` integration gate additionally covers:

- `place_segment(...)` mirroring;
- a four-way crossing built through production placement calls;
- `place_tile(...)` in non-sequential order to match save-load behavior;
- demolition rebuild with no ghost node/edge;
- `clear()` synchronization;
- independent mirror state after copying `RoadManager`.

GitHub Actions run `36635699865` completed successfully. It compiled `src/road_system.cpp`, linked the production `RoadManager` mirror integration test and executed all focused procedural-road gates successfully.

## Non-goals for V1

V1 does not yet provide:

- procedural road class persistence in save files;
- player-facing Local/Collector/Arterial runtime selection;
- freeform spline drawing in the production runtime;
- procedural graph authority for demolition;
- graph compression of straight degree-2 runs;
- automatic terrain elevation sampling;
- runtime procedural mesh drawing as the authoritative road visual.

These remain explicit migration gates rather than implicit behavior.
