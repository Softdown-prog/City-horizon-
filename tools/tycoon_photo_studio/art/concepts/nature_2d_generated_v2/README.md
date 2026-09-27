# Nature 2D generated review V2

These are **new 2D painted RGBA masters** made with the built-in image generation tool using the two user-supplied reference captures. The captures guide subject, palette, camera and density; they are not raster sources for background removal. This corrects V1, where we recreated the art with simple Pillow polygons and then extracted it from JPEG screenshots. V1 was visually rejected and removed from the working tree.

| Asset | Master | Game-size candidate | Placement for review |
| --- | --- | --- | --- |
| Pine | `sources/pine_master_rgba.png` | `pine_2d_candidate.png` (256×368) | Base near (128, 357) |
| Golden flower bed | `sources/flower_bed_master_rgba.png` | `flower_bed_2d_candidate.png` (256×160) | Base near (128, 151), one 128×64 tile |

`nature_2d_review.png` shows both candidates at 1× and nearest-neighbor 2× on a neutral green tile comparison. Regenerate the game-size exports with:

```sh
python tools/tycoon_photo_studio/export_nature_2d_rgba.py
```

The exporter accepts only actual RGBA PNG masters with transparent margins. It does not reconstruct transparency from a screenshot, flatten on black, add outlines, quantize colors or create new artwork.

## Runtime promotion

The player authorized runtime integration after the visual review. `pine_2d_candidate.png` now supplies `assets/tree/pine_tree_01.png`; `flower_bed_2d_candidate.png` supplies `assets/decor/flower_bed_01.png`. The corresponding definitions are `assets/definitions/pine_tree_01.json` and `assets/definitions/flower_bed_01.json`. Both appear in the decoration catalog without a new renderer path. The pine keeps the existing `pine_tree_01` ID so saved placements resolve.

`runtime_placement_review.png` compares the prior deterministic pine with both new sprites using the actual definition art scales and normalized anchors on 128×64 diamonds. It is a static placement check; a capture from the running SDL game remains useful for final judgment.

## Generation prompts, condensed

- Pine: rebuild the supplied conifer as a standalone transparent 2D sprite, retaining its tapered silhouette, irregular layered boughs, mint/deep-green palette and narrow foot; replace compression spots with coherent needles and soft green shadows.
- Flower bed: rebuild the supplied low emerald-green mound, warm soil lip and many small yellow four-point flowers on stems as a standalone transparent one-tile sprite; replace screenshot artifacts with coherent leaves and soft green shadows.

Before runtime promotion, compare the 1× results with the game's current vegetation on a real map capture. The new pine has fuller, more regular branches than the reference; its density and shadow behavior may need another art pass. Also check the flower bed's footprint, alpha edges and tile contact at the intended game zoom.
