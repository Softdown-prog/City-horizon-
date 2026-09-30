# CH Blender Authoring Core — Agent Rules

The Authoring Core is the preferred geometry interface for new City Horizon assets.

## Required mindset

Describe **semantic forms**, not low-level Blender operations. Prefer `soft_form`,
`tapered_segment`, `loft_form`, `rounded_box`, `curve_tube`, `torus`,
`CharacterAuthoring`, or a `CH_AUTHORING_RECIPE_V1` recipe. Raw `bpy.ops` inside
individual asset scripts is a last resort, not the default.

## Primitive selection

Use primitives according to the visual job instead of convenience:

- `soft_form`: head, cheeks, hair puffs, gloves and genuinely soft compact masses.
- `tapered_segment`: sleeves, arms, trousers, legs and other articulated elongated forms. Keep rounded caps enabled for organic/cloth joints unless a hard cut is intentional.
- `loft_form`: jackets, shirts, dresses, torsos, skirts, canopies and any silhouette that needs independent shoulder/chest/waist/hem control. Prefer this over a box or giant ellipsoid for clothing.
- `rounded_box`: shoes, bags, props, machinery or intentionally block-like forms.
- `curve_tube`: locks, straps, piping, hoses and flowing linear details.
- `torus`: collars, cuffs, rings and circular trims.

A technically valid primitive choice can still be visually wrong. If a jacket reads
as a box, a limb reads as a pipe, or hair reads as a few balloons, reject the proxy
and change the semantic construction before final bake.

## Character rule

A character is authored **once** as one physical model under one root. Canonical
S/E/N/W views come from rotating that root. Never author four independent body
silhouettes to fake a turntable.

## Visual quality rule

Passing preflight only proves the scene is technically valid. It does not prove the
asset looks good. Every new asset must render an enlarged proxy/review before final
bake. Reject balloon torsos, tube limbs, collapsed silhouettes, accidental overlap,
or proportions that do not match the approved reference.

## Source-tree rule

CH Blender owns a pinned Blender source tree, but do not patch Blender C/C++ merely
to avoid writing a proper Python authoring layer. Patch upstream source only when a
required capability cannot be implemented cleanly through the supported Blender API
or when a measured renderer limitation justifies the maintenance cost.

## Determinism

Recipes must be deterministic. Randomized authoring requires an explicit seed and
must emit it in the machine-readable report.
