# CH_PEDESTRIAN_NAVIGATION_V1

Status: DESIGN CONTRACT / NOT YET IMPLEMENTED

## Goal

Define the scalable navigation and behavior architecture for City Horizon visitors, residents, workers and other pedestrian-like agents without replacing the current proven tile topology prematurely.

This contract is an evolution of the existing `NavigationNetwork` / `PedestrianSystem` runtime. It keeps the current tile network as the authoritative source of connectivity and introduces a derived decision graph only when population scale makes whole-grid route searches too expensive.

The design is inspired by classic tycoon-style crowd movement principles, but the values in this document are City Horizon defaults, not claims about any specific historical game's internal implementation.

## Current runtime baseline

The runtime already has:

- `NavigationNetwork`, an entity-agnostic N/E/S/W topology interface;
- `RoadNavigationNetwork` for vehicles;
- `PedestrianLaneNavigationNetwork`, currently derived from road topology;
- `SidewalkNavigationNetwork` for walkable sidewalk topology;
- uniform-cost BFS over tiles through `find_navigation_path()`;
- `PedestrianSystem`, which consumes a route, moves continuously between waypoints, validates the remaining path after topology changes and replans once before stopping;
- visual animation state kept outside navigation.

These systems remain valid. V1 of this contract does **not** require deleting or bypassing them.

## Core principle

Navigation is split into four responsibilities:

```text
Tile topology
    -> compressed decision graph
    -> agent behavior / goal selection
    -> budgeted route planning
    -> route execution by PedestrianSystem
```

Rendering and animation remain consumers of locomotion state. They do not choose routes.

## 1. Authoritative tile topology and derived decision graph

### 1.1 Tile topology remains authoritative

Roads, sidewalks and future path types continue to expose connectivity through `NavigationNetwork`.

The decision graph is a cache derived from that topology. It must never become a second independent source of truth.

If the player changes a road/path, the affected graph region is marked dirty and rebuilt from the updated tile network.

### 1.2 Decision nodes

A tile becomes a decision node when at least one of these conditions is true:

- it has 3 or 4 valid connections;
- it is a dead end;
- it has exactly 2 connections that form a 90-degree turn;
- it is a semantic destination or portal;
- it is an entrance/exit to a navigation region such as a plaza;
- game logic explicitly marks it as a decision point.

A straight tile with exactly two opposite connections is normally **not** a decision node.

### 1.3 Compressed edges

A maximal chain of ordinary linear tiles between two decision nodes is represented as one graph edge.

Recommended logical record:

```text
NavigationEdge
    from_node_id
    to_node_id
    length_tiles
    traversal_cost
    entry_direction
    exit_direction
    navigation_class
    capacity_hint
    flags
```

Use stable node IDs/indices rather than raw pointers so the cache can be rebuilt safely.

The full tile chain may still be stored or regenerated for actual movement. Compression reduces planning work; it does not remove tile-accurate route execution.

### 1.4 Semantic destinations

The following may register graph terminals/portals:

- building entrances;
- attraction entrances/exits;
- shops and service points;
- transit stops;
- employee/work destinations;
- farm/traktor interaction points where pedestrian navigation is relevant;
- queue entrances;
- plaza/path portals.

A dead end containing a useful destination is therefore not considered an empty dead end.

## 2. Separate behavior state from locomotion/animation state

City Horizon must not overload the existing visual `idle` / `walking` state with AI intent.

Use two layers:

```text
BehaviorState
    WANDERING
    SEEKING_GOAL
    APPROACHING_DESTINATION   (future)
    WAITING / QUEUING         (future)
    INSIDE_ACTIVITY           (future)

LocomotionState
    IDLE
    WALKING
```

The behavior layer selects destinations and routes.

The locomotion layer describes whether the agent is physically moving and continues to drive the animation system.

### 2.1 WANDERING

The agent has no urgent destination.

It follows its current graph edge without pathfinding. A new local choice is normally made only when it reaches a decision node.

### 2.2 SEEKING_GOAL

The agent has a semantic target such as home, shop, workplace, attraction, queue, service point or exit.

It uses the budgeted graph planner described below.

If the target disappears or becomes unreachable, policy decides whether the agent:

- chooses a replacement goal;
- falls back to `WANDERING`;
- waits and retries later.

For the first implementation, falling back to `WANDERING` is acceptable.

## 3. Local junction choice for WANDERING

A wandering agent should not run a full route search at every tile.

At a decision node:

### Step 1 — collect hard-valid exits

Only exits that pass authoritative topology rules are candidates.

A randomness rule must **never** permit an agent to:

