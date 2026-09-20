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

## Current game-first building pilot

The active visual pilot for new small buildings is:

- recipe: `tycoon_house_pilot_2x2_01.house.json`;
- recipe contract: `CITY_HORIZON_TYCOON_HOUSE_V1`;
- art direction: `CH_TYCOON_MINIATURE_V1`;
- expander: `../generate_tycoon_miniature_house.py`;
- workflow: `.github/workflows/tycoon-miniature-house-bake.yml`.

`CH_TYCOON_MINIATURE_V1` is layered on the technical bake/style base `CH_STYLIZED_PRERENDER_V1`. Its purpose is to make geometry and color design look like a **game miniature from the start**: compact body, strong roof silhouette, slightly oversized openings, large clean color blocks, low material noise and restrained landscaping.

This pilot is intentionally independent from the older suburban-house grammar. Do not derive the new shape language from the older house simply because it exists.

## Older residential recipes

`suburban_house_simple_2x2_01.house.json` and `residential_house_2x2_01.json` may remain for pipeline/history/testing, but they are **not the target visual reference** for the new game-first miniature direction unless the user explicitly re-approves them.

## Reference policy

Classic/casual Tycoon games may be used as references for readability, silhouette, miniature charm, information density and broad color blocking. Do not copy a specific proprietary building design. Build original geometry that shares the general game-art language.
