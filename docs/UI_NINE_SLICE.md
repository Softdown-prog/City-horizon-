# City Horizon UI Nine-Slice Contract

## Status

Initial runtime infrastructure is available in `src/ui_nine_slice.h`.

This is an incremental UI migration. Existing procedural SDL panels remain the visual fallback until a panel skin is authored and approved at gameplay scale.

## Why nine-slice

City Horizon uses panels, dialogs, catalog windows, contextual building cards and HUD elements whose dimensions vary with viewport size and content. Scaling one complete raster frame would distort corners, bevels and borders.

Nine-slice divides a source texture into a 3x3 grid:

```text
TOP_LEFT     TOP       TOP_RIGHT
LEFT         CENTER    RIGHT
BOTTOM_LEFT  BOTTOM    BOTTOM_RIGHT
```

The four corners preserve their authored shape. Horizontal edges stretch only horizontally, vertical edges stretch only vertically, and the center fills the remaining space.

## Runtime API

`ch::ui::make_nine_slice_regions(...)` calculates the nine source/destination rectangles.

`ch::ui::render_nine_slice(...)` renders those regions with SDL3 `SDL_RenderTexture`.

The source insets are supplied as left/top/right/bottom pixel margins. If invalid source margins exceed the source texture size, they are clamped proportionally. If a destination becomes smaller than the combined border widths/heights, the destination borders compress proportionally and the center safely collapses instead of producing negative rectangles.

## Migration rule

Do not convert every UI element at once.

1. Author one approved panel frame under `assets/ui/`.
2. Validate the frame at normal gameplay scale.
3. Integrate it into one representative resizable panel.
4. Keep the current procedural panel as fallback while the skin is unavailable.
5. Only after the first panel is visually approved should the same skin be promoted to compatible dialogs/cards.

Use nine-slice for resizable panels and dialogs. Fixed-height controls that only change width may later use the same infrastructure as a three-slice by setting unused margins to zero rather than introducing a second renderer.

## Tests

`src/ui_manager_test.cpp` verifies normal nine-slice geometry and compact destinations where borders must compress and the center collapses.

Visual approval still requires an in-game/runtime capture after a real UI skin is connected; geometry tests alone do not approve the artwork.
