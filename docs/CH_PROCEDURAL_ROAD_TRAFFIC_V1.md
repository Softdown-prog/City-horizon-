# CH_PROCEDURAL_ROAD_TRAFFIC_V1

## Purpose

`CH_PROCEDURAL_ROAD_TRAFFIC_V1` is the first runtime-facing owner for vehicles travelling on City Horizon's elastic procedural roads.

It remains parallel to the existing tile-based `TrafficVehicleManager`. The legacy manager stays the gameplay fallback until the procedural road system has passed runtime, visual, traffic-separation and save/load gates.

## Implementation

The contract is implemented by `src/procedural_road_traffic.h`.

`ProceduralRoadTrafficManager` owns zero or more `ProceduralRoadTrafficInstance` objects. Each instance contains:

- a stable caller-provided vehicle ID;
- one `ProceduralRoadVehicleFollower`;
- one `ProceduralRoadVehicleFollowerConfig`;
- one `ProceduralRoadVehicleVisual`.

The manager does not own road topology. Routes are produced upstream by `ProceduralRoadNavigator` and `ProceduralRoadRouteSampler`.

## Lifecycle

`add(...)` accepts an already sampled continuous procedural-road route, movement configuration and visual description. Empty IDs, duplicate IDs and invalid routes are rejected.

`update_tick(dt)` advances every follower deterministically by the supplied fixed-tick duration.

`render_entities()` converts each current follower pose through `ProceduralRoadVehicleRenderAdapter` and returns `std::vector<MobileEntityRenderData>`.

The logical render state is currently:

- `moving` while follower speed is positive and the route is incomplete;
- `stopped` before first acceleration and after the follower reaches the route end.

`remove(...)` and `clear()` own only procedural traffic instances and never modify the legacy traffic manager.

## Rendering boundary

The manager deliberately returns the existing shared mobile-render vocabulary rather than introducing a second renderer-facing vehicle type.

That means downstream code can eventually append procedural traffic entities to the same mobile render collection used by pedestrians and legacy vehicles.

`MobileEntityRenderData` now preserves continuous X/Y/Z, but elevated vehicle visual approval still requires the main mobile draw path to consume `visual_world_z` through the canonical 3D projection overload. This contract does not claim that final runtime draw integration is complete.

## Isolation rules

- Do not migrate `TrafficVehicleManager` to this manager implicitly.
- Do not mirror procedural routes back into tile routes merely for rendering.
- Do not create traffic connectivity from geometric XY crossings; only graph topology creates routes.
- Do not hard-code a placeholder road-car asset into this manager.
- Keep camera-relative sprite direction downstream in the existing runtime renderer.

## Next gates

Before procedural traffic can replace legacy city traffic, validate:

1. canonical mobile Z projection in runtime drawing;
2. approved four-direction road-vehicle sprites/animation;
3. multi-vehicle following distance and collision avoidance;
4. junction reservation/priority or signal control;
5. spawn/despawn and route reassignment;
6. save/load representation;
7. gameplay-scale visual proof on straight road, S-curve, intersection, ramp and viaduct;
8. elevated depth and occlusion against roads, bridges, buildings and other mobile entities.
