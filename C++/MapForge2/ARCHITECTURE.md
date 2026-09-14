# Map Forge 2 Architecture

## Goal

Map Forge 2 is the native C++ successor to the interactive Python Map Forge UI. The migration is incremental: the existing Python editor remains available until native parity is reached and homologated.

Map Forge 2 is also the first native module of the broader **City Horizon Studio**: a deterministic authoring and homologation environment specialized for City Horizon. The Studio direction is governed by `CH_STUDIO_ARCHITECTURE_V1.md`.

## Hard boundaries

1. Python asset-production tools are not migrated here.
2. Frozen contracts remain authoritative: CH_MASK_V1, CH_OVERLAY_V1, CH_ANIMATED_PROP_V1, CH_SHORELINE_V1, CH_TERRAIN_SEMANTICS_V1 and MAP FORGE ACTIVE EDITING V1.
3. The editor must consume the same canonical C++ projection/map/render paths as runtime rather than reimplementing them in Qt.
4. Technical terrain pieces (shoreline edges/corners, blend primitives) are renderer implementation details and must never appear as normal user paint choices.
5. Production save remains disabled until mutation + serialization can preserve every scenario field losslessly.
6. Content that can be represented by existing engine capabilities should be data-driven and must not require new C++ merely to place or configure it.

## Native layers

```text
Qt6 desktop UI / input / event loop
      |
ch_editor / Studio adapters
      |
mapforge2_studio_core (typed content contracts / validation)
      |
ch_core (MapDocument / projection / semantics / placement)
      |
ch_render + SDL3 (canonical City Horizon world presentation)
```

Qt owns desktop chrome, authoring controls and the native child viewport. SDL3 wraps that Qt-owned HWND only for rendering. Qt remains the single input and event-loop authority.

## Phase 1 — bootable native editor shell (complete)

- C++20 + Qt6 Widgets
- canonical 2:1 projection
- canonical scenario read path
- native pan/zoom/hover
- semantic-facing terrain palette
- road brush
- 1x1 / 3x3 / 5x5 brush sizes
- Bresenham drag interpolation
- one undo transaction per stroke
- GitHub Actions Windows deployment artifact

The Phase 1 scratch canvas uses a lightweight diagnostic QPainter representation so the editor interaction core can be migrated independently. It is not the production visual renderer.

## Phase 1.5 — City Horizon Studio content foundation (complete foundation / not frozen)

- Qt-independent `mapforge2_studio_core`
- `CH_CONTENT_PACK_V1` typed package/definition model
- stable content ID rules
- package validation diagnostics
- catalog collision detection
- cross-definition dependency validation
- Qt JSON loading adapter
- Studio dock tab with validation report
- JSON Schema plus a technical validation fixture
- production scenario Save still intentionally disabled

This phase does **not** generate C++ from content packs. C++ defines reusable engine capabilities; content packs describe and combine those capabilities.

## Phase 2 — canonical renderer integration (current pilot)

Governed by `CH_STUDIO_CANONICAL_VIEWPORT_V1.md`.

- SDL3 is built into the standalone Studio target.
- A Studio-side adapter wraps the Qt-owned Win32 viewport HWND.
- Terrain is rendered by canonical `MapRenderer` paths and game assets.
- Roads use `RoadManager` connectivity plus `RoadVisualCatalog` and `MapRenderer`.
- Buildings use `BuildingCatalog`, canonical anchors/footprints/rotation selection and `MapRenderer::render_building`.
- Qt schedules rendering at ~60 FPS; SDL does not own editor input.
- Qt logical pixels are converted explicitly to renderer physical pixels using DPR.
- Loaded scenario bounds preserve negative coordinates and Center uses real content extents.
- Canonical scenario mode is read-only until lossless mutation exists.
- Scratch-map diagnostic authoring remains available separately.

The renderer contract is **not frozen yet**. Windows build, manual DPI/resize smoke and runtime-vs-Studio parity capture must pass first.

## Phase 3 — lossless native document editing

Create `ch_editor` commands operating on a mutable canonical MapDocument representation:

- PaintTerrainCommand
- BuildRoadCommand
- PlaceBuildingCommand
- RemoveEntityCommand
- RotateEntityCommand
- SetSemanticCommand

Mutation must preserve unrelated scenario JSON/data. Only after round-trip parity gates pass is Save enabled. This is also the point where canonical scenario authoring tools can be re-enabled without creating a second source of truth.

## Phase 4 — production catalogs

- terrain definitions (user intent only)
- roads/sidewalks
- buildings/decorations
- footprint/access points
- rotations
- thumbnail browser
- hot reload

## Phase 5 — diagnostics and bot access

- semantic overlay
- navigation overlay
- collision/depth overlay
- frame/editor performance counters
- `mapforge_cli` native command surface
- optional thin Python binding for agent automation

## Performance rule

Interactive high-frequency work belongs in C++: mouse strokes, brushes, command application, selection, document mutation and renderer synchronization. Offline generation/validation/Blender automation remains in Python.
