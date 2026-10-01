# CH_COASTER_PHYSICS_V1

City Horizon keeps the coaster runtime 2D, but the logical track is a sampled 3D centerline. The train moves by **distance along that centerline** and its speed is updated by a small deterministic physics model.

## Core rule

Gravity is projected onto the local track tangent:

`a_g = -g * tangent.z`

With world Z pointing upward:

- uphill (`tangent.z > 0`) removes speed;
- downhill (`tangent.z < 0`) adds speed;
- flat track (`tangent.z = 0`) receives no gravity acceleration along the rail.

The ideal specific mechanical energy is:

`E/m = 0.5 * v^2 + g * h`

That gives the intended tycoon behavior: the train trades kinetic energy for height on climbs and gets it back on descents, minus losses.

## Losses

V1 applies three small losses on free-running track:

- rolling resistance;
- aerodynamic drag proportional to `v^2`;
- a small speed-proportional mechanical/bearing loss.

These values are gameplay-tunable. They are not intended to reproduce one real coaster manufacturer exactly.

## Lift hills

A separate visual lift-hill track piece is not required. A normal `slope_up` route segment can be flagged `DriveMode::Lift`.

The lift uses a target-speed controller with gravity/loss feed-forward, so it can pull a stopped train uphill and hold a stable chain-lift speed.

## Brakes and station

`DriveMode::Brake` converges toward a configured target speed. `DriveMode::Station` targets zero speed with a stronger deceleration limit.

## Curves and G forces

A flat curve does not create propulsion by itself. It redirects the velocity vector and therefore creates lateral G:

`lateralG = v^2 * horizontalCurvature / g`

Vertical curvature creates the familiar hill/valley loading:

`verticalG = cos(pitch) + v^2 * verticalCurvature / g`

By convention:

- positive vertical curvature = valley / concave-up -> more vertical G;
- negative vertical curvature = crest / concave-down -> less vertical G;
- `verticalG < 0.2` is exposed as an airtime signal for future ride ratings.

These outputs are deliberately already available for later **Excitement / Intensity / Nausea** scoring without making that rating system a dependency of the first moving-train slice.

## V1 stall behavior

If a free-running train reaches zero speed while still climbing, V1 reports a **forward stall**. It does not reverse the train yet. Rollback sprites and reverse route traversal are deferred so they do not block the simple coaster.

## Runtime integration path

1. Build/validate a connected `CH_COASTER_TRACK_V1` route.
2. Sample its 3D centerline at the train's current distance.
3. Feed tangent Z and local curvature into `ch::coaster::step`.
4. Advance route distance by the returned `distance_delta_m`.
5. Sample each individual car at its own distance offset.
6. Choose the appropriate `CH_COASTER_CAR_V1` heading/pitch sprite.
7. Use G-force telemetry later for ride ratings and debugging.

Implementation: `src/coaster_physics.h`  
Regression: `src/coaster_physics_test.cpp`  
Machine contract: `tools/ch_blender/contracts/ch_coaster_physics_v1.json`
