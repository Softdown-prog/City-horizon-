# CH_PROCEDURAL_ROAD_SIGNALS_V1

## Purpose

`CH_PROCEDURAL_ROAD_SIGNALS_V1` adds deterministic fixed-phase traffic control to explicit procedural-road junction nodes.

It is layered on top of `CH_PROCEDURAL_ROAD_JUNCTION_RESERVATION_V1`. Signals decide which approach may request a junction; the reservation system still guarantees one active vehicle owner for the conservative V1 conflict zone.

The system remains parallel to the legacy tile-based `TrafficVehicleManager` and does not replace save/load, legacy traffic or runtime road authority.

## Runtime implementation

The contract is implemented in `src/procedural_road_traffic.h`.

A signalized junction is registered by `ProceduralRoadNodeId` with `add_signalized_junction(...)`.

Each signal owns:

- its explicit graph node ID;
- current `ProceduralRoadSignalPhase`;
- elapsed phase time;
- `green_duration`;
- `clearance_duration`.

The V1 phase cycle is:

1. `east_west_green`
2. `all_red_to_north_south`
3. `north_south_green`
4. `all_red_to_east_west`
5. repeat

World approach classification is deterministic: if `abs(forward.x) >= abs(forward.y)` the vehicle is considered an east/west approach; otherwise it is a north/south approach.

## Reservation integration

Unsignalized junctions keep the existing reservation behavior.

For a signalized junction:

- a vehicle may request a free junction only when its approach has green;
- during either all-red clearance phase, no approaching vehicle receives a new reservation;
- a vehicle blocked by a red signal receives the same kinematic stop cap used by reservation conflicts;
- `signal_blocked_junction` identifies a red-signal block separately from the generic `blocked_junction` diagnostic;
- if a signal changes after a vehicle has reserved the junction but before it enters, that reservation is released when the approach is no longer permitted;
- if a vehicle is already inside the junction connector, it keeps the reservation and is allowed to clear the conflict zone even after the phase changes.

This last rule prevents a vehicle from freezing in the middle of an intersection.

## Safety and topology

Signals attach only to explicit `ProceduralRoadNodeId` values already present in continuous routes.

A geometric XY crossing that is not a shared graph node is not signalized and does not become a traffic conflict. This preserves ramps, bridges and viaducts crossing roads at another elevation.

The all-red clearance phases intentionally leave a short deterministic gap between competing axis greens. V1 favors correctness and debuggability over throughput.

## Public inspection

The traffic manager exposes:

- `is_signalized_junction(node_id)`;
- `junction_signal_phase(node_id)`;
- `junction_signal_allows(node_id, forward)`;
- `signal_states()`;
- `signal_blocked_junction` per procedural traffic instance.

These are runtime/test diagnostics and are not yet a save-game format or player-facing UI contract.

## Validation gate

`src/procedural_road_lane_connector_test.cpp` covers a shared four-way crossing with one horizontal and one vertical vehicle.

The test verifies:

- east/west is initially green;
- the east/west vehicle receives the reservation first;
- the north/south vehicle is marked as signal-blocked;
- both vehicles never occupy the connector simultaneously;
- an all-red phase is observed;
- north/south eventually receives green;
- the north/south vehicle then owns the reservation while crossing.

A green project runner is still required before this contract is considered compile-validated.

## Explicit non-goals for V1

V1 does not yet implement:

- adaptive or traffic-actuated phase timing;
- road-class priority plans;
- protected left/right turn arrows;
- multiple simultaneous non-conflicting movements;
- lane-specific signal heads;
- pedestrian crossing phases;
- emergency vehicle pre-emption;
- coordinated green waves across adjacent intersections;
- stop/yield sign control;
- player-facing signal placement/editing UI;
- signal persistence in save/load;
- visual traffic-light props or emissive red/yellow/green animation.

Those can be layered on the same node/reservation contracts after the fixed-phase behavior is compile- and gameplay-validated.
