# City Horizon UI Nine-Slice Contract

## Status

The reusable runtime infrastructure is available in `src/ui_nine_slice.h`.

The V2 reference-derived skin is now promoted from a catalog-only asset to the reusable window pilot:

- skin: `assets/ui/chrome/panel_window_9slice_v2.png`;
- source size: 192x192;
- insets: 32 / 32 / 32 / 32 pixels;
- center patch: transparent, so runtime content and the procedural fallback remain visible;
- filtering: nearest-neighbor for this skin to avoid an extra blur pass;
- construction catalog hook: `src/ui_build_panel_nine_slice.inl`;
- modal hook: `src/ui_window_nine_slice.inl`;
- first modal migration: Pause, Settings and Administration;
- registry entry: `panel_window_nine_slice` in `assets/ui/ui_asset_catalog.json`.

The original V1 and build-catalog V2 files remain in the repository as rollback/reference points. Runtime rendering now uses the generic `panel_window_9slice_v2.png` asset so the same authored corners and borders are not maintained in multiple places.

This remains an incremental migration. The procedural SDL panel stays underneath every migrated window. A missing or invalid skin therefore leaves the interface usable instead of removing the window background.

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

1. Validate the construction catalog plus Pause, Settings and Administration at normal gameplay scale.
2. Adjust only the shared skin/insets if a concrete visual defect appears in all migrated windows.
3. Keep the current procedural panel as fallback while the skin remains a pilot.
4. After approval, extend the same frame to Reports, Save/Load, Main Menu and confirmation dialogs where their proportions remain compatible.
5. Only then consider specialized variants for HUD, compact controls or themed panels.

Use nine-slice for resizable panels and dialogs. Fixed-height controls that only change width may later use the same infrastructure as a three-slice by setting unused margins to zero rather than introducing a second renderer.

## Tests and visual proof

`src/ui_manager_test.cpp` verifies normal nine-slice geometry and compact destinations where borders must compress and the center collapses.

`src/ui_visual_capture.cpp` covers the existing catalog/settings interaction proof.

`src/ui_modal_visual_capture.cpp` renders deterministic Pause, Settings and Administration screenshots through the production `GameplayUi` renderer. The focused Windows workflow requires all modal captures before publishing the `City-Builder-UI-Visual-Proof` artifact.

Geometry and file-existence checks do not approve artwork. The shared V2 skin remains `pilot_v2` until the generated gameplay-scale captures are visually reviewed.
