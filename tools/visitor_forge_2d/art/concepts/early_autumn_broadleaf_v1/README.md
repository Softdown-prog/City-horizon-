# Early autumn broadleaf study

Generated from `examples/briefs/park_tree_early_autumn.json` using `author-art`.
The PNG and boards are visual review candidates, not approved runtime assets.

Inspection at 1x and on the canonical grid: the canopy is one connected,
rounded mass with separate olive/gold clusters. The earlier `organic_02`
candidate had four visible horizontal shelves and a nearly flat gold front.
The current candidate still has conspicuous large clumps and four views that
look similar; decide whether its painterly structure fits the game before
promoting or requesting another focused art revision.

The deterministic author selected the new continuous broadleaf template,
kept the `CH_CAMERA_V1` anchor/canvas, used seed `84317` and density `dense`.
To regenerate the study:

```bash
PYTHONPATH=tools/visitor_forge_2d/src python -m visitor_forge_2d author-art \
  --brief tools/visitor_forge_2d/examples/briefs/park_tree_early_autumn.json \
  --output out/visitor_forge_2d/author
```
