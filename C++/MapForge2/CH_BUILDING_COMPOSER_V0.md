# CH_BUILDING_COMPOSER_V0

Status: PILOT

The Building / Asset Composer is the first deterministic structure-authoring slice inside City Horizon Studio. It does not turn the runtime into a 3D engine. The editable source is parametric/vector-like geometry; the game-facing output remains PNG RGBA bitmap sprites.

## Pilot contract

- Projection is fixed to the City Horizon 2:1 isometric grid contract.
- One structural definition generates SOUTH, EAST, WEST and NORTH views.
- Logical façade identity is preserved across views. The pilot entrance belongs to the south façade rather than being redrawn independently per image.
- Footprint, wall height, roof family, palette and simple façade features are parameters.
- Runtime output is a four-view PNG RGBA sheet plus JSON manifest.
- Source/game scenarios are never mutated by the composer.
- The pilot is intentionally limited to simple convex building volumes. Arbitrary footprints, socket-based details, calibrated Blender import and production-grade roof solving remain future gates.

## Visual gate

GitHub Actions builds the same composer renderer and runs `MapForge2ComposerPreview` headlessly. It emits a four-view review image, transparent sprite sheet and manifest under `visual_tests/`. This gives the project a deterministic image that can be inspected before requiring a manual Windows session.

## Why this exists

The objective is to stop treating every rotation as a separate illustration. Geometry is authored once, then projected into the required views. More complex buildings may later use Blender as an offline geometry backend, but they must still land in the same City Horizon contract and export the same bitmap-facing representation.
