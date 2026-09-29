# CH Character Studio Art — Agent Entry Point

This directory is the agent-facing entry point for City Horizon character art. Do not change approved CH Actor motion, canonical camera, frame size or ground anchor to solve an art problem.

## Read first

1. `studio_manifest.json`
2. `contracts/ch_character_spatial_v0.json`
3. `contracts/ch_character_color_mask_v0.json`
4. `contracts/ch_character_hand_socket_v0.json`
5. `contracts/ch_character_photoshop_tools_v0.json`
6. `palettes/ch_character_palette_v1.json`
7. `workers/ch_character_workers_v0.json`

Canonical runtime frame: `48x64`. Canonical ground anchor: `[24,60]`. Canonical runtime camera remains `CH_ACTOR_CAMERA_V1`.

## Photoshop-reference editing tools

The Studio borrows productive image-editing concepts from Photoshop, but it is not a UI clone and must remain character-production focused.

Stage 1 is implemented through `CH_CHARACTER_PHOTOSHOP_TOOLS_V0` and `photoshop_tools.js`:

- rectangular selection (`M`);
- lasso selection (`L`);
- move selected pixels (`V`);
- nearest-neighbor transform with translation, scale, rotation and H/V flip;
- eyedropper (`I`);
- paint bucket with tolerance (`G`);
- fill/delete selection;
- per-frame undo/redo (`Ctrl+Z`, `Ctrl+Shift+Z`), capped at 50 checkpoints;
- layer opacity;
- layer blend modes.

Selections and transforms affect only the active art layer. They must never move the character ground anchor, edit CH Actor motion, modify Blender landmarks, or become a substitute for pose editing.

Stage 2 is reserved for groups, layer masks, clipping masks, non-destructive transform state and duplicate/merge/flatten operations. Stage 3 is reserved for advanced brushes, gradients and tonal/color adjustment tools.

## Deterministic workers / subagent handoff

The Studio does not claim to spawn remote agents. It creates deterministic work packets that ChatGPT, Codex, Claude or another repository-connected agent can consume.

```bash
python tools/ch_character_studio/character_workers.py plan \
  --spec tools/ch_character_studio/specs/clown_01.character.json \
  --seed 1337 \
  --out out/ch_character_studio/clown_01/work_plan.json
```

Generate one packet only:

```bash
python tools/ch_character_studio/character_workers.py plan \
  --spec tools/ch_character_studio/specs/clown_01.character.json \
  --seed 1337 \
  --worker silhouette_artist
```

Every worker returns `CH_CHARACTER_WORKER_HANDOFF_V0`. Validate a handoff with:

```bash
python tools/ch_character_studio/character_workers.py validate-handoff --handoff <handoff.json>
```

The same spec + base seed + worker ID must produce the same worker seed and plan hash.

## CLI drawing

Use `CH_CHARACTER_DRAW_RECIPE_V0` recipes for deterministic 48x64 art/mask drawing:

```bash
python tools/ch_character_studio/character_draw_cli.py \
  --recipe art/clown_01/south_idle_face.recipe.json \
  --out art/clown_01/south/idle/face.png \
  --seed 1337
```

Supported primitives: pixel, rect, ellipse, polygon and line. Mask recipes target one of `appearance`, `clothing`, `held_object` and use semantic channel `R/G/B` instead of painted color.

## Spatial validation

`landmarks.json` exports per-frame:

- fixed `ground` anchor;
- `leftFoot` and `rightFoot` anchors;
- selected `supportFoot`;
- projected 2:1-ground footprint polygon;
- left/right hand sockets.

The editor can display these without putting them into exported PNGs.

## Rotational inspection camera

The canonical camera is locked. For visual review, create a separate non-canonical inspection job:

```bash
python tools/ch_character_studio/character_studio.py make-inspection-job \
  --spec tools/ch_character_studio/specs/clown_01.character.json \
  --direction S --frame idle \
  --yaw 120 --pitch 25 --ortho-scale 1.8 --resolution-scale 4 \
  --out tools/ch_blender/jobs/character.clown_01.inspect.120.job.json
```

Inspection output is `inspection.png`; its report sets `runtimeExportAllowed=false`. Never promote it as runtime art. Use it only for screenshots, occlusion checks, silhouette review and diagnosing props/clothing.

Canonical jobs still use:

```bash
python tools/ch_character_studio/character_studio.py make-job \
  --spec tools/ch_character_studio/specs/clown_01.character.json \
  --stage proxy --direction S --frame idle \
  --out tools/ch_blender/jobs/character.clown_01.proxy.s_idle.job.json
```

## Palette rules

Use stable IDs from `CH_CHARACTER_PALETTE_V1` when possible. Families include skin, hair, neutral, vivid, pastel, earth, deep, metal and fantasy. Random selection requires an explicit seed.

## Mask rules

There are three independent RGB banks: appearance, clothing and held object. Alpha is coverage only. Never put lighting, AO, outline or dithering into masks.

## Stop conditions

Stop and report instead of improvising if:

- ground anchor moves from `[24,60]`;
- a foot contact is outside the frame;
- support foot is more than 10 px from the ground anchor without a justified airborne pose;
- inspection output is being used as runtime output;
- a worker packet asks an agent to edit outside its `mayEdit` scope;
- mask and visual transforms differ;
- a held object changes approved hand motion;
- a Photoshop-reference transform is being used to alter body pose instead of appearance;
- a selection/transform operation writes outside the active art layer.
