# CH_PROCEDURAL_ROAD_JUNCTION_LANES_V1

## Purpose

This contract defines continuous vehicle lane connectors inside explicit nodes of `ProceduralRoadGraph`.

It is a parallel migration layer. `CH_ROAD_TRAFFIC_V1` remains the runtime fallback until procedural traffic is validated end to end.

## Topology rule

A junction connector may exist only when the incoming and outgoing road segments share the same explicit `ProceduralRoadNodeId`.

A geometric crossing in XY is not a junction. This is required for viaducts, bridges and grade-separated roads.

## Movement classes

`ProceduralRoadTurnKind` classifies one incoming-to-outgoing movement as:

- `straight`
- `right`
- `left`
- `u_turn`

Classification uses the travel directions at the shared node, not tile orientation or sprite orientation.

## Geometry

`ProceduralRoadLaneConnectorBuilder` builds a cubic connector from the incoming right-hand lane anchor to the outgoing right-hand lane anchor.

The connector:

- stays at the shared node Z;
- uses endpoint tangents from the authored road splines;
- preserves right-hand traffic offset;
- is sampled deterministically;
- does not modify `RoadManager`, occupancy, save data or legacy traffic.

## Runtime migration sequence

1. Keep `TrafficVehicleManager` on tile routes as fallback.
2. Use `ProceduralRoadNavigator` to resolve graph routes.
3. Sample right-hand lane points on each road segment.
4. Insert a `ProceduralRoadLaneConnector` between consecutive route segments at every shared node.
5. Move vehicle anchors continuously through segment samples + connector samples.
6. Only after visual/gameplay validation, migrate production traffic and persistence away from tile-only routes.

## Validation gate

The focused contract test is `procedural_road_lane_connector_test`.

It must prove:

- straight connector;
- right-turn connector;
- left-turn connector;
- stable node elevation;
- deterministic sampling;
- no connector between grade-separated roads that merely cross in XY.
