# City Horizon — C++ Tools

This folder contains the native replacement path for interactive editor tooling.

## MapForge2

`MapForge2` is the new native map editor. It is intentionally isolated from the existing Python `tools/map_forge` implementation so migration can happen incrementally without breaking the homologated editor contracts.

Technology:
- C++20
- Qt 6 Widgets for desktop UI
- direct reuse of canonical City Horizon C++ projection/map parsing code
- no Python in the interactive event loop

Current migration milestone:
- native Qt window and docked editor UI
- canonical isometric projection from `src/ch_core/projection.*`
- canonical scenario loading from `src/ch_core/map_document.*`
- native pan/zoom/hover
- 1x1 / 3x3 / 5x5 brushes
- continuous Bresenham strokes
- one undo/redo transaction per stroke
- in-memory terrain/road editing prototype
- Windows GitHub Actions build with deployable Qt runtime artifact

Safety rule: MapForge2 does not overwrite production scenarios yet. Saving is deliberately withheld until full lossless MapDocument mutation/serialization is migrated to C++.

The existing Python asset pipelines remain untouched. They continue to serve Blender automation, masks, validators, recipes, batch generation and diagnostics.
