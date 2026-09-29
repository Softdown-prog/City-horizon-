# CH_PROCEDURAL_ROAD_NAV_V1

Status: experimental, parallel to `CH_ROAD_TRAFFIC_V1`.

## Purpose

Provide deterministic continuous navigation over `ProceduralRoadGraph` without changing the legacy tile traffic/save contract yet.

## Authority

- Topology authority: explicit `ProceduralRoadGraph` nodes and segments.
- Geometry authority: `RoadSplineSegment` / `RoadMeshBuilder` cubic Bezier sampling.
- Camera/projection authority remains `CH_CAMERA_V1` in `src/ch_core/projection.*`.
- Runtime Blender dependency is forbidden; CH Blender remains offline authoring only.

## Core invariants

1. A geometric XY crossing is not a connection. Roads connect only through a shared graph node.
2. `z` travels with every sampled lane point, so an overpass route remains elevated.
3. Route traversal can use a segment in either authored direction.
4. Right-hand lane offset is derived from the actual travel tangent, not from tile/cardinal direction.
5. The tile-based `CH_ROAD_TRAFFIC_V1` remains the runtime fallback until procedural traffic, save/load, placement and visual gates pass.

## API

`ProceduralRoadNavigator::find_route(...)`

Returns a node/segment route through explicit graph connectivity.

`ProceduralRoadNavigator::sample_right_hand_lane(...)`

Converts that route into continuous `(x,y,z)` lane points sampled along the Bezier segments. Shared graph nodes are de-duplicated between adjacent sampled segments.

## Migration sequence

1. Validate spline/junction visuals in MapForge2.
2. Validate route/lane sampling, reverse traversal and overpass isolation.
3. Add continuous vehicle progress on sampled/arc-length road lanes.
4. Add junction turn connectors and lane choice.
5. Add save/load schema for procedural road graph.
6. Move placement/pathfinding authority from `RoadManager` tiles to the procedural graph only after all gates pass.
