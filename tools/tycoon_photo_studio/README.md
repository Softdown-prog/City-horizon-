# Tycoon Photo Studio — Proof of Concept

Status: VISUAL EXPERIMENT ONLY

This folder exists to answer one question before more editor/tooling work is funded:

> Can a deterministic Blender headless bake plus controlled post-processing produce a City Horizon sprite that belongs visually to the classic Zoo Tycoon 1 / RollerCoaster Tycoon family?

## Deliberate scope

The POC uses one small park kiosk only. It does not add editor UI, AI authoring, Layers tooling, carousel work or a general renderer framework.

The fixed studio contract is:

- `CH_CAMERA_V1` visual target;
- orthographic camera;
- 45 degree yaw;
- 30 degree elevation;
- warm northwest key light;
- cool southeast fill light;
- supersampled 1024x1024 source render;
- 256x256 review output;
- separate object color source and ground-shadow reference;
- deterministic post-processing.

## Four review variants

1. Full-color smooth downsample.
2. 128-color palette reduction without dithering.
3. 128-color palette reduction with Floyd-Steinberg dithering.
4. Variant 3 plus hard alpha cleanup and a restrained one-pixel sel-out experiment.

The point is not to claim that any of these is historically identical to Zoo Tycoon 1. The point is to isolate which treatment produces the strongest small-sprite miniature read for City Horizon.

## Outputs

The GitHub Actions workflow `Tycoon Photo Studio POC` publishes the artifact `Tycoon-Photo-Studio-POC` containing:

- `tycoon_photo_studio_variant_01.png`
- `tycoon_photo_studio_variant_02.png`
- `tycoon_photo_studio_variant_03.png`
- `tycoon_photo_studio_variant_04.png`
- `tycoon_photo_studio_color_pass.png`
- `tycoon_photo_studio_shadow_pass.png`
- `tycoon_photo_studio_comparison_board.png`
- `tycoon_photo_studio_in_game_context.png`
- `tycoon_photo_studio_manifest.json`
- raw 1024px source/reference passes

The context image is explicitly synthetic and is **not** a runtime screenshot.

## Stop rule

A green workflow means only that the deterministic bake pipeline executed successfully. It does **not** mean the art is approved.

Do not expand this into a general production tool until the downsampled result is manually accepted as belonging to the intended classic Tycoon visual family. If the result fails visually, adjust geometry, lighting, materials and post-processing here first.
