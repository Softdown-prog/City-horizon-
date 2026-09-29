# CH Character Studio Art — Agent Entry Point

This directory is the agent-facing entry point for City Horizon character art. Do not change approved CH Actor motion, canonical camera, frame size or ground anchor to solve an art problem.

## Read first

1. `studio_manifest.json`
2. `contracts/ch_character_spatial_v0.json`
3. `contracts/ch_character_color_mask_v0.json`
4. `contracts/ch_character_hand_socket_v0.json`
5. `contracts/ch_character_photoshop_tools_v0.json`
6. `contracts/ch_character_layer_stack_v0.json`
7. `contracts/ch_character_art_tools_v0.json`
8. `palettes/ch_character_palette_v1.json`
9. `workers/ch_character_workers_v0.json`

Canonical runtime frame: `48x64`. Canonical ground anchor: `[24,60]`. Canonical runtime camera remains `CH_ACTOR_CAMERA_V1`.

## Photoshop-reference editing tools

The Studio borrows productive image-editing concepts from Photoshop, but it is not a UI clone and must remain character-production focused.

### Stage 1 — pixel editing

Implemented through `CH_CHARACTER_PHOTOSHOP_TOOLS_V0` and `photoshop_tools.js`:

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

Selections and destructive transforms affect only the active art layer. They must never move the character ground anchor, edit CH Actor motion, modify Blender landmarks, or become a substitute for pose editing.

### Stage 2 — advanced layer stack

Implemented through `CH_CHARACTER_LAYER_STACK_V0`, `photoshop_layers_v2.js` and `photoshop_layers_v2_bridge.js`.

The advanced stack provides:

- Photoshop-style layer groups with visibility and group opacity;
- layer masks linked to the layer transform;
- mask creation from white or source alpha;
- black/white mask painting and mask inversion;
- clipping mask to the immediately previous visible stack entry;
- non-destructive X/Y, scale, rotation and H/V flip state;
- layer duplication;
- safe merge that creates a new raster layer and hides, rather than deletes, its sources;
- safe flatten that creates a flattened art layer while preserving hidden semantic sources;
- restore-source operation;
- per-frame stack state and independent stack undo/redo;
- layer-mask PNG export and stack-metadata JSON export.

The compatibility bridge keeps the main visible canvas equal to base + advanced art. This is important because older tools such as eyedropper and color-mask coverage must continue reading the visible final character rather than only the Blender underlay.

Canonical semantic layers remain authoritative. Do not permanently collapse `skin`, `hair`, clothing or other semantic layers merely to simplify a one-off art operation. Use safe merge/flatten for review and raster validation while preserving the source stack.

### Stage 3 — brushes and color/tonal tools

Implemented through `CH_CHARACTER_ART_TOOLS_V0` and `photoshop_art_v3.js`.

Brush engine:

- presets: `pixel_1`, `pixel_2`, `hard_round`, `marker`, `dither`, `airbrush`;
- brush size from 1 to 12 px;
- spacing from 5% to 200%;
- stroke opacity and flow as separate controls;
- vertical, horizontal and quad symmetry around the locked 48x64 frame center;
- deterministic checker dither;
- no spatial image smoothing.

Gradient and adjustments:

- linear and radial two-color gradients;
- gradient opacity while preserving existing layer alpha;
- Levels with input black/white, gamma and output black/white;
- Curves using output values for fixed input points 0/64/128/192/255 with piecewise-linear interpolation;
- Hue, Saturation and Lightness adjustment;
- alpha is preserved by Levels, Curves and Hue/Saturation.

Stage 3 tools write only to the selected canonical semantic art layer. If a duplicate, merged or flattened raster entry is selected in the Stage 2 stack, Stage 3 must refuse the edit instead of silently modifying a different semantic layer. Select `skin`, `hair`, clothing, `paint_over`, etc. first.

Every Stage 3 raster edit creates a Studio history checkpoint. These tools may improve color, shading, edge treatment or local paint, but they must never paint around a bad pose to hide an anchor/contact/landmark problem. Fix spatial problems in the CH Actor/CH Blender source instead.

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

There are three independent RGB recolor banks: appearance, clothing and held object. Alpha is coverage only. Never put lighting, AO, outline or dithering into those recolor masks.

Layer masks are a separate Photoshop-reference concept. Their alpha represents visibility for one art layer and must never be confused with the RGB recolor-mask banks.

## Stop conditions

Stop and report instead of improvising if:

- ground anchor moves from `[24,60]`;
- a foot contact is outside the frame;
- support foot is more than 10 px from the ground anchor without a justified airborne pose;
- inspection output is being used as runtime output;
- a worker packet asks an agent to edit outside its `mayEdit` scope;
- recolor mask and visual transforms differ;
- a held object changes approved hand motion;
- a Photoshop-reference transform is being used to alter body pose instead of appearance;
- a selection/transform operation writes outside the active art layer;
- a layer mask is mistaken for an appearance/clothing/object recolor mask;
- safe merge/flatten is used as a reason to delete the canonical semantic source layers;
- a Stage 3 brush or tonal adjustment is used to paint over a spatial/pose defect that belongs in CH Actor/CH Blender;
- Stage 3 is asked to edit a duplicate/merged/flattened raster entry without first selecting an authoritative semantic source layer.
