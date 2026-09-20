# CH_STYLIZED_3D_PRERENDER_V1

Status: **AUTHORITATIVE VISUAL DIRECTION**

This contract defines the production visual language for City Horizon going forward.

## Core decision

City Horizon uses **stylized 3D assets rendered offline and shipped as 2D RGBA PNG sprites**.

The asset is allowed to visibly read as a stylized 3D render. The pipeline must **not** try to disguise Blender output as a year-2000 sprite through aggressive posterization, forced dithering, palette reduction, fake pixel-art treatment, or other destructive retro emulation.

The runtime remains 2D. Blender is an offline authoring/rendering tool only.

## Visual target

Target a clean, colorful, toy-like / miniature / diorama presentation with:

- simple, readable silhouettes;
- rounded and softened forms where appropriate;
- saturated but controlled colors;
- large material/value groupings that remain clear at gameplay scale;
- soft directional lighting;
- readable contact shadows and localized ambient occlusion;
- restrained gloss/specular response;
- simplified stylized materials rather than photorealism;
- prominent identifying props/signage for gameplay readability;
- enough depth and shading to preserve a deliberate 3D-rendered appearance.

The reference intent is closer to modern stylized tycoon/mobile/management-game prerender art than to hand-painted or retro pixel/isometric sprites.

## What is explicitly allowed

The following are **not defects** under this contract:

- smooth gradients produced by lighting;
- visibly rounded geometry;
- soft bevels;
- stylized highlights;
- soft AO/contact shadows;
- clean antialiasing;
- a miniature/toy-like 3D appearance;
- modern Blender rendering characteristics, provided they are controlled and coherent.

Do not reject an asset merely because the viewer can tell that it originated from 3D geometry.

## What to avoid

Reject or revise assets that read as:

- photoreal architectural visualization;
- physically accurate PBR showcase renders;
- raw low-poly geometry with no art treatment;
- generic engineering/CAD visualization;
- flat vector icon art;
- noisy procedural surfaces whose detail disappears at gameplay scale;
- retro/pixel filters applied only to hide the 3D origin;
- inconsistent camera, scale, lighting or material language between assets.

## Blender role

Blender is the primary production renderer for buildings, props, attractions, vegetation and other suitable assets.

Use it for:

- consistent geometry and proportions;
- canonical camera;
- four directional renders;
- controlled stylized lighting;
- contact shadows/AO;
- simplified materials;
- deterministic export.

The preferred result is a render that is already visually close to the final sprite. Post-processing should be corrective and presentation-oriented, not an attempt to erase the 3D rendering style.

## Camera and output

Use the existing canonical project rules unless a newer explicit contract supersedes them:

- `CH_CAMERA_V1`;
- orthographic/dimetric 2:1 projection;
- 45° yaw;
- 30° elevation;
- 128×64 reference tile;
- SOUTH / EAST / WEST / NORTH canonical directions;
- final runtime output: PNG RGBA.

## Material language

Prefer broad, readable material response over physical realism.

Examples:

- painted metal: smooth body color, restrained highlight, darker contact/recesses;
- painted wood: simple warm tonal variation, no noisy grain requirement;
- plaster/concrete: mostly matte, soft tonal shift, minimal high-frequency texture;
- glass: simplified dark/light read, not physically accurate transmission/reflection;
- plastic/signage: clean saturated color with controlled highlight;
- roofs/awnings/fabric: broad shade differences and readable folds/panels, not microdetail.

## Gameplay-scale rule

Final judgment happens at actual gameplay scale and in map context.

A large standalone render can look attractive and still fail if:

- silhouette is weak;
- identifying details disappear;
- colors merge into neighboring assets;
- footprint/pivot feels wrong;
- the asset becomes visually noisy when repeated.

## Production priority

Favor repeatable, reusable asset families over one-off hero renders.

A successful style is one that can be applied consistently to:

- kiosks and shops;
- small buildings and services;
- attractions;
- trees and vegetation;
- benches, lamps and props;
- path-adjacent objects;
- UI thumbnails/icons derived from the same source when practical.

## Relationship to older contracts

`CH_STYLIZED_3D_PRERENDER_V1` supersedes older instructions that tried to force Blender renders toward classic late-1990s/early-2000s sprite limitations.

`CH_CLASSIC_TYCOON_STYLE_V1` may remain as historical/reference material for readability, but it is **not authoritative** for production rendering when it conflicts with this document.

The project should no longer spend time trying to remove the visible 3D character of good stylized Blender renders.
