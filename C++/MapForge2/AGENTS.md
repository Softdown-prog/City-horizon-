# MapForge2 Agent Rules

These rules extend the repository-root `AGENTS.md` for work under `C++/MapForge2/`.

## Camera and projection

- `CH_CAMERA_V1` in `src/ch_core` is the gameplay source of truth.
- Do not add another local isometric `(x-y)/(x+y)` projection to MapForge tools.
- Interactive/runtime-like views must call `ch::world_to_screen_point(...)` / `ch::screen_to_world_point(...)` or `EngineProjectionAdapter`.
- Asset-authoring previews that use vertical dimensions in output pixels must use `src/authoring_projection.h`: canonical gameplay XY/view rotation plus intentional pixel-space Z.
- Asset-view quarter turns rotate the asset; runtime `CameraRotation` rotates the camera. Use `authoringCameraRotation(...)` rather than assuming the enum directions are identical.
- New ground/elevated captures must project all four tile corners at the requested world Z; do not move only an anchor while leaving the tile at Z=0.

## Pixel-Z authoring renderers

The former Building Composer compatibility allowlist has been retired. `building_composer.cpp`, `building_facade_renderer.cpp` and `building_roof_editor_renderer.cpp` now delegate XY/view projection to `authoring_projection.h` while preserving authored vertical dimensions in output pixels.

Do not convert authored pixel-Z values such as wall/roof/fascia heights into gameplay world elevation unless a newer explicit contract replaces this authoring model.

## Procedural road rollout

- `RoadManager` remains the authoritative gameplay/save/occupancy road system until a later migration gate explicitly changes that.
- The synchronized procedural graph is a visual/traffic migration surface, not a second gameplay authority.
- The first MapForge canonical-viewport rollout is `CH_PROCEDURAL_ROAD_GROUND_RENDER_V1`: only splines entirely on the ground plane may render procedurally.
- Elevated spans, ramps and mixed-height junctions must be rejected by the ground render plan instead of being approximated silently.
- The legacy tile/PNG renderer remains the immediate fallback if the procedural SDL geometry submission fails or the ground plan is unavailable.
- Do not make viaducts/bridges a dependency for proving ordinary streets. If elevated-road complexity threatens the stable city-builder slice, keep elevated rendering disabled and continue with ground roads.

## Validation

For camera/projection changes, prefer the focused checks before broader builds:

- `src/mapforge_camera_parity_test.cpp` — runtime/editor XYZ, inverse projection, four rotations, preserved focus.
- `src/mapforge_authoring_projection_test.cpp` — authoring XY/view + pixel-Z compatibility.
- `tools/check_projection_drift.py` — blocks new local projection formulas.
- `${CH_ROOT}/src/procedural_road_ground_render_plan_test.cpp` / `MapForge2ProceduralRoadGroundRenderPlanTest` — ground roads admitted; elevated and mixed-height geometry rejected.

A workflow run that ends with `jobs: []` did not compile or execute these gates. Do not report it as a code-test failure or success.
