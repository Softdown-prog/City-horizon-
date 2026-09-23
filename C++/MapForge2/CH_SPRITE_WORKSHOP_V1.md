# CH_SPRITE_WORKSHOP_V1

Status: ACTIVE FIRST TRANCHE

## Purpose

`CityHorizonSpriteWorkshop` is a focused raster inspection and post-render QA tool inside the MapForge2 toolchain.

It is **not** a Photoshop/PaintShop Pro clone and it does not introduce a second authored asset format. The canonical authoring model remains `CH_ASSET_DOCUMENT_V1` / `.chasset` through `CityHorizonAssetEditor`.

The workshop exists for the narrow stage between a rendered PNG and runtime approval:

```text
Blender / procedural source -> PNG RGBA -> Sprite Workshop QA -> .chasset/runtime packaging
```

## V1 capabilities

- open a base PNG;
- checkerboard transparency preview;
- horizontal spritesheet slicing;
- configurable frame count and frame duration;
- animated play/pause preview;
- manual frame stepping;
- normalized anchor crosshair preview;
- opaque pixel bounds overlay;
- alpha statistics;
- semi-transparent edge-fringe diagnostic;
- open and composite a `CH_BUILDING_ACTIVITY_OVERLAY_V1` PNG over the base sprite;
- verify base-frame and overlay-frame canvas geometry;
- export the currently inspected frame as PNG.

## Halo diagnostic rule

The V1 tool deliberately does **not** auto-delete semi-transparent edge pixels.

`edge fringe` means a semi-transparent pixel that touches a fully transparent pixel. This is useful for finding suspicious borders and background-removal residue, but it is not automatic proof of a bad halo because valid anti-aliasing also creates semi-transparent edge pixels.

Future cleanup operations must therefore be explicit, previewable and undoable before they are allowed to change production PNGs.

## Activity overlay rule

The overlay preview follows the existing `CH_BUILDING_ACTIVITY_OVERLAY_V1` principle:

- the building/base sprite remains unchanged;
- only temporary animated content belongs in the overlay;
- a horizontal overlay spritesheet may use the same frame count as the base inspection;
- each overlay frame should match the corresponding base frame canvas and anchor exactly;
- geometry mismatch is reported before runtime integration.

This supports effects such as:

- rotating ice-cream/popsicle sign;
- barber pole rotation;
- window/light animation;
- steam;
- door motion;
- small character or machinery animation attached to a building.

## Architecture decision

The executable lives under `C++/MapForge2` and is built/installed beside MapForge2 and `CityHorizonAssetEditor`.

It intentionally has no separate project/save format. The next integration tranche should let `CityHorizonAssetEditor` launch the workshop with the selected direction/layer and later write approved anchor/animation/overlay metadata back through the existing `.chasset` document transaction/history system.

## Recommended next tranche

1. Launch Sprite Workshop directly from the selected `.chasset` direction.
2. Read frame count/duration and normalized anchor from the document instead of manual entry.
3. Add explicit non-destructive crop/padding operations with undo preview.
4. Add fringe color inspection and optional decontamination preview without touching source pixels until approved.
5. Add four-direction comparison board and animation synchronization gate.
6. Add `CH_COLOR_MASK_V1` preview beside `CH_BUILDING_ACTIVITY_OVERLAY_V1`.
7. Export approved changes only through the canonical asset document/runtime packaging path.
