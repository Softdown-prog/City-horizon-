# CH_VISITOR_MVP_V1

Status: FIRST GUARDED PEDESTRIAN TRANCHE

## Goal

Validate one City Horizon pedestrian before scaling the system.

The first target is `visitor_male_base_01`. The female visitor must reuse the same rig/animation logic after this male SOUTH proxy is visually approved.

## Visual/animation contract

- runtime remains 2D pre-rendered PNG RGBA;
- one deterministic CH Blender source, never independently generated walk frames;
- four canonical directions: SOUTH/EAST/NORTH/WEST;
- walking uses two opposite contact poses per direction;
- idle uses one neutral pose per direction;
- short restrained steps;
- low arm swing;
- near-zero vertical bob;
- no visible hopping;
- simple old-tycoon-scale silhouette, but full-color RGBA rather than a retro palette restriction.

## Quality sequence

```text
visitor recipe
  -> CH Blender guarded build
  -> structural preflight
  -> SOUTH idle proxy
  -> SOUTH walk A proxy
  -> SOUTH walk B proxy
  -> human visual approval
  -> only then enable final 4-direction bake
  -> only then create female/body/clothing variants
```

The final stage is intentionally blocked in `build_visitor_guarded.py` until the first SOUTH idle/walk result is approved. This prevents the project from producing dozens of bad frames before the basic silhouette and motion are accepted.

## Shared rig principle

Male and female pedestrians are variants of one visitor system, not separate animation pipelines. Geometry/proportions/materials may differ, but direction rotation, anchor policy and walk-pose logic stay shared.

## Runtime intent

The first functional runtime path after art approval is:

```text
walk path
  -> approach attraction/building
  -> idle/queue
  -> board/enter
  -> hide world sprite while inside
  -> activate building/attraction activity
  -> leave
  -> resume walk
```

No child visitor is required for this MVP.
