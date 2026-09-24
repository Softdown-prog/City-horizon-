# Compact 256 pipeline

Default City Horizon runtime render class.

Use this pipeline for normal buildings, props, scenery and any asset whose silhouette/material read survives gameplay-scale downsampling.

- studio contract: `CH_TYCOON_STUDIO_V1`
- camera: `CH_CAMERA_V1`
- source: 1024×1024
- final: 256×256
- output: transparent PNG RGBA
- directions: SOUTH / EAST / WEST / NORTH

Preset: `studio.json`.

This is the economical/default path. Do not move an asset to the large pipeline merely because a larger isolated PNG looks nicer. Escalate only when thin geometry, landmark scale, tall-building scale or map inspection shows a real loss of readability.
