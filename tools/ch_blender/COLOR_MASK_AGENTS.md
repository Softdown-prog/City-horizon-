# CH Blender — Color Mask Guide for Agents

This guide is the agent-facing usage contract for optional building/prop recolor masks.

## Authority

The mask contract is `CH_COLOR_MASK_V1`:

`tools/tycoon_photo_studio/contracts/ch_color_mask_v1.json`

The Blender helper is:

`tools/tycoon_photo_studio/ch_color_mask.py`

Do not invent a second channel convention in prompts or individual builders.

## When to use a mask

Use color masks only when recoloring adds useful player-visible variation. Good candidates include houses, shops, apartment blocks, warehouses and modular service buildings.

Do not add masks automatically to landmarks, one-off hero buildings, glass-heavy assets, UI art, terrain or assets whose authored color identity should remain fixed.

## V1 channel policy

`CH_COLOR_MASK_V1` packs three recolor groups into one PNG:

- `R` — normally wall / primary body;
- `G` — normally roof / secondary body;
- `B` — normally trim / accent;
- `A` — object coverage only. Alpha is **not** a fourth tint channel in V1.

Unassigned visible surfaces render RGB black and remain covered by alpha. They keep their original sprite color at runtime.

Roles are semantic. The source declares which semantic role maps to R/G/B. Agents should prefer `wall`, `roof`, `trim` for ordinary buildings unless a different semantic split is genuinely more useful.

## Canonical TYCOON_ASSET_SOURCE_V1 declaration

Add this only to assets that should support recoloring:

```json
"colorMask": {
  "contract": "CH_COLOR_MASK_V1",
  "enabled": true,
  "channels": {
    "R": "wall",
    "G": "roof",
    "B": "trim"
  },
  "alpha": "coverage"
}
```

Then classify reusable source materials:

```json
"materials": {
  "wall_plaster": {
    "rgba": [0.74, 0.70, 0.61, 1.0],
    "recipe": "plaster",
    "maskRole": "wall"
  },
  "roof_tile": {
    "rgba": [0.35, 0.16, 0.10, 1.0],
    "maskRole": "roof"
  },
  "trim_wood": {
    "rgba": [0.28, 0.18, 0.10, 1.0],
    "maskRole": "trim"
  },
  "glass": {
    "rgba": [0.20, 0.32, 0.38, 1.0],
    "recipe": "glass"
  }
}
```

Do not assign `maskRole` to a material that should keep its authored color.

## Imported .blend / FBX / GLB geometry

Preferred method: tag the imported Blender material itself with custom property:

```text
ch_color_mask_role = wall
```

Valid role names are the values declared by the asset's `colorMask.channels` mapping.

For a coarse import where the whole imported part belongs to one role, the canonical source part may declare:

```json
{
  "type": "blend_import",
  "blendFile": "...",
  "collection": "Building",
  "maskRole": "wall"
}
```

Material-level tagging is preferred when one mesh contains several semantic surfaces.

## Direct guarded Blender builders

A direct builder that does not use the canonical declarative material creation may use:

```python
import ch_color_mask as color_mask

color_mask.tag_material(wall_material, "wall")
color_mask.tag_material(roof_material, "roof")
color_mask.tag_object(single_role_object, "trim")
```

Before final mask rendering, call `normalize_spec(asset)` and `assignment_summary(authored, spec)`. The assignment check intentionally fails if the source declares a role that was never assigned or if geometry uses an undeclared role.

## Required output behavior

When mask support is enabled, the canonical pipeline must produce the normal color/shadow outputs plus:

```text
<asset>_south_mask_source.png
<asset>_east_mask_source.png
<asset>_west_mask_source.png
<asset>_north_mask_source.png

<asset>_south_mask.png
<asset>_east_mask.png
<asset>_west_mask.png
<asset>_north_mask.png

<asset>_mask_4view.png
<asset>_mask_review.png
```

The mask must use the exact same camera, AssetRoot rotation, frame size and projected pivot as the corresponding color sprite.

Masks are data. Do not apply palette reduction, dithering, AO, lighting, cast shadows, edge outlines or background-removal passes to them. Only deterministic resolution reduction is allowed.

## Review rules

For a new mask-enabled building, review both the normal visual proxy and the mask review before promotion.

Check that:

- wall pixels are only in the declared wall channel;
- roof does not leak into wall/trim channels;
- glass, signs and authored fixed-color details stay black unless intentionally recolorable;
- all four directions stay aligned with the normal sprite;
- no shadow is present in the mask;
- mask edges follow the object silhouette.

A green Action still means execution success, not visual approval.

## Runtime boundary

`CH_COLOR_MASK_V1` prepares authoring outputs and metadata. It does **not** by itself implement the SDL runtime tint shader/texture blend.

Do not claim a building is player-recolorable in-game until the runtime color-customization path reads the mask and applies selected colors while preserving the base sprite's lighting/value structure.

## Quality flow remains mandatory

For new agent-authored geometry:

```text
preflight
  -> SOUTH proxy
  -> human visual review
  -> final four-direction bake
  -> mask review
  -> runtime promotion
```

Mask generation never bypasses the existing CH Blender quality gate.
