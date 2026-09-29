# CH_PROCEDURAL_ROAD_PRIORITY_CONTROL_V1

## Purpose

`CH_PROCEDURAL_ROAD_PRIORITY_CONTROL_V1` adds unsignalized intersection control to City Horizon's experimental procedural traffic system.

It sits on top of the existing continuous road route, vehicle follower, car-following and junction-reservation layers. It does not replace the legacy tile-based `TrafficVehicleManager`.

The first version supports three approach controls:

- `priority`
- `yield`
- `stop`

A policy is attached to an explicit `ProceduralRoadNodeId` and currently classifies approaches by the two canonical world axes:

- East/West
- North/South

This is intentionally a small deterministic traffic rule, not a complete traffic-law simulation.

## Runtime API

The implementation lives in `src/procedural_road_traffic.h`.

`ProceduralRoadJunctionPriorityPolicy` contains:

- `node_id`
- `east_west`
- `north_south`
- `stop_hold_duration`
- `stop_speed_threshold`

Policies are configured through `ProceduralRoadTrafficManager::set_junction_priority_policy(...)` and can be removed with `remove_junction_priority_policy(...)`.

Read-only inspection is available through:

- `junction_priority_policy(node_id)`
- `junction_approach_control(node_id, forward)`
- `priority_policies()`

## Arbitration order

For an unsignalized junction with a priority policy, reservation requests are ordered conservatively:

1. a vehicle already inside the connector;
2. `priority` approach;
3. `yield` approach;
4. `stop` approach after its mandatory stop has been satisfied;
5. route distance to the junction;
6. stable `vehicle_id` as the deterministic tie breaker.

A vehicle that already owns the junction is never pre-empted merely because a higher-priority approach appears later. It finishes the committed crossing first.

This preserves the one-owner-per-node safety rule from `CH_PROCEDURAL_ROAD_JUNCTION_RESERVATION_V1`.

## YIELD behavior

A `yield` approach may request the junction while it is free.

When a `priority` and a `yield` approach request the same free junction in the same arbitration pass, the `priority` approach wins even if the yield vehicle has a lexicographically earlier ID or an equal geometric distance.

Once a yield vehicle has already obtained the reservation, a newly arriving priority vehicle does not revoke it. The priority vehicle waits for the current crossing to clear.

This V1 behavior is deliberately deterministic and avoids reservation thrashing.

## STOP behavior

A `stop` approach cannot obtain a reservation merely by entering the request lookahead.

The manager first applies the normal junction braking cap and brings the vehicle to the configured stop line before the connector. The vehicle must then remain at or below `stop_speed_threshold` for at least `stop_hold_duration`.

Only after that hold is satisfied may the vehicle participate in reservation arbitration.

The manager exposes per-vehicle diagnostic state:

- `stop_wait_junction`
- `stop_wait_elapsed`
- `priority_blocked_junction`

After a STOP-controlled vehicle wins the reservation, the approach braking cap is released so it can leave the stop line and enter the junction. The stop-wait state is cleared after it enters/leaves the controlled approach.

## Signal precedence

Traffic signals have higher authority than STOP/YIELD/priority policies.

If a node is both signalized and has a priority policy:

- the current signal phase decides whether an approach may request the junction;
- the priority policy does not override a red or all-red phase;
- STOP dwell is not required while the node is under active signal control;
- a vehicle already inside continues through under the existing reservation safety rule.

This allows a junction to retain a fallback policy while being operated by a signal controller.

## Topology and elevation

Policies are keyed only by explicit graph node IDs.

A geometric XY crossing without a shared graph node is not a junction and therefore receives no STOP, YIELD or priority arbitration. Roads on different elevations continue to remain independent unless their graph topology explicitly connects them.

## Current validation source

`src/procedural_road_priority_control_test.cpp` covers:

- `priority` beating `yield` on simultaneous requests;
- the yield vehicle waiting until the priority vehicle clears;
- STOP preventing reservation before a real stop and dwell;
- STOP reservation being released from the braking cap after the hold;
- signal control overriding an otherwise conflicting priority policy.

The source is intentionally standalone and uses manually sampled continuous routes so it tests traffic arbitration without depending on MapForge or visual assets.

A project-runner compile/test result is still required before this contract is considered compile-validated.

## Explicit non-goals for V1

V1 does not yet implement:

- road-class metadata such as arterial/collector/local;
- automatic policy generation from road class;
- right-of-way by turn movement;
- simultaneous non-conflicting movements inside a large junction;
- arrival-time ordering for all-way STOP;
- pedestrian priority/crosswalk phases;
- emergency-vehicle pre-emption;
- roundabout yield logic;
- persistence in save/load.

Those can be added later without changing the core continuous-road graph or follower contracts.
