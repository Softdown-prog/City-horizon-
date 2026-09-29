# CH_PROCEDURAL_ROAD_ROUTE_V1

## Purpose

`CH_PROCEDURAL_ROAD_ROUTE_V1` defines the continuous vehicle path produced from the procedural road graph. It bridges the gap between graph routing and future runtime vehicle movement without changing the legacy tile traffic yet.

## Source hierarchy

A continuous route is derived only from:

1. `ProceduralRoadGraph` topology;
2. `ProceduralRoadNavigator::find_route(...)`;
3. right-hand lane samples from each traversed spline;
4. `CH_PROCEDURAL_ROAD_JUNCTION_LANES_V1` connectors at shared intermediate nodes.

Geometric XY overlap never creates topology. Roads at different elevations remain disconnected unless they deliberately share a graph node.

## Output

`ProceduralRoadRouteSampler::sample_right_hand_route(...)` returns one ordered sequence of `ProceduralRoadRoutePoint` values in world `(x,y,z)` coordinates.

Each point records whether it belongs to:

- a normal road lane; or
- a junction connector.

Lane points keep their source `segment_id`. Connector points carry the explicit `junction_node` and classified turn (`straight`, `right`, `left`, or `u_turn`).

## Continuity rule

For each intermediate node:

```text
incoming lane
    -> junction connector
    -> outgoing lane
```

The incoming lane endpoint is the connector start and the connector endpoint is the outgoing lane start. Shared endpoints are emitted only once so distance accumulation does not contain artificial zero-length duplicate samples.

The connector tangent is aligned with the incoming and outgoing spline tangents. This prevents tile-style direction snapping in the middle of a junction.

## Elevation

Normal lane samples retain spline elevation. Junction connectors use the shared node elevation. This permits ramps and elevated road networks while keeping overpass crossings independent.

## Runtime migration policy

`CH_ROAD_TRAFFIC_V1` remains the production fallback while vehicles still consume `std::vector<TileCoordinate>`.

Migration to procedural traffic should happen only after:

1. this route sampler passes its focused regression gate;
2. MapForge gameplay-scale visual proof confirms curves/junctions do not visibly jump;
3. a procedural vehicle follower proves stable speed, heading and separation along this world-space route;
4. save/load representation for procedural graphs is explicitly versioned.

Do not remove the tile-road fallback before those gates pass.
