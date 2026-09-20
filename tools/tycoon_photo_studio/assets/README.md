# Tycoon Photo Studio asset recipes

This directory contains **design recipes**, not a visual reference library of arbitrary runtime sprites.

## Source hierarchy

For a new procedural building, prefer this order:

1. human-readable design recipe (`*.house.json` or category equivalent);
2. art-direction contract under `../contracts/`;
3. deterministic expander script;
4. generated `TYCOON_ASSET_SOURCE_V1`;
5. Blender bake under the frozen studio/camera;
6. final PNG review at gameplay scale;
7. only after human approval, promote the asset as a visual reference.

A successful workflow is not visual approval.

## Current building status

There is currently **no approved house recipe, house-specific generator, or house geometry reference** in this directory.

The previous suburban-house and miniature-house pilots were retired because they kept converging on the same unwanted design language. They are not historical templates to revive later and must not be reconstructed from memory, old artifacts, commit history, screenshots, or parameter variations unless the user explicitly asks to recover one.

The generic art-direction contract `CH_TYCOON_MINIATURE_V1` remains valid as guidance for game-first readability: strong silhouette, miniature charm, clean color blocking, readable openings, low material noise and restrained detail. It is **not** an approved building design.

For the next house/building experiment, create a genuinely new silhouette/grammar before materials and post-processing. Reuse the generic technical pipeline — camera, grid, studio, material system, Blender bake, four-direction export and review tooling — but not the retired house geometry or composition.

## Reference policy

Classic/casual Tycoon games may be used as references for readability, silhouette, miniature charm, information density and broad color blocking. Do not copy a specific proprietary building design. Build original geometry that shares the general game-art language.
