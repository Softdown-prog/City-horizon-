# City Horizon UI Nine-Slice Contract

## Status

The reusable runtime infrastructure is available in `src/ui_nine_slice.h`.

The construction-catalog pilot now uses the V2 reference-derived skin:

- skin: `assets/ui/chrome/panel_build_catalog_9slice_v2.png`;
- source size: 192x192;
- insets: 32 / 32 / 32 / 32 pixels;
- center patch: transparent, so runtime content and the procedural fallback remain visible;
- filtering: nearest-neighbor for this skin to avoid an extra blur pass;
- runtime hook: `src/ui_build_panel_nine_slice.inl`;
- registry entry: `panel_build_catalog_nine_slice` in `assets/ui/ui_asset_catalog.json`.

V1 remains in the repository as the original minimal pilot and rollback point. V2 preserves the heavier frame, bevels and four decorated corners from the supplied visual reference while keeping the center free for catalog content.

This remains an incremental migration. The construction-catalog skin is integrated but is not yet promoted as the universal UI frame until an in-game/runtime capture is reviewed at gameplay scale.

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

1. Validate the construction-catalog pilot at normal gameplay scale.
2. Adjust only its skin/insets if a concrete visual defect appears.
3. Keep the current procedural panel as fallback while the skin remains a pilot.
4. After approval, promote the same frame to compatible dialogs/cards.
5. Only then consider specialized variants for HUD, compact controls or themed panels.

Use nine-slice for resizable panels and dialogs. Fixed-height controls that only change width may later use the same infrastructure as a three-slice by setting unused margins to zero rather than introducing a second renderer.

## Tests

`src/ui_manager_test.cpp` verifies normal nine-slice geometry and compact destinations where borders must compress and the center collapses.

Geometry tests do not approve artwork. The V2 construction-catalog skin still requires an actual runtime/gameplay-scale capture before its visual status changes from `pilot_v2` to `approved`.
