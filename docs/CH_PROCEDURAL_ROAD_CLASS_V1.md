# CH_PROCEDURAL_ROAD_CLASS_V1

## Purpose

`CH_PROCEDURAL_ROAD_CLASS_V1` adds deterministic road hierarchy metadata to City Horizon's experimental procedural road system.

The first supported classes are:

- `local`
- `collector`
- `arterial`

`unspecified` exists only as a compatibility state for routes created without class metadata.

This contract stays parallel to the legacy tile-based road/traffic system while procedural roads are still passing runtime and gameplay gates.

## Segment metadata

The implementation lives primarily in:

- `src/procedural_road_class.h`
- `src/procedural_road_classified_route.h`
- `src/procedural_road_class_policy.h`
- `src/procedural_road_vehicle_follower.h`

Road class is stored in `ProceduralRoadClassCatalog`, keyed by the stable `ProceduralRoadSegmentId` from `ProceduralRoadGraph`.

The class catalog is deliberately separate from the graph structure in V1. This preserves the already-established graph topology/ID contract while road hierarchy is proven. Semantically the class still belongs to the segment identified by that stable ID.

A catalog entry can be assigned only to a segment that exists in the supplied graph. Missing explicit entries use the catalog default, which is currently `local`.

## Class profiles

V1 defines these traffic speed limits in world units per second:

| Class | Speed limit | Priority rank |
| --- | ---: | ---: |
| local | 1.35 | 1 |
| collector | 1.70 | 2 |
| arterial | 2.10 | 3 |
| unspecified | no class cap | 0 |

The speed limit is a cap, not a forced vehicle speed. A vehicle whose own `cruise_speed` is lower remains slower.

The follower therefore uses the minimum of:

1. vehicle cruise speed;
2. current road-class speed limit;
3. junction/turn speed limits;
4. car-following cap;
5. signal/reservation/STOP cap.

This keeps one deterministic speed-limiting pipeline instead of adding a separate class-specific vehicle mover.

## Route propagation

`ProceduralRoadRoutePoint` now carries `road_class`.

Existing callers of `ProceduralRoadRouteSampler` remain compatible and produce `unspecified` class metadata unless a class-aware route is requested.

`ProceduralRoadClassifiedRouteSampler` decorates the canonical continuous route from a `ProceduralRoadClassCatalog`:

- normal lane samples receive the class of their graph segment;
- a junction connector inherits the class of the incoming approach;
- the class changes to the outgoing segment as soon as the vehicle leaves the connector.

The vehicle follower exposes the current class on `ProceduralRoadVehiclePose` and applies its speed cap automatically.

## Automatic junction priority

`ProceduralRoadClassPolicyBuilder` derives unsignalized junction policies from the connected segment classes.

For every explicit graph junction with degree 3 or greater, it inspects the endpoint handles to determine the local East/West versus North/South approach axis. The highest class rank present on each axis is compared.

Rules:

1. arterial outranks collector;
2. collector outranks local;
3. the higher-ranked axis receives `priority`;
4. the lower-ranked axis receives `yield`;
5. equal-ranked axes both receive `priority`, after which the existing deterministic reservation distance/ID rules arbitrate the crossing.

`apply_all_junction_policies(...)` can populate policies for an entire procedural graph, avoiding manual configuration of every ordinary intersection.

## Authority order

The runtime authority remains:

1. active traffic signal phase;
2. explicit hand-authored STOP/YIELD/priority policy;
3. generated road-class priority policy;
4. deterministic reservation distance and stable vehicle ID tie break.

A caller may replace a generated policy through the existing `set_junction_priority_policy(...)` API when a particular intersection needs a special STOP/YIELD arrangement.

Signals continue to override any priority policy attached to the same graph node.

## Topology rule

Road classes do not create connectivity.

A geometric XY crossing on different graph segments remains disconnected unless both roads share an explicit graph node. Therefore an arterial viaduct passing over a local road does not create a class conflict, reservation or junction policy merely because their projected geometry crosses.

## Validation

The focused source `src/procedural_road_class_test.cpp` covers:

- catalog default and explicit segment classes;
- canonical class speed profiles;
- class propagation through a lane/junction/lane route;
- automatic follower speed limiting for local, collector and arterial roads;
- automatic junction policy generation with arterial priority over local;
- equal-class fallback to equal-priority reservation arbitration.

`.github/workflows/ch-procedural-road-priority-check.yml` compiles and executes this test together with the existing STOP/YIELD/priority gate using C++20 on the lightweight Ubuntu runner.

The first class-aware validation run, GitHub Actions run `36621774227`, completed successfully. Both the existing priority-control compile/run steps and the new road-class compile/run steps passed.

## Explicit non-goals for V1

V1 does not yet implement:

- persistence in save/load;
- player-facing road-class construction UI;
- automatic lane-count/width changes from class;
- class-specific road textures or markings;
- congestion-aware class upgrades;
- automatic signal installation at high-capacity intersections;
- speed signage or enforcement visuals;
- vehicle-type restrictions by road class.

Those features can build on this metadata contract after the class-aware traffic behavior is validated in runtime and MapForge.