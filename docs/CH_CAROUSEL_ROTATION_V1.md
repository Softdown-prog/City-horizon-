# CH_CAROUSEL_ROTATION_V1

This contract defines the canonical pre-rendered rotation sampling for the City Horizon carousel.

## Why 48 frames

The carousel canopy has 24 radial stripes: 12 recolorable stripes alternating with 12 fixed cream stripes. A full stripe spans 15 degrees. Rendering only one sample per full stripe would give 24 frames and a visibly coarse rotational step.

City Horizon therefore samples at half-stripe increments:

- canopy stripes: 24 total;
- full stripe angle: 15 degrees;
- samples per full stripe: 2;
- exported frames per full turn: 48;
- angular step per exported frame: 7.5 degrees.

This keeps the alternating canopy pattern moving coherently instead of appearing to jump between distant white/yellow stripe positions.

## Exact frame rule

Export frames `1..48` only.

Frame `n` represents:

`angleDegrees = (n - 1) * 7.5`

Therefore:

- frame 1 = 0.0 degrees;
- frame 2 = 7.5 degrees;
- frame 3 = 15.0 degrees;
- ...;
- frame 48 = 352.5 degrees.

A non-exported loop-closure key may exist at frame 49 = 360.0 degrees. Do not export frame 49. Exporting both 0 and 360 degrees would duplicate the same visual pose and would turn the intended 7.5-degree sampling into the wrong interval across the exported set.

## Playback

The current authored playback is 8 fps. With 48 exported frames, one revolution lasts 6.0 seconds.

Frame count and playback speed are separate concerns. If the carousel is later made slower or faster, prefer changing runtime fps/timing while preserving the 48 unique angular samples unless a new visual review explicitly approves another sampling contract.

## Color mask

Use `CH_COLOR_MASK_V1` and generate one animated recolor region only: the 12 authored recolor stripes on the canopy.

- R channel: recolorable canopy stripes;
- G channel: unused;
- B channel: unused;
- cream canopy stripes: fixed color;
- all other carousel parts: fixed color.

The mask must be rendered for the same 48 frames as the beauty animation. For every frame and direction, beauty and mask must share exactly the same camera, object rotation, canvas size, pivot and frame index.

The runtime must apply the color mask using the same animation frame currently used by the beauty sprite. A mask frame may never lag or advance relative to the beauty frame.

## Spritesheet packaging

Per direction:

- 1 row;
- 48 columns;
- frame order `1..48`.

If a combined four-direction sheet is generated, each direction remains one row and every row contains the same 48-frame order.

Recommended names:

- beauty: `<assetId>_<direction>_animation.png`;
- color mask: `<assetId>_<direction>_color_mask_animation.png`.

## Validation gates

Reject the bake if any of the following is true:

- canopy stripe count is not 24;
- recolor/fixed canopy stripes are not 12 + 12;
- exported frame count is not 48;
- angular step is not 7.5 degrees;
- frame 48 is a duplicated 360-degree pose;
- frame 49 is exported;
- mask and beauty frame counts differ;
- mask and beauty pivots/canvas differ;
- anything outside the intended canopy recolor stripes is included in the recolor channel.
