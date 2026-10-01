# CH_PATH_SLOPE_SPRITE_V1

Status: approved visual recipe for City Horizon ground-path slopes and stairs.

## Purpose

Ground paths remain tile/grid gameplay and remain visually pre-rendered 2D. The runtime may inspect neighbours and `CH_TERRAIN_HEIGHTFIELD_V1`, but it must **select a baked PNG** for a slope/stair rather than paint free-form artistic stair geometry during gameplay.

This contract stores the recipe approved after the dirt-path pilot and makes it reusable by every compatible ground-path material family.

## Source-art rule

Each material supplies its already-approved straight sprites:

- NS: `<prefix>_05_straight_ns.png`
- EW: `<prefix>_10_straight_ew.png`

The bake copies the original RGBA source pixels and only changes their screen-space Y position. This preserves the exact dirt/sand texture, edge alpha and old-tycoon 2D look. Generated vertical riser faces are derived from those same source pixels by darkening them.

Current compatible families:

- `dirt_01` / prefix `dirt_path`
- `sand_01` / prefix `sand_path`

## Canonical dimensions

- legacy tile: `128x64`
- slope sprite canvas: `128x112`
- legacy surface row inside slope canvas: `y=32`
- visual terrain scale: `16 px / height unit`

The runtime therefore anchors a baked slope sprite at `legacy tile top - 32px`, after applying the low/base terrain height.

## Approved discrete profiles

| Profile | Mode | Rise | Steps |
| --- | --- | ---: | ---: |
| `ramp_025` | ramp | 0.25 unit / 4 px | continuous |
| `ramp_050` | ramp | 0.50 unit / 8 px | continuous |
| `stairs_050_4` | stairs | 0.50 unit / 8 px | 4 |
| `stairs_075_6` | stairs | 0.75 unit / 12 px | 6 |
| `stairs_100_8` | stairs | 1.00 unit / 16 px | 8 |

The selector chooses the nearest approved profile for the local `height_delta`; the heightfield itself is not quantized.

## Critical isometric riser rule

A stair riser is **not** a Euclidean perpendicular to the path in screen space.

For the fixed 2:1 isometric projection, each stair edge follows the *other isometric grid axis*:

- NS path -> riser parallel to the EW diamond axis
- EW path -> riser parallel to the NS diamond axis

The bake script validates this invariant and fails if it regresses. This is the correction that removed the rejected diagonal/vertical stripe appearance.

## Runtime selection key

For a supported straight path tile:

`material + visual_axis + vertical_profile + visual_high_end -> baked PNG`

Example:

`dirt_01 + ns + stairs_100_8 + n -> dirt_path_straight_ns_stairs_100_8_high_n.png`

Camera rotation is applied to the logical connections and high endpoint before the filename is selected.

Flat cells continue to use the legacy auto-tile PNG exactly. Curves, ends, tees and crosses also remain on their legacy PNGs until an approved baked slope library exists for those topologies; the runtime must not fall back to free-form artistic stair strokes.

## Runtime policy

`runtime_visual_policy = sprite_select_only`

The heightfield remains canonical gameplay/geometry data. This contract is only presentation. Save/load, occupancy, path connectivity and navigation do not store a sprite variant.

## Generator

`tools/generate_dirt_slope_sprites.py` is intentionally kept as the historical entrypoint, but it is material-parameterized and emits `CH_PATH_SLOPE_SPRITE_V1` for all compatible ground-path families.

The CI workflow `.github/workflows/ch-dirt-slope-sprite-pilot.yml` bakes and validates both `dirt_01` and `sand_01` so the approved recipe cannot silently diverge between materials.
