# RCT / OpenRCT2 Simulation Engineering Lessons

Status: architectural reference for City Horizon. This document records techniques worth studying; it is not a claim that City Horizon should reproduce RollerCoaster Tycoon implementation details or 1990s hardware limitations.

## Principle

Adopt the engineering reason, not the historical limitation.

City Horizon is a modern SDL3/C++ city builder. It can use larger memory budgets, modern data structures and more capable pathfinding, while still benefiting from the same broad discipline that made large tycoon simulations practical: fixed simulation cadence, bounded work, deterministic decisions, explicit topology, and avoiding expensive global reasoning when local state already determines what an agent can do.

## Lessons that fit the current runtime

### 1. Separate render cadence from simulation cadence

The runtime already has `SimulationScheduler`. Mobile simulation uses a fixed 15 Hz step while frame rendering/interpolation remains independent. Keep this separation: higher display FPS must not accelerate pedestrians, vehicles, economy or future attraction physics.

The scheduler also caps catch-up work after a long stall. Preserve that protection against a spiral of death.

### 2. Route execution is not route planning

A moving pedestrian should consume the route it already owns. It should not repeat destination selection or home-reachability pathfinding every movement tick.

The autonomous decision layer should wake for actual decision events: route completion, activity completion, topology invalidation, weather policy after the current segment, target changes, or a retry timer.

This is now an explicit City Horizon rule. `PedestrianDecisionNode` short-circuits while the actor is walking or visiting; `PedestrianSystem` remains responsible for route execution and live-route invalidation/replan.

### 3. Cheap local decisions before global searches

The current tile `NavigationNetwork` remains authoritative. Do not replace it merely to imitate another game.

As crowds grow, prefer the staged design already described by `CH_PEDESTRIAN_NAVIGATION_V1`:

- local decisions at meaningful junctions;
- short recent-node memory to reduce oscillation;
- compressed decision graph only when profiling justifies it;
- bounded A*/Dijkstra for semantic destinations;
- progressive planning when a destination is outside the current search budget;
- a global pathfinding work budget per simulation tick.

### 4. Stagger expensive agent work

When City Horizon gains individual needs, happiness, shopping preferences, jobs or other expensive per-agent logic, do not evaluate every subsystem for every citizen on every simulation tick.

Use deterministic phases based on stable agent IDs / city seed so different groups receive heavy updates on different ticks. Locomotion may remain frequent while needs, destination scoring and economy decisions run at lower cadences.

Do not use render-frame timing as a phase or random seed.

### 5. Determinism is a debugging feature

Simulation randomness should eventually come from stable seeded PRNG state, not frame timing or `random_device` inside simulation decisions. Given the same save/state and inputs, behavior should be reproducible enough to diagnose routing and economic bugs.

Purely cosmetic randomness may remain separate from simulation state, but it must not influence path choice, money, capacities or activity outcomes unless it is seeded/persisted appropriately.

### 6. Explicit budgets beat accidental slowdowns

Future scaling work should expose deliberate limits such as:

- maximum navigation node expansions per request;
- maximum navigation work per simulation tick;
- maximum new spawns per tick;
- maximum expensive need/economy evaluations per tick;
- bounded catch-up ticks after a stall;
- explicit particle/audio concurrency where relevant.

When a budget is exhausted, defer work safely rather than blocking rendering or performing an unbounded burst.

### 7. Wide paths and plazas need region-aware thinking

Do not blindly model every cell of a wide plaza as an equally expensive decision junction. When real maps require it, follow `CH_PEDESTRIAN_NAVIGATION_V1`: use corridor/region abstractions and a small set of portals while keeping tile topology authoritative for actual movement validity.

### 8. Accumulate activity measurements, score later

For future rides and services, collect compact measurements during an activity and calculate its final rating/result at well-defined events rather than recomputing a full score every frame.

Possible City Horizon examples include duration, queue wait, capacity utilization, downtime, speed/forces for rides, service satisfaction and price perception.

## Numeric safety

City Horizon does not need to reproduce historical 8/16/32-bit overflow behavior. Use modern integer widths deliberately, validate conversions and clamp externally authored/economic values where overflow or wraparound could create invalid simulation state.

Fixed-point math should be adopted only where deterministic cross-platform behavior or exact economic units justify it. Money should remain integer minor units. Do not replace suitable floating-point presentation/interpolation math merely for nostalgia.

## Current implementation notes

As of September 2026:

- `SimulationScheduler` provides fixed-rate mobile ticks and bounded catch-up.
- `PedestrianSystem` executes an existing route and replans once when live topology invalidates the remaining route.
- `PedestrianDecisionNode` owns the small autonomous home/activity state machine.
- Active walking/visiting now bypasses decision-layer reachability searches until a new decision is possible.
- A resident already standing on its candidate home entrance does not run BFS to prove reachability to the same tile.
- `CH_PEDESTRIAN_NAVIGATION_V1` remains the source for future crowd-scale navigation work; do not implement all later phases before profiling demonstrates the need.

## Source-use rule

Videos, community explanations and historical reverse-engineering notes are useful leads, not automatically authoritative specifications. Before City Horizon depends on a precise historical claim, verify it against current OpenRCT2 source/documentation or another primary source. The architectural lessons above are kept because they stand on their own even when a historical detail is simplified.
