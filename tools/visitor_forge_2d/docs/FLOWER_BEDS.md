# Procedural 2D Flower Beds

The flower-bed study uses the existing `CH_2D_ORGANIC_SCENERY_V1` contract with `sceneryType: "flower_bed"` and the frozen `CH_CAMERA_V1` tile contract (`128x64`). It is a deterministic 2D raster-painted generator inside Visitor Forge 2D; Blender is not involved.

The canonical study recipe is `examples/flower_bed_01.json`. It targets a 1x1 decorative footprint and intentionally favors a dense, irregular green mound with tall yellow flower stalks, visible warm soil/stone edging, gameplay-scale texture and small raster accents rather than clean vector petals.

Render it with:

```bash
PYTHONPATH=tools/visitor_forge_2d/src \
python -m visitor_forge_2d.core.flower_bed_scenery \
  --recipe tools/visitor_forge_2d/examples/flower_bed_01.json \
  --output out/flower_bed
```

Outputs:

- `flower_bed_01.png`: transparent RGBA gameplay sprite;
- `flower_bed_01_review.png`: 1x gameplay plus 2x nearest-neighbor inspection;
- `flower_bed_01_isometric_review.png`: placement on the canonical isometric grid;
- `flower_bed_01.json`: provenance and bounds.

The generator is seed-driven and deterministic. Edit the recipe for palette, flower density, mound density, footprint shape and raster density. Keep the camera, tile and anchor contract unchanged unless a real placement defect is proven in MapForge/runtime.

The reference target for this family is a classic raster/pre-rendered tycoon read: dense organic foliage, a slightly pixel-textured finish and flowers that remain legible at gameplay scale. Do not promote generated output to runtime solely because tests pass; inspect the 1x review and in-grid review first.
