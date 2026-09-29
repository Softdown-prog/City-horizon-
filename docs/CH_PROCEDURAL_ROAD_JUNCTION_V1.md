# CH_PROCEDURAL_ROAD_JUNCTION_V1

## Purpose

`CH_PROCEDURAL_ROAD_JUNCTION_V1` is the first deterministic pavement-junction layer for City Horizon's elastic road system.

It consumes explicit `CH_PROCEDURAL_ROAD_GRAPH_V1` topology and produces a small central `RoadMesh` patch that joins the ribbons generated for incident segments. It does not infer connectivity from screen-space or XY line intersections.

## Topology authority

A junction exists only when multiple `ProceduralRoadGraphSegment` objects reference the same `ProceduralRoadNodeId`.

This rule is mandatory for elevated infrastructure:

- a ground road at `z=0` may cross an elevated road at `z>0` in the same XY region;
- if they do not share a graph node, they are not connected;
- therefore a viaduct does not accidentally become a four-way intersection.

## Classification

`RoadJunctionBuilder::classify(...)` maps graph degree to the first-stage junction family:

- missing node -> `invalid`;
- degree 0 -> `isolated`;
- degree 1 -> `end`;
- degree 2 -> `continuation`;
- degree 3 -> `tee`;
- degree 4 -> `intersection`;
- degree >4 -> `complex`.

Classification is topology only. It does not yet decide traffic priority, signals, lane arrows or turn restrictions.

## Patch construction

`RoadJunctionBuilder::build_patch(...)` currently builds pavement for degree >=2.

For every incident segment it:

1. resolves the tangent from the endpoint's relative Bézier handle;
2. falls back to the vector toward the opposite node if the handle is degenerate;
3. normalizes the planar tangent;
4. moves a short distance down the incident arm;
5. computes left/right edge points using half the segment width;
6. places those points at the junction node's Z elevation;
7. sorts all boundary points by angle around the node;
8. emits a triangle fan from the node center.

The patch deliberately overlaps a short part of every incident road ribbon. This prevents terrain/alpha cracks between independently sampled meshes at fractional zoom.

## UV contract

The initial patch uses planar world-relative UVs centered on `(0.5, 0.5)`. This is sufficient for a continuous asphalt source texture and avoids reintroducing a fixed atlas of intersection PNGs.

Future material work may add separate channels for lane paint, curb boundaries and masks, but pavement topology must remain independent of a particular texture atlas.

## Elevation

The first patch is flat at `ProceduralRoadNode.position.z`.

This supports:

- flat ground junctions;
- flat elevated junctions;
- bridge/viaduct nodes at a common elevation.

A later grade-aware junction layer may interpolate arm elevation near a node. That extension must not change the graph rule that connectivity comes from shared node identity.

## Current non-goals

This version does not yet create:

- lane centerline connectors;
- left/right-turn paths;
- traffic signals or priority rules;
- stop lines or crosswalk paint;
- medians/islands;
- roundabout-specific geometry;
- curb/sidewalk junction meshes;
- bridge supports;
- automatic intersection creation from two crossing splines.

## Validation gate

The focused navigation regression test covers the topology/geometry invariants needed before visual promotion:

- degree-3 node classifies as a T junction and emits a non-empty patch;
- degree-4 node classifies as an intersection and emits a non-empty patch;
- moving a shared node updates spline endpoints while relative handles remain attached;
- junction vertices inherit the node elevation;
- two geometrically crossing roads that share no node remain independent ends;
- removing a node removes its incident segments and stable IDs are not reused.

After these deterministic checks pass, the next visual gate is to draw graph segments plus their junction patches together in the MapForge procedural-road preview and inspect T/cross seams at gameplay scale.
