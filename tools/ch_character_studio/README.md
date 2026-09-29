# CH Character Studio Art V0

CH Character Studio Art separates **character appearance** from **character motion**.

The approved CH Actor walk, frame size, ground anchor and CH Actor camera stay authoritative. CH Blender runs underneath the Studio to provide consistent pose/camera/depth and render passes; the Studio owns the final visible art through paintable layers and palette/mask data.

## Pipeline

```text
Character Spec
  -> CH Blender base passes
  -> Studio paint layers
  -> recolor mask
  -> outline/readability pass
  -> preview
  -> spritesheet/export
```

The design rule is simple: **Blender solves spatial consistency; Studio Art owns the final character style.**

## V0 contracts

- studio contract: `CH_CHARACTER_STUDIO_V0`
- editable character spec: `CH_CHARACTER_ART_SPEC_V0`
- CH Blender job: `CH_BLENDER_AGENT_JOB_V1`
- frame: `48x64`
- ground anchor: `[24,60]`
- directions: `S/E/N/W`
- walk: approved CH Actor, 8 frames
- art is forbidden from changing pose or anchor

## Art layers

The canonical layer order is:

```text
silhouette
skin
hair
face
upper_clothing
lower_clothing
footwear
accessories_back
accessories_front
paint_over
outline
```

Each layer is optional unless a character spec marks it as required. PNG layers are composed at native 48x64 and can later be edited by the visual Studio UI.

## CH Blender underlay

`character_studio.py make-job` creates a guarded CH Blender job instead of bypassing the repository pipeline. This preserves the existing preflight -> proxy -> reviewed final policy.

Example:

```bash
python tools/ch_character_studio/character_studio.py validate-spec \
  --spec tools/ch_character_studio/specs/clown_01.character.json

python tools/ch_character_studio/character_studio.py make-job \
  --spec tools/ch_character_studio/specs/clown_01.character.json \
  --stage preflight \
  --out tools/ch_blender/jobs/character.clown_01.studio.preflight.001.job.json
```

After CH Blender produces the base frame/pass, Studio layers can be composited with:

```bash
python tools/ch_character_studio/character_studio.py compose \
  --spec tools/ch_character_studio/specs/clown_01.character.json \
  --base out/ch_character_studio/clown_01/base.png \
  --layers art/clown_01/south/walk_00 \
  --out out/ch_character_studio/clown_01/preview.png
```

## Why this replaces the current clown approach

The current CH Clown generator mixes pose reconstruction and appearance drawing in one Python renderer. That was useful to prove the walk, but it makes art refinement slow and code-heavy. Character Studio keeps the approved walk untouched and turns the visible character into editable art data.

This means a clown, worker, visitor, police officer or any future profession can share the same motion skeleton while independently changing silhouette, proportions, clothing, hair, facial design, material treatment and paint-over.

## V0 status

Implemented:

- Studio contract and locked actor rules
- editable character specification
- palette and ordered art layers
- CH Blender guarded-job generation
- 48x64 paint-layer compositor
- clown test spec

Next implementation layer is the visual editor: canvas, brush/eraser, layer visibility, palette controls, reference/base-pass overlays, direction/frame selector and export controls.