- cross a missing edge;
- enter a non-navigable tile;
- ignore a hard access restriction;
- walk through a building or blocked topology.

### Step 2 — empty dead-end pruning

Temporarily remove exits whose branch terminates in a dead end with no useful destination or navigation portal.

If pruning removes every exit, restore the original hard-valid set so the agent cannot become stuck merely because all local choices are poor.

### Step 3 — short-term anti-loop policy

An immediate U-turn or recently visited branch may receive a penalty.

It is a penalty, not an absolute prohibition. A U-turn must remain possible when it is the only valid escape.

### Step 4 — configurable exploration chance

Use a small configurable probability to bypass *preference rules* and choose uniformly among the hard-valid connected exits.

Initial tuning candidate:

```text
wandering_exploration_probability = 0.033
```

This value is not a hard contract. It exists to avoid perfectly robotic repetition and must be tuned from gameplay observation.

Exploration bypasses soft pruning/preferences only; it never bypasses topology validity.

### Step 5 — straight-line bias

If continuing in the current direction is valid and there is at least one alternative, use an initial tuning candidate of:

```text
straight_ahead_probability = 0.50
```

Recommended interpretation:

- 50%: continue straight;
- remaining 50%: choose among the other valid exits using equal or weighted probability.

This makes the straight probability unambiguous instead of accidentally counting it twice.

If straight is the only valid exit, take it.

All percentages remain data/tuning values rather than constants embedded throughout gameplay code.

## 4. Budgeted goal seeking

A compressed graph has weighted edges because one edge may represent many tiles. Therefore the scalable planner should use bounded A* or bounded Dijkstra rather than assuming every graph edge has equal cost.

The existing tile BFS remains useful for tests, small routes, diagnostics and fallback.

### 4.1 Do not plan every tick

Pathfinding should normally run only when:

- an agent receives a new goal;
- it reaches the end of a partial planned segment;
- the target changes;
- its route becomes invalid after a topology edit;
- a higher-level activity explicitly requests replanning.

Movement ticks consume an existing route and should not perform a fresh global search.

### 4.2 Per-request budget

Initial candidate limits:

```text
max_decision_hops = 8
max_expanded_nodes = 64
```

The exact values must be profiled and tuned. Node-expansion budget is the primary CPU guard; hop budget also prevents very long partial plans.

### 4.3 Progressive planning

If the real goal is found inside the budget, return the route normally.

If the goal is outside the current budget:

1. inspect the reachable frontier discovered within budget;
2. score frontier nodes by estimated progress toward the final goal plus route cost and anti-loop penalties;
3. choose the best reachable intermediate node;
4. walk to that intermediate node;
5. request another bounded plan from there.

The chosen intermediate node must always be reachable through the explored topology. Euclidean/Manhattan distance alone may rank candidates, but must never create a route that ignores obstacles.

### 4.4 Short-term node memory

Each agent may retain a small ring buffer:

```text
recent_decision_nodes[4]
```

When planning a progressive route, recently visited nodes receive an additional cost penalty.

They are not forbidden absolutely because topology changes or cul-de-sacs may require backtracking.

This memory is intended to suppress oscillation such as:

```text
A -> B -> A -> B -> A
```

### 4.5 Global planning budget

Large crowds require a second protection in addition to per-agent limits.

Route requests should eventually be processed through a small planner queue with a maximum amount of navigation work per simulation tick/frame.

Example concept:

```text
NavigationPlannerBudget
    queued_requests
    max_node_expansions_per_tick
    max_requests_completed_per_tick
```

If the budget is exhausted, remaining agents continue their current valid route or wait until a later simulation tick. The renderer must never block waiting for pathfinding.

## 5. Determinism and crowd variation

Random wandering should be deterministic enough for reproducible debugging.

Recommended approach:

- each agent owns a small PRNG state seeded from stable simulation data such as agent ID plus city seed;
- do not use render-frame timing as a random seed;
- behavior randomness advances on behavior decisions, not every rendered frame.

This allows crowds to look varied while keeping bugs reproducible.

## 6. Topology edits and invalidation

The current `PedestrianSystem` already validates its remaining route and attempts one replan after a network change. Preserve that defensive behavior.

The future graph layer should add explicit topology versioning/dirty regions:

```text
navigation_topology_version
changed_tile_bounds
compressed_graph_version
```

When roads/paths change:

1. update the authoritative tile topology;
2. invalidate/rebuild only the affected compressed graph area where practical;
3. agents whose remaining edge/route intersects invalid topology request a replan;
4. unrelated agents keep walking.

Do not recompute every pedestrian route after every road edit.

## 7. Wide paths, double roads and plazas

This is a later scalability feature, not required for the first visitor slice.

