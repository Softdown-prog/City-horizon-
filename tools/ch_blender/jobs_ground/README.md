# CH Blender ground-asset job lane

This directory is the dedicated CH Blender queue for ground-facing assets such as terrain tiles, surface tiles, farming-ground overlays and other map-ground visuals.

It is intentionally separate from `tools/ch_blender/jobs/`, which remains the general/building/prop queue.

Ground jobs use the same `CH_BLENDER_AGENT_JOB_V1` contract and the same frozen CH Blender 4.2.3 / `CH_CAMERA_V1` / `CH_TYCOON_STUDIO_V1` contracts. The separation is only at queue/trigger level so ground assets can be dispatched and diagnosed without mixing with building/prop jobs.

Use unique `*.ground.job.json` files. Do not place building/prop jobs here.
