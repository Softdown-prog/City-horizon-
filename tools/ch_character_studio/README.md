# CH Character Studio Art V0

CH Character Studio Art separates **appearance authoring** from **approved character motion**. CH Blender supplies pose, depth, canonical camera and landmarks; the Studio owns visible art, masks, palettes, optional hand props and review tooling.

## Locked runtime contract

- frame: `48x64`
- ground anchor: `[24,60]`
- directions: `S/E/N/W`
- walk: approved CH Actor, 8 frames
- canonical camera: `CH_ACTOR_CAMERA_V1`
- art, props and inspection tools may not change approved motion or runtime anchor

## Current pipeline

```text
character spec
  -> CH Blender canonical base + 36-state landmarks
  -> ground / foot-anchor / footprint validation
  -> Studio semantic layers / deterministic drawing CLI
  -> Photoshop-reference pixel tools + advanced layer stack + art tools
  -> landmark pose transfer
  -> appearance + clothing + held-object RGB masks
  -> optional hand-held prop sockets
  -> 1px outline/readability
  -> rotatable non-canonical inspection renders
  -> visual review
  -> runtime export
```

## Editor

`index.html` provides native 48x64 editing with pixel brush/eraser, smart shapes, character templates, semantic layers, broad palette families, frame/direction storage, pose propagation, mask painting, held-object sockets and spatial debug overlays.

The spatial overlay can show the canonical ground anchor, left/right foot anchors, selected support foot, projected character footprint and left/right hand sockets. These overlays never enter exported character PNGs.

## Photoshop-reference tools

The Studio uses selected Photoshop-style concepts without trying to clone Photoshop itself.

Stage 1 (`CH_CHARACTER_PHOTOSHOP_TOOLS_V0`) provides rectangular/lasso selection, move/free-transform, eyedropper, paint bucket, fill/delete selection, per-frame undo/redo, opacity and blend modes.

Stage 2 (`CH_CHARACTER_LAYER_STACK_V0`) provides layer groups, layer masks, clipping masks, non-destructive transform state, duplicate layer, safe merge/flatten, source restore, per-frame stack state and advanced composite export.

Stage 3 (`CH_CHARACTER_ART_TOOLS_V0`) provides:

- brush presets: Pixel 1, Pixel 2, Hard Round, Marker, Dither and Airbrush;
- brush size, spacing, opacity and flow;
- vertical, horizontal and quad symmetry;
- linear/radial two-color gradients preserving existing alpha;
- Levels;
- piecewise-linear Curves at 0/64/128/192/255;
- Hue/Saturation/Lightness adjustment.

Stage 3 works on authoritative semantic art layers such as `skin`, `hair`, clothing and `paint_over`. If an advanced duplicate/merged/flattened entry is selected, it refuses to silently edit a different source layer.

## Palette library

Authoritative palette: `palettes/ch_character_palette_v1.json` (`CH_CHARACTER_PALETTE_V1`). It includes stable named IDs for skin, hair, neutral, vivid, pastel, earth, deep, metal and fantasy families. Random palette selection requires an explicit deterministic seed.

## Deterministic drawing CLI

`character_draw_cli.py` renders `CH_CHARACTER_DRAW_RECIPE_V0` recipes at native 48x64. Supported primitives are pixel, rectangle, ellipse, polygon and line. Recipes may target a normal art layer or a semantic RGB mask bank.

```bash
python tools/ch_character_studio/character_draw_cli.py \
  --recipe <recipe.json> --out <layer.png> --seed 1337
```

The report contains the output SHA-256 so agents can prove byte-stable results.

## Deterministic workers / subagent packets

`workers/ch_character_workers_v0.json` defines role-limited workers for spatial validation, silhouette art, face art, masks, held objects, inspection review and production QA.

`character_workers.py` creates stable work packets; it does not pretend to spawn remote agents. Any repository-connected agent can consume a packet and return `CH_CHARACTER_WORKER_HANDOFF_V0`.

```bash
python tools/ch_character_studio/character_workers.py plan \
  --spec tools/ch_character_studio/specs/clown_01.character.json \
  --seed 1337 --out out/ch_character_studio/clown_01/work_plan.json
```

Agent-specific operational instructions live in `AGENTS.md`.

## Canonical and inspection cameras

Canonical runtime jobs:

```bash
python tools/ch_character_studio/character_studio.py make-job \
  --spec tools/ch_character_studio/specs/clown_01.character.json \
  --stage proxy --direction S --frame idle \
  --out tools/ch_blender/jobs/character.clown_01.proxy.s_idle.job.json
```

Rotatable inspection jobs:

```bash
python tools/ch_character_studio/character_studio.py make-inspection-job \
  --spec tools/ch_character_studio/specs/clown_01.character.json \
  --direction S --frame idle \
  --yaw 120 --pitch 25 --ortho-scale 1.8 --resolution-scale 4 \
  --out tools/ch_blender/jobs/character.clown_01.inspect.120.job.json
```

Inspection produces `inspection.png` and explicitly records `runtimeExportAllowed=false`. It exists for screenshots, silhouette/occlusion checks and agent review only.

## Spatial gate

Run after generating `landmarks.json`:

```bash
python tools/ch_character_studio/validate_spatial.py \
  --landmarks out/.../landmarks.json \
  --report out/.../spatial_report.json
```

The gate validates all 36 states, the fixed ground anchor, foot/ankle bounds, support-foot distance, projected footprint polygon and hand-socket alignment.

## Pose propagation

CH Blender exports `CH_CHARACTER_LANDMARKS_V0` for all 36 states. The Studio can freeze one approved art frame and deform its semantic layers through those landmarks to the remaining frames of the same direction. Appearance and clothing masks follow the same transfer; the outline is regenerated rather than warped. Cross-direction automatic transfer remains disabled because it would invent hidden surfaces.

## Color masks

Character Studio uses three independent packed RGB banks:

- appearance: `R=skin`, `G=hair`, `B=appearance_accent`
- clothing: `R=primary_clothing`, `G=secondary_clothing`, `B=clothing_accent`
- held object: `R=object_primary`, `G=object_secondary`, `B=object_accent`

Alpha is coverage only. Masks never contain lighting, AO, outline or dithering.

## Held objects

`left_hand` and `right_hand` are invisible sockets driven by canonical hand landmarks. A balloon, broom, tool or another prop can be enabled later without changing the character walk. Visual and mask always share the same grip transform. If an object has no authored mask, opaque pixels fall back to `held_object.R`.

## Design rule

**Blender solves spatial consistency. Character Studio owns final visible style. Inspection and Photoshop-reference tooling may explore/edit appearance freely but may never rewrite the canonical runtime contract.**