### 7.1 Wide corridors

Do not blindly create a full decision graph node for every tile of a 2+ tile wide corridor.

A future corridor abstraction may expose one logical centerline/edge with metadata such as capacity and visual lane offsets.

The logical route may therefore be shared while rendering two or more pedestrians with small lateral offsets.

This optimization must respect the semantics of the underlying network. Vehicle roads and pedestrian sidewalks are not automatically interchangeable.

### 7.2 Plazas/open walkable regions

A large open plaza should eventually be represented as a `NavigationRegion` with a small set of boundary portals.

Planning happens between portals; movement inside the region may use a direct local steering segment when unobstructed.

Example:

```text
street edge
    -> plaza portal A
    -> local movement inside plaza
    -> plaza portal B
    -> street edge
```

Avoid creating a dense all-to-all junction graph for every tile inside a rectangular plaza.

## 8. Pedestrian and vehicle separation

The compressed graph concept may be reused by multiple network classes, but each network keeps its own traversal semantics.

Examples:

- vehicles: road/drivable topology;
- visitors on integrated road edges: `PedestrianLaneNavigationNetwork`;
- dedicated pedestrian paths: `SidewalkNavigationNetwork`;
- future parks/plazas: pedestrian region/portal network.

A shared graph builder is desirable; a shared rule set for all entity types is not.

## 9. Destination/interest layer

Navigation answers **how to reach a location**. It should not decide **why an agent wants to go there**.

Keep destination scoring in a behavior/activity layer.

Possible future goal scoring inputs:

- distance/travel cost;
- service demand;
- building capacity;
- queue length;
- price;
- visitor needs/preferences;
- opening/availability state;
- job/home assignment;
- random exploration weight.

After a goal is selected, navigation receives a target portal/node and plans toward it.

## 10. Recommended implementation order

Do not build the entire crowd architecture before the first functional visitors exist.

### Phase A — current vertical slice

Keep:

- tile `NavigationNetwork`;
- current BFS;
- current continuous pedestrian movement;
- current route invalidation/replan behavior;
- one/few test visitors.

Add only behavior state separation if gameplay begins needing autonomous visitors.

### Phase B — autonomous wandering

Add:

- `BehaviorState::WANDERING` / `SEEKING_GOAL`;
- junction detection from existing topology;
- local wandering decisions;
- dead-end metadata;
- four-node recent history;
- deterministic per-agent randomness.

This phase can still execute movement on tile routes.

### Phase C — compressed decision graph

Add:

- stable decision node IDs;
- compressed straight-chain edges;
- destination/portal nodes;
- incremental graph rebuild after topology edits;
- graph debug overlay/tests.

### Phase D — budgeted planning and crowd scale

Add:

- bounded A*/Dijkstra;
- progressive intermediate targets;
- per-agent and global expansion budgets;
- planner request queue;
- profiling with increasing visitor counts.

### Phase E — plazas and wide corridors

Only after actual map content requires them:

- navigation regions/portals;
- corridor centerline abstraction;
- visual lateral offsets/capacity hints.

## 11. Data and tuning candidates

Keep these values centralized in one navigation/behavior tuning structure rather than scattering magic numbers:

```text
wandering_exploration_probability = 0.033
straight_ahead_probability = 0.50
recent_node_history_size = 4
max_decision_hops = 8
max_expanded_nodes_per_request = 64
recent_node_penalty = configurable
```

They are initial candidates, not immutable gameplay contracts.

## 12. Non-goals

This contract does not authorize:

- replacing the current tile topology with a disconnected second map representation;
- running pathfinding every rendered frame;
- allowing random behavior to bypass blocked topology;
- mixing AI behavior state with animation state;
- rebuilding every route whenever one road tile changes;
- implementing local collision avoidance / ORCA / flocking before crowd density proves it is needed;
- implementing plaza/corridor abstractions before real gameplay maps require them.

## 13. Validation requirements

Every future implementation stage should have focused tests for:

- graph compression preserves tile reachability;
- turns/dead ends/intersections become correct decision nodes;
- semantic destinations survive dead-end pruning;
- wandering never chooses an invalid topology edge;
- recent-node penalty reduces two-node oscillation without making escape impossible;
- bounded planning never exceeds its node-expansion budget;
- progressive plans continue making reasonable goal progress;
- network edits invalidate only affected routes/graph regions where practical;
- pedestrian and vehicle network semantics remain separate;
- deterministic seeds reproduce the same junction choices.

The final acceptance test is still gameplay: many visitors must move naturally through a player-built city without visible oscillation, constant zig-zagging, frozen junctions or pathfinding spikes.
