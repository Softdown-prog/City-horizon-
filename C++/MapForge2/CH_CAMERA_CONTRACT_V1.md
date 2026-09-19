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

## Important correction

The previous metadata exposed 35.264 degrees as `kIsometricInclinationDeg`. That value belongs to mathematically true isometric projection and is inconsistent with a 2:1 diamond.

City Horizon does **not** use true-isometric 35.264-degree elevation as its visual camera. CH_CAMERA_V1 uses 30-degree orthographic elevation with 45-degree yaw, which produces the classic 2:1 dimetric ground read.

`kIsometricInclinationDeg` remains only as a compatibility alias and now resolves to the canonical 30-degree camera elevation. New code must use `kCameraElevationDeg`.

## Sources of truth

Projection implementation:

`src/ch_core/projection.cpp::ch::world_to_screen_point()`

Camera/grid constants:

`src/ch_core/contracts.h`

MapForge2 must consume those runtime definitions rather than maintain an independent projection formula.

## Composer rules

1. Building, animation and ride geometry is authored in logical world space whenever placement/depth depends on the ground plane.
2. Ground-plane world coordinates are projected through the runtime projection implementation.
3. A Composer must not use 35.264 degrees, a generic isometric matrix or a separately tuned screen-space ellipse as a substitute for CH_CAMERA_V1.
4. Raster source pieces intended to represent 3D objects must be painted/rendered for the same CH_CAMERA_V1 visual read.
5. Passing coordinate parity is necessary but not sufficient: the calibration gate must also validate the CH_CAMERA_V1 basis, ratio and ground-axis angle.

## Calibration gate

`engine_projection_calibration_2` validates both:

- runtime ↔ MapForge2 coordinate parity over multiple rotations, pan and zoom;
- the actual visual camera profile: 128×64 basis, 2:1 diamond, 26.565-degree ground axes, 45-degree yaw, 30-degree orthographic elevation and no perspective.

A failed camera-profile check blocks Carousel Composer QA export.

## Relationship to CH_GRID_V1

`CH_GRID_V1` defines logical tile/grid dimensions and map constraints.

`CH_CAMERA_V1` defines how that world is visually projected.

They are intentionally separate contracts. A valid grid contract by itself is not proof that an asset uses the correct visual camera.

## Viewport status

The broader `CH_STUDIO_CANONICAL_VIEWPORT_V1` remains a pilot until full runtime/Studio parity capture is approved. That does not make CH_CAMERA_V1 ambiguous: the projection geometry itself is frozen here, while viewport embedding, DPR behavior and final scene-parity validation remain separate gates.
