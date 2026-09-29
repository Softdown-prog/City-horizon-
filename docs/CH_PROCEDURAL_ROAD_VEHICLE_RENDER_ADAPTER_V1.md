# CH_PROCEDURAL_ROAD_VEHICLE_RENDER_ADAPTER_V1

## Purpose

Bridge the continuous procedural-road vehicle pose into City Horizon's existing 2D mobile-entity rendering contract without replacing `TrafficVehicleManager` yet.

The game remains 2D. Procedural road traffic supplies continuous logical world coordinates and elevation; the renderer still consumes pre-rendered 2D sprites.

## Contract

`src/procedural_road_vehicle_render_adapter.h` converts `ProceduralRoadVehiclePose` into `MobileEntityRenderData`.

The adapter owns:

- conversion from a world-space forward vector to the four logical directions SOUTH/EAST/NORTH/WEST;
- selection of the logical directional sprite supplied by `ProceduralRoadVehicleVisual`;
- transfer of continuous X/Y/Z into `MobileEntitySpatialState`;
- zero ground-anchor offset for procedural lane points, because the sampled lane position is already the exact world contact point;
- art scale and sprite anchor metadata.

The adapter does **not** own camera rotation. `camera_relative_mobile_entity(...)` remains the runtime authority for rotating logical entity direction into the current camera view.

## Mobile entity elevation

`MobileEntitySpatialState` now contains:

- `logical_world_z`;
- `visual_world_z`.

Both default to zero. Existing pedestrians, service vehicles and other tile-bound actors therefore keep their old behavior without call-site changes.

Procedural vehicles copy their follower pose Z into both fields.

## Current runtime boundary

At the time this contract was introduced, the main runtime mobile draw path still projects mobile entities from `visual_world_x` and `visual_world_y` only. Therefore:

- the procedural pose and render data preserve correct elevation;
- existing ground-level mobile rendering remains unchanged;
- a vehicle on an elevated procedural road is **not yet visually approved** until the runtime draw anchor consumes `visual_world_z` through the canonical `ch::world_to_screen_point(x, y, z, ...)` projection;
- general elevated-entity occlusion/depth ordering is a later visual gate and must not be inferred as solved by this adapter.

## Direction rule

The logical world direction is derived from the dominant planar component of the follower's forward vector:

- +X -> EAST;
- -X -> WEST;
- +Y -> SOUTH;
- -Y -> NORTH.

Camera-relative rotation remains downstream.

## Visual assets

The adapter receives a `ProceduralRoadVehicleVisual` instead of hard-coding a car asset path. No generic road-car sprite should be invented or promoted merely to satisfy this plumbing layer. A road vehicle must use an approved four-direction sprite/animation set before visual acceptance.

## Migration rule

`CH_ROAD_TRAFFIC_V1` remains the gameplay/runtime fallback. The procedural adapter may be connected to live traffic only after:

1. canonical Z projection is consumed by mobile drawing;
2. an approved road-vehicle visual exists;
3. the vehicle is inspected on straight road, S-curve, junction, ramp and viaduct at gameplay scale;
4. camera rotation is visually checked in all four canonical views;
5. elevated depth/occlusion behavior is explicitly validated.
