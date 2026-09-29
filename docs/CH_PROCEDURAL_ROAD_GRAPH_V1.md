# CH_PROCEDURAL_ROAD_GRAPH_V1

## Purpose

`CH_PROCEDURAL_ROAD_GRAPH_V1` is the topology foundation for elastic roads in City Horizon.

It exists in parallel with the production `RoadManager`. The existing tile network remains authoritative for occupancy, construction cost, building access, pathfinding, immigration and save data until the procedural road system passes its visual and gameplay migration gates.

The graph does **not** turn City Horizon into a general-purpose 3D game. It only gives the road subsystem stable world-space topology that can drive the existing `CH_PROCEDURAL_ROAD_MESH_V1` renderer.

## Canonical data model

A procedural road network contains two stable-ID object types:

- `ProceduralRoadNode` — one shared world-space anchor `(x, y, z)`;
- `ProceduralRoadGraphSegment` — one directed description between two node IDs.

ID `0` is reserved as invalid. IDs are monotonic and are never derived from vector positions, so internal compaction does not change references.

Each segment stores:

- start node ID;
- end node ID;
- start Bézier handle relative to the start node;
- end Bézier handle relative to the end node;
- road width;
- texture repeat distance;
- mesh subdivisions;
- lane count.

Relative handles are deliberate. Moving a shared node moves every incident road endpoint with it while keeping each segment's authored tangent/curve intent attached to that endpoint.

## Conversion to visual geometry

`ProceduralRoadGraph::spline_for(id)` resolves the two endpoint nodes and returns the existing `RoadSplineSegment` contract:

```text
node A
  + start_handle
      -> cubic Bezier centerline
  + end_handle
node B
      -> RoadMeshBuilder
      -> RoadMesh
      -> CH_CAMERA_V1 projection
      -> SDL_RenderGeometry
```

The graph therefore owns topology; `RoadMeshBuilder` owns sampled visual geometry. They remain separate so moving a node does not require storing redundant mesh vertices in the save model.

## Junction semantics

Node degree is intentionally exposed now because it becomes the deterministic junction classifier later:

- degree 0 — isolated node;
- degree 1 — road end;
- degree 2 — continuation, bend or grade transition;
- degree 3 — T/merge family;
- degree 4 — four-way/intersection family;
- degree >4 — complex junction/roundabout/connector family requiring an explicit junction recipe.

This stage does not yet generate intersection pavement. It only establishes the topology needed for a future `RoadJunctionBuilder`.

## Elevation

Node positions carry `z` using the same world units as `CH_PROCEDURAL_ROAD_MESH_V1`.

This enables topology such as:

- ground road crossing under an elevated road without sharing a node;
- ramp nodes with gradually changing Z;
- bridge and viaduct spans;
- future clearance validation.

Two segments crossing in XY are **not** connected unless they explicitly share a node. This is required so a viaduct can cross a ground road without becoming an intersection.

## Mutation behavior

The initial graph supports deterministic operations needed by MapForge tooling:

- add node;
- add segment only when both nodes exist and are distinct;
- move node;
- query node/segment by stable ID;
- list segments connected to a node;
- query node degree;
- convert a graph segment to a cubic spline;
- remove segment;
- remove node and its incident segments;
- clear graph and reset ID allocation.

Removing a node removes all incident segments so dangling references cannot survive inside the graph.

## Current non-goals

`CH_PROCEDURAL_ROAD_GRAPH_V1` does not yet:

- replace `RoadManager`;
- serialize into production saves;
- calculate construction cost;
- claim building-road access;
- drive vehicle pathfinding;
- solve lane merging;
- create junction pavement;
- create bridge supports;
- infer intersections solely from line crossing;
- remove the existing 16-mask PNG fallback.

## Migration gates

Before the graph becomes production gameplay authority:

1. **Visual mesh gate** — smooth S-curves, ramps and elevated spans align under all four camera rotations.
2. **MapForge editing gate** — nodes and handles can be created/moved without projection drift.
3. **Junction gate** — degree-2/3/4 nodes produce deterministic watertight junction geometry.
4. **Grid compatibility gate** — graph coverage can answer legacy building access/ownership checks during migration.
5. **Lane gate** — lane centerlines and turn connectors are deterministic and vehicles can follow them.
6. **Save gate** — stable node/segment IDs serialize losslessly and old tile-road saves remain loadable.
7. **Fallback gate** — disabling procedural roads still renders/plays the current tile network until migration is explicitly completed.

## Relationship to CH Math Worker

Agents should use `CH_MATH_WORKER_V1` for reusable projection, Bézier and mesh calculations. The C++ graph remains runtime/editor authority; the worker must mirror contracts rather than invent alternate topology or camera rules.
