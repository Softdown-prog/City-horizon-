# City Horizon Tycoon Asset Baker V1

Status: **production pipeline active; frozen studio V1**

City Horizon renders final game art offline in Blender and ships only 2D RGBA PNG packages to the SDL3 runtime. The fixed visual authority is `CH_CAMERA_V1`: orthographic, yaw 45°, elevation 30°, 2:1 dimetric tiles.

## Canonical invocation

```bash
python tools/blender_bake_runner.py \
  --contract C++/MapForge2/presets/tycoon_asset_bake_contract.json \
  --asset-config tools/tycoon_photo_studio/assets/neighborhood_cafe_2x1.json \
  --studio-preset tools/tycoon_photo_studio/studio_presets/ch_tycoon_studio_v1.json \
  --blender /path/to/blender \
  --output-dir out/neighborhood_cafe_2x1
```

The runner is the only orchestration entry point. It forwards the declarative source and frozen preset to Blender, runs post-process and validation, creates a road/sidewalk/terrain placement board for all four rotations, and writes `bake_run_report.json`.

Use the optional promotion bridge only after visual approval:

```bash
  --promote-asset-dir assets/buildings \
  --promote-pack-out assets/definitions/buildings/neighborhood_cafe_2x1_pack.json
```

Promotion uses `asset_catalog_ingest.py`; it copies the exact validated PNG package and writes a `CH_CONTENT_PACK_V1` record. It never invents anchors: the shared pivot is the projection of world origin.

## Proven static assets

Both `park_kiosk_1x1` and `neighborhood_cafe_2x1` are baked in CI through the unchanged studio. This proves cross-asset coherence; the old “second asset” next-gate is complete.

## Source vocabulary

`TYCOON_ASSET_SOURCE_V1` supports boxes, pyramid roofs, UV spheres, cylinders, bevelled curves, Blender text and reusable `collection_instance` parts from a checked-in Blender library. This is enough for modular façades, signs, rails, vegetation, attractions and port details without changing camera, lighting or export rules.

## Character sequence standard

Visitor sprites use one canonical 3D source and action: eight directions × eight frames, one projected-origin pivot and `TYCOON_CHARACTER_SEQUENCE_V1`. The sequence is promoted through `character_catalog_ingest.py` into a `CH_ACTOR_CONTENT_PACK_V1`. Human gameplay-scale approval remains mandatory before shipping any candidate.
