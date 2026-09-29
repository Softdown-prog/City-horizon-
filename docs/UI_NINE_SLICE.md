# City Horizon UI Nine-Slice Contract

## Canonical window contract

`CH_WINDOW_FRAME_V2` is the canonical resizable-window frame for City Horizon.

New standard UI windows should reference the contract instead of hard-coding the physical PNG name or border values. The runtime constants live in `src/ui_nine_slice.h`:

- contract id: `CH_WINDOW_FRAME_V2`;
- asset stem: `panel_window_9slice_v2`;
- physical skin: `assets/ui/chrome/panel_window_9slice_v2.png`;
- source size: 192x192;
- insets: 32 / 32 / 32 / 32 pixels;
- filtering: nearest-neighbor;
- center patch: transparent, preserving runtime content and the procedural fallback beneath it.

The physical filename remains stable for compatibility, while `CH_WINDOW_FRAME_V2` is the semantic contract used by new UI work.

## Default usage

Use `CH_WINDOW_FRAME_V2` by default for:

- instruction windows;
- help windows;
- information screens presented as windows;
- tutorial steps/cards that use a standard modal or resizable panel;
- alerts and ordinary confirmation dialogs;
- objectives/details windows;
- standard reports and management windows;
- other resizable modal windows that do not require a deliberately unique art direction.

Existing runtime usages include the construction catalog, Pause, Settings, Administration, Reports, Save/Load, Main Menu and Quit Confirmation.

Do **not** force this contract onto every UI element. HUD strips, compact tooltips, fixed-size buttons, loading screens, splash screens, credits and deliberately full-screen illustrated tutorials may use dedicated layouts. Standard windows/cards inside those screens may still use `CH_WINDOW_FRAME_V2`.

## Runtime behavior

The reusable renderer is available in `src/ui_nine_slice.h`.

`ch::ui::make_nine_slice_regions(...)` calculates the nine source/destination rectangles and `ch::ui::render_nine_slice(...)` renders them through SDL3 `SDL_RenderTexture`.

The canonical constants are:

- `ch::ui::kWindowFrameV2ContractId`;
- `ch::ui::kWindowFrameV2AssetStem`;
- `ch::ui::kWindowFrameV2Insets`;
- `ch::ui::kWindowFrameV2MinimumWidth`;
- `ch::ui::kWindowFrameV2MinimumHeight`.

`src/ui_build_panel_nine_slice.inl` and `src/ui_window_nine_slice.inl` consume these constants directly, so the runtime has one source of truth for the asset and border contract.

The procedural SDL panel remains underneath migrated windows as a fallback/background. A missing or invalid skin therefore leaves the interface usable instead of removing the window background.

## Why nine-slice

City Horizon uses panels, dialogs, catalog windows, contextual building cards and other windows whose dimensions vary with viewport size and content. Scaling one complete raster frame would distort corners, bevels and borders.

Nine-slice divides a source texture into a 3x3 grid:

```text
TOP_LEFT     TOP       TOP_RIGHT
LEFT         CENTER    RIGHT
BOTTOM_LEFT  BOTTOM    BOTTOM_RIGHT
```

The four corners preserve their authored shape. Horizontal edges stretch only horizontally, vertical edges stretch only vertically, and the center fills the remaining space.

If source margins exceed the source texture size, the renderer clamps them proportionally. If a destination becomes smaller than the combined border widths/heights, destination borders compress proportionally and the center safely collapses instead of producing negative rectangles.

## Asset registry

`assets/ui/ui_asset_catalog.json` registers `panel_window_nine_slice` with `contract_id: CH_WINDOW_FRAME_V2`, its runtime usages, and the categories for which it is the default frame.

The old construction-catalog entry remains as a compatibility alias to the same physical asset and contract.

## Tests and visual proof

`src/ui_manager_test.cpp` verifies normal nine-slice geometry and compact destinations where borders must compress and the center collapses.

`src/ui_visual_capture.cpp` covers catalog/settings interaction proof.

`src/ui_modal_visual_capture.cpp` renders deterministic modal screenshots through the production `GameplayUi` renderer. The focused Windows workflow publishes the `City-Builder-UI-Visual-Proof` artifact independently of the full runtime build, so unrelated runtime compile failures do not block UI visual validation.

The V2 frame is a runtime-standard component. New screens using `CH_WINDOW_FRAME_V2` still require gameplay-scale visual review when their proportions or content layout are materially different from the already validated windows.
