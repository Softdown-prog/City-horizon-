# CH Character Studio Art V0

CH Character Studio Art separates **character appearance** from **character motion**.

The approved CH Actor walk, frame size, ground anchor and CH Actor camera stay authoritative. CH Blender runs underneath the Studio to provide consistent pose/camera/depth and projected landmarks; the Studio owns the final visible art, recolor masks and optional hand props.

## Pipeline

```text
Character Spec
  -> CH Blender base pass + pose landmarks
  -> Studio paint layers
  -> landmark pose transfer
  -> appearance/clothing/held-object color masks
  -> optional held object on invisible hand socket
  -> outline/readability pass
  -> preview
  -> spritesheet/export
```

The design rule is simple: **Blender solves spatial consistency; Studio Art owns the final character style.**

## V0 contracts

- studio: `CH_CHARACTER_STUDIO_V0`
- editable character spec: `CH_CHARACTER_ART_SPEC_V0`
- pose transfer: `CH_CHARACTER_POSE_TRANSFER_V0`
- color masks: `CH_CHARACTER_COLOR_MASK_V0`
- invisible hand sockets: `CH_CHARACTER_HAND_SOCKET_V0`
- CH Blender job: `CH_BLENDER_AGENT_JOB_V1`
- frame: `48x64`
- ground anchor: `[24,60]`
- directions: `S/E/N/W`
- walk: approved CH Actor, 8 frames
- art, masks and held objects are forbidden from changing pose or anchor

## Art layers

The canonical editable layer order is:

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

Each layer is optional unless a character spec marks it as required. PNG layers are authored at native 48x64. The editor also provides smart shapes, reusable character templates, a true dilated 1px outline and independent art storage for every direction/frame.

## Pose propagation

CH Blender exports `CH_CHARACTER_LANDMARKS_V0` for all 36 states: four directions multiplied by idle + eight walk frames. The Studio can freeze one approved art frame as a reference and deform its semantic layers through those landmarks to the remaining frames of the same direction.

Appearance and clothing color masks follow the same reference/propagation operation. The outline is regenerated after transfer instead of being warped.

Cross-direction automatic transfer stays disabled because it would have to invent hidden character surfaces.

## Color masks

Character masks extend the repository `CH_COLOR_MASK_V1` packed-RGB policy, but use three independent banks so character semantics are not forced into one texture:

```text
appearance
  R = skin
  G = hair
  B = appearance_accent

clothing
  R = primary_clothing
  G = secondary_clothing
  B = clothing_accent

held_object
  R = object_primary
  G = object_secondary
  B = object_accent
```

Alpha is coverage only. It is never a fourth tint channel. Masks must not contain lighting, AO, cast shadows, outlines, dithering or palette reduction.

The editor can paint/erase mask pixels directly, fill current visual coverage into a selected channel, preview a bank over the character and export one or all three frame-aligned PNG masks.

## Invisible hand sockets and held objects

Every character is prepared for optional props through `CH_CHARACTER_HAND_SOCKET_V0`:

```text
left_hand  -> landmark hand_L
right_hand -> landmark hand_R
```

Sockets are invisible in exported art. The debug cross exists only inside the Studio.

A held object declares:

- enabled/disabled state;
- object ID;
- left or right hand socket;
- front/back/automatic depth;
- visual PNG;
- optional RGB color-mask PNG;
- grip-anchor pixel inside the object image;
- integer X/Y offset.

The same transform is applied to the object visual and its mask on every animation frame. This lets a character later activate a balloon, broom, tool or other prop without changing the approved walk.

If an object has no authored mask, every opaque object pixel automatically becomes `held_object.R` (`object_primary`). A disabled object produces no visible pixels and an empty held-object mask.

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

## V0 status

Implemented:

- Studio contract and locked actor rules
- editable character specification
- CH Blender spatial underlay and 36-state landmarks
- visual paint editor with brush/eraser/layers/palette
- smart semantic character shapes and templates
- independent art storage per direction and animation frame
- same-direction appearance propagation through landmarks
- true 1px dilated outline generation
- three packed RGB character mask banks
- mask painting, preview and PNG export
- mask propagation with the approved pose landmarks
- invisible left/right hand sockets
- optional held-object visual + RGB mask attachment
- automatic object-primary fallback mask
- composite export with an active held object
- clown test spec prepared for masks and an inactive hand prop slot
