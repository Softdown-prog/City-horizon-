# Tycoon Photo Studio asset recipes

This directory contains **design recipes**, not a visual reference library of arbitrary runtime sprites.

## Source hierarchy

For a new procedural building, prefer this order:

1. human-readable design recipe (`*.kiosk.json`, `*.house.json` or category equivalent);
2. art-direction contract under `../contracts/`;
3. deterministic expander / guarded authoring script;
4. generated procedural scene/source;
5. Blender bake under the frozen studio/camera;
6. SOUTH proxy review at gameplay scale;
7. final four-direction bake only after human approval;
8. only after final human approval, promote the asset as a visual reference.

A successful workflow or preflight is not visual approval.

## Current building status

There is currently **no approved house visual reference** in this directory.

Previous suburban-house visual pilots were retired because they kept converging on the same unwanted design language. They are not historical templates to revive later and must not be reconstructed from memory, old artifacts, commit history, screenshots, or parameter variations unless the user explicitly asks to recover one.

A fresh residential pilot now exists: `residential_suburban_cottage_3x3_01.house.json`, authored by `../build_residential_suburban_cottage_guarded.py`. It was started from a new user-supplied art-direction reference and is intentionally original geometry rather than a recovery of any retired house. It remains **not promoted as an approved runtime asset**: it must pass the guarded preflight, then a SOUTH proxy must be inspected and explicitly approved before any final four-direction bake.

The latest visual review approved the overall cottage direction but requested a higher level of detail. That detail target is implemented as a non-destructive decorator in `../build_residential_suburban_cottage_detail_v2.py`, which preserves the original 3×3 massing and guarded workflow while adding game-readable roof, trim, porch, window, foundation and garden detail.

The active art-direction contract is `CH_STYLIZED_PRERENDER_V1`. It provides the shared guidance for gameplay readability, silhouette clarity, clean color blocking, readable openings, controlled material noise and restrained detail. It is not an approved building design by itself.

## Active residential pilot

`residential_suburban_cottage_3x3_01` is a 3×3 compact cottage whose intended read is:

- dominant charcoal gabled roof;
- two front dormers as the secondary silhouette;
- cream/white siding and dark window frames;
- compact gabled entry portico with two columns;
- offset chimney and warm amber window glow;
- restrained low private landscaping.

The v2 detail pass adds, without redesigning the silhouette:

- staggered roof-shingle joints and chunkier ridge caps;
- cream fascia plus dark gutter lines;
- oversized corner boards for rotation readability;
- stronger window headers/casings and sills;
- recessed front-door panels and a warm porch lamp;
- porch column capitals/plinths and foundation courses;
- denser shrub lobes, flower detail and private mulch strips.

The public sidewalk/curb and the large foreground tree visible in the supplied reference are deliberately **not** baked into the building. Sidewalks remain runtime path/terrain systems and large trees remain separate placeable vegetation assets.

For the next review, use `build_residential_suburban_cottage_detail_v2.py` with the same frozen studio and guarded preflight/proxy stages. Do not render the final four directions until the new SOUTH proxy is explicitly approved.

## Active fresh-silhouette park pilot

The park experiment is `park_snack_kiosk_1x1.kiosk.json`, expanded by `../generate_park_kiosk_asset.py` and baked by `.github/workflows/tycoon-park-snack-kiosk-bake.yml`.

This pilot deliberately does **not** use residential grammar. Its authored read is:

- short compact park-service body;
- oversized floating canopy as the primary silhouette;
- one tall asymmetric sign fin as the secondary silhouette;
- large south/east service windows and chunky counters;
- large turquoise / cream / coral color blocks;
- low material noise and restrained post-processing.

The kiosk exists to answer one visual question first: **does a genuinely different, game-first silhouette finally read as a Tycoon asset rather than an architectural render?** Do not promote it to a visual reference until its generated PNGs are inspected and explicitly approved.

For later house/building experiments, create a genuinely new silhouette/grammar before materials and post-processing. Reuse the generic technical pipeline — camera, grid, studio, material system, Blender bake, four-direction export and review tooling — but not the retired house geometry or composition.

## Reference policy

Classic/casual Tycoon games and supplied images may be used as references for readability, silhouette, information density and broad color blocking. Do not copy a specific proprietary building design. Build original geometry that shares only broad game-art language and design cues.
