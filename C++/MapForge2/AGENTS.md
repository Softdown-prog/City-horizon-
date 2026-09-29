# MapForge2 Agent Rules

These rules extend the repository-root `AGENTS.md` for work under `C++/MapForge2/`.

## Camera and projection

- `CH_CAMERA_V1` in `src/ch_core` is the gameplay source of truth.
- Do not add another local isometric `(x-y)/(x+y)` projection to MapForge tools.
- Interactive/runtime-like views must call `ch::world_to_screen_point(...)` / `ch::screen_to_world_point(...)` or `EngineProjectionAdapter`.
- Asset-authoring previews that use vertical dimensions in output pixels must use `src/authoring_projection.h`: canonical gameplay XY/view rotation plus intentional pixel-space Z.
- Asset-view quarter turns rotate the asset; runtime `CameraRotation` rotates the camera. Use `authoringCameraRotation(...)` rather than assuming the enum directions are identical.
- New ground/elevated captures must project all four tile corners at the requested world Z; do not move only an anchor while leaving the tile at Z=0.

## Temporary pixel-Z compatibility allowlist

The following renderers still contain the historical authoring projection formula because their building Z values are authored in pixels:

- `src/building_composer.cpp`
- `src/building_facade_renderer.cpp`
- `src/building_roof_editor_renderer.cpp`

Do not add files to this list. Their XY/view behavior is guarded by `CH_MAPFORGE_AUTHORING_PROJECTION_V1`. Migrate these files only in a focused change with before/after visual proof because a blind conversion of their pixel Z to world elevation changes asset proportions.

## Validation

For camera/projection changes, prefer the focused checks before broader builds:

- `src/mapforge_camera_parity_test.cpp` — runtime/editor XYZ, inverse projection, four rotations, preserved focus.
- `src/mapforge_authoring_projection_test.cpp` — authoring XY/view + pixel-Z compatibility.
- `tools/check_projection_drift.py` — blocks new local projection formulas outside the explicit compatibility allowlist.

A workflow run that ends with `jobs: []` did not compile or execute these gates. Do not report it as a code-test failure or success.
