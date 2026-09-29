# CH_PROCEDURAL_ROAD_JUNCTION_RESERVATION_V1

## Purpose

`CH_PROCEDURAL_ROAD_JUNCTION_RESERVATION_V1` prevents procedural-road vehicles from occupying the same explicit graph junction at the same time.

This is a traffic-arbitration layer for the experimental procedural road system. It remains parallel to the legacy tile-based traffic system and does not migrate or replace `TrafficVehicleManager`.

## Runtime components

The contract is implemented by:

- `src/procedural_road_vehicle_follower.h`
- `src/procedural_road_traffic.h`

`ProceduralRoadVehicleFollower::upcoming_junction(...)` reports the next explicit junction on the already sampled continuous route, including:

- graph node ID;
- remaining route distance to the connector;
- whether the vehicle is already inside that junction connector.

The follower does not decide priority. It only exposes deterministic route information.

`ProceduralRoadTrafficManager` owns junction reservations.

## Reservation rules

A reservation is keyed by `ProceduralRoadNodeId` and has one vehicle owner.

The V1 rules are deliberately simple and deterministic:

1. A vehicle already holding a reservation keeps it while that junction is still the current/upcoming junction on its route.
2. If a junction has no owner, approaching vehicles inside `request_lookahead` may request it.
3. A vehicle already inside an unowned junction has highest priority.
4. Otherwise the vehicle with the smallest route distance to the junction wins.
5. Exact-distance ties are broken lexicographically by stable `vehicle_id`.
6. Vehicles that do not own the junction receive an external speed cap that brings them to a stop before the connector.
7. The reservation is released after the owner has left that junction and its next upcoming junction is different or absent.

There is no random arbitration in V1, so identical simulation input produces identical ownership.

## Stop behavior

Blocked vehicles do not teleport, snap to tiles or modify their route.

The manager combines the junction stop cap with any existing car-following cap and the follower's normal road/junction speed limit.

The stop cap uses the remaining route distance and configured braking strength:

`v_max = sqrt(2 * braking * available_distance)`

where `available_distance` is the distance to the junction minus `stop_buffer`.

At or inside the stop buffer the external cap is zero.

## Topology rule

Reservations exist only for explicit procedural graph junction nodes already present in the sampled route.

A geometric XY crossing does not create a reservation target by itself. Therefore a road passing below a viaduct does not contend with traffic on the viaduct unless both roads intentionally share the same graph node.

This preserves the existing procedural-road rule that topology, not visual overlap, defines connectivity.

## Configuration

`ProceduralRoadJunctionReservationConfig` currently exposes:

- `enabled`
- `request_lookahead`
- `stop_buffer`

The manager also exposes diagnostic state per vehicle:

- `reserved_junction`
- `blocked_junction`

and read-only inspection through:

- `junction_owner(node_id)`
- `junction_reservation_count()`

These fields are intended for tests, debugging and future runtime overlays; they are not save-game format yet.

## Current validation gate

`src/procedural_road_lane_connector_test.cpp` now covers:

- upcoming-junction lookup from a continuous route;
- deterministic tie breaking between two equally distant vehicles;
- one reservation owner per shared node;
- the losing vehicle braking before the connector;
- no simultaneous connector occupancy in the test crossing;
- release and transfer of the reservation after the first vehicle exits.

A green build/test run is still required before this contract can be considered compile-validated on the project runner.

## Explicit non-goals for V1

V1 does not yet implement:

- traffic lights;
- stop/yield sign policy;
- road-class priority;
- protected turn phases;
- simultaneous non-conflicting movements through the same large junction;
- pedestrian crossing phases;
- emergency vehicle priority;
- deadlock recovery across multiple adjacent junctions;
- persistence in save/load.

The conservative one-owner-per-node policy is intentional for the first playable proof. It can later be refined into movement-level conflict zones without changing the road graph or continuous vehicle follower contracts.
