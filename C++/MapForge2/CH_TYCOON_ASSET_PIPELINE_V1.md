# City Horizon Tycoon Asset Pipeline V1

Status: **VISUAL CANDIDATE — human approval required**

This stage converts the successful one-view Blender proof into a real game-asset bake: one deterministic source object generates four coherent rotations for the fixed City Horizon camera.

## Canonical rule

The camera does not rotate between asset directions. `CH_CAMERA_V1` and the studio lights remain fixed. The asset root rotates around world origin in the same quarter-turn convention already used by `BuildingComposer` and `BuildingExportPipeline`:

| Direction | Quarter turns | Asset Z rotation |
| --- | ---: | ---: |
| South | 0 | 0° |
| East | 1 | 90° |
| West | 3 | 270° |
| North | 2 | 180° |

The output order remains `south, east, west, north` because that is the current canonical order in `building_export_pipeline.cpp`.

## What is reused from the existing toolchain

This pipeline does **not** discard the existing MapForge2 foundation. It deliberately reuses:

- `CH_CAMERA_V1` and `CH_GRID_V1`;
- the four-view naming and direction convention from `BuildingExportPipeline`;
- footprint concepts and 128×64 tile contract;
- persistent pivot/anchor metadata;
- PNG + JSON package conventions;
- sprite-sheet/atlas export concepts;
- Animation Core as the later expansion path for `directions × frames`;
- Asset Browser, validation, LOD, halo and integration gates as later consumers of baked output.

What changes is the final visual authority: simple QPainter/procedural shapes remain useful for debug, composition and authored metadata, but Blender baking becomes the source of production sprite pixels for this pipeline.

## Pivot rule

All four rotations use the projection of the same world-space origin `(0,0,0)` as their gameplay pivot. Alpha bounds are recorded for trimming and atlas packing, but they never define the pivot. CI rejects the package if the four final pivots differ.

This is important because asymmetric roofs, awnings and shadows change alpha bounds between rotations while the building must stay planted on exactly the same tile origin.

## Current visual recipe

The current candidate keeps the successful POC setup:

- Blender 4.2.3 LTS;
- Cycles CPU render;
- 1024×1024 source bake;
- 256×256 gameplay frame;
- fixed warm key + cool fill;
- Cycles shadow catcher;
- palette reduction to 128 colors;
- Floyd-Steinberg dithering;
- no hard edge-cleanup in the provisional production candidate.

Variant 03 remains a **candidate**, not a frozen final style. All four post-process variants are kept in the review artifact so the visual recipe can still be calibrated without changing geometry or camera.

## Package produced by the proof

For `park_kiosk_1x1` the pipeline emits:

- `park_kiosk_1x1_south.png`
- `park_kiosk_1x1_east.png`
- `park_kiosk_1x1_west.png`
- `park_kiosk_1x1_north.png`
- `park_kiosk_1x1_4view.png` — fixed-cell compatibility sheet
- `park_kiosk_1x1_atlas.png` — trimmed deterministic atlas
- `park_kiosk_1x1_manifest.json` — directions, rotations, pivots, bounds, footprint and atlas rects
- `park_kiosk_1x1_review.png` — all four candidate directions with tile/pivot overlay
- `park_kiosk_1x1_style_matrix.png` — four directions × four post-process variants
- `park_kiosk_1x1_4dir_context.png` — gameplay-scale synthetic grid comparison

## Gate before the next expansion

Do not generalize this system to a large asset library yet. First review the four rotations together. The next stage is justified only if the same asset:

1. stays planted on the same tile pivot in every direction;
2. preserves material and lighting identity across all rotations;
3. reads correctly at gameplay scale;
4. remains visually inside the intended classic Tycoon / Zoo Tycoon 1 family.

Once this golden static asset is accepted, the same root-rotation contract can be extended to animated assets by baking `4 directions × N animation frames` without independently redrawing frames.
