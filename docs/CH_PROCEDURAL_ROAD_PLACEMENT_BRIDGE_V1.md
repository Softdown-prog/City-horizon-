# CH_PROCEDURAL_ROAD_PLACEMENT_BRIDGE_V1

## Purpose

`CH_PROCEDURAL_ROAD_PLACEMENT_BRIDGE_V1` is the migration bridge between City Horizon's authoritative legacy tile roads and the experimental continuous procedural-road graph.

The bridge does not replace `RoadManager`. It mirrors a tile sequence that has already been accepted by the legacy placement rules into `ProceduralRoadGraph` plus `ProceduralRoadClassCatalog`.

This makes it possible to prove procedural rendering and traffic against real player-authored topology while legacy occupancy, access, economy and save/load remain stable.

## Source

Implementation:

- `src/procedural_road_placement_bridge.h`

Focused gate:

- `src/procedural_road_placement_bridge_test.cpp`

## V1 topology mapping

Every legacy road tile center becomes one explicit procedural graph node.

Adjacent tiles in the accepted sequence become one procedural graph segment each.

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

## Input validation

`mirror_tile_segment(...)` rejects before graph mutation when:

- the input sequence is empty;
- the class is `unspecified`;
- elevation is not finite;
- consecutive tiles are not cardinally adjacent.

The bridge is designed to receive a segment only after the legacy placement layer has already decided that construction is valid.

## Incremental placement versus rebuild

V1 deliberately provides two synchronization paths.

### Incremental placement

After the existing runtime accepts a new road drag, `mirror_tile_segment(...)` can add only that accepted sequence to the procedural mirror.

It reuses coincident same-elevation nodes and existing edges, so a new crossing automatically becomes an explicit procedural graph junction.

### Full rebuild

`rebuild_from_legacy_tiles(...)` clears the procedural mirror and deterministically reconstructs it from the complete legacy `RoadTile` collection.

The rebuild:

1. creates/reuses one node for every legacy road tile;
2. scans only East and South neighbors after all nodes exist;
3. emits every undirected logical adjacency exactly once;
4. restores class/geometry through the canonical construction builder.

This is the safe V1 synchronization primitive after save/load and demolition. Instead of trying to patch multiple procedural edges after a legacy tile disappears, the runtime can rebuild from the authoritative legacy network and cannot retain a procedural "ghost road".

Because the legacy save format does not carry road class yet, a production rebuild should currently use `Local` as the compatibility class.

## Production runtime migration

V1 integration order is deliberately conservative:

1. player placement is validated by the existing legacy road system;
2. economy/occupancy remains owned by `RoadManager`;
3. after successful legacy placement, the accepted tile sequence can be mirrored incrementally;
4. after load or demolition, the mirror can be rebuilt from `RoadManager::tiles()`;
5. procedural rendering/traffic can consume the mirrored graph behind their own gates;
6. save/load authority remains legacy until procedural persistence is explicitly implemented.

If procedural mirroring fails, production placement must not retroactively corrupt the accepted legacy road. The mirror is a migration/debug layer until it becomes authoritative.

## Load/rebuild rule

Because procedural road classes are not yet persisted in the production save format, V1 rebuilds legacy roads with one supplied compatibility class, expected to be `Local` in production.

Collector/Arterial must not be exposed as durable player-facing runtime choices until class persistence exists. Doing so would make a save silently lose road hierarchy.

## Validation

The focused placement test covers:

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

The lightweight Ubuntu workflow `CH Procedural Road Priority Check` compiles and executes this gate together with the earlier priority, road-class and construction gates.

GitHub Actions run `36623824882` completed successfully for the initial bridge gate. A subsequent run also covers the rebuild cases added afterward.

## Non-goals for V1

V1 does not yet provide:

- procedural road save/load persistence;
- player-facing Local/Collector/Arterial runtime selection;
- freeform spline drawing in the production runtime;
- incremental procedural edge deletion as the authoritative demolition path;
- graph compression of straight degree-2 runs;
- automatic terrain elevation sampling;
- runtime procedural mesh drawing as the authoritative road visual.

These remain explicit migration gates rather than implicit behavior.
