# CH Blender architecture vocabulary

`CH_ARCHITECTURE_VOCABULARY_V1` turns visual improvements discovered on one asset into reusable building blocks for later assets. The library is implemented in `ch_architecture_modules.py`; the contract lives in `contracts/ch_architecture_vocabulary_v1.json`.

The important rule is that the vocabulary **does not learn automatically**. It improves because approved solutions are promoted into reusable deterministic modules instead of being left inside one-off asset scripts.

## Ten reusable module families

1. **roof_form** — gables, hips, dormers, eaves and ridge silhouette.
2. **roof_surface** — shingles, staggered joints, ridge caps and future roof material variants.
3. **windows** — frames, mullions, sills, casings and warm glass.
4. **entrances** — doors, panels, porches, columns, stoops and entry lamps.
5. **architectural_trim** — fascia, gutters, corner boards and edge hierarchy.
6. **foundation** — base courses, plinths, steps and ground-contact read.
7. **ornamental_vegetation** — compact shrubs, flowers and private mulch beds.
8. **emissive_lighting** — standardized warm window/lamp emission without requiring overlays.
9. **wall_surfaces** — siding and future plaster/masonry/timber/concrete facade families.
10. **small_arch_props** — chimneys, downspouts, vents, awnings, small signs and planters.

## Implementation order

Phase 1 focuses on silhouette and primary read: roof form, roof surface, windows, entrances and architectural trim.

Phase 2 focuses on grounding and materials: foundation, wall surfaces and emissive lighting.

Phase 3 adds personality after the asset already reads correctly at gameplay scale: ornamental vegetation and small architectural props.

## First calibration asset

`residential_suburban_cottage_3x3_01` is the first calibration asset. Its profile is recorded in:

`assets/residential_suburban_cottage_3x3_01.arch_modules.json`

The approved cottage is deliberately not redesigned just to adopt the vocabulary. Shared detail helpers are migrated only when the visual result remains equivalent. That prevents a library refactor from silently changing an already approved asset.

## Rules for future assets

- Start with a compact recipe and declare which module families the asset intends to use.
- Prefer `ch_architecture_modules.py` for a reusable solution before adding another private helper to a building script.
- Asset-specific composition is still allowed; the library is a vocabulary, not a forced template.
- Public sidewalks, roads and terrain remain runtime systems unless an asset contract explicitly says otherwise.
- Large vegetation should normally remain separate placeable assets; private low landscaping may be baked when it belongs to the lot composition.
- Modules own geometry vocabulary only. Camera, studio, projection, render scale and quality gates remain frozen by the existing CH Blender pipeline.
- A technically valid module or new variant is **not visually approved**. New silhouettes/variants still follow preflight → SOUTH proxy → explicit approval → four-direction final bake.
- Do not scale a building family from a module until one exemplar using that module has passed gameplay-scale review.

## Color masks and overlays

The vocabulary is compatible with `CH_COLOR_MASK_V1`. Recolor roles should remain semantic and coarse (for example wall / roof / trim) rather than masking every micro-detail.

Architecture modules do not imply activity overlays. A building may use emissive materials in its canonical sprite while still declaring `overlayPolicy: none`, as the approved residential cottage does.
