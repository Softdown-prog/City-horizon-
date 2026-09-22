# Raspadinha Vendor — Lightweight Animation Production Plan

Status: approved production direction; Phase 2 SOUTH proxy v2 generated for review

This document defines the intended animation scope for the approved `raspadinha_vendor` asset. The goal is to add a small amount of life without turning the prop into a complex character-animation project.

## Production decision

Keep the current static four-direction runtime asset as the shipping baseline.

Animation is optional enrichment and must remain cheap, deterministic, reusable, and agent-friendly.

Do not build a large cinematic or high-frame-count animation system for this prop.

## Phase 1 — current shipping state

Use the already-approved static asset:

- `assets/props/raspadinha_vendor/raspadinha_vendor_south.png`
- `assets/props/raspadinha_vendor/raspadinha_vendor_east.png`
- `assets/props/raspadinha_vendor/raspadinha_vendor_west.png`
- `assets/props/raspadinha_vendor/raspadinha_vendor_north.png`

This remains the fallback if any animation work becomes disproportionately expensive.

## Phase 2 — first animation to implement

Implement only a short `GREET` behavior in addition to `IDLE`.

Target behavior:

- vendor remains in the approved base pose most of the time;
- occasionally performs a short wave/greeting toward the street;
- returns to the exact base pose;
- no full-body locomotion;
- no exaggerated body motion;
- no continuous looping wave;
- no requirement for many frames.

Preferred production target:

- `IDLE`: 1 canonical pose per direction;
- `GREET`: smallest frame count that reads clearly at gameplay scale;
- event-driven playback with long idle intervals;
- static cart and umbrella unless a concrete visual reason requires otherwise.

The objective is a "living sprite" effect, not modern full-character animation.

### Current Phase 2 authority

The original experimental GREET keyframes in `build_raspadinha_vendor_blender.py` are **not** production authority. Visual proxy review showed that they read as a downward/outward arm rather than a greeting.

Use these files for the reviewed Phase 2 path:

- `tools/tycoon_photo_studio/raspadinha_vendor_greet_v1.py` — lightweight raised-hand GREET pose authority for frames 5–8;
- `tools/tycoon_photo_studio/build_raspadinha_vendor_animation_review_guarded.py` — cheap 20-sample structural review and SOUTH animation spritesheet;
- `tools/tycoon_photo_studio/build_raspadinha_vendor_animated_v2_guarded.py` — canonical guarded builder for any future final bake.

Current review frame order is:

```text
IDLE 1 -> GREET 5 -> GREET 6 -> GREET 7 -> GREET 8/return-to-idle
```

Do not use the older `build_raspadinha_vendor_animated_guarded.py` directly for a final production bake unless it has first been updated to apply the same GREET authority.

## Phase 3 — SERVE only when customer interaction exists

Do not implement `SERVE` merely because the reference art contains it.

Add `SERVE` only after gameplay has a real customer/NPC interaction that can trigger the behavior.

When implemented, keep it short and conservative:

- torso mostly stable;
- one arm reaches toward cup/product area;
- optional small head turn;
- hand-off/serving gesture;
- return to `IDLE`;
- no locomotion;
- no complex finger animation;
- no unnecessary secondary motion.

A rough target of a few key poses / low frame count is preferred over 20+ unique frames.

## CH Blender implementation direction

If animation work proceeds, prefer a reusable minimal rig/action layer rather than rebuilding poses from scratch for every vendor.

Suggested reusable contract:

`CH_HUMAN_VENDOR_RIG_V1`

Initial actions:

- `IDLE`
- `GREET`
- later: `SERVE`

Agent-facing intent should be semantic, for example:

```text
apply_action("greet")
apply_action("serve", hand="right", target="customer")
```

The implementation may internally use Blender Actions / armature keyframes, but agents should not need to invent arbitrary bone rotations every time.

## Mandatory quality flow

Any new animation authored through CH Blender must preserve the existing fail-fast pipeline:

```text
animation authoring
  -> structural preflight across review poses
  -> cheap SOUTH animation spritesheet
  -> visual review
  -> four-direction proxy if needed
  -> final bake only after approval
```

Do not immediately render all directions and all animation frames in Cycles after changing a pose.

## Stop rule

If `GREET` requires major rig reconstruction, large runtime changes, many bespoke frames, or repeated visual repair, stop and keep the vendor static.

The static approved asset is already acceptable production content.

Animation is only worth keeping if it remains a small, reusable enhancement.

## Style intent

The City Horizon target is a Windows 2D pre-rendered city-builder with classic-tycoon influence. Animation should therefore favor readable, infrequent, economical state changes over continuous high-frame-rate motion.

The original visual reference establishes three useful states conceptually:

1. friendly idle;
2. greeting/waving;
3. serving/preparing raspadinha.

These are references for behavior and pose, not a requirement to reproduce the original generated images frame-for-frame.
