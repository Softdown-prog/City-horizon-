# CH_BUILDING_COMPOSER_V0

Status: PILOT — FINAL HOUSE PRODUCTION GATE ACTIVE

The Building / Asset Composer is the first deterministic structure-authoring slice inside City Horizon Studio. It does not turn the runtime into a 3D engine. The editable source is parametric/vector-like geometry; the game-facing output remains PNG RGBA bitmap sprites.

The current residential house is a complete technical prototype and geometric foundation, not the final visual-quality reference for City Horizon. Projection, volume, roof, basic materials, four views, footprint, anchor, supersampling and structural rules are functioning, but the render still requires a controlled visual-finish pass before the house can become an official specimen.

CH_WORLD_ASSET_CONTRACT_V1 is explicitly NOT frozen. The house may become its first official specimen only after the user gives explicit visual approval at the end of the Final House Production Gate.

## Pilot contract

- Projection is fixed to the City Horizon 2:1 isometric grid contract.
- One structural definition generates SOUTH, EAST, WEST and NORTH views.
- Logical façade identity is preserved across views. The entrance belongs to the south façade rather than being redrawn independently per image.
- Footprint, wall height, roof family, palette and façade modules are parameters.
- Runtime output is a four-view PNG RGBA sheet plus JSON manifest.
- Source/game scenarios are never mutated by the composer.
- The renderer is deterministic: Studio preview and GitHub visual gate call the same BuildingComposer implementation.
- Existing camera, projection, footprint, anchor and 2× supersampling remain authoritative during the visual-finish pass.

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

## FINAL HOUSE PRODUCTION GATE

This gate applies exclusively to the current complete residential house. It is a visual-finish phase, not a new structural-family phase and not a license to redesign the architecture.

### Objective

Elevate the house from a simple procedural prototype to a clean, convincing asset suitable for a commercial PC 2.5D pre-rendered isometric tycoon, while preserving legibility, simplicity and City Horizon coherence.

The target should read as a small finished architectural model, not as filled polygons with an outline. It must remain stylized and readable: not photorealistic 3D, glossy mobile art, or an over-detailed asset.

### Controlled visual priorities

Implement and review these priorities incrementally, one visual aspect per commit:

1. Increase physical depth at structural junctions so the result does not feel line-drawn.
2. Improve face lighting beyond near-flat shading while keeping the light coherent across all four views.
3. Add soft, controlled ambient occlusion at structural contacts:
   - under the eaves;
   - roof/wall junctions;
   - corners and recesses;
   - around frames;
   - wall base where it meets the ground.
4. Improve roof-volume readability, including visible eave thickness and roof/wall fit.
5. Make doors and windows read as embedded components with depth; improve sills, thresholds and structural finishes where needed.
6. Add restrained material richness without visual noise, preserving the already-approved subtle plaster treatment.
7. Keep the existing 2× supersampling and generate review PNGs for SOUTH, EAST, WEST and NORTH after each relevant stage.

### Explicit exclusions

- Do not change the house's architectural design.
- Do not add balconies, fences, plants, signs or other new scene elements.
- Do not start new asset families.
- Do not use thick outlines.
- Do not add artificial highlights painted over the model.
- Do not introduce excessive weathering, dirt, moss or decorative detail.
- Do not expand the work into the engine, maps, trees, characters or unrelated systems.
- Do not implement every effect in one change.
- Do not revert previous commits. Earlier improvements to corners, roof/wall contact, wall/ground contact, line-weight consistency and removal of artificial highlights remain valid technical foundations.

### Review workflow

- Work exclusively on this house-base.
- Make small, controlled changes.
- Use one visual aspect per commit.
- Generate the four-view PNG review after every relevant stage.
- Prioritize depth, lighting and structural contact before secondary material refinement.
- Keep CH_WORLD_ASSET_CONTRACT_V1 unfrozen until explicit human visual approval.
- Treat the current house as a technical base, never as the final quality bar.

### Approval criteria

The gate passes only when the house has convincing depth, clean structural contacts, coherent lighting, legible materials and a distinct City Horizon identity at game viewing scale. It must look like a finished city-builder/tycoon 2.5D asset rather than a procedural construction preview.

After explicit human approval, this house may become the first official specimen from which CH_WORLD_ASSET_CONTRACT_V1 is extracted and frozen.

## Current limits

The current pilot still uses simple convex rectangular primary volumes. Arbitrary/L-shaped footprints, compound roof solving, user-authored socket coordinates, calibrated Blender import and production catalog insertion remain later gates. Those structural/catalog expansions are intentionally deferred while the Final House Production Gate is active; the next work on the composer is visual finishing of this house, not a new structural gate.

## Why this exists

The objective is to stop treating every rotation as a separate illustration. Geometry and logical modules are authored once, then projected into the required views. More complex buildings may later use Blender as an offline geometry backend, but they must still land in the same City Horizon contract and export the same bitmap-facing representation.
