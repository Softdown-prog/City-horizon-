# CH_CAMERA_CONTRACT_V1

Status: **CANONICAL / FROZEN FOR PROJECTION GEOMETRY**

## Purpose

Define one visual camera contract for City Horizon runtime, MapForge2, Building Composer and Animation/Carousel Composer.

The target is the classic late-1990s/early-2000s tycoon read used by games such as Zoo Tycoon 1: fixed orthographic 2.5D presentation, strong top visibility, screen-vertical world height and a 2:1 dimetric ground diamond. This is a projection/style reference only; no third-party art, code or proprietary assets are copied.

## Canonical geometry

- Projection: orthographic dimetric.
- Perspective: disabled.
- World yaw: 45 degrees.
- Camera elevation: 30 degrees.
- Ground screen-axis angle: `atan(1/2)` = 26.56505117707799 degrees.
- Canonical logical tile render size: 128 × 64 px at zoom 1.
- Ground diamond ratio: 2:1.
- World height remains screen vertical.
- Camera rotations are quarter-turn logical world rotations before projection.
- Optional elevated geometry uses the canonical `world_to_screen_point(x, y, z, ...)` overload; Z changes screen height only and does not create a second ground/picking convention.

## Important correction

The previous metadata exposed 35.264 degrees as `kIsometricInclinationDeg`. That value belongs to mathematically true isometric projection and is inconsistent with a 2:1 diamond.

City Horizon does **not** use true-isometric 35.264-degree elevation as its visual camera. CH_CAMERA_V1 uses 30-degree orthographic elevation with 45-degree yaw, which produces the classic 2:1 dimetric ground read.

`kIsometricInclinationDeg` remains only as a compatibility alias and now resolves to the canonical 30-degree camera elevation. New code must use `kCameraElevationDeg`.

## Sources of truth

Projection implementation:

`src/ch_core/projection.cpp::ch::world_to_screen_point()`

Continuous inverse/picking implementation:

`src/ch_core/projection.cpp::ch::screen_to_world_point()`

Camera/grid constants:

`src/ch_core/contracts.h`

MapForge2 must consume those runtime definitions rather than maintain an independent projection formula.

## Runtime ↔ MapForge interaction parity

The MapForge map viewport is not a separate camera product. It follows the gameplay camera contract.

Required parity:

- `Z` rotates one quarter-turn counter-clockwise;
- `X` rotates one quarter-turn clockwise;
- all four canonical facings are supported (`r0`, `r90`, `r180`, `r270`);
- rotating the view preserves the logical world point currently under the viewport centre instead of making the map jump;
- pan and zoom continue in screen space through the shared `CameraState`;
- picking uses `screen_to_world_point` / `screen_to_tile_coord` from the same projection core;
- the canonical embedded viewport receives the exact same camera state used by the editor interaction layer.

`C++/MapForge2/src/engine_projection_adapter.*` is the MapForge bridge to the runtime camera core. `engine_projection_adapter_3` exposes ground projection, elevated projection, inverse projection, depth and focus-preserving quarter-turn rotation without duplicating the projection matrix.

## Deterministic capture parity

`MAPFORGE_CAPTURE_REQUEST_V1` remains backward compatible, but camera-aware captures should declare:

```json
"camera": {
  "contract": "CH_CAMERA_V1",
  "rotationQuarterTurns": 0,
  "zoom": 0.92,
  "focusTile": [0.0, 0.0],
  "focusScreen": [0.5, 0.72]
}
```

`rotationQuarterTurns` is normalized to `0..3`. A non-empty camera contract different from `CH_CAMERA_V1` is rejected rather than silently rendered with the wrong projection.

Candidates that genuinely represent elevated geometry may also declare:

```json
"elevationWorld": 1.25
```

The candidate ground anchor is then projected with the same canonical XYZ projection used by procedural roads/bridges in the game. Ground tiles remain at Z=0.

## Composer rules

1. Building, animation and ride geometry is authored in logical world space whenever placement/depth depends on the ground plane.
2. Ground-plane world coordinates are projected through the runtime projection implementation.
3. A Composer must not use 35.264 degrees, a generic isometric matrix or a separately tuned screen-space ellipse as a substitute for CH_CAMERA_V1.
4. Raster source pieces intended to represent 3D objects must be painted/rendered for the same CH_CAMERA_V1 visual read.
5. Passing coordinate parity is necessary but not sufficient: the calibration gate must also validate the CH_CAMERA_V1 basis, ratio and ground-axis angle.
6. MapForge interaction/capture code must not hard-code a single camera facing when the runtime supports all four quarter-turns.

## Calibration gate

The camera calibration gate validates:

- runtime ↔ MapForge2 coordinate parity over multiple rotations, pan and zoom;
- the actual visual camera profile: 128×64 basis, 2:1 diamond, 26.565-degree ground axes, 45-degree yaw, 30-degree orthographic elevation and no perspective;
- MapForge elevated projection against the runtime XYZ projection;
- focus preservation when changing quarter-turn camera facing.

A failed camera-profile check blocks camera-dependent Studio QA export. A green compile alone is not visual approval; viewport/capture artifacts still require gameplay-scale inspection.

## Relationship to CH_GRID_V1

`CH_GRID_V1` defines logical tile/grid dimensions and map constraints.

`CH_CAMERA_V1` defines how that world is visually projected.

They are intentionally separate contracts. A valid grid contract by itself is not proof that an asset uses the correct visual camera.

## Viewport status

The broader `CH_STUDIO_CANONICAL_VIEWPORT_V1` remains a pilot until full runtime/Studio scene-parity capture is approved. That does not make CH_CAMERA_V1 ambiguous: the projection geometry itself is frozen here, while viewport embedding, DPR behavior and final scene-parity validation remain separate gates.
