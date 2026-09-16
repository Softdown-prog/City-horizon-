# CH_BUILDING_COMPOSER_V0

Status: PILOT

The Building / Asset Composer is the first deterministic structure-authoring slice inside City Horizon Studio. It does not turn the runtime into a 3D engine. The editable source is parametric/vector-like geometry; the game-facing output remains PNG RGBA bitmap sprites.

## Pilot contract

- Projection is fixed to the City Horizon 2:1 isometric grid contract.
- One structural definition generates SOUTH, EAST, WEST and NORTH views.
- Logical façade identity is preserved across views. The entrance belongs to the south façade rather than being redrawn independently per image.
- Footprint, wall height, roof family, palette and façade modules are parameters.
- Runtime output is a four-view PNG RGBA sheet plus JSON manifest.
- Source/game scenarios are never mutated by the composer.
- The renderer is deterministic: Studio preview and GitHub visual gate call the same BuildingComposer implementation.

## Socket modules — revision 1

The first modular-assembly slice is now active. Details attach to logical building locations rather than screen coordinates.

- Entrance socket: south façade, with left/center/right placement.
- Window module: single/pair/strip patterns, distributed per visible façade.
- Awning socket: attached to the logical south entrance and projected consistently into every view.
- Sign socket: attached above the logical south entrance.
- Roof chimney socket: attached to the roof in building space and rotated with the structure.
- Detail presets in the Studio provide Residence, Small shop and Utility / depot starting points without creating separate render code paths.
- The JSON manifest records the enabled sockets/modules so later catalog/export stages can reason about the structure without inspecting pixels.

These modules do not change footprint/collision semantics. They are presentation/authoring details generated from the same structural definition.

## Visual gate

GitHub Actions builds the same composer renderer and runs `MapForge2ComposerPreview` headlessly. It emits the original residential pilot plus a shop/socket gate under `visual_tests/`. Each gate includes a four-view review image, transparent sprite sheet and manifest. This gives the project deterministic images that can be inspected before requiring a manual Windows session.

## Current limits

The current pilot still uses simple convex rectangular primary volumes. Arbitrary/L-shaped footprints, compound roof solving, user-authored socket coordinates, calibrated Blender import and production catalog insertion remain later gates. The next structural gate should introduce footprint-shape composition without weakening the four-view/same-geometry invariant.

## Why this exists

The objective is to stop treating every rotation as a separate illustration. Geometry and logical modules are authored once, then projected into the required views. More complex buildings may later use Blender as an offline geometry backend, but they must still land in the same City Horizon contract and export the same bitmap-facing representation.
