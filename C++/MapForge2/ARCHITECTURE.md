# Map Forge 2 Architecture

## Goal

Map Forge 2 is the native C++ successor to the interactive Python Map Forge UI. The migration is incremental: the existing Python editor remains available until native parity is reached and homologated.

## Hard boundaries

1. Python asset-production tools are not migrated here.
2. Frozen contracts remain authoritative: CH_MASK_V1, CH_OVERLAY_V1, CH_ANIMATED_PROP_V1, CH_SHORELINE_V1, CH_TERRAIN_SEMANTICS_V1 and MAP FORGE ACTIVE EDITING V1.
3. The editor must consume the same canonical C++ projection/map/render paths as runtime rather than reimplementing them in Qt.
4. Technical terrain pieces (shoreline edges/corners, blend primitives) are renderer implementation details and must never appear as normal user paint choices.
5. Production save remains disabled until mutation + serialization can preserve every scenario field losslessly.

## Native layers

```text
Qt6 desktop UI
      |
ch_editor (native editing state / commands / strokes / undo)
      |
ch_core (MapDocument / projection / semantics / placement)
      |
ch_render + SDL3 (canonical runtime rendering; next migration stage)
```

Qt owns desktop chrome: menus, toolbars, docks, catalog lists, property inspectors and shortcuts. Qt does not become a second game renderer.

## Phase 1 — bootable native editor shell (current)

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

The Phase 1 canvas uses a lightweight diagnostic QPainter representation so the editor interaction core can be migrated independently. It is not the final visual renderer.

## Phase 2 — canonical renderer integration

Replace diagnostic QPainter map drawing with `ch_render`/SDL3 output while keeping Qt for UI chrome. Runtime and editor must remain pixel-parity consumers of the same renderer path.

## Phase 3 — lossless native document editing

Create `ch_editor` commands operating on a mutable canonical MapDocument representation:

- PaintTerrainCommand
- BuildRoadCommand
- PlaceBuildingCommand
- RemoveEntityCommand
- RotateEntityCommand
- SetSemanticCommand

Mutation must preserve unrelated scenario JSON/data. Only after round-trip parity gates pass is Save enabled.

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
