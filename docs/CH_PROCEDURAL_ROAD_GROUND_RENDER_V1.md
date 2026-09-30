# CH_PROCEDURAL_ROAD_GROUND_RENDER_V1

## Goal

Prove procedural street rendering inside the real MapForge canonical viewport without making bridges/viaducts a dependency and without removing the legacy road renderer.

## Authority boundary

`RoadManager` remains authoritative for gameplay occupancy, save/load, economy and legacy routing.

Its synchronized `ProceduralRoadPlacementBridge` supplies a parallel graph used by the visual migration layer. The graph does not become a second gameplay authority in this contract.

## Ground-only admission rule

A procedural spline is eligible only when start, both cubic handles and end are all finite and within the ground epsilon (`abs(z) <= 0.0001`).

Eligible segments are converted with `RoadMeshBuilder::build_cubic(...)` and cached in `CanonicalViewport` when the document scene cache is rebuilt.

Junction patches are emitted only for ground nodes with at least two incident segments and only when every incident spline is ground-only. A node that mixes a ground road with an elevated/ramp segment is intentionally not patched by this contract.

This makes elevated geometry fail closed instead of leaking partially implemented viaduct behavior into the ordinary-street rollout.

## MapForge integration

`CanonicalViewport` enables the procedural ground-road preview by default for canonical scenarios.

Render order remains:

1. terrain;
2. roads;
3. buildings;
4. hover/inspection overlay.

Within the road layer, MapForge first submits the cached procedural ground plan through `SDL_RenderGeometry`. Segment ribbons are drawn first and junction patches second so patches cover sub-pixel seams at shared nodes.

If the procedural plan is empty or an SDL geometry submission fails, MapForge immediately calls the unchanged legacy `MapRenderer::render_roads(...)` path.

The public `CanonicalViewport::setProceduralRoadPreviewEnabled(bool)` switch preserves an explicit legacy/procedural comparison surface for later UI wiring.

## Viaduct / bridge non-goal

This contract does **not** approve:

- elevated road rendering in the canonical viewport;
- bridge supports;
- ramps;
- mixed-height junctions;
- elevated-road/building occlusion;
- vehicle Z sorting;
- save/load of authored road elevation.

The existing procedural-road preview may continue to exercise Z geometry as an isolated research/proof tool, but elevated rendering must not block ordinary streets. If bridge complexity is not justified by visible gameplay value, City Horizon may keep only the ground procedural street system.

## Current visual limitation

The `RoadManager` mirror still represents legacy tile adjacency as explicit graph nodes at tile centers. This proves the procedural renderer, shared camera and topology, but does not yet automatically smooth every 90-degree legacy corner into an authored Bézier curve. Smoothing/compression is a later visual gate and must not change gameplay topology silently.

## Validation

Focused gate: `MapForge2ProceduralRoadGroundRenderPlanTest`.

It verifies:

- an ordinary ground road produces procedural segment meshes and a continuation patch;
- a fully elevated segment is rejected;
- a mixed ground/elevated junction does not receive a procedural junction patch.

Visual approval still requires a real MapForge screenshot/artifact at gameplay scale. A workflow ending with `jobs: []` is neither a pass nor a code failure.
